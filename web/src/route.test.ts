import { describe, expect, it } from "vitest";

import { type Asked, type Operation, type Refusal, decided, hostRefused, nameProblem, within, writable } from "./route";

const asked = (method: string, url: string, headers: Partial<Asked> = {}): Asked => ({
  method,
  url,
  scheme: "http",
  host: "localhost:5173",
  origin: undefined,
  fetchSite: undefined,
  ifMatch: undefined,
  ifNoneMatch: undefined,
  ...headers,
});

const reason = (found: Operation | Refusal | null): string | null =>
  found === null ? null : "refused" in found ? found.refused : found.op;

describe("decided: the path", () => {
  it("leaves every other URL to the next middleware", () => {
    expect(decided(asked("GET", "/"), [])).toBeNull();
    expect(decided(asked("GET", "/__bench/generated-at"), [])).toBeNull();
    expect(decided(asked("GET", "/__bench/projectsX"), [])).toBeNull();
  });

  it("reads a project and a file as the two names they are", () => {
    expect(decided(asked("GET", "/__bench/projects"), [])).toEqual({ op: "projects" });
    expect(decided(asked("GET", "/__bench/projects?x=1"), [])).toEqual({ op: "projects" });
    expect(decided(asked("GET", "/__bench/projects/cabinet"), [])).toEqual({ op: "files", project: "cabinet" });
    expect(decided(asked("GET", "/__bench/projects/my%20cabinet/cabinet.py"), [])).toEqual({
      op: "read",
      project: "my cabinet",
      file: "cabinet.py",
    });
  });

  it.each([
    ["dot-dot", "/__bench/projects/../etc"],
    ["dot-dot as a file", "/__bench/projects/cabinet/.."],
    ["encoded dot-dot", "/__bench/projects/%2e%2e/passwd"],
    ["an encoded separator", "/__bench/projects/cabinet/..%2F..%2Fescape.py"],
    ["an encoded absolute path", "/__bench/projects/%2Fetc%2Fpasswd"],
    ["a doubled slash", "/__bench/projects//etc/passwd"],
    ["a backslash", "/__bench/projects/cabinet/..%5Cescape.py"],
    ["a NUL", "/__bench/projects/cabinet/cabinet.py%00.txt"],
    ["a hidden file", "/__bench/projects/cabinet/.env"],
    ["a malformed escape", "/__bench/projects/cabinet/%E0%A4%A"],
    ["a path deeper than a project and a file", "/__bench/projects/a/b/c.py"],
  ])("refuses %s", (_what, url) => {
    expect(reason(decided(asked("GET", url), []))).toBe("name");
    expect(reason(decided(asked("PUT", url, { ifNoneMatch: "*" }), []))).toBe("name");
  });

  it("decodes once, so a doubly encoded dot-dot is a name with a percent sign, not a traversal", () => {
    expect(decided(asked("GET", "/__bench/projects/cabinet/%252e%252e"), [])).toEqual({
      op: "read",
      project: "cabinet",
      file: "%2e%2e",
    });
  });
});

describe("decided: writes", () => {
  it("writes only .py, .toml and .stl, whatever the case of the extension", () => {
    const put = (file: string) => reason(decided(asked("PUT", `/__bench/projects/p/${file}`, { ifNoneMatch: "*" }), []));
    expect(put("cabinet.py")).toBe("create");
    expect(put("cabinet.toml")).toBe("create");
    expect(put("slide.STL")).toBe("create");
    expect(put("notes.txt")).toBe("type");
    expect(put("run.sh")).toBe("type");
    expect(put("py")).toBe("type");
    expect(reason(decided(asked("DELETE", "/__bench/projects/p/notes.txt", { ifMatch: '"a"' }), []))).toBe("type");
  });

  it("refuses a rename onto a name that is not plain, or not writable", () => {
    const post = (to: string) => reason(decided(asked("POST", `/__bench/projects/p/a.py?to=${to}`), []));
    expect(post("b.py")).toBe("rename");
    expect(post("..%2Fb.py")).toBe("name");
    expect(post("b.txt")).toBe("type");
    expect(reason(decided(asked("POST", "/__bench/projects/p/a.py"), []))).toBe("name");
  });

  it("takes a write only with the version it was made from, or as a create", () => {
    const url = "/__bench/projects/p/a.py";
    expect(decided(asked("PUT", url, { ifMatch: '"abc"' }), [])).toEqual({
      op: "write",
      project: "p",
      file: "a.py",
      base: "abc",
    });
    expect(reason(decided(asked("PUT", url), []))).toBe("precondition");
    expect(reason(decided(asked("PUT", url, { ifMatch: 'W/"abc"' }), []))).toBe("precondition");
    expect(reason(decided(asked("DELETE", url), []))).toBe("precondition");
    expect(reason(decided(asked("DELETE", url, { ifMatch: '"abc"' }), []))).toBe("delete");
  });

  it("refuses methods a path does not take", () => {
    expect(reason(decided(asked("DELETE", "/__bench/projects"), []))).toBe("method");
    expect(reason(decided(asked("PUT", "/__bench/projects/p"), []))).toBe("method");
    expect(reason(decided(asked("PATCH", "/__bench/projects/p/a.py"), []))).toBe("method");
  });
});

