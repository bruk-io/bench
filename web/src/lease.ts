/** Who may write a project, decided from the leases the host holds and the time alone.
 *
 * decision-9: "The host grants a write lease on a project, and holds it for one client.
 * Everyone else may open it, read it, run it and look at it; nobody else may write to it." A
 * lease, not a lock, because clients vanish - a tab shut, a lid closed, a tablet backgrounded -
 * and a lock outlives all of them. So a lease carries a holder and the last time it was heard
 * from, the holder renews it while it is alive, and it lapses on its own once the renewals stop.
 *
 * The leases themselves live in the server's memory (`server/projects.ts`) and nowhere else: a
 * restart voids every one of them and leaves nothing on a disk for somebody to delete by hand.
 * This module is what that memory is *for*: a lease asked for, taken, taken over or let go, and
 * whether a write may go ahead, as data in and data out. No clock is read here - `now` is handed
 * in - and nothing is kept, so it is tested in the browser like `route.ts` and loaded by the
 * server like `route.ts`.
 *
 * **The holder id is the credential.** Whoever sends it may write, so it is never handed to
 * anybody else: what another client is told about a holder is `Held` - what the holder called
 * itself, the address it asked from, and how long it has held the project - never its id.
 *
 * **What a lease does not cover**: the maker's own editor, `git checkout`, anything that is not
 * a client of this route. `vim` does not ask for permission; the stale-write check in
 * `server/projects.ts` is what stands between the app and them.
 */

/** How long a lease lasts without being heard from, in milliseconds.
 *
 * *Provisional.* decision-9 leaves this to the owner - "somewhere around a minute, renewed
 * every fifteen seconds, is the shape - but the number wants to be met rather than guessed" -
 * and this is that shape, not a measurement. A short expiry frees a shut tab's project sooner
 * and makes a slow network look like a lost lease; a long one is the reverse. The server may be
 * started with another (`BENCH_LEASE_MS`), which is how the tests make a lease lapse in seconds
 * and how the number can be tried before it is fixed. */
export const EXPIRY_MS = 60_000;

/** How often a holder renews - and a reader asks again whether the project has come free.
 * *Provisional*, like `EXPIRY_MS`, and derived from it rather than set beside it, so a
 * shortened expiry can never be renewed less often than it lapses: four renewals to a lease,
 * so one or two lost on a poor network do not lose it. */
export const renewEvery = (expiryMs: number): number => Math.max(250, Math.floor(expiryMs / 4));

/** The longest label a client may give itself - a sentence, not a document. */
const LABEL_MAX = 80;

/** A client asking about a lease: the id it holds leases under, what it calls itself for
 * others to read, and the address the host saw it ask from. */
export interface Client {
  readonly id: string;
  readonly label: string;
  readonly address: string;
}

/** A lease, as the host holds it. */
export interface Lease extends Client {
  /** When this holder took the project - not when it last renewed. */
  readonly sinceMs: number;
  /** When this holder was last heard from: a take, a renewal. */
  readonly heardMs: number;
}

/** A lease as anybody but its holder is shown it: no id. */
export interface Held {
  readonly label: string;
  readonly address: string;
  /** How long ago it was taken, and how long ago its holder was last heard from - ages rather
   * than times, since the host's clock and a tablet's need not agree. */
  readonly forMs: number;
  readonly heardAgoMs: number;
}

/** What a client is told about one project's lease. */
export interface Standing {
  readonly project: string;
  /** Whether the client asking holds it. */
  readonly yours: boolean;
  /** Who holds it when it is somebody else, `null` when nobody does or the asker does. */
  readonly holder: Held | null;
  /** How long this lease lasts unheard, and how often to ask again - the server's own, so a
   * client never renews on a cadence that lets its lease lapse. */
  readonly expiryMs: number;
  readonly renewMs: number;
}

/** Every lease the host holds, by project name. */
export type Leases = ReadonlyMap<string, Lease>;

