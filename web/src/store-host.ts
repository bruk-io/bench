/** The projects on the host: `ProjectStore` over `host.ts`'s route, `outbox.ts` behind it for
 * whatever has not landed there yet.
 *
 * `project-files.ts` decides how the one document `store.ts` moves maps onto real files - a
 * directory per project under the root, each with its scripts and one `bench.toml`; this
 * module is the impure edge around that pure mapping - the reads, the writes, and the outbox
 * that holds a write the host has not taken yet.
 *
 * **`load()` reads every project under the root, and overlays the outbox on top.** A file the
 * outbox is still holding is what the person actually asked for, even though the host has
 * something older (or nothing at all): reading only the host after a reload would show a
 * person's edit vanishing while the outbox quietly kept trying to land it behind their back.
 * Every file read this way is also handed to `outbox.rebase`, which seeds a base for a file
 * with nothing pending (so the very next edit does not read as a "create"), and gives a refusal
 * from before the reload a fair try against the version actually on the host now - unless what
 * is pending is still unresolved, in which case `rebase` leaves it exactly alone (see
 * `outbox.ts`). `load()` also asks the outbox to `drain()` once it is done, so work queued
 * before a reload is sent again without waiting for the next keystroke.
 *
 * **`save()` diffs, and only the diff is queued.** `keep()` calls this on every keystroke;
 * `project-files.ts`'s `writesFor` compares the workspace structurally against what this store
 * last saw, so a boot that reads the host back and hands it straight to `keep()` enqueues
 * nothing, and typing in one script never touches another's files. Which project is open is
 * in none of it: that is the browser's (`files.ts`), and it is never written here.
 */
import { restored, serialized, type Workspace } from "./files";
import type { Host } from "./host";
import type { Outbox } from "./outbox";
import { owned, removalsFor, workspaceFrom, writesFor } from "./project-files";
import type { ProjectStore } from "./store";

/** The projects on the host, reached through `client`, with `box` holding what has not landed
 * there yet. Both are handed in rather than built here, so a caller can share one outbox
 * across a session and a test can give either a database of its own. */
export function hostStore(client: Host, box: Outbox): ProjectStore {
  let known: Workspace | null = null;

  async function read(): Promise<Map<string, Map<string, string>>> {
    const directories = new Map<string, Map<string, string>>();
    const seen = new Set<string>();
    const listed = await client.projects();
    // Anything but a listing is `store.ts`'s "a store that cannot be read": the root went away
    // between the probe that chose this store and this read, or the host did.
    if (!listed.ok) throw new Error(listed.refusal.message);
    for (const project of listed.value.projects) {
      const files = await client.files(project);
      if (!files.ok) {
        if (files.refusal.refused === "missing") continue; // gone since the listing
        throw new Error(files.refusal.message);
      }
      const texts = new Map<string, string>();
      for (const entry of files.value) {
        if (!owned(entry.name)) continue; // an STL: bytes, read when a placement asks for it
        const got = await client.read(project, entry.name);
        if (!got.ok) continue; // gone between the listing and the read; the next load tries again
        const text = new TextDecoder().decode(got.value.bytes);
        texts.set(entry.name, text);
        seen.add(`${project}/${entry.name}`);
        await box.rebase(project, entry.name, got.value.version.version, text);
      }
      directories.set(project, texts);
    }

    // Anything this outbox is still holding for a file the listing above did not show does not
    // exist on the host - rebase with `null` so a landed delete (or a refusal that is no longer
    // true) can clear, while a create still waiting to land is left alone.
    for (const [, one] of await box.pending()) {
      if (seen.has(`${one.project}/${one.file}`)) continue;
      await box.rebase(one.project, one.file, null, null);
    }

    return directories;
  }

  return {
    kind: "host",

    async load() {
      const directories = await read();
      for (const [, one] of await box.pending()) {
        if (!owned(one.file)) continue;
        const files = directories.get(one.project) ?? new Map<string, string>();
        if (one.op === "delete") files.delete(one.file);
        else files.set(one.file, one.text);
        directories.set(one.project, files);
      }
      known = workspaceFrom(directories);
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
          await box.enqueue(write.project, write.file, write.text, null);
        }
        for (const gone of removed) {
          await box.enqueueDelete(gone.project, gone.file, null);
        }
      })();
    },
  };
}