describe("decided: who is asking", () => {
  const url = "/__bench/projects/p/a.py";

  it("takes a same-origin write, including from a tablet that reached the host by address", () => {
    const tablet = { host: "192.168.1.20:5173", origin: "http://192.168.1.20:5173", ifNoneMatch: "*" };
    expect(reason(decided(asked("PUT", url, tablet), []))).toBe("create");
    const here = { origin: "http://localhost:5173", fetchSite: "same-origin", ifNoneMatch: "*" };
    expect(reason(decided(asked("PUT", url, here), []))).toBe("create");
  });

  it("refuses a page on another origin, another port on the same host included", () => {
    for (const origin of ["http://evil.example", "http://localhost:3000", "https://localhost:5173", "null"]) {
      expect(reason(decided(asked("PUT", url, { origin, ifNoneMatch: "*" }), []))).toBe("origin");
    }
    expect(reason(decided(asked("GET", url, { fetchSite: "same-site" }), []))).toBe("origin");
    expect(reason(decided(asked("GET", url, { fetchSite: "cross-site" }), []))).toBe("origin");
  });

  it("lets a request with no Origin through, since only a client that is not a page sends none", () => {
    expect(reason(decided(asked("PUT", url, { ifNoneMatch: "*" }), []))).toBe("create");
  });

  it("refuses a name the server was not told to answer to, even when the origin matches it", () => {
    const rebound = { host: "evil.example:5173", origin: "http://evil.example:5173", ifNoneMatch: "*" };
    expect(reason(decided(asked("PUT", url, rebound), []))).toBe("host");
    expect(reason(decided(asked("PUT", url, rebound), ["evil.example"]))).toBe("create");
    expect(reason(decided(asked("PUT", url, rebound), true))).toBe("create");
  });
});

describe("hostRefused", () => {
  it("answers to addresses, localhost and what it was told, as Vite's own check does", () => {
    for (const host of ["127.0.0.1:5173", "192.168.1.20", "[::1]:5173", "localhost:4173", "bench.localhost"]) {
      expect(hostRefused(host, [])).toBeNull();
    }
    expect(hostRefused("workshop.lan:5173", [".lan"])).toBeNull();
    expect(hostRefused("workshop.lan:5173", [])?.refused).toBe("host");
    expect(hostRefused("[evil]:5173", [])?.refused).toBe("host");
    expect(hostRefused(undefined, [])?.refused).toBe("host");
  });
});

describe("names", () => {
  it("says why a name is not plain", () => {
    expect(nameProblem("cabinet.py")).toBeNull();
    expect(nameProblem("")).not.toBeNull();
    expect(nameProblem("a\u0000b")).not.toBeNull();
    expect(nameProblem("a\nb")).not.toBeNull();
    expect(nameProblem("x".repeat(256))).not.toBeNull();
  });

  it("knows the writable kinds", () => {
    expect(writable("a.py")).toBe(true);
    expect(writable(".py")).toBe(false);
    expect(writable("a.py.txt")).toBe(false);
  });
});

describe("within", () => {
  it("is strictly under the root and a separator, so a sibling with the same prefix is out", () => {
    expect(within("/r/projects", "/r/projects/cabinet")).toBe(true);
    expect(within("/r/projects", "/r/projects/cabinet/a.py")).toBe(true);
    expect(within("/r/projects", "/r/projects-evil/a.py")).toBe(false);
    expect(within("/r/projects", "/r/projects")).toBe(false);
    expect(within("/r/projects", "/r/projects/")).toBe(false);
    expect(within("/r/projects", "/etc/passwd")).toBe(false);
  });
});
