import { describe, expect, it } from "vitest";

import { type Project, type Workspace, project, single } from "./files";
import { type Directories, filesFor, owned, removalsFor, workspaceFrom, writesFor } from "./project-files";
import { BENCH, NOTHING_KEPT } from "./values";

/** A root on disk, as the store reads one: project directory to file name to text. */
const root = (layout: Record<string, Record<string, string>>): Directories =>
  new Map(Object.entries(layout).map(([name, files]) => [name, new Map(Object.entries(files))]));

const two = (a: Project, b: Project, current = a.name): Workspace => ({
  projects: [a, b],
  current,
  script: current === a.name ? a.entry : b.entry,
});

describe("filesFor", () => {
  it("writes each script and one bench.toml into the project's own directory", () => {
    const writes = filesFor(single("cabinet", "x = 1\n", { units_x: 4 }));
    expect(writes.map((w) => `${w.project}/${w.file}`)).toEqual(["cabinet/cabinet.py", `cabinet/${BENCH}`]);
    expect(writes.find((w) => w.file === "cabinet.py")?.text).toBe("x = 1\n");
    const document = writes.find((w) => w.file === BENCH)?.text ?? "";
    expect(document).toContain('[project]\nentry = "cabinet.py"\n');
    expect(document).toContain("units_x = 4");
  });

  it("writes nothing that says which project is open - that is each browser's own", () => {
    const writes = filesFor(two(project("a", "1"), project("b", "2"), "b"));
    expect(writes.map((w) => w.file)).toEqual(["a.py", BENCH, "b.py", BENCH]);
    expect(writes.some((w) => w.file.startsWith("_"))).toBe(false);
  });
});

describe("writesFor", () => {
  it("writes every file when there is nothing to compare against", () => {
    const space = single("cabinet", "x = 1\n");
    expect(writesFor(null, space)).toEqual(filesFor(space));
  });

  it("writes nothing for a workspace kept again unchanged - the boot-writes-nothing rule", () => {
    const space = single("cabinet", "x = 1\n", { units_x: 4 });
    // A structurally identical workspace built by a different code path (as `workspaceFrom`
    // would build one read back from disk), not the same object.
    const again = single("cabinet", "x = 1\n", { units_x: 4 });
    expect(writesFor(space, again)).toEqual([]);
  });

  it("writes only the script that changed, and only its script - not its document too", () => {
    const before = two(project("a", "1"), project("b", "2"));
    const after = two(project("a", "1"), project("b", "3"));
    expect(writesFor(before, after)).toEqual([{ project: "b", file: "b.py", text: "3" }]);
  });

  it("writes nothing when only the open project or the open script changed", () => {
    const before = two(project("a", "1"), project("b", "2"));
    expect(writesFor(before, { ...before, current: "b", script: "b.py" })).toEqual([]);
  });

  it("writes only one script of several when one of them was edited", () => {
    const one: Project = {
      name: "cabinet",
      entry: "main.py",
      scripts: { "main.py": "m", "parts.py": "p" },
      overrides: {},
      reference: null,
      kept: NOTHING_KEPT,
    };
    const edited = { ...one, scripts: { ...one.scripts, "parts.py": "p2" } };
    const writes = writesFor(
      { projects: [one], current: "cabinet", script: "parts.py" },
      { projects: [edited], current: "cabinet", script: "parts.py" },
    );
    expect(writes).toEqual([{ project: "cabinet", file: "parts.py", text: "p2" }]);
  });

  it("writes bench.toml again when only a value changed, and only bench.toml", () => {
    const before = single("cabinet", "x = 1\n", { units_x: 4 });
    const after = single("cabinet", "x = 1\n", { units_x: 5 });
    expect(writesFor(before, after).map((w) => w.file)).toEqual([BENCH]);
  });

  it("does not care which order an overrides object's keys were built in", () => {
    const before = single("cabinet", "x = 1\n", { a: 1, b: 2 });
    const after = single("cabinet", "x = 1\n", { b: 2, a: 1 });
    expect(writesFor(before, after)).toEqual([]);
  });

  it("never rewrites a hand-edited bench.toml just because the script beside it changed", () => {
    // What `store-host.ts`'s boot rule is for: typing in the editor must not regenerate
    // `bench.toml` (and strip a comment a maker wrote in it by hand) underneath the person.
    const before = single("cabinet", "x = 1\n", { units_x: 4 });
    const after = single("cabinet", "x = 2\n", { units_x: 4 });
    expect(writesFor(before, after)).toEqual([{ project: "cabinet", file: "cabinet.py", text: "x = 2\n" }]);
  });

  it("writes a new project's every file into a directory of its own", () => {
    const before = single("a", "1");
    const after = two(project("a", "1"), project("b", "2"), "b");
    expect(writesFor(before, after).map((w) => `${w.project}/${w.file}`)).toEqual(["b/b.py", `b/${BENCH}`]);
  });
});

describe("removalsFor", () => {
  it("names every file of a project no longer in the workspace", () => {
    const before = single("cabinet", "x = 1\n");
    const after = single("other", "x = 2\n");
    expect(removalsFor(before, after)).toEqual([
      { project: "cabinet", file: "cabinet.py" },
      { project: "cabinet", file: BENCH },
    ]);
  });

  it("names a script gone from a project that is still there, and not its document", () => {
    const one: Project = { ...project("c", "c"), scripts: { "c.py": "c", "old.py": "o" } };
    const before = { projects: [one], current: "c", script: "c.py" };
    const after = { projects: [project("c", "c")], current: "c", script: "c.py" };
    expect(removalsFor(before, after)).toEqual([{ project: "c", file: "old.py" }]);
  });

  it("names nothing when there is nothing to compare against", () => {
    expect(removalsFor(null, single("cabinet", "x = 1\n"))).toEqual([]);
  });
});

