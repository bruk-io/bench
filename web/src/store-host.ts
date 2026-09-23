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
 * handed to `outbox.rebase`, which both seeds a base for a file with nothing pending (so the
 * very next edit does not read as a "create") and gives a refusal from before the reload a fair
 * try against what is actually on the host now, rather than replaying the version that lost.
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
    const listed = await client.files(PROJECT);
    if (!listed.ok) {
      if (listed.refusal.refused === "missing") return entries; // an empty or absent project: nothing kept yet
      throw new Error(listed.refusal.message);
    }
    const scripts = new Set(listed.value.filter((one) => one.name.endsWith(".py")).map((one) => one.name));
    for (const entry of listed.value) {
      if (!owned(entry.name, scripts)) continue; // an STL, or a stray `.toml` with no script - not this mapping's
      const got = await client.read(PROJECT, entry.name);
      if (!got.ok) continue; // gone between the listing and the read; the next load tries again
      entries.set(entry.name, new TextDecoder().decode(got.value.bytes));
      await box.rebase(PROJECT, entry.name, got.value.version.version);
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
