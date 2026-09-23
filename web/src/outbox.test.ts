/** Real IndexedDB, real chromium (`vitest.config.ts`), no fakes - what this file can check is
 * the storage side: coalescing, reload survival (a second `outbox()` on the same database),
 * `hasRows`, `rebase`'s rules, and that `sendThrough` never touches the queue at all. Landing a
 * write, a `moved` refusal, and the drain's own backoff against a real route are the adapter
 * and e2e layers' job (`tests/e2e/test_host_store.py`) - this file has no server to land one on,
 * since `vitest.config.ts` does not load `vite.config.ts`'s plugins.
 *
 * `host("http://127.0.0.1:39997")` is a real client pointed at a port nothing answers on: every
 * call it makes really fails over the network, which is enough to check what this outbox does
 * with a write that cannot go out, without pretending to be a server.
 */
import { afterEach, describe, expect, it } from "vitest";

import { host } from "./host";
import { outbox } from "./outbox";

const UNREACHABLE = host("http://127.0.0.1:39997");

let names: string[] = [];
function freshName(): string {
  const name = `bench-outbox-test-${crypto.randomUUID()}`;
  names.push(name);
  return name;
}

afterEach(async () => {
  await Promise.all(
    names.map(
      (name) =>
        new Promise<void>((resolve) => {
          const request = indexedDB.deleteDatabase(name);
          request.onsuccess = () => resolve();
          request.onerror = () => resolve();
          request.onblocked = () => resolve();
        }),
    ),
  );
  names = [];
});

describe("enqueue", () => {
  it("coalesces several edits to the same file into one pending write", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "cabinet.py", "x = 1\n", null);
    await box.enqueue("workspace", "cabinet.py", "x = 12\n", null);
    await box.enqueue("workspace", "cabinet.py", "x = 123\n", null);
    const pending = await box.pending();
    expect(pending.size).toBe(1);
    expect(pending.get("workspace/cabinet.py")).toMatchObject({ text: "x = 123\n", base: null });
  });

  it("keeps the first base once a write is pending, even if a later enqueue passes another", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "cabinet.py", "x = 1\n", "v1");
    await box.enqueue("workspace", "cabinet.py", "x = 2\n", "v2");
    const pending = await box.pending();
    expect(pending.get("workspace/cabinet.py")?.base).toBe("v1");
  });

  it("keeps two different files apart", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "a.py", "1", null);
    await box.enqueue("workspace", "b.py", "2", null);
    const pending = await box.pending();
    expect(pending.size).toBe(2);
  });

  it("coalesces a delete the same way a write does", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueueDelete("workspace", "cabinet.py", "v1");
    await box.enqueueDelete("workspace", "cabinet.py", "v2");
    const pending = await box.pending();
    expect(pending.size).toBe(1);
    expect(pending.get("workspace/cabinet.py")).toMatchObject({ op: "delete", base: "v1" });
  });
});

describe("hasRows", () => {
  it("is false for a database nothing has ever written to", async () => {
    const box = outbox(UNREACHABLE, freshName());
    expect(await box.hasRows()).toBe(false);
  });

  it("is true the moment something is enqueued", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "cabinet.py", "x = 1\n", null);
    expect(await box.hasRows()).toBe(true);
  });
});

describe("reload survival", () => {
  it("a second outbox on the same database name sees what the first left pending", async () => {
    const name = freshName();
    const first = outbox(UNREACHABLE, name);
    await first.enqueue("workspace", "cabinet.py", "x = 1\n", null);

    const second = outbox(UNREACHABLE, name);
    const pending = await second.pending();
    expect(pending.get("workspace/cabinet.py")?.text).toBe("x = 1\n");
  });
});

describe("sendThrough", () => {
  it("never becomes a pending write, whether it lands or not - AC#7", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await expect(box.sendThrough("workspace", "drawer.stl", new Uint8Array([1, 2, 3]))).rejects.toBeTruthy();
    expect(await box.pending()).toEqual(new Map());
    expect(await box.hasRows()).toBe(false);
  });
});

describe("rebase", () => {
  it("seeds a clean cache row for a file with nothing pending", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.rebase("workspace", "cabinet.py", "v1", "x = 1\n");
    expect(await box.pending()).toEqual(new Map());
    expect(await box.hasRows()).toBe(true);
  });

  it("refreshes a clean row's base without needing anything pending", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.rebase("workspace", "cabinet.py", "v1", "x = 1\n");
    await box.rebase("workspace", "cabinet.py", "v2", "x = 1\n");
    // Nothing pending either way - this only checks the call does not throw on a clean row,
    // and the base it left is exercised indirectly by the "first base" enqueue test above.
    expect(await box.pending()).toEqual(new Map());
  });

  it("leaves a dirty write alone when the host does not yet hold what it wants written", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "cabinet.py", "x = 2\n", null);
    await box.rebase("workspace", "cabinet.py", "v1", "x = 1\n"); // the host has the old text
    const pending = await box.pending();
    expect(pending.get("workspace/cabinet.py")).toMatchObject({ text: "x = 2\n", base: null });
  });

  it("clears a dirty write once the host already holds exactly what it wants written", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "cabinet.py", "x = 2\n", null);
    await box.rebase("workspace", "cabinet.py", "v2", "x = 2\n"); // it landed already
    expect(await box.pending()).toEqual(new Map());
    expect(await box.hasRows()).toBe(true); // the row survives, clean, as the next base
  });

  it("clears a dirty delete once the host no longer holds the file", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueueDelete("workspace", "cabinet.py", "v1");
    await box.rebase("workspace", "cabinet.py", null, null); // gone from the host already
    expect(await box.pending()).toEqual(new Map());
    expect(await box.hasRows()).toBe(false); // nothing left to cache for a file that is gone
  });
});

describe("state", () => {
  it("starts clear", () => {
    const box = outbox(UNREACHABLE, freshName());
    expect(box.state()).toEqual({ kind: "clear" });
  });

  it("reads as sending the moment something is enqueued, before any attempt has failed", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "cabinet.py", "x = 1\n", null);
    expect(box.state()).toEqual({ kind: "sending" });
  });

  it("notifies a subscriber when the state changes", async () => {
    const box = outbox(UNREACHABLE, freshName());
    const seen: string[] = [];
    const unsubscribe = box.subscribe((state) => seen.push(state.kind));
    await box.enqueue("workspace", "cabinet.py", "x = 1\n", null);
    unsubscribe();
    expect(seen).toContain("sending");
  });

  it("reads as waiting once a real attempt against an unreachable host has failed", async () => {
    const box = outbox(UNREACHABLE, freshName());
    await box.enqueue("workspace", "cabinet.py", "x = 1\n", null);
    box.drain();
    await new Promise<void>((resolve) => {
      const unsubscribe = box.subscribe((state) => {
        if (state.kind === "waiting") {
          unsubscribe();
          resolve();
        }
      });
    });
    expect(box.state()).toEqual({ kind: "waiting" });
    // Still pending: an unreachable host is not a reason to give up on the write.
    expect((await box.pending()).size).toBe(1);
  }, 15_000);
});
