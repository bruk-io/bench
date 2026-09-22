import { afterEach, describe, expect, it } from "vitest";

import { KEYS } from "./storage";
import { localStore } from "./store-local";

const DOCUMENT = '{"files":[{"name":"cabinet.py","source":"x = 1","values":""}],"current":"cabinet.py"}';

afterEach(() => {
  window.localStorage.clear();
});

describe("localStore", () => {
  it("answers null for a browser with nothing kept, which is a first visit", async () => {
    expect(await localStore().load()).toBeNull();
  });

  it("gives back what it was given", async () => {
    const store = localStore();
    await store.save(DOCUMENT);
    expect(await store.load()).toBe(DOCUMENT);
  });

  it("keeps it under the key the app has always used, so nothing is lost on the way in", async () => {
    // The retrofit must not move a person's work: a browser that had projects before this
    // module existed still has them.
    await localStore().save(DOCUMENT);
    expect(window.localStorage.getItem(KEYS.files)).toBe(DOCUMENT);
  });

  it("reads what was kept before there was a store at all", async () => {
    window.localStorage.setItem(KEYS.files, DOCUMENT);
    expect(await localStore().load()).toBe(DOCUMENT);
  });

  it("says which place it is, for the log and for anything on screen", () => {
    expect(localStore().kind).toBe("browser");
  });

  it("reports a write the browser would not take, rather than swallowing it", async () => {
    // `storage.ts` never throws - right for a remembered tab, wrong for a person's projects.
    const setItem = window.localStorage.setItem.bind(window.localStorage);
    window.localStorage.setItem = () => {
      throw new DOMException("quota", "QuotaExceededError");
    };
    try {
      await expect(localStore().save(DOCUMENT)).rejects.toThrow(/would not keep/);
    } finally {
      window.localStorage.setItem = setItem;
    }
  });

  it("does not report a write that landed", async () => {
    await expect(localStore().save(DOCUMENT)).resolves.toBeUndefined();
  });
});
