/** Writes that have not reached the host yet, kept in IndexedDB until they do.
 *
 * decision-9's outbox rule: `keep()` is synchronous and must never wait on the network, so a
 * write that cannot go out at once has to live somewhere until it can - bounded by what is in
 * flight, coalesced on the run's own 300 ms cadence, drained when the host answers again.
 *
 * **An outbox, never a mirror.** There is no merge and no conflict resolution here: a queue
 * drains, and a drain the route refuses as `moved` or `exists` is reported and left alone -
 * never retried in the background hoping it eventually wins, because it structurally cannot
 * until somebody looks at it. Recovery is a fresh `load()` (a reload): `rebase` is what that
 * gives a refused file a fair try, against the version actually on the host rather than the
 * one that was refused.
 *
 * **One record per file is both the queue and the version cache.** A file this outbox has
 * ever been told about keeps its record after a write lands - `dirty` turns `false` rather
 * than the row disappearing - so the *next* edit to that file already knows the base to write
 * from without asking the host again. `store-host.ts`'s `load()` seeds every file it reads with
 * `rebase` for exactly this: an edit made the moment the app boots must not be a "create"
 * because nothing has told this outbox the file exists yet.
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

export interface Outbox {
  /** Queue `text` for `project`/`file`, made from `base` - only used the first time this
   * outbox hears of the file; after that its own last known base wins, whatever is passed. */
  enqueue(project: string, file: string, text: string, base: string | null): Promise<void>;
  /** Queue the removal of `project`/`file`, made from `base`, the same coalescing rule. */
  enqueueDelete(project: string, file: string, base: string | null): Promise<void>;
  /** Every write this outbox has not landed yet, keyed `project/file` - what a caller
   * reconstructing what the host does not have yet needs (`store-host.ts`'s `load()`). */
  pending(): Promise<ReadonlyMap<string, Pending>>;
  /** Tell this outbox `project`/`file` is really at `base` - what `load()` does for every
   * file it reads, so the next edit's base is right and a refusal made before a reload gets a
   * fair try against what is actually there now. */
  rebase(project: string, file: string, base: string | null): Promise<void>;
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

  const inflight = new Set<string>();
  const listeners = new Set<(state: OutboxState) => void>();
  let current: OutboxState = { kind: "clear" };
  let drainTimer: ReturnType<typeof setTimeout> | undefined;
  let backoffMs = 0;
  let failedThisRound = false;

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
      setState({ kind: "clear" });
      return;
    }
    setState(inflight.size > 0 ? { kind: "sending" } : { kind: "waiting" });
  }

  function schedule(delay: number): void {
    clearTimeout(drainTimer);
    drainTimer = setTimeout(() => {
      void run();
    }, delay);
  }

  async function attempt(key: string): Promise<void> {
    if (inflight.has(key)) return;
    const record = await get(key);
    if (record === undefined || !record.dirty || record.refused) return;
    inflight.add(key);
    try {
      let answer: Answer<Version | null>;
      try {
        if (record.op === "delete") {
          answer =
            record.base === null
              ? { ok: true, value: null }
              : await client.remove(record.project, record.file, record.base);
        } else {
          answer =
            record.base === null
              ? await client.create(record.project, record.file, record.text)
              : await client.write(record.project, record.file, record.text, record.base);
        }
      } catch {
        failedThisRound = true;
        return;
      }
      if (answer.ok) {
        const now = await get(key);
        if (now === undefined) return;
        const same = now.op === record.op && now.text === record.text && now.base === record.base;
        if (record.op === "delete") {
          if (same) await drop(key);
          return;
        }
        const version = answer.value?.version ?? null;
        await put(key, same ? { ...now, dirty: false, base: version } : { ...now, base: version });
        return;
      }
      if (answer.refusal.refused === "moved" || answer.refusal.refused === "exists") {
        await put(key, { ...record, refused: true, message: answer.refusal.message });
        return;
      }
      if (record.op === "delete" && answer.refusal.refused === "missing") {
        await drop(key);
        return;
      }
      failedThisRound = true;
    } finally {
      inflight.delete(key);
    }
  }

  async function run(): Promise<void> {
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
      backoffMs = backoffMs === 0 ? BACKOFF_START : Math.min(backoffMs * 2, BACKOFF_MAX);
      schedule(backoffMs);
    } else {
      backoffMs = 0;
      schedule(DEBOUNCE);
    }
  }

  if (typeof window !== "undefined") {
    window.addEventListener("online", () => {
      backoffMs = 0;
      schedule(0);
    });
  }

  async function coalesced(project: string, file: string, op: "write" | "delete", text: string, base: string | null): Promise<void> {
    const key = keyed(project, file);
    const was = await get(key);
    const record: Row = {
      project,
      file,
      op,
      text,
      base: was === undefined ? base : was.base,
      dirty: true,
      refused: was?.refused ?? false,
      message: was?.message ?? null,
    };
    await put(key, record);
    await recompute();
    schedule(DEBOUNCE);
  }

  return {
    enqueue: (project, file, text, base) => coalesced(project, file, "write", text, base),
    enqueueDelete: (project, file, base) => coalesced(project, file, "delete", "", base),
    async pending() {
      const held = await all();
      const held2 = new Map<string, Pending>();
      for (const [key, record] of held) {
        if (record.dirty) held2.set(key, record);
      }
      return held2;
    },
    async rebase(project, file, base) {
      const key = keyed(project, file);
      const was = await get(key);
      await put(key, {
        project,
        file,
        op: was?.op ?? "write",
        text: was?.text ?? "",
        base,
        dirty: was?.dirty ?? false,
        refused: false,
        message: null,
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
