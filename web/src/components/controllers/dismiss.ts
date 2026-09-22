/** Shut something that is open - a menu, a popover - the two ways a person expects to: a
 * click anywhere outside it, or Escape.
 *
 * A Lit reactive controller, so the listening follows the host: added to the document when the
 * host is connected and taken off again when it is not, with nothing for the host to remember
 * to undo. Escape is left alone when something nearer the keyboard - the editor - has already
 * handled it.
 */
import type { ReactiveController, ReactiveControllerHost } from "lit";

export class DismissController implements ReactiveController {
  readonly #host: ReactiveControllerHost & HTMLElement;

  readonly #dismiss: () => void;

  /** `dismiss` is called for every click outside `host` and every unclaimed Escape; it is the
   * host's to make that a no-op while nothing is open. */
  constructor(host: ReactiveControllerHost & HTMLElement, dismiss: () => void) {
    this.#host = host;
    this.#dismiss = dismiss;
    host.addController(this);
  }

  readonly #onClick = (event: MouseEvent): void => {
    // The composed path, not the target: a click inside the host's shadow root is retargeted
    // to the host itself by the time it reaches the document.
    if (!event.composedPath().includes(this.#host)) this.#dismiss();
  };

  readonly #onKeydown = (event: KeyboardEvent): void => {
    if (event.key === "Escape" && !event.defaultPrevented) this.#dismiss();
  };

  hostConnected(): void {
    document.addEventListener("click", this.#onClick);
    document.addEventListener("keydown", this.#onKeydown);
  }

  hostDisconnected(): void {
    document.removeEventListener("click", this.#onClick);
    document.removeEventListener("keydown", this.#onKeydown);
  }
}