describe("owned", () => {
  it("reads scripts and TOML documents", () => {
    expect(owned("cabinet.py")).toBe(true);
    expect(owned(BENCH)).toBe(true);
    expect(owned("cabinet.toml")).toBe(true);
  });

  it("does not read an STL, which is bytes and asked for by a placement", () => {
    expect(owned("drawer.stl")).toBe(false);
  });
});

describe("workspaceFrom", () => {
  it("answers null for a root with no project in it that holds a script", () => {
    expect(workspaceFrom(new Map())).toBeNull();
    expect(workspaceFrom(root({ empty: {}, meshes: { "drawer.stl": "binary" } }))).toBeNull();
  });

  it("reads each directory as a project, by name, opened on the first at its entry", () => {
    const space = workspaceFrom(
      root({
        b: { "b.py": "x = 2\n" },
        a: { "a.py": "x = 1\n", [BENCH]: '[project]\nentry = "a.py"\n\n[values]\nunits_x = 4\n' },
        left: {},
      }),
    );
    expect(space?.projects.map((one) => one.name)).toEqual(["a", "b"]);
    expect(space?.current).toBe("a");
    expect(space?.script).toBe("a.py");
    expect(space?.projects[0]?.overrides).toEqual({ units_x: 4 });
    expect(space?.projects[1]).toEqual(project("b", "x = 2\n"));
  });

  it("runs the entry bench.toml names, and every script in the directory is held", () => {
    const space = workspaceFrom(
      root({ cabinet: { "main.py": "m", "parts.py": "p", [BENCH]: '[project]\nentry = "parts.py"\n' } }),
    );
    expect(space?.projects[0]?.entry).toBe("parts.py");
    expect(space?.script).toBe("parts.py");
    expect(space?.projects[0]?.scripts).toEqual({ "main.py": "m", "parts.py": "p" });
  });

  it("opens an older bench.toml with no [project] table on the script named for the directory", () => {
    const space = workspaceFrom(
      root({ cabinet: { "cabinet.py": "c", "zz.py": "z", [BENCH]: "[values]\nw = 3\n" } }),
    );
    expect(space?.projects[0]?.entry).toBe("cabinet.py");
    expect(space?.projects[0]?.overrides).toEqual({ w: 3 });
  });

  it("falls back from an entry that is not there, to the first script by name", () => {
    const space = workspaceFrom(root({ shelf: { "b.py": "b", "a.py": "a", [BENCH]: '[project]\nentry = "gone.py"\n' } }));
    expect(space?.projects[0]?.entry).toBe("a.py");
  });

  it("reads decision-3's <script>.toml when there is no bench.toml, and bench.toml when both are there", () => {
    const legacy = workspaceFrom(root({ cabinet: { "cabinet.py": "c", "cabinet.toml": "[values]\nw = 3\n" } }));
    expect(legacy?.projects[0]?.overrides).toEqual({ w: 3 });
    const both = workspaceFrom(
      root({ cabinet: { "cabinet.py": "c", "cabinet.toml": "[values]\nw = 3\n", [BENCH]: "[values]\nw = 9\n" } }),
    );
    expect(both?.projects[0]?.overrides).toEqual({ w: 9 });
  });

  it("keeps what bench.toml holds that it does not read, and writes it back unchanged", () => {
    const text = [
      'note = "from a later bench"',
      "[project]",
      'entry = "cabinet.py"',
      'modules = ["parts.py"]',
      "",
      "[values]",
      "w = 3",
      "",
      "[[measured]]",
      'name = "wall"',
      "value = 2.41",
    ].join("\n");
    const space = workspaceFrom(root({ cabinet: { "cabinet.py": "c", [BENCH]: text } }));
    if (space === null) throw new Error("the project did not open");
    const turned = { ...space, projects: space.projects.map((one) => ({ ...one, overrides: { w: 4 } })) };
    const [write] = writesFor(space, turned);
    expect(write?.file).toBe(BENCH);
    expect(write?.text).toContain('note = "from a later bench"\n[project]\nentry = "cabinet.py"\nmodules = ["parts.py"]\n');
    expect(write?.text).toContain("[values]\nw = 4\n");
    expect(write?.text).toContain('[[measured]]\nname = "wall"\nvalue = 2.41\n');
  });

  it("opens a project whose bench.toml cannot be read on its script's defaults", () => {
    const space = workspaceFrom(root({ cabinet: { "cabinet.py": "c", [BENCH]: "[values]\nw = [1, 2]\n" } }));
    expect(space?.projects[0]).toEqual(project("cabinet", "c"));
  });

  it("round-trips through filesFor: reading what was written gives back what was written", () => {
    const space = two(project("a", "x = 1\n", { units_x: 4 }, { file: "a.stl", origin: "low" }), project("b", "y"));
    const layout: Record<string, Record<string, string>> = {};
    for (const w of filesFor(space)) layout[w.project] = { ...layout[w.project], [w.file]: w.text };
    expect(workspaceFrom(root(layout))).toEqual(space);
  });
});
