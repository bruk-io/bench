/** This tab's write lease on the project it has open: taken when the project opens, renewed
 * while the tab lives, let go when it goes or opens another (decision-9, task-47).
 *
 * `lease.ts` is what the host decides; this is the one client of it the page has. It asks the
 * route, keeps what it was last told as a `Standing` - asking, writing, or reading because
 * somebody else is writing - and says so to whoever subscribed. `main.ts` is what turns that
 * into an editor that takes typing or does not, knobs that are kept or are not, and a notice
 * saying who holds the project.
 *
 * **A reader keeps asking, a holder renews.** Every answer says how soon to ask again
 * (`renewMs`, the server's own). A reader asks `take` on that cadence, so a lease that lapses,
 * or is let go, is picked up by whoever is still looking at the project with nobody having to
 * press anything (AC#3) - a tab left open on a project somebody else is writing becomes its
 * writer the moment they stop. A holder asks `renew` instead: `renew` only ever extends a lease
 * this tab still holds, never creates one, so a renewal already on the wire when the tab closes
 * cannot land after the release and hand the lease back to a tab that is gone (task-55). A
 * `renew` answered "not yours" is read as: held by somebody else now - become their reader; or
 * free - take it, the same as a reader would.
 *
 * **Not being able to ask changes nothing.** A lease request that does not get an answer - the
 * network, a restart mid-renewal - leaves the standing as it was and asks again sooner: a holder
 * that lost a renewal or two still holds the lease, which is what four renewals to a lifetime
 * are for (`lease.ts`), and the route refuses a write if it truly has lapsed and somebody else
 * has taken it.
 *
 * **Letting go on `pagehide` is a courtesy, never relied on.** iOS is free to discard a
 * backgrounded page without running anything, and the expiry is what makes that merely slow
 * rather than wrong (decision-9).
 */
import type { Host, Identity } from "./host";
import type { Act, Held } from "./lease";
import { KEYS, tabRemember, tabRemembered } from "./storage";

/** Where this tab stands on the project it has open. */
export type Standing =
  /** Asked, and not answered yet - nothing is written until it is. */
  | { readonly kind: "asking"; readonly project: string }
  /** This tab holds the lease: it may write. */
  | { readonly kind: "writer"; readonly project: string }
  /** Somebody else holds it, and who. `lost` when this tab held it and it was taken over - the
   * one case where the person has to be told something changed under them. */
  | { readonly kind: "reader"; readonly project: string; readonly holder: Held; readonly lost: boolean };

export interface Leasing {
  /** Make `project` the one this tab has open: let go of the one it had, and take this one if
   * it is free. Nothing when it is already the one open. */
  open(project: string): void;
  /** Take the open project's lease whoever holds it - the in-page action a person takes after
   * being told whose it is (AC#6). */
  takeOver(): Promise<void>;
  /** Let go of the open project's lease on the way out: sent so it finishes after the page has
   * gone, and answered by nobody. */
  release(): void;
  /** Ask again at once - a page come back from the back-forward cache, which let go on its way
   * into it. */
  resume(): void;
  standing(): Standing | null;
  subscribe(fn: (standing: Standing) => void): () => void;
}

/** How soon to ask again after a request that got no answer, when no answer has said. */
const RETRY_MS = 5000;

/** A fresh holder id: sixteen random bytes, as hex. `getRandomValues` rather than
 * `randomUUID`, because the second is secure-context only and a tablet reaching the host as
 * `http://192.168.1.20:5173` is exactly the page that is not one (decision-9). */
function freshId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (one) => one.toString(16).padStart(2, "0")).join("");
}

/** What a browser calls itself for somebody else to read - "Chrome on a Mac", "Safari on an
 * iPad" - from its user agent, and the touch points that are the only way left to tell an iPad
 * from a Mac (iPadOS asks for the desktop site, and says "Macintosh"). A guess for a person to
 * read, never a thing anything is decided on. */
export function clientLabel(agent: string, touchPoints: number): string {
  const browser = /Edg\//.test(agent)
    ? "Edge"
    : /Firefox\/|FxiOS\//.test(agent)
      ? "Firefox"
      : /Chrome\/|CriOS\//.test(agent)
        ? "Chrome"
        : /Safari\//.test(agent)
          ? "Safari"
          : "A browser";
  const device = /iPad/.test(agent) || (/Macintosh/.test(agent) && touchPoints > 1)
    ? "an iPad"
    : /iPhone/.test(agent)
      ? "an iPhone"
      : /Android/.test(agent)
        ? "Android"
        : /Macintosh/.test(agent)
          ? "a Mac"
          : /Windows/.test(agent)
            ? "Windows"
            : /Linux/.test(agent)
              ? "Linux"
              : null;
  return device === null ? browser : `${browser} on ${device}`;
}

