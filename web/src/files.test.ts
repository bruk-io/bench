import { describe, expect, it } from "vitest";

import {
  UNTITLED,
  type Project,
  type Workspace,
  adopted,
  created,
  deleted,
  document,
  duplicated,
  freeName,
  merged,
  nameProblem,
  normalized,
  openSource,
  opened,
  pristine,
  project,
  renamed,
  restored,
  scriptsOf,
  serialized,
  single,
  switched,
  withExample,
  withOverrides,
  withScript,
  withSource,
} from "./files";
import { NOTHING_KEPT, keptOf } from "./values";

const STARTER = "from bench import *\n";

/** Three projects of one script each, the middle one open. */
const three = (): Workspace => ({
  projects: [project("a", "a"), project("b", "b", { w: 3 }), project("c", "c")],
  current: "b",
  script: "b.py",
});

/** A project of two scripts: `main.py` its entry, `parts.py` beside it. */
const pair = (): Project => ({
  name: "cabinet",
  entry: "main.py",
  scripts: { "main.py": "import parts", "parts.py": "WIDTH = 3" },
  overrides: { w: 3 },
  reference: null,
  kept: NOTHING_KEPT,
});

const namesOf = (space: Workspace): string[] => space.projects.map((one) => one.name);

describe("files, the open project", () => {
  it("edits only the open project's open script and overrides", () => {
    const space = withOverrides(withSource(three(), "b2"), { w: 9 });
    expect(opened(space)).toEqual(project("b", "b2", { w: 9 }));
    expect(space.projects[0]).toEqual(three().projects[0]);
  });

  it("switches to a project by name, at its entry, and ignores a name that is not there", () => {
    const space = { projects: [...three().projects, pair()], current: "b", script: "b.py" };
    expect(switched(space, "c").current).toBe("c");
    expect(switched(space, "cabinet").script).toBe("main.py");
    expect(switched(space, "nope")).toEqual(space);
  });
});

describe("files, a project of several scripts", () => {
  const space = (): Workspace => ({ projects: [pair()], current: "cabinet", script: "main.py" });

  it("opens its entry, and the script a person opens is the one a run gets", () => {
    expect(openSource(space())).toBe("import parts");
    const other = withScript(space(), "parts.py");
    expect(other.script).toBe("parts.py");
    expect(openSource(other)).toBe("WIDTH = 3");
    expect(opened(other).entry).toBe("main.py");
  });

  it("does not open a script the project does not hold", () => {
    expect(withScript(space(), "nope.py")).toEqual(space());
  });

  it("edits the open script and leaves the others alone", () => {
    const edited = withSource(withScript(space(), "parts.py"), "WIDTH = 4");
    expect(opened(edited).scripts).toEqual({ "main.py": "import parts", "parts.py": "WIDTH = 4" });
  });

  it("lists its scripts entry first, the rest by name", () => {
    const more = { ...pair(), scripts: { ...pair().scripts, "a.py": "" } };
    expect(scriptsOf(more)).toEqual(["main.py", "a.py", "parts.py"]);
  });
});

describe("files, names", () => {
  it("reads a typed name as a project name, without a .py a person put on the end", () => {
    expect(normalized("  shelf ")).toBe("shelf");
    expect(normalized("shelf.py")).toBe("shelf");
    expect(normalized("   ")).toBe("");
  });

  it("finds a free name next to a taken one", () => {
    expect(freeName([], UNTITLED)).toBe(UNTITLED);
    expect(freeName([UNTITLED], UNTITLED)).toBe("untitled-2");
    expect(freeName([UNTITLED, "untitled-2"], UNTITLED)).toBe("untitled-3");
  });

  it("says why a name will not do - the route's own rule for a directory, as well as taken", () => {
    const taken = ["a", "b"];
    expect(nameProblem(taken, "a", "")).toBe("a project needs a name");
    expect(nameProblem(taken, "a", ".py")).toBe("a project needs a name");
    expect(nameProblem(taken, "a", "x/y")).toBe("a project name cannot have a slash in it");
    expect(nameProblem(taken, "a", ".git")).toBe("a project name cannot start with a dot");
    expect(nameProblem(taken, "a", "a\u0000b")).not.toBeNull();
    expect(nameProblem(taken, "a", "b")).toBe("there is already a project called b");
    expect(nameProblem(taken, "a", "a")).toBeNull();
    expect(nameProblem(taken, "a", "shelf")).toBeNull();
  });
});

