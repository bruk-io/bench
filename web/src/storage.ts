/** What the browser remembers between visits, under which keys, and how the app asks.
 *
 * `localStorage` can refuse - private browsing, a full quota, a blocked origin - and the app
 * still works when it does; it just forgets. So every access goes through here, and none of
 * them throws.
 */

/** Every key the app keeps something under.
 *
 * Most of these are about *this browser on this device* and go nowhere else: which container
 * the rail had open, whether the panel was shut, the log level, the fingerprint of a script
 * the watchdog stopped, which project this browser has open. `files` is the exception: the
 * projects a browser kept before they lived on the host, read once - through
 * `store-local.ts` - to adopt them there (task-46), and never written again.
 */
export const KEYS = {
  /** Every project a browser kept before projects lived on the host - its script, and its
   * values as the TOML document `tools/build.py` reads (`files.ts`). Read through
   * `store-local.ts`, never directly, and only to adopt it; left in place afterwards, since it
   * is somebody's work and the host now has its own copy. */
  files: "bench.files",
  /** Whether this browser's own projects were adopted onto the host (`"adopted"`) or the
   * person said to leave them (`"declined"`) - either way, asked once and not again. */
  adopted: "bench.adopted",
  /** Which project, and which of its scripts, this browser has open - `{project, script}` as
   * JSON. Kept here and never on the host, so a second device switching projects does not
   * move this one. */
  open: "bench.open",
  /** The one script a browser kept before there were files - read once, to adopt it. */
  source: "bench.source",
  /** That script's overrides, likewise. */
  overrides: "bench.overrides",
  /** The fingerprint of a script the watchdog had to stop, so a reload does not replay it. */
  hang: "bench.lastHang",
  /** Which container the rail last had open in the sidebar. */
  container: "bench.container",
  /** Whether the bottom panel was last put away. */
  panel: "bench.panel",
  /** The console's log level. */
  log: "bench.log",
  /** The id this tab holds a project's write lease under (`leasing.ts`) - in `sessionStorage`,
   * never `localStorage`: it has to survive a reload of this tab, so the reload reclaims its
   * own lease at once, and must not be shared with any other tab, which is another writer. */
  holder: "bench.holder",
} as const;

/** What this tab alone remembers - `sessionStorage`, which a reload keeps and another tab does
 * not see. `null` when there is nothing, or the browser refuses. */
export function tabRemembered(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function tabRemember(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    // as `remember`: the tab still works; a reload is just a new client to the host
  }
}

export function remembered(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function remember(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // private browsing, a full quota: the app still works, it just forgets
  }
}

export function forget(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // as above: nothing to do about it and nothing depends on it
  }
}

/** A short, stable fingerprint of a script - FNV-1a, which is plenty to tell two apart. */
export function hashOf(text: string): string {
  let hash = 0x811c9dc5;
  for (let at = 0; at < text.length; at += 1) {
    hash = Math.imul(hash ^ text.charCodeAt(at), 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, "0");
}
