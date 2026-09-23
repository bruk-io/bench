/** Writes that have not reached the host yet, kept in IndexedDB until they do.
 *
 * decision-9's outbox rule: `keep()` is synchronous and must never wait on the network, so a
 * write that cannot go out at once has to live somewhere until it can - bounded by what is in
 * flight, coalesced on the run's own 300 ms cadence, drained when the host answers again.
 *
 * **An outbox, never a mirror.** There is no merge and no conflict resolution here: a queue
 * drains, and a drain the route refuses is reported and left alone - never retried in the
 * background hoping it eventually wins, because it structurally cannot until somebody looks at
 * it. Recovery is a fresh `load()` (a reload): `rebase` is what that gives a refused file a
 * fair try, against the version actually on the host rather than the one that was refused - and
 * only a fair try, never a silent overwrite: a dirty row keeps its own base and its refusal
 * unless the host already holds exactly what it wants written, which is the one case a rebase
 * is allowed to clear on its own (a write that landed right before the tab closed).
 *
 * **One row per file is both the queue and the version cache.** A file this outbox has ever
 * been told about keeps its row after a write lands - `dirty` turns `false` rather than the row
 * disappearing - so the *next* edit to that file already knows the base to write from without
 * asking the host again. `store-host.ts`'s `load()` seeds every file it reads with `rebase` for
 * exactly this: an edit made the moment the app boots must not be a "create" because nothing
 * has told this outbox the file exists yet.
 *
 * **Every mutation goes through one queue of its own** (`locked`), because `get`-then-`put` is
 * not atomic across two IndexedDB transactions: a keystroke's `enqueue` and a landing write's
 * own read-decide-write would otherwise be able to interleave, coalescing an edit that arrived
 * a moment too early into a write already believed to have landed, or the reverse. The network
 * call itself sits outside the lock, so a slow or stuck request never holds up a keystroke.
 *
 * IndexedDB rather than `localStorage`: no five-megabyte wall, and it answers on a plain-http
 * LAN origin, which the origin private filesystem does not (decision-9).
 */
import type { Answer, Host, Version } from "./host";

/** Every state a person watching the status bar cares about. `refused` can sit beside other
 * files still draining normally - only the refused file is named. */
export type OutboxState =
  | { readonly kind: "clear" }
  | { readonly kind: "sending" }
  | { readonly kind: "waiting" }
  | { readonly kind: "refused"; readonly file: string; readonly message: string };

/** A write this outbox is still holding: what to send, or that the file should go. */
export interface Pending {
  readonly project: string;
  readonly file: string;
  readonly op: "write" | "delete";
  readonly text: string;
  readonly base: string | null;
}

interface Row extends Pending {
  readonly dirty: boolean;
  readonly refused: boolean;
  readonly message: string | null;
}

/** The coalescing cadence: several edits to the same file before the first of them lands
 * become one write, on the same 300 ms the run already debounces at (decision-9). */
const DEBOUNCE = 300;
const BACKOFF_START = 1000;
const BACKOFF_MAX = 30_000;

/** Refusals worth retrying once the host might be in better shape - a full disk, no root
 * configured yet. Everything else (`moved`, `exists`, a bad name, an origin refused, a file
 * type this route never writes...) cannot succeed by trying again unchanged, so it is reported
 * instead (AC#5) - the same rule task-52 asks for `moved` alone, widened to every reason a
 * retry cannot fix. */
const TRANSIENT = new Set(["failed", "no-root"]);

export interface Outbox {
  /** Queue `text` for `project`/`file`, made from `base` - only used the first time this
   * outbox hears of the file; after that its own last known base wins, whatever is passed. */
  enqueue(project: string, file: string, text: string, base: string | null): Promise<void>;
  /** Queue the removal of `project`/`file`, made from `base`, the same coalescing rule. */
  enqueueDelete(project: string, file: string, base: string | null): Promise<void>;
  /** Every write this outbox has not landed yet, keyed `project/file` - what a caller
   * reconstructing what the host does not have yet needs (`store-host.ts`'s `load()`). */
  pending(): Promise<ReadonlyMap<string, Pending>>;
  /** Whether this outbox is holding anything at all, landed or not - a browser that has ever
   * used the host store, even one with nothing left to send right now. `main.ts` reads this
   * before it will let a store choice fall back to the browser's own store (AC#8): a host that
   * merely answers slowly must not look the same as one this browser never used. */
  hasRows(): Promise<boolean>;
  /** Tell this outbox `project`/`file` is really at `base`, holding `text` - what `load()`
   * does for every file it reads. A row with nothing pending just has its cached base
   * refreshed. A row with something pending is left alone - base, refusal and all - unless
   * `text` already matches what it wants written, which means the write landed and this is
   * only catching up; a pending delete is cleared the same way when `text` is `null`. */
  rebase(project: string, file: string, base: string | null, text: string | null): Promise<void>;
  /** A write that is never queued: a dropped mesh is not edited, so there is nothing to
   * coalesce and nothing worth surviving a reload for - it either lands now or says it did
   * not (decision-9). */
  sendThrough(project: string, file: string, bytes: Uint8Array): ReturnType<Host["create"]>;
  state(): OutboxState;
  subscribe(fn: (state: OutboxState) => void): () => void;
  /** Try to send everything pending, now rather than waiting out any backoff - the `online`
   * event and a fresh boot both want this. */
  drain(): void;
}

