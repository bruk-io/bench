import { describe, expect, it } from "vitest";

import {
  UNTITLED,
  type Workspace,
  adopted,
  created,
  deleted,
  document,
  duplicated,
  freeName,
  nameProblem,
  normalized,
  opened,
  renamed,
  restored,
  serialized,
  single,
  switched,
  withExample,
  withOverrides,
  withSource,
} from "./files";

const STARTER = "from bench import *\n";

/** Three files, the middle one open. */
const three = (): Workspace => ({
  files: [
    { name: "a.py", source: "a", overrides: {}, reference: null },
    { name: "b.py", source: "b", overrides: { w: 3 }, reference: null },
    { name: "c.py", source: "c", overrides: {}, reference: null },
  ],
  current: "b.py",
});

const namesOf = (space: Workspace): string[] => space.files.map((file) => file.name);

describe("files, the open file", () => {
  it("edits only the open file's script and overrides", () => {
    const space = withOverrides(withSource(three(), "b2"), { w: 9 });
    expect(opened(space)).toEqual({ name: "b.py", source: "b2", overrides: { w: 9 }, reference: null });
    expect(space.files[0]).toEqual(three().files[0]);
  });

  it("switches to a file by name, and ignores a name that is not there", () => {
    expect(switched(three(), "c.py").current).toBe("c.py");
    expect(switched(three(), "nope.py")).toEqual(three());
  });
});

describe("files, names", () => {
  it("reads a typed name as a file name", () => {
    expect(normalized("  shelf ")).toBe("shelf.py");
    expect(normalized("shelf.py")).toBe("shelf.py");
    expect(normalized("   ")).toBe("");
  });

  it("finds a free name next to a taken one", () => {
    expect(freeName([], UNTITLED)).toBe(UNTITLED);
    expect(freeName([UNTITLED], UNTITLED)).toBe("untitled-2.py");
    expect(freeName([UNTITLED, "untitled-2.py"], UNTITLED)).toBe("untitled-3.py");
  });

  it("says why a name will not do", () => {
    const taken = ["a.py", "b.py"];
    expect(nameProblem(taken, "a.py", "")).toBe("a file needs a name");
    expect(nameProblem(taken, "a.py", ".py")).toBe("a file needs a name");
    expect(nameProblem(taken, "a.py", "x/y")).toBe("a file name cannot have a slash in it");
    expect(nameProblem(taken, "a.py", "b")).toBe("there is already a file called b.py");
    expect(nameProblem(taken, "a.py", "a")).toBeNull();
    expect(nameProblem(taken, "a.py", "shelf")).toBeNull();
  });
});

describe("files, making, renaming and deleting", () => {
  it("opens a new file under a free name, with no overrides", () => {
    const space = created(created(single(UNTITLED, "x"), UNTITLED, STARTER), UNTITLED, STARTER);
    expect(namesOf(space)).toEqual([UNTITLED, "untitled-2.py", "untitled-3.py"]);
    expect(opened(space)).toEqual({
      name: "untitled-3.py",
      source: STARTER,
      overrides: {},
      reference: null,
    });
  });

  it("opens a file from disk with the values that came with it", () => {
    const space = created(three(), "plate.py", "p", { w: 40 });
    expect(opened(space)).toEqual({
      name: "plate.py",
      source: "p",
      overrides: { w: 40 },
      reference: null,
    });
  });

  it("opens a file from disk with its [reference] table too", () => {
    const reference = { file: "obj_2.stl", origin: "low" };
    const space = created(three(), "foot.py", "p", { w: 40 }, reference);
    expect(opened(space)).toEqual({
      name: "foot.py",
      source: "p",
      overrides: { w: 40 },
      reference,
    });
  });

  it("renames a file, keeping it open when it was, and its values with it", () => {
    const space = renamed(three(), "b.py", "shelf");
    expect(namesOf(space)).toEqual(["a.py", "shelf.py", "c.py"]);
    expect(opened(space)).toEqual({
      name: "shelf.py",
      source: "b",
      overrides: { w: 3 },
      reference: null,
    });
  });

  it("duplicates a file beside itself, script and values both, under a free name", () => {
    const space = duplicated(three(), "b.py");
    expect(namesOf(space)).toEqual(["a.py", "b.py", "b-2.py", "c.py"]);
    expect(opened(space)).toEqual({
      name: "b-2.py",
      source: "b",
      overrides: { w: 3 },
      reference: null,
    });
    expect(namesOf(duplicated(space, "b.py"))).toEqual(["a.py", "b.py", "b-3.py", "b-2.py", "c.py"]);
    expect(duplicated(three(), "nope.py")).toEqual(three());
  });

  it("refuses a rename onto a name already taken", () => {
    expect(renamed(three(), "b.py", "a.py")).toEqual(three());
  });

  it("deleting the open file opens its neighbour", () => {
    expect(deleted(three(), "b.py", STARTER).current).toBe("c.py");
    const last = { ...three(), current: "c.py" };
    expect(deleted(last, "c.py", STARTER).current).toBe("b.py");
  });

  it("deleting another file leaves the open one open", () => {
    const space = deleted(three(), "a.py", STARTER);
    expect(namesOf(space)).toEqual(["b.py", "c.py"]);
    expect(space.current).toBe("b.py");
  });

  it("deleting the last file leaves a new untitled one", () => {
    expect(deleted(single("only.py", "x"), "only.py", STARTER)).toEqual(single(UNTITLED, STARTER));
  });
});

