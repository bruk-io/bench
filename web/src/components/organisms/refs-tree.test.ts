import { afterEach, describe, expect, it } from "vitest";

import "./refs-tree";
import {
  type BenchRefsTree,
  type ReferencePickDetail,
  type RefPickDetail,
  treeOf,
} from "./refs-tree";

const CABINET = [
  "cabinet-side-left",
  "drawer-front-1",
  "drawer-front-1/pull",
  "drawer-front-1/label",
  "drawer-back-3",
];

type Fields = Partial<
  Pick<BenchRefsTree, "refs" | "selected" | "flagged" | "references" | "selectedReference">
>;

async function mounted(fields: Fields = {}): Promise<BenchRefsTree> {
  const tree = document.createElement("bench-refs-tree");
  Object.assign(tree, fields);
  document.body.append(tree);
  await tree.updateComplete;
  return tree;
}

async function given(tree: BenchRefsTree, fields: Fields): Promise<void> {
  Object.assign(tree, fields);
  await tree.updateComplete;
}

const rows = (tree: BenchRefsTree): HTMLElement[] =>
  Array.from(tree.shadowRoot?.querySelectorAll<HTMLElement>(".row") ?? []);

/** Every row on screen, by the ref it stands for. */
const shown = (tree: BenchRefsTree): string[] =>
  rows(tree).map((row) => row.dataset["ref"] ?? "");

const rowFor = (tree: BenchRefsTree, ref: string): HTMLElement | undefined =>
  rows(tree).find((row) => row.dataset["ref"] === ref);

/** The row for `ref`, insisting it is on screen.
 *
 * `rowFor` answers `undefined` for a row inside a shut branch, and `undefined?.querySelector`
 * is `undefined` rather than an error - so an assertion about a row nobody drew quietly tests
 * nothing at all. Branches start shut now, which makes that trap easy to walk into; this
 * shuts it by failing where the row is missing rather than where the assertion is.
 */
function drawn(tree: BenchRefsTree, ref: string): HTMLElement {
  const row = rowFor(tree, ref);
  if (row === undefined) {
    throw new Error(`no row for ${ref}; on screen: ${shown(tree).join(", ")}`);
  }
  return row;
}

