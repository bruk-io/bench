/** The projects on the host: `ProjectStore` over `host.ts`'s route, `outbox.ts` behind it for
 * whatever has not landed there yet.
 *
 * `project-files.ts` decides how the one document `store.ts` moves maps onto real files under
 * one project directory (`PROJECT`); this module is the impure edge around that pure mapping -
 * the reads, the writes, and the outbox that holds a write the host has not taken yet.
 *
 * **`load()` overlays the outbox on top of the host.** A file the outbox is still holding is
 * what the person actually asked for, even though the host has something older (or nothing at
 * all): reading only the host after a reload would show a person's edit vanishing while the
 * outbox quietly kept trying to land it behind their back. Every file read this way is also
 * handed to `outbox.rebase`, which seeds a base for a file with nothing pending (so the very
 * next edit does not read as a "create"), and gives a refusal from before the reload a fair try
 * against the version actually on the host now - unless what is pending is still unresolved,
 * in which case `rebase` leaves it exactly alone (see `outbox.ts`). `load()` also asks the
 * outbox to `drain()` once it is done, so work queued before a reload is sent again without
 * waiting for the next keystroke.
 *
 * **`save()` diffs, and only the diff is queued.** `keep()` calls this on every keystroke;
 * `project-files.ts`'s `writesFor` compares the workspace structurally against what this store
 * last saw, so a boot that reads the host back and hands it straight to `keep()` enqueues
 * nothing, and typing in one script never touches another's files.
 */
import { restored, serialized, type Workspace } from "./files";
import type { Host } from "./host";
import type { Outbox } from "./outbox";
import { PROJECT, owned, removalsFor, workspaceFrom, writesFor } from "./project-files";
import type { ProjectStore } from "./store";

/** The projects on the host, reached through `client`, with `box` holding what has not landed
 * there yet. Both are handed in rather than built here, so a caller can share one outbox
 * across a session and a test can give either a database of its own. */
export function hostStore(client: Host, box: Outbox): ProjectStore {
  let known: Workspace | null = null;

  async function read(): Promise<Map<string, string>> {
    const entries = new Map<string, string>();
    const seen = new Set<string>();
    const listed = await client.files(PROJECT);
    if (listed.ok) {
      const scripts = new Set(listed.value.filter((one) => one.name.endsWith(".py")).map((one) => one.name));
      for (const entry of listed.value) {
        if (!owned(entry.name, scripts)) continue; // an STL, or a stray `.toml` with no script
        const got = await client.read(PROJECT, entry.name);
        if (!got.ok) continue; // gone between the listing and the read; the next load tries again
        const text = new TextDecoder().decode(got.value.bytes);
        entries.set(entry.name, text);
        seen.add(entry.name);
        await box.rebase(PROJECT, entry.name, got.value.version.version, text);
      }
    } else if (listed.refusal.refused !== "missing") {
      // "missing" is an empty or not-yet-created project directory - nothing kept yet, not a
      // failure. Anything else is `store.ts`'s "a store that cannot be read" case.
      throw new Error(listed.refusal.message);
    }

    // Anything this outbox is still holding for a file the listing above did not show does not
    // exist on the host - rebase with `null` so a landed delete (or a refusal that is no longer
    // true) can clear, while a create still waiting to land is left alone.
    const pendingNow = await box.pending();
    for (const [, one] of pendingNow) {
      if (one.project !== PROJECT || seen.has(one.file)) continue;
      await box.rebase(PROJECT, one.file, null, null);
    }

    return entries;
  }

  return {
    kind: "host",

    async load() {
      const entries = await read();
      const pending = await box.pending();
      for (const [, one] of pending) {
        if (one.project !== PROJECT) continue;
        if (one.op === "delete") entries.delete(one.file);
        else entries.set(one.file, one.text);
      }
      known = workspaceFrom(entries);
      box.drain();
      return known === null ? null : serialized(known);
    },

    save(text) {
      const next = restored(text);
      if (next === null) return Promise.reject(new Error("nothing to keep - the document was not a workspace"));
      const writes = writesFor(known, next);
      const removed = removalsFor(known, next);
      known = next;
      return (async () => {
        for (const write of writes) {
          await box.enqueue(PROJECT, write.file, write.text, null);
        }
        for (const file of removed) {
          await box.enqueueDelete(PROJECT, file, null);
        }
      })();
    },
  };
}