describe("files, examples", () => {
  it("opens an example as a file of its own, so the open script is not lost", () => {
    const space = withExample(three(), "hinge.py", "hinge");
    expect(namesOf(space)).toEqual(["a.py", "b.py", "c.py", "hinge.py"]);
    expect(opened(space).source).toBe("hinge");
  });

  it("opens an untouched copy again rather than making another", () => {
    const once = withExample(three(), "hinge.py", "hinge");
    const twice = withExample(switched(once, "a.py"), "hinge.py", "hinge");
    expect(namesOf(twice)).toEqual(namesOf(once));
    expect(twice.current).toBe("hinge.py");
  });

  it("makes a second copy when the first has been changed", () => {
    const edited = withSource(withExample(three(), "hinge.py", "hinge"), "hinge, edited");
    const space = withExample(edited, "hinge.py", "hinge");
    expect(space.current).toBe("hinge-2.py");
    expect(opened(space).source).toBe("hinge");
  });
});

describe("files, storage", () => {
  it("reads back what it wrote", () => {
    expect(restored(serialized(three()))).toEqual(three());
  });

  it("keeps each file's values as the TOML document tools/build.py reads", () => {
    const kept = JSON.parse(serialized(three())) as { files: { values: string }[] };
    expect(kept.files[1]?.values).toContain("[values]\nw = 3\n");
    expect(kept.files[1]?.values).toContain("b.py");
    expect(kept.files[0]).not.toHaveProperty("overrides");
  });

  it("reads a record kept before the values were a document, and one with no values at all", () => {
    const said = JSON.stringify({
      files: [
        { name: "old.py", source: "o", overrides: { w: 3, bad: [1] } },
        { name: "bare.py", source: "b" },
        { name: "broken.py", source: "k", values: "[values]\nw = [1, 2]\n" },
      ],
      current: "bare.py",
    });
    expect(restored(said)).toEqual({
      files: [
        { name: "old.py", source: "o", overrides: { w: 3 }, reference: null },
        { name: "bare.py", source: "b", overrides: {}, reference: null },
        { name: "broken.py", source: "k", overrides: {}, reference: null },
      ],
      current: "bare.py",
    });
  });

  it("reads a record's [reference] table too, kept the way it was", () => {
    const said = JSON.stringify({
      files: [
        {
          name: "foot.py",
          source: "f",
          values: '[reference]\nfile = "obj_2.stl"\norigin = [606.795, -116.868, 0.0]\n',
        },
      ],
      current: "foot.py",
    });
    expect(restored(said)).toEqual({
      files: [
        {
          name: "foot.py",
          source: "f",
          overrides: {},
          reference: { file: "obj_2.stl", origin: [606.795, -116.868, 0.0] },
        },
      ],
      current: "foot.py",
    });
  });

  it("has nothing to restore from nothing, or from what is not a workspace", () => {
    expect(restored(null)).toBeNull();
    expect(restored("{not json")).toBeNull();
    expect(restored(JSON.stringify({ files: [], current: "a.py" }))).toBeNull();
    expect(restored(JSON.stringify(["a.py"]))).toBeNull();
  });

  it("drops the files that are not files, and opens the first when the open one went", () => {
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
    expect(restored(said)).toEqual({
      files: [{ name: "b.py", source: "b", overrides: { w: 3 }, reference: null }],
      current: "b.py",
    });
  });

  it("adopts the one script a browser kept before there were files", () => {
    const examples = { "hinge.py": "hinge", "bin.py": "bin" };
    expect(adopted("mine", { w: 2 }, examples, "bin.py")).toEqual(single(UNTITLED, "mine", { w: 2 }));
    expect(adopted("hinge", {}, examples, "bin.py")).toEqual(single("hinge.py", "hinge"));
    expect(adopted(null, {}, examples, "bin.py")).toEqual(single("bin.py", "bin"));
  });
});

describe("files, document", () => {
  it("carries a project's [reference] table into the document it shows and hands over", () => {
    const project = {
      name: "foot.py",
      source: "f",
      overrides: { draft: 8.4 },
      reference: { file: "obj_2.stl", origin: "low" as const },
    };
    const text = document(project);
    expect(text).toContain("[values]\ndraft = 8.4\n");
    expect(text).toContain('[reference]\nfile = "obj_2.stl"\norigin = "low"\n');
  });

  it("leaves out [reference] entirely for a project with none", () => {
    const project = { name: "plate.py", source: "p", overrides: { w: 3 }, reference: null };
    expect(document(project)).not.toContain("[reference]");
  });

  it("still orders [values] by a run's declaration order when it is given", () => {
    const project = { name: "cabinet.py", source: "c", overrides: { kerf: 0.25, units_x: 6 }, reference: null };
    const text = document(project, ["units_x", "kerf"]);
    expect(text.indexOf("units_x")).toBeLessThan(text.indexOf("kerf"));
  });
});