const STORE = "pending";

function open(name: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("indexedDB.open failed"));
  });
}

function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error ?? new Error("IndexedDB transaction failed"));
    tx.onabort = () => reject(tx.error ?? new Error("IndexedDB transaction aborted"));
  });
}

function req<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB request failed"));
  });
}

const keyed = (project: string, file: string): string => `${project}/${file}`;

/** The outbox over `client` - `host.ts`'s calls - kept in the IndexedDB database `name` (one
 * per store; tests give each their own so they do not see each other's queues). */
export function outbox(client: Host, name = "bench-outbox"): Outbox {
  const db = open(name);

  async function get(key: string): Promise<Row | undefined> {
    const store = (await db).transaction(STORE, "readonly").objectStore(STORE);
    return req<Row | undefined>(store.get(key));
  }

  async function put(key: string, value: Row): Promise<void> {
    const tx = (await db).transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(value, key);
    await txDone(tx);
  }

  async function drop(key: string): Promise<void> {
    const tx = (await db).transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(key);
    await txDone(tx);
  }

  async function all(): Promise<ReadonlyMap<string, Row>> {
    const store = (await db).transaction(STORE, "readonly").objectStore(STORE);
    const keys = await req<IDBValidKey[]>(store.getAllKeys());
    const values = await req<Row[]>(store.getAll());
    return new Map(keys.map((key, at) => [String(key), values[at] as Row]));
  }

  // Every mutating call runs through this chain, one at a time, so a `get`-then-`put` pair
  // from one caller can never interleave with another's.
  let chain: Promise<unknown> = Promise.resolve();
  function locked<T>(fn: () => Promise<T>): Promise<T> {
    const result = chain.then(fn, fn);
    chain = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }

  const inflight = new Set<string>();
  const listeners = new Set<(state: OutboxState) => void>();
  let current: OutboxState = { kind: "clear" };
  let drainTimer: ReturnType<typeof setTimeout> | undefined;
  let backoffMs = 0;
  let failedThisRound = false;
  let sinceFailure = false;

  function setState(next: OutboxState): void {
    current = next;
    for (const fn of listeners) fn(next);
  }

  async function recompute(): Promise<void> {
    const held = [...(await all()).values()];
    const trouble = held.find((one) => one.refused);
    if (trouble !== undefined) {
      setState({ kind: "refused", file: keyed(trouble.project, trouble.file), message: trouble.message ?? "" });
      return;
    }
    const waiting = held.filter((one) => one.dirty);
    if (waiting.length === 0) {
      sinceFailure = false;
      setState({ kind: "clear" });
      return;
    }
    setState(inflight.size > 0 || !sinceFailure ? { kind: "sending" } : { kind: "waiting" });
  }

  function schedule(delay: number): void {
    clearTimeout(drainTimer);
    drainTimer = setTimeout(() => {
      void run();
    }, delay);
  }

  /** The row to send for `key`, claimed under the lock - `null` when there is nothing to do. */
  async function claim(key: string): Promise<Row | null> {
    return locked(async () => {
      const row = await get(key);
      return row === undefined || !row.dirty || row.refused ? null : row;
    });
  }

  /** What `sent` (the row `claim` handed out) becomes once the host has answered - under the
   * lock again, because what is there now may not be what was sent any more. */
  async function settle(key: string, sent: Row, answer: Answer<Version | null>): Promise<void> {
    await locked(async () => {
      const now = await get(key);
      if (now === undefined) return;
      const same = now.op === sent.op && now.text === sent.text && now.base === sent.base;
      if (answer.ok) {
        if (sent.op === "delete") {
          if (same) await drop(key);
          return;
        }
        const version = answer.value?.version ?? null;
        await put(key, same ? { ...now, dirty: false, base: version } : { ...now, base: version });
        return;
      }
      if (sent.op === "delete" && answer.refusal.refused === "missing") {
        if (same) await drop(key);
        return;
      }
      if (TRANSIENT.has(answer.refusal.refused)) {
        failedThisRound = true;
        return;
      }
      await put(key, { ...now, refused: true, message: answer.refusal.message });
    });
  }

  async function attempt(key: string): Promise<void> {
    if (inflight.has(key)) return;
    const sent = await claim(key);
    if (sent === null) return;
    inflight.add(key);
    try {
      let answer: Answer<Version | null>;
      try {
        if (sent.op === "delete") {
          answer =
            sent.base === null ? { ok: true, value: null } : await client.remove(sent.project, sent.file, sent.base);
        } else {
          answer =
            sent.base === null
              ? await client.create(sent.project, sent.file, sent.text)
              : await client.write(sent.project, sent.file, sent.text, sent.base);
        }
      } catch {
        failedThisRound = true;
        return;
      }
      await settle(key, sent, answer);
    } finally {
      inflight.delete(key);
    }
  }

  async function run(): Promise<void> {
    try {
      failedThisRound = false;
      const held = await all();
      await recompute();
      for (const key of held.keys()) {
        await attempt(key);
      }
      await recompute();
      const remaining = [...(await all()).values()];
      const stillPending = remaining.some((one) => one.dirty && !one.refused);
      if (!stillPending) {
        backoffMs = 0;
        return;
      }
      if (failedThisRound) {
        sinceFailure = true;
        await recompute();
        backoffMs = backoffMs === 0 ? BACKOFF_START : Math.min(backoffMs * 2, BACKOFF_MAX);
        schedule(backoffMs);
      } else {
        backoffMs = 0;
        schedule(DEBOUNCE);
      }
    } catch {
      // An IndexedDB failure mid-drain must not become an unhandled rejection inside the
      // fire-and-forget `void run()` this is always called through - so it is swallowed here,
      // not re-thrown; the next enqueue or the next `drain()` tries again.
      failedThisRound = true;
      backoffMs = backoffMs === 0 ? BACKOFF_START : Math.min(backoffMs * 2, BACKOFF_MAX);
      schedule(backoffMs);
    }
  }

  if (typeof window !== "undefined") {
    window.addEventListener("online", () => {
      backoffMs = 0;
      schedule(0);
    });
  }

  async function coalesced(
    project: string,
    file: string,
    op: "write" | "delete",
    text: string,
    base: string | null,
  ): Promise<void> {
    const key = keyed(project, file);
    await locked(async () => {
      const was = await get(key);
      const row: Row = {
        project,
        file,
        op,
        text,
        base: was === undefined ? base : was.base,
        dirty: true,
        refused: was?.refused ?? false,
        message: was?.message ?? null,
      };
      await put(key, row);
    });
    await recompute();
    schedule(DEBOUNCE);
  }

  return {
    enqueue: (project, file, text, base) => coalesced(project, file, "write", text, base),
    enqueueDelete: (project, file, base) => coalesced(project, file, "delete", "", base),
    async pending() {
      const held = await all();
      const dirty = new Map<string, Pending>();
      for (const [key, row] of held) {
        if (row.dirty) dirty.set(key, row);
      }
      return dirty;
    },
    async hasRows() {
      return (await all()).size > 0;
    },
    async rebase(project, file, base, text) {
      const key = keyed(project, file);
      await locked(async () => {
        const was = await get(key);
        if (was === undefined) {
          await put(key, { project, file, op: "write", text: "", base, dirty: false, refused: false, message: null });
          return;
        }
        if (!was.dirty) {
          await put(key, { ...was, base, refused: false, message: null });
          return;
        }
        if (was.op === "write" && text === was.text) {
          await put(key, { ...was, dirty: false, base, refused: false, message: null });
        } else if (was.op === "delete" && text === null) {
          await drop(key);
        }
        // Otherwise: a dirty row whose host content does not yet match what it wants written
        // (or wants deleted) is left exactly alone - its base, its text and any refusal stay
        // what they were, so a reload never silently overwrites a conflict it has not resolved.
      });
      await recompute();
    },
    sendThrough: (project, file, bytes) => client.create(project, file, bytes),
    state: () => current,
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    drain() {
      schedule(0);
    },
  };
}