/** Open a branch the way a person does, by its twisty. */
async function open(tree: BenchRefsTree, ref: string): Promise<void> {
  drawn(tree, ref).querySelector<HTMLElement>(".twist")?.click();
  await tree.updateComplete;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("treeOf", () => {
  it("nests on the separator rather than listing whole paths", () => {
    const [front] = treeOf(["drawer-front-1", "drawer-front-1/pull"]);
    expect(front?.name).toBe("drawer-front-1");
    expect(front?.children.map((one) => one.name)).toEqual(["pull"]);
  });

  it("gives a path whose parent nothing named a node of its own", () => {
    const [root] = treeOf(["a/b"]);
    expect(root?.path).toBe("a");
    expect(root?.children[0]?.path).toBe("a/b");
  });

  it("puts a name under one node however many of its children are named", () => {
    const [front] = treeOf(["drawer-front-1/pull", "drawer-front-1/label"]);
    expect(front?.children.map((one) => one.name)).toEqual(["label", "pull"]);
  });
});

describe("bench-refs-tree, what it draws", () => {
  it("says so rather than drawing an empty tree", async () => {
    const tree = await mounted();
    expect(tree.shadowRoot?.querySelector(".empty")).not.toBeNull();
  });

  it("draws the parts and not their faces, because a run names hundreds of faces", async () => {
    const tree = await mounted({ refs: CABINET });
    expect(shown(tree)).toContain("cabinet-side-left");
    expect(shown(tree)).toContain("drawer-front-1");
    expect(shown(tree)).not.toContain("drawer-front-1/pull");
  });

  it("opens a branch on its twisty without selecting it", async () => {
    const tree = await mounted({ refs: CABINET });
    rowFor(tree, "drawer-front-1")?.querySelector<HTMLElement>(".twist")?.click();
    await tree.updateComplete;
    expect(shown(tree)).toContain("drawer-front-1/pull");
    expect(rowFor(tree, "drawer-front-1")?.getAttribute("aria-current")).toBe("false");
  });

  it("shuts it again on the same twisty", async () => {
    const tree = await mounted({ refs: CABINET });
    const twist = () => rowFor(tree, "drawer-front-1")?.querySelector<HTMLElement>(".twist")?.click();
    twist();
    await tree.updateComplete;
    twist();
    await tree.updateComplete;
    expect(shown(tree)).not.toContain("drawer-front-1/pull");
  });
});

describe("bench-refs-tree, at the scale a run actually reaches", () => {
  /** What `gridfinity_cabinet.py` actually names: fourteen parts, and every finger of every
   * joint a wall with a name of its own - 770 refs in all, measured off a real run rather
   * than imagined. The shape here is that run's: fourteen parts, 54 faces each. */
  const PARTS = [
    "cabinet-back",
    "cabinet-side-left",
    "cabinet-side-right",
    "cabinet-top-bottom",
    "drawer-back",
    "drawer-bottom",
    "drawer-front-1",
    "drawer-front-2",
    "drawer-front-3",
    "drawer-front-4",
    "drawer-front-5",
    "drawer-front-6",
    "drawer-side",
    "runner",
  ];
  const AT_SCALE = [
    ...PARTS,
    ...PARTS.flatMap((part) => [
      `${part}/bottom`,
      ...Array.from({ length: 53 }, (_, at) => `${part}/bottom-${String(at + 1)}`),
    ]),
  ];

  it("opens as one row per part however many faces hang under them", async () => {
    const tree = await mounted({ refs: AT_SCALE });
    // The real run's numbers: 770 names, of which fourteen are parts.
    expect(AT_SCALE).toHaveLength(770);
    expect(shown(tree)).toEqual(PARTS);
  });

  it("counts a part's faces rather than filing them alphabetically", async () => {
    const tree = await mounted({ refs: AT_SCALE });
    rowFor(tree, "cabinet-back")?.querySelector<HTMLElement>(".twist")?.click();
    await tree.updateComplete;

    const faces = shown(tree).filter((ref) => ref.startsWith("cabinet-back/"));
    expect(faces.indexOf("cabinet-back/bottom-2")).toBeLessThan(
      faces.indexOf("cabinet-back/bottom-10"),
    );
    expect(faces.at(-1)).toBe("cabinet-back/bottom-53");
  });

  it("still reveals a face picked on the drawing, out of a shut branch", async () => {
    const tree = await mounted({ refs: AT_SCALE });
    expect(shown(tree)).not.toContain("cabinet-back/bottom-12");

    await given(tree, { selected: "cabinet-back/bottom-12" });
    expect(shown(tree)).toContain("cabinet-back/bottom-12");
    expect(rowFor(tree, "cabinet-back/bottom-12")?.getAttribute("aria-current")).toBe("true");
  });
});

describe("bench-refs-tree, the round-trip with the view", () => {
  it("sends a picked ref up and never selects itself", async () => {
    const tree = await mounted({ refs: CABINET });
    let picked: string | null = null;
    tree.addEventListener("ref-pick", (event) => {
      picked = (event as CustomEvent<RefPickDetail>).detail.ref;
    });
    await open(tree, "drawer-front-1");
    drawn(tree, "drawer-front-1/pull").click();
    await tree.updateComplete;
    expect(picked).toBe("drawer-front-1/pull");
    // The page owns the selection: the tree marks nothing until it is told to.
    expect(drawn(tree, "drawer-front-1/pull").getAttribute("aria-current")).toBe("false");
  });

  it("marks the row the page says is selected", async () => {
    const tree = await mounted({ refs: CABINET, selected: "drawer-front-1/pull" });
    expect(rowFor(tree, "drawer-front-1/pull")?.getAttribute("aria-current")).toBe("true");
  });

  it("opens whatever is shut above a ref selected on the drawing", async () => {
    const tree = await mounted({ refs: CABINET });
    expect(shown(tree)).not.toContain("drawer-front-1/pull");

    await given(tree, { selected: "drawer-front-1/pull" });
    expect(shown(tree)).toContain("drawer-front-1/pull");
    expect(rowFor(tree, "drawer-front-1/pull")?.getAttribute("aria-current")).toBe("true");
  });

  it("leaves a branch it opened for a selection open when the selection moves on", async () => {
    const tree = await mounted({ refs: CABINET, selected: "drawer-front-1/pull" });
    await given(tree, { selected: "cabinet-side-left" });
    expect(shown(tree)).toContain("drawer-front-1/pull");
  });

  it("marks nothing when the newest run no longer names what was selected", async () => {
    /* Half of "a ref the newest run no longer names stops being selected rather than
     * pointing at nothing". The dropping itself is the viewer's - it sees the new scene,
     * finds the chosen ref gone and tells the page, which sets this back to null. What the
     * tree owes is the other half: a name it was told about that its refs no longer hold
     * marks no row, rather than leaving a stale row lit. */
    const tree = await mounted({ refs: CABINET, selected: "drawer-front-1/pull" });
    expect(rowFor(tree, "drawer-front-1/pull")?.getAttribute("aria-current")).toBe("true");

    await given(tree, { refs: ["cabinet-side-left", "runner"] });

    expect(shown(tree)).toEqual(["cabinet-side-left", "runner"]);
    expect(rows(tree).filter((row) => row.getAttribute("aria-current") === "true")).toEqual([]);
  });

  it("puts the mark down when the page says nothing is selected", async () => {
    const tree = await mounted({ refs: CABINET, selected: "cabinet-side-left" });
    expect(drawn(tree, "cabinet-side-left").getAttribute("aria-current")).toBe("true");

    await given(tree, { selected: null });

    expect(rows(tree).filter((row) => row.getAttribute("aria-current") === "true")).toEqual([]);
  });
});

describe("bench-refs-tree, what a check reported", () => {
  it("marks the row a finding is about", async () => {
    const tree = await mounted({ refs: CABINET, flagged: ["drawer-back-3"] });
    expect(rowFor(tree, "drawer-back-3")?.querySelector(".flag")).not.toBeNull();
    expect(rowFor(tree, "cabinet-side-left")?.querySelector(".flag")).toBeNull();
  });

  it("marks the rows above it too, so a shut branch still shows it", async () => {
    const tree = await mounted({ refs: CABINET, flagged: ["drawer-front-1/pull"] });
    // The whole point of marking a parent: the face it is about is not on screen.
    expect(shown(tree)).not.toContain("drawer-front-1/pull");
    expect(drawn(tree, "drawer-front-1").querySelector(".flag")).not.toBeNull();
  });

  it("marks only what a finding is about once the branch is opened", async () => {
    const tree = await mounted({ refs: CABINET, flagged: ["drawer-front-1/pull"] });
    await open(tree, "drawer-front-1");
    expect(drawn(tree, "drawer-front-1/pull").querySelector(".flag")).not.toBeNull();
    expect(drawn(tree, "drawer-front-1/label").querySelector(".flag")).toBeNull();
  });
});

/** The rows in the References group, by the file each stands for. */
const references = (tree: BenchRefsTree): string[] =>
  Array.from(tree.shadowRoot?.querySelectorAll<HTMLElement>(".row.reference") ?? []).map(
    (row) => row.dataset["reference"] ?? "",
  );

const referenceRow = (tree: BenchRefsTree, file: string): HTMLElement => {
  const row = Array.from(
    tree.shadowRoot?.querySelectorAll<HTMLElement>(".row.reference") ?? [],
  ).find((one) => one.dataset["reference"] === file);
  if (row === undefined) {
    throw new Error(`no reference row for ${file}; on screen: ${references(tree).join(", ")}`);
  }
  return row;
};

const BRACKET = "bracket.stl";

describe("bench-refs-tree, the bodies somebody else made", () => {
  it("lists a dropped body in a group of its own", async () => {
    const tree = await mounted({ refs: CABINET, references: [BRACKET] });
    expect(references(tree)).toEqual([BRACKET]);
  });

  it("keeps them out of the run's own tree, which is what refs means", async () => {
    const tree = await mounted({ refs: CABINET, references: [BRACKET] });
    // `refs` says it holds what the newest run named, and a dropped body was named by no run.
    expect(shown(tree)).not.toContain(BRACKET);
    expect(tree.refs).toEqual(CABINET);
  });

  it("gives a dropped body one row and nothing under it", async () => {
    // decision-8: an imported mesh names nothing under it. decision-7: no survey indexing.
    const tree = await mounted({ references: [BRACKET] });
    const row = referenceRow(tree, BRACKET);
    expect(row.getAttribute("aria-expanded")).toBeNull();
    expect(row.querySelector('.twist[data-leaf="true"]')).not.toBeNull();
  });

  it("shows the group with a body dropped before anything has run", async () => {
    const tree = await mounted({ refs: [], references: [BRACKET] });
    expect(references(tree)).toEqual([BRACKET]);
  });

  it("still says the run named nothing, because it did not", async () => {
    const tree = await mounted({ refs: [], references: [BRACKET] });
    expect(tree.shadowRoot?.querySelector(".empty")?.textContent).toContain("named nothing");
  });

  it("says nothing at all when there is neither a run nor a body", async () => {
    const tree = await mounted();
    expect(references(tree)).toEqual([]);
    expect(tree.shadowRoot?.querySelector(".empty")).not.toBeNull();
  });

  it("sends the file up on a click and never selects itself", async () => {
    const tree = await mounted({ references: [BRACKET] });
    const seen: string[] = [];
    tree.addEventListener("reference-pick", (event: CustomEvent<ReferencePickDetail>) => {
      seen.push(event.detail.file);
    });
    referenceRow(tree, BRACKET).click();
    await tree.updateComplete;
    expect(seen).toEqual([BRACKET]);
    // The page owns the selection, exactly as it does for a ref.
    expect(tree.selectedReference).toBeNull();
  });

  it("marks the one the page says is selected", async () => {
    const tree = await mounted({ references: [BRACKET], selectedReference: BRACKET });
    expect(referenceRow(tree, BRACKET).getAttribute("aria-current")).toBe("true");
  });

  it("does not mark a ref row when a body is what is selected", async () => {
    const tree = await mounted({
      refs: CABINET,
      references: [BRACKET],
      selectedReference: BRACKET,
      selected: null,
    });
    expect(rowFor(tree, "cabinet-side-left")?.getAttribute("aria-current")).toBe("false");
  });

  it("answers the keyboard the way a ref row does", async () => {
    const tree = await mounted({ references: [BRACKET] });
    const seen: string[] = [];
    tree.addEventListener("reference-pick", (event: CustomEvent<ReferencePickDetail>) => {
      seen.push(event.detail.file);
    });
    referenceRow(tree, BRACKET).dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true }),
    );
    await tree.updateComplete;
    expect(seen).toEqual([BRACKET]);
  });
});
