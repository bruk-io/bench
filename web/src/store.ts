/** Where the projects are kept, as a protocol rather than a place.
 *
 * The app has kept its projects in `localStorage` since there were projects, and decision-9
 * says they belong on the host instead. This is the seam between those two answers: one
 * interface, an implementation per place, and nothing above it knowing which it has.
 *
 * **A seam is not a fallback.** decision-9 is explicit that the app does not silently degrade
 * from one store to another - "a build with no host behind it is not a degraded bench". A
 * store is chosen once, by whoever starts the app; it is never a chain that gets tried in
 * order, and an implementation that cannot answer says so rather than quietly handing over to
 * the next one.
 *
 * **What crosses is a document, never a `Workspace`.** `files.ts` owns the one pair of
 * functions that turn projects into text and back - including the two shapes a browser may
 * have kept from before - and a store that returned a `Workspace` would make every
 * implementation re-own that. So a store moves the serialized text and nothing else, which is
 * also what makes a bucket or an HTTP route a matter of shifting bytes.
 *
 * **What is *not* kept here**: which container the rail had open, whether the bottom panel was
 * shut, the console's log level, the fingerprint of a script the watchdog stopped. Those are
 * `storage.ts`'s, and they stay there. They are about this browser on this device - a panel
 * left shut on a tablet is not a fact about the project - so they must not travel to a host
 * or a bucket, and a store that carried them would be carrying the wrong thing.
 */

/** A place the projects can be kept.
 *
 * Asynchronous throughout, because the two implementations that matter are not local: an
 * HTTP route on the host and whatever is behind it. The one synchronous store there is
 * (`localStorage`) answers immediately and loses nothing by saying so with a promise.
 */
export interface ProjectStore {
  /** What this store is, for the log and for anything on screen that has to say where a
   * person's work is. One word, lower case. */
  readonly kind: string;

  /** The kept document, or `null` where this store has nothing yet - a first visit, a
   * cleared browser, a host with no projects on it.
   *
   * Throws rather than answering `null` when the store is *there and unreadable*: the two
   * are different, and a caller that cannot tell them apart would silently start a person's
   * work again from scratch on a blip. `null` means "nothing kept", never "could not ask".
   */
  load(): Promise<string | null>;

  /** Keep `text` as the whole of what this store holds.
   *
   * Whole, rather than a change to it, because that is what the app has always written and
   * what `files.ts` serializes. A store that would rather hold one file per project is free
   * to take this apart; nothing above it has an opinion.
   */
  save(text: string): Promise<void>;
}
