import { describe, expect, it } from "vitest";

import { STALE_MESSAGE, bundleStale, stale } from "./staleness";

describe("stale", () => {
  it("is false when nothing on disk is newer than what was bundled", () => {
    expect(stale(100, 100)).toBe(false);
    expect(stale(100, 50)).toBe(false);
  });

  it("is true once something on disk is newer than what was bundled", () => {
    expect(stale(100, 101)).toBe(true);
  });
});

describe("bundleStale", () => {
  const ok = (body: unknown): typeof fetch =>
    (() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) })) as unknown as typeof fetch;

  it("is false when the endpoint reports nothing newer", async () => {
    await expect(bundleStale(ok({ newest: 0 }))).resolves.toBe(false);
  });

  it("is true when the endpoint reports something far in the future", async () => {
    await expect(bundleStale(ok({ newest: Number.MAX_SAFE_INTEGER }))).resolves.toBe(true);
  });

  it("is false, never thrown, when the endpoint answers with the wrong shape", async () => {
    await expect(bundleStale(ok({}))).resolves.toBe(false);
    await expect(bundleStale(ok({ newest: "soon" }))).resolves.toBe(false);
  });

  it("is false when the response is not ok - no such route on a static deploy", async () => {
    const notFound = (() =>
      Promise.resolve({ ok: false, json: () => Promise.resolve({}) })) as unknown as typeof fetch;
    await expect(bundleStale(notFound)).resolves.toBe(false);
  });

  it("is false when the fetch itself rejects", async () => {
    const broken = (() => Promise.reject(new Error("network"))) as unknown as typeof fetch;
    await expect(bundleStale(broken)).resolves.toBe(false);
  });
});

describe("STALE_MESSAGE", () => {
  it("names the command that fixes it", () => {
    expect(STALE_MESSAGE).toContain("npm --prefix web run generate");
  });
});
