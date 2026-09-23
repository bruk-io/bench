/** The projects kept in this browser: `ProjectStore` over `localStorage`.
 *
 * Since task-46 this is not where projects live - the host is (decision-9), and the app never
 * chooses this store to keep work in. It is read once, by `main.ts`'s adoption, to find what a
 * browser kept before, and ask whether to write it to the host. `save` stays because the
 * protocol has it and its tests pin it; nothing in the app calls it.
 *
 * What the app did before there was a protocol, behind the protocol, and behaving exactly as
 * it did: the same key, the same document, the same never-throwing access through
 * `storage.ts`. A retrofit that changed behaviour would be two changes wearing one coat.
 *
 * One deliberate difference, and it is the protocol's doing rather than this module's:
 * `save` *reports* a write that did not happen. `storage.ts` is written never to throw -
 * private browsing, a full quota, a blocked origin - because forgetting which tab was open is
 * not worth an exception. Forgetting a person's project is. So the swallowing stops here: the
 * quota is about five megabytes and a workspace of a few scripts is nowhere near it, but
 * "nowhere near it" is not "cannot happen", and the caller is owed the truth either way.
 */
import { KEYS, remember, remembered } from "./storage";
import type { ProjectStore } from "./store";

/** Whether `localStorage` took what it was given.
 *
 * `remember` cannot say - it catches everything and returns nothing - so this reads the key
 * back. Cheap at this size, and the only way to tell a write that landed from one the browser
 * declined.
 */
function wrote(key: string, text: string): boolean {
  remember(key, text);
  return remembered(key) === text;
}

/** The projects in this browser, under the key they have always been under. */
export const localStore = (): ProjectStore => ({
  kind: "browser",

  load: () => Promise.resolve(remembered(KEYS.files)),

  save(text: string) {
    if (!wrote(KEYS.files, text)) {
      return Promise.reject(
        new Error(
          "this browser would not keep the projects - it may be full, or storage may be" +
            " blocked for this site",
        ),
      );
    }
    return Promise.resolve();
  },
});
