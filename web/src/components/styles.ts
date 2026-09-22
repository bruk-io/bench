/** Style fragments every component shares.
 *
 * The tokens themselves - colours, fonts, radii - are custom properties on `:root` in
 * `styles.css`. Custom properties inherit through a shadow boundary, so a component reads
 * `var(--danger)` exactly as the page does; what does not cross is a *rule*, and the rules
 * more than one component needs live here.
 */
import { css } from "lit";

/** What every component starts from, because the page's own resets stop at a shadow root.
 *
 * Border-box sizing: `* { box-sizing: border-box }` in `styles.css` does not reach inside a
 * component, and without it a `width: 100%` input grows by its own padding and border and
 * spills out of the column it was sized to. And `hidden` on the host meaning hidden: a
 * `:host { display: … }` would otherwise beat the user agent's `[hidden] { display: none }`. */
export const base = css`
  :host,
  *,
  *::before,
  *::after {
    box-sizing: border-box;
  }

  :host([hidden]) {
    display: none !important;
  }
`;

/** The chevron on a button that opens something - Examples, Export. Give it the class. */
export const disclosure = css`
  .disclosure::after {
    content: "";
    width: 6px;
    height: 6px;
    margin: -3px 0 0 2px;
    border-right: 1.5px solid currentcolor;
    border-bottom: 1.5px solid currentcolor;
    transform: rotate(45deg);
    opacity: 0.6;
  }
`;

/** The one button, and its variants: `primary` (ink, the one filled button), `ghost`,
 * `small` and `link`.
 *
 * A native `<button>` rather than a wrapping element, so focus, the keyboard and forms are the
 * browser's own. The page adopts this same sheet for the markup that is not a component yet,
 * so there is one definition of a button, not one per shadow root. */
export const buttons = css`
  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font: inherit;
    font-size: 12px;
    font-weight: 500;
    color: var(--fg);
    background: var(--panel);
    border: 1px solid var(--line-strong);
    border-radius: var(--radius);
    padding: 0 11px;
    height: 28px;
    cursor: pointer;
    box-shadow: var(--shadow);
    white-space: nowrap;
    transition:
      background-color 0.12s,
      border-color 0.12s,
      color 0.12s;
  }

  button:hover:not(:disabled) {
    background: var(--panel-2);
    border-color: var(--fg-faint);
  }

  button:disabled {
    opacity: 0.4;
    cursor: default;
    box-shadow: none;
  }

  /* The inline-flex above would otherwise win over the hidden attribute. */
  button[hidden] {
    display: none;
  }

  button.primary {
    background: var(--ink);
    border-color: var(--ink);
    color: var(--ink-fg);
    padding: 0 10px 0 14px;
  }

  button.primary:hover:not(:disabled) {
    background: color-mix(in srgb, var(--ink) 85%, var(--bg));
    border-color: transparent;
  }

  button.ghost {
    background: none;
    border-color: transparent;
    box-shadow: none;
  }

  button.ghost:hover:not(:disabled),
  button.ghost[aria-expanded="true"] {
    background: var(--panel-2);
    border-color: var(--line);
  }

  button.small {
    height: 24px;
    padding: 0 8px;
    font-size: 11px;
  }

  button.link {
    height: auto;
    background: none;
    border: none;
    box-shadow: none;
    color: var(--accent);
    padding: 0 2px;
    font-size: 11px;
    letter-spacing: normal;
    text-transform: none;
  }

  button.link:hover:not(:disabled) {
    background: none;
    text-decoration: underline;
  }

  button.link:disabled {
    visibility: hidden;
  }
`;