describe("files, making, renaming and deleting", () => {
  it("opens a new project under a free name, its one script named for it", () => {
    const space = created(created(single(UNTITLED, "x"), UNTITLED, STARTER), UNTITLED, STARTER);
    expect(namesOf(space)).toEqual([UNTITLED, "untitled-2", "untitled-3"]);
    expect(opened(space)).toEqual(project("untitled-3", STARTER));
    expect(opened(space).entry).toBe("untitled-3.py");
    expect(space.script).toBe("untitled-3.py");
  });

  it("opens a project from disk with the values that came with it", () => {
    const space = created(three(), "plate", "p", { w: 40 });
    expect(opened(space)).toEqual(project("plate", "p", { w: 40 }));
  });

  it("opens a project from disk with its [reference] table, and what else its file held", () => {
    const reference = { file: "obj_2.stl", origin: "low" };
    const kept = keptOf("[[measured]]\nname = 'wall'\n");
    const space = created(three(), "foot", "p", { w: 40 }, reference, kept);
    expect(opened(space)).toEqual(project("foot", "p", { w: 40 }, reference, kept));
  });

  it("renames a project, keeping it open when it was, its values and its entry with it", () => {
    const space = renamed(three(), "b", "shelf");
    expect(namesOf(space)).toEqual(["a", "shelf", "c"]);
    expect(opened(space)).toEqual(project("shelf", "b", { w: 3 }));
    expect(space.script).toBe("shelf.py");
  });

  it("renames only the directory when its entry is not named for it", () => {
    const space = renamed({ projects: [pair()], current: "cabinet", script: "parts.py" }, "cabinet", "shelf");
    expect(opened(space)).toEqual({ ...pair(), name: "shelf" });
    expect(space.script).toBe("parts.py");
  });

  it("duplicates a project beside itself, scripts and values both, under a free name", () => {
    const space = duplicated(three(), "b");
    expect(namesOf(space)).toEqual(["a", "b", "b-2", "c"]);
    expect(opened(space)).toEqual(project("b-2", "b", { w: 3 }));
    expect(namesOf(duplicated(space, "b"))).toEqual(["a", "b", "b-3", "b-2", "c"]);
    expect(duplicated(three(), "nope")).toEqual(three());
  });

  it("refuses a rename onto a name already taken", () => {
    expect(renamed(three(), "b", "a")).toEqual(three());
    expect(renamed(three(), "b", "a.py")).toEqual(three());
  });

  it("deleting the open project opens its neighbour, at its entry", () => {
    expect(deleted(three(), "b", STARTER).current).toBe("c");
    expect(deleted(three(), "b", STARTER).script).toBe("c.py");
    const last = { ...three(), current: "c", script: "c.py" };
    expect(deleted(last, "c", STARTER).current).toBe("b");
  });

  it("deleting another project leaves the open one open", () => {
    const space = deleted(three(), "a", STARTER);
    expect(namesOf(space)).toEqual(["b", "c"]);
    expect(space.current).toBe("b");
  });

  it("deleting the last project leaves a new untitled one", () => {
    expect(deleted(single("only", "x"), "only", STARTER)).toEqual(single(UNTITLED, STARTER));
  });
});

describe("files, examples", () => {
  it("opens an example as a project of its own, named for it, so the open script is not lost", () => {
    const space = withExample(three(), "hinge.py", "hinge");
    expect(namesOf(space)).toEqual(["a", "b", "c", "hinge"]);
    expect(opened(space).entry).toBe("hinge.py");
    expect(openSource(space)).toBe("hinge");
  });

  it("opens an untouched copy again rather than making another", () => {
    const once = withExample(three(), "hinge.py", "hinge");
    const twice = withExample(switched(once, "a"), "hinge.py", "hinge");
    expect(namesOf(twice)).toEqual(namesOf(once));
    expect(twice.current).toBe("hinge");
  });

  it("makes a second copy when the first has been changed", () => {
    const edited = withSource(withExample(three(), "hinge.py", "hinge"), "hinge, edited");
    const space = withExample(edited, "hinge.py", "hinge");
    expect(space.current).toBe("hinge-2");
    expect(openSource(space)).toBe("hinge");
  });

  it("knows an example nobody touched from work somebody did", () => {
    const examples = { "hinge.py": "hinge" };
    expect(pristine(project("hinge", "hinge"), examples)).toBe(true);
    expect(pristine(project("hinge", "hinge, edited"), examples)).toBe(false);
    expect(pristine(project("hinge", "hinge", { w: 1 }), examples)).toBe(false);
    expect(pristine(project("mine", "mine"), examples)).toBe(false);
  });
});

describe("files, adopting a browser's projects onto the host", () => {
  it("puts them beside what the host holds, each under a free name, and opens the first", () => {
    const host = { projects: [project("a", "host a")], current: "a", script: "a.py" };
    const space = merged(host, [project("a", "mine"), project("z", "z")]);
    expect(space === null ? [] : namesOf(space)).toEqual(["a", "a-2", "z"]);
    expect(space?.current).toBe("a-2");
    expect(space === null ? null : openSource(space)).toBe("mine");
    expect(space?.projects[0]).toEqual(project("a", "host a"));
  });

  it("is only what it adopts on a host with nothing on it, and nothing new with nothing to adopt", () => {
    expect(merged(null, [project("z", "z")])).toEqual(single("z", "z"));
    expect(merged(null, [])).toBeNull();
    expect(merged(three(), [])).toEqual(three());
  });
});

