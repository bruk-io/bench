/** How the centre is shared between the script and the view (decision-12, task-91).
 *
 * **Code** gives the editor the whole centre, for writing; **View** gives it to the view, for
 * checking and printing; **Split** is the two side by side, as the app always was. The
 * inspector stays on the right in every one of them - it follows the selection, not the layout.
 * What replaces workbenches for screen space: one script, one view, and a choice of how much of
 * each is on screen.
 *
 * Pure: which layouts there are, what a remembered string means, and which comes next for the
 * shortcut. Remembering it is `storage.ts`'s, and putting it on the page is `main.ts`'s.
 */

export type Layout = "code" | "split" | "view";

/** Every layout, in the order the control shows them and the shortcut steps through them. */
export const LAYOUTS: readonly Layout[] = ["code", "split", "view"];

/** What a browser that has never chosen sees: the two side by side, as before there was a
 * choice. */
export const FIRST_LAYOUT: Layout = "split";

/** What each layout is called on its button. */
export const LAYOUT_NAMES: Readonly<Record<Layout, string>> = { code: "Code", split: "Split", view: "View" };

export const isLayout = (said: unknown): said is Layout =>
  typeof said === "string" && (LAYOUTS as readonly string[]).includes(said);

/** The layout a remembered string names - or the first one, for nothing, or for anything a
 * later or an earlier version of the app might have left under the key. */
export const layoutOf = (said: string | null): Layout => (isLayout(said) ? said : FIRST_LAYOUT);

/** The layout after `now`, round again after the last: what the shortcut moves to. */
export const nextLayout = (now: Layout): Layout => LAYOUTS[(LAYOUTS.indexOf(now) + 1) % LAYOUTS.length] ?? FIRST_LAYOUT;