/** This tab's identity to the leases: the id it has held them under since it was opened -
 * kept across a reload, so a reload reclaims its own lease at once rather than queueing behind
 * the ghost of itself (AC#4) - and what it calls itself.
 *
 * A tab *duplicated* by the browser copies its `sessionStorage`, and so its id, and the two are
 * one writer to the host until one of them is reloaded somewhere else. Known, and left: telling
 * them apart needs something a page does not have. */
export function identity(): Identity {
  let id = tabRemembered(KEYS.holder);
  if (id === null) {
    id = freshId();
    tabRemember(KEYS.holder, id);
  }
  return { id, label: clientLabel(navigator.userAgent, navigator.maxTouchPoints) };
}

/** The lease on whichever project this tab has open, over `client` - which must carry this
 * tab's `identity()`, since that is who the host is told is asking. */
export function leasing(client: Host): Leasing {
  let current: Standing | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  /** Bumped whenever the project changes, so an answer about the one before is dropped. */
  let generation = 0;
  let renewMs = RETRY_MS;
  /** The ask on its way, so letting go can call it back: a renewal still in flight when the
   * page goes is now harmless on the server even if it lands after the release (task-55 -
   * `renew` never creates a lease), but sending it anyway would only be answered "you do not
   * hold it" for a tab that is no longer there to hear it, so it is aborted as a courtesy. */
  let asking: AbortController | null = null;
  const listeners = new Set<(standing: Standing) => void>();

  function set(next: Standing): void {
    current = next;
    for (const fn of listeners) fn(next);
  }

  /** `take` for a tab that does not hold the lease - opening, reclaiming its own after a
   * reload, or a reader noticing it might have come free - `renew` for one that does: a holder
   * schedules its own next ask as `renew`, never `take`, so a renewal already on its way to the
   * server when this tab closes can only ever extend the lease this tab holds, never re-create
   * it for a tab that is gone (task-55). */
  function schedule(project: string, delay: number, act: "take" | "renew"): void {
    clearTimeout(timer);
    const asked = generation;
    timer = setTimeout(() => {
      void ask(project, act, asked);
    }, delay);
  }

  async function ask(project: string, act: Act, asked: number): Promise<void> {
    let answer: Awaited<ReturnType<Host["lease"]>> | null;
    const mine = new AbortController();
    asking = mine;
    try {
      answer = await client.lease(project, act, false, mine.signal);
    } catch {
      answer = null;
    }
    if (mine.signal.aborted) return; // let go of while this was asked
    if (asked !== generation) return; // another project was opened while this was asked
    if (answer === null || !answer.ok) {
      schedule(project, Math.min(renewMs, RETRY_MS), act === "renew" ? "renew" : "take");
      return;
    }
    const said = answer.value;
    renewMs = said.renewMs;
    if (said.yours) {
      set({ kind: "writer", project });
      schedule(project, renewMs, "renew");
      return;
    }
    if (act === "renew" && said.holder === null) {
      // This tab's lease lapsed - a laptop that slept through a renewal or two - and nobody
      // has taken it in between: free is free, so it is taken again, the same as a reader
      // would. What `renew` must never do on its own is hand the lease back once somebody else
      // holds it (`said.holder !== null`, below) - that is not this tab's to decide.
      void ask(project, "take", asked);
      return;
    }
    if (said.holder !== null) {
      const was = current;
      const lost = was?.project === project && (was.kind === "writer" || (was.kind === "reader" && was.lost));
      set({ kind: "reader", project, holder: said.holder, lost });
    }
    schedule(project, renewMs, "take");
  }

  return {
    open(project) {
      if (current?.project === project) return;
      if (current?.kind === "writer") void client.lease(current.project, "release").catch(() => undefined);
      generation += 1;
      set({ kind: "asking", project });
      void ask(project, "take", generation);
    },
    async takeOver() {
      if (current === null) return;
      await ask(current.project, "take-over", generation);
    },
    release() {
      clearTimeout(timer);
      asking?.abort();
      if (current?.kind !== "writer") return;
      void client.lease(current.project, "release", true).catch(() => undefined);
    },
    resume() {
      if (current === null) return;
      generation += 1;
      void ask(current.project, "take", generation);
    },
    standing: () => current,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}