describe("files, storage", () => {
  it("reads back what it wrote", () => {
    expect(restored(serialized(three()))).toEqual(three());
    const two = { projects: [pair()], current: "cabinet", script: "parts.py" };
    expect(restored(serialized(two))).toEqual(two);
  });

  it("keeps each project's document as the TOML it is, [project] naming the entry", () => {
    const kept = JSON.parse(serialized(three())) as { projects: { values: string }[] };
    expect(kept.projects[1]?.values).toContain("[values]\nw = 3\n");
    expect(kept.projects[1]?.values).toContain('[project]\nentry = "b.py"\n');
    expect(kept.projects[0]).not.toHaveProperty("overrides");
  });

  it("reads a record kept before a project was a directory as a one-script directory", () => {
    const said = JSON.stringify({
      files: [
        { name: "old.py", source: "o", overrides: { w: 3, bad: [1] } },
        { name: "bare.py", source: "b" },
        { name: "broken.py", source: "k", values: "[values]\nw = [1, 2]\n" },
      ],
      current: "bare.py",
    });
    expect(restored(said)).toEqual({
      projects: [project("old", "o", { w: 3 }), project("bare", "b"), project("broken", "k")],
      current: "bare",
      script: "bare.py",
    });
  });

  it("reads a record's [reference] table too, and the tables it does not know", () => {
    const values = '[reference]\nfile = "obj_2.stl"\norigin = [606.795, -116.868, 0.0]\n\n[[measured]]\nx = 1\n';
    const said = JSON.stringify({ files: [{ name: "foot.py", source: "f", values }], current: "foot.py" });
    const reference = { file: "obj_2.stl", origin: [606.795, -116.868, 0.0] as const };
    expect(restored(said)).toEqual({
      projects: [project("foot", "f", {}, reference, keptOf(values))],
      current: "foot",
      script: "foot.py",
    });
  });

  it("has nothing to restore from nothing, or from what is not a workspace", () => {
    expect(restored(null)).toBeNull();
    expect(restored("{not json")).toBeNull();
    expect(restored(JSON.stringify({ files: [], current: "a.py" }))).toBeNull();
    expect(restored(JSON.stringify({ projects: [], current: "a" }))).toBeNull();
    expect(restored(JSON.stringify(["a.py"]))).toBeNull();
  });

  it("drops the records that are not projects, and opens the first when the open one went", () => {
    const said = JSON.stringify({
      files: [
        { name: "a.py", source: 1 },
        { name: "b.py", source: "b", values: "[values]\nw = 3\n" },
        { name: "b.py", source: "again" },
        { name: "x/y.py", source: "y" },
        { name: "c", source: "no extension" },
        "junk",
      ],
      current: "a.py",
    });
    expect(restored(said)).toEqual({ projects: [project("b", "b", { w: 3 })], current: "b", script: "b.py" });
  });

  it("falls back to a script named for the directory, or the first, when the entry is not there", () => {
    const said = JSON.stringify({
      projects: [
        { name: "p", entry: "gone.py", scripts: { "z.py": "z", "p.py": "p" }, values: "" },
        { name: "q", scripts: { "y.py": "y", "x.py": "x" } },
        { name: "r", scripts: { "notes.txt": "no scripts" } },
      ],
      current: "q",
      script: "nope.py",
    });
    const space = restored(said);
    expect(space?.projects.map((one) => [one.name, one.entry])).toEqual([
      ["p", "p.py"],
      ["q", "x.py"],
    ]);
    expect(space?.current).toBe("q");
    expect(space?.script).toBe("x.py");
  });

  it("adopts the one script a browser kept before there were files", () => {
    const examples = { "hinge.py": "hinge", "bin.py": "bin" };
    expect(adopted("mine", { w: 2 }, examples, "bin.py")).toEqual(single(UNTITLED, "mine", { w: 2 }));
    expect(adopted("hinge", {}, examples, "bin.py")).toEqual(single("hinge", "hinge"));
    expect(adopted(null, {}, examples, "bin.py")).toEqual(single("bin", "bin"));
  });
});

describe("files, document", () => {
  it("carries a project's [reference] table into the document it shows and hands over", () => {
    const text = document(project("foot", "f", { draft: 8.4 }, { file: "obj_2.stl", origin: "low" }));
    expect(text).toContain("[values]\ndraft = 8.4\n");
    expect(text).toContain('[reference]\nfile = "obj_2.stl"\norigin = "low"\n');
  });

  it("leaves out [reference] entirely for a project with none", () => {
    expect(document(project("plate", "p", { w: 3 }))).not.toContain("[reference]");
  });

  it("still orders [values] by a run's declaration order when it is given", () => {
    const text = document(project("cabinet", "c", { kerf: 0.25, units_x: 6 }), ["units_x", "kerf"]);
    expect(text.indexOf("units_x")).toBeLessThan(text.indexOf("kerf"));
  });

  it("names the entry in [project], whatever the document it was opened with said", () => {
    const one = { ...pair(), kept: keptOf('[project]\nentry = "old.py"\nmodules = ["parts.py"]\n') };
    const text = document(one);
    expect(text).toContain('[project]\nentry = "main.py"\nmodules = ["parts.py"]\n');
    expect(text).not.toContain("old.py");
  });
});
