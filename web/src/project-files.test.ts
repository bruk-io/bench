import { describe, expect, it } from "vitest";

import { single } from "./files";
import { MANIFEST, PROJECT, filesFor, owned, removalsFor, workspaceFrom, writesFor } from "./project-files";

describe("PROJECT and MANIFEST", () => {
  it("names the one directory and the one reserved file this mapping uses", () => {
    expect(PROJECT).toBe("workspace");
    expect(MANIFEST.endsWith(".toml")).toBe(true);
    expect(MANIFEST.startsWith(".")).toBe(false); // route.ts refuses a hidden file
  });
});

describe("filesFor", () => {
  it("writes one .py, one .toml and the manifest for a workspace of one project", () => {
    const space = single("cabinet.py", "x = 1\n", { units_x: 4 });
    const writes = filesFor(space);
    const names = writes.map((w) => w.file);
    expect(names).toEqual(["cabinet.py", "cabinet.toml", MANIFEST]);
    expect(writes.find((w) => w.file === "cabinet.py")?.text).toBe("x = 1\n");
    expect(writes.find((w) => w.file === "cabinet.toml")?.text).toContain("units_x = 4");
    expect(writes.find((w) => w.file === MANIFEST)?.text).toContain('current = "cabinet.py"');
  });
});

describe("writesFor", () => {
  it("writes every file when there is nothing to compare against", () => {
    const space = single("cabinet.py", "x = 1\n");
    expect(writesFor(null, space)).toEqual(filesFor(space));
  });

  it("writes nothing for a workspace kept again unchanged - the boot-writes-nothing rule", () => {
    const space = single("cabinet.py", "x = 1\n", { units_x: 4 });
    // A structurally identical workspace built by a different code path (as `workspaceFrom`
    // would build one read back from disk), not the same object.
    const again = single("cabinet.py", "x = 1\n", { units_x: 4 });
    expect(writesFor(space, again)).toEqual([]);
  });

  it("writes only the script that changed, and only its script - not its values file too", () => {
    const before = { files: [{ name: "a.py", source: "1", overrides: {}, reference: null }, { name: "b.py", source: "2", overrides: {}, reference: null }], current: "a.py" };
    const after = { ...before, files: [before.files[0]!, { name: "b.py", source: "3", overrides: {}, reference: null }] };
    const writes = writesFor(before, after);
    expect(writes.map((w) => w.file)).toEqual(["b.py"]);
  });

  it("writes only the manifest when just the open project changed", () => {
    const before = { files: [{ name: "a.py", source: "1", overrides: {}, reference: null }, { name: "b.py", source: "2", overrides: {}, reference: null }], current: "a.py" };
    const after = { ...before, current: "b.py" };
    expect(writesFor(before, after)).toEqual([{ file: MANIFEST, text: 'current = "b.py"\n' }]);
  });

  it("writes the values file again when only a value changed, and only the values file", () => {
    const before = single("cabinet.py", "x = 1\n", { units_x: 4 });
    const after = single("cabinet.py", "x = 1\n", { units_x: 5 });
    const writes = writesFor(before, after);
    expect(writes.map((w) => w.file)).toEqual(["cabinet.toml"]);
  });

  it("does not care which order an overrides object's keys were built in", () => {
    const before = single("cabinet.py", "x = 1\n", { a: 1, b: 2 });
    const after = single("cabinet.py", "x = 1\n", { b: 2, a: 1 });
    expect(writesFor(before, after)).toEqual([]);
  });

  it("never rewrites a hand-edited values file just because the script beside it changed", () => {
    // What `store-host.ts`'s boot rule is for: typing in the editor must not regenerate
    // `cabinet.toml` (and strip a comment a maker wrote in it by hand) underneath the person.
    const before = single("cabinet.py", "x = 1\n", { units_x: 4 });
    const after = single("cabinet.py", "x = 2\n", { units_x: 4 });
    expect(writesFor(before, after)).toEqual([{ file: "cabinet.py", text: "x = 2\n" }]);
  });
});

describe("removalsFor", () => {
  it("names both files of a project no longer in the workspace", () => {
    const before = single("cabinet.py", "x = 1\n");
    const after = { files: [{ name: "other.py", source: "x = 2\n", overrides: {}, reference: null }], current: "other.py" };
    expect(removalsFor(before, after)).toEqual(["cabinet.py", "cabinet.toml"]);
  });

  it("names nothing when there is nothing to compare against", () => {
    expect(removalsFor(null, single("cabinet.py", "x = 1\n"))).toEqual([]);
  });
});

describe("owned", () => {
  const scripts = new Set(["cabinet.py"]);

  it("owns a script, its paired values file and the manifest", () => {
    expect(owned("cabinet.py", scripts)).toBe(true);
    expect(owned("cabinet.toml", scripts)).toBe(true);
    expect(owned(MANIFEST, scripts)).toBe(true);
  });

  it("does not own an STL or a toml with no script beside it", () => {
    expect(owned("drawer.stl", scripts)).toBe(false);
    expect(owned("orphan.toml", scripts)).toBe(false);
  });
});

describe("workspaceFrom", () => {
  it("answers null for a project directory with no script in it", () => {
    expect(workspaceFrom(new Map())).toBeNull();
    expect(workspaceFrom(new Map([["drawer.stl", "binary"]]))).toBeNull();
  });

  it("pairs a script with its values file and reads the manifest's current", () => {
    const entries = new Map([
      ["a.py", "x = 1\n"],
      ["a.toml", "[values]\nunits_x = 4\n"],
      ["b.py", "x = 2\n"],
      [MANIFEST, 'current = "b.py"\n'],
    ]);
    const space = workspaceFrom(entries);
    expect(space?.current).toBe("b.py");
    expect(space?.files).toEqual([
      { name: "a.py", source: "x = 1\n", overrides: { units_x: 4 }, reference: null },
      { name: "b.py", source: "x = 2\n", overrides: {}, reference: null },
    ]);
  });

  it("opens on the first script when the manifest is missing or names one that is not there", () => {
    const entries = new Map([["a.py", "x = 1\n"]]);
    expect(workspaceFrom(entries)?.current).toBe("a.py");
    entries.set(MANIFEST, 'current = "nope.py"\n');
    expect(workspaceFrom(entries)?.current).toBe("a.py");
  });

  it("round-trips through filesFor: reading what was written gives back what was written", () => {
    const space = single("cabinet.py", "x = 1\n", { units_x: 4 });
    const entries = new Map(filesFor(space).map((w) => [w.file, w.text]));
    expect(workspaceFrom(entries)).toEqual(space);
  });
});