/** What a client may ask of a lease. */
export type Act =
  /** Take it if it is free or already yours (which renews it); otherwise be told whose it is. */
  | "take"
  /** Take it whoever holds it - decision-9's "a person can take it", after being told whose. */
  | "take-over"
  /** Let it go, if it is yours. */
  | "release"
  /** Only be told. */
  | "look";

export const ACTS: readonly Act[] = ["take", "take-over", "release", "look"];

/** Whether `lease` is still alive at `now`. */
export const live = (lease: Lease, now: number, expiryMs: number): boolean => now - lease.heardMs < expiryMs;

/** A holder id as the route takes one: long enough not to be guessed, plain enough for a
 * header. The client makes it from sixteen random bytes (`leasing.ts`). */
export const holderProblem = (id: string): string | null =>
  /^[A-Za-z0-9_-]{16,128}$/.test(id) ? null : "a holder id is 16 to 128 letters, digits, - or _";

/** What a client called itself, made safe to show to somebody else: one line, not too long,
 * and something rather than nothing. */
export function labelled(said: string | undefined): string {
  const plain = [...(said ?? "")].filter((c) => c.charCodeAt(0) >= 0x20 && c !== "\x7f").join("").trim();
  const cut = plain.length > LABEL_MAX ? `${plain.slice(0, LABEL_MAX - 1)}…` : plain;
  return cut === "" ? "a client that did not say what it is" : cut;
}

const shown = (lease: Lease, now: number): Held => ({
  label: lease.label,
  address: lease.address,
  forMs: Math.max(0, now - lease.sinceMs),
  heardAgoMs: Math.max(0, now - lease.heardMs),
});

/** `leases` without any that have lapsed by `now` - what every answer starts from, so a lapsed
 * lease is never shown to anybody as held. */
export function pruned(leases: Leases, now: number, expiryMs: number): Leases {
  const kept = new Map<string, Lease>();
  for (const [project, lease] of leases) if (live(lease, now, expiryMs)) kept.set(project, lease);
  return kept.size === leases.size ? leases : kept;
}

/** `act`, asked by `client` of `project`'s lease at `now`: the leases afterwards, and what the
 * client is told. Nothing here refuses - a take of a lease somebody else holds is answered with
 * whose it is, which is the answer the asker needs, not an error. */
export function leased(
  leases: Leases,
  project: string,
  act: Act,
  client: Client,
  now: number,
  expiryMs: number,
): { readonly leases: Leases; readonly standing: Standing } {
  const current = pruned(leases, now, expiryMs);
  const held = current.get(project);
  const mine = held !== undefined && held.id === client.id;
  let next: Map<string, Lease> | null = null;
  const change = (): Map<string, Lease> => (next ??= new Map(current));

  if (act === "take-over" || (act === "take" && (held === undefined || mine))) {
    change().set(project, {
      ...client,
      // A renewal keeps the time it was taken: "held for twenty minutes" is about the holder.
      sinceMs: mine && act === "take" ? held.sinceMs : now,
      heardMs: now,
    });
  } else if (act === "release" && mine) {
    change().delete(project);
  }

  const after = next ?? current;
  const holding = after.get(project);
  return {
    leases: after,
    standing: {
      project,
      yours: holding !== undefined && holding.id === client.id,
      holder: holding === undefined || holding.id === client.id ? null : shown(holding, now),
      expiryMs,
      renewMs: renewEvery(expiryMs),
    },
  };
}

/** Who holds `project` at `now`, as somebody who does not is shown it - or `null` when nobody
 * does, or `holder` does. What a write is checked against: a write to a project somebody else
 * holds is refused, and one to a project nobody holds goes ahead, whoever sent it. */
export function heldAgainst(
  leases: Leases,
  project: string,
  holder: string | null,
  now: number,
  expiryMs: number,
): Held | null {
  const lease = leases.get(project);
  if (lease === undefined || !live(lease, now, expiryMs) || lease.id === holder) return null;
  return shown(lease, now);
}
