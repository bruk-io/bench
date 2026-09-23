import { afterEach, describe, expect, it } from "vitest";

import "./explorer";
import type { BenchExplorer, ImportDetail, NameDetail, RenameDetail } from "./explorer";

const KEPT = ["gridfinity_cabinet", "shelf", "untitled"];

const FILES = { scripts: ["shelf.py", "parts.py"], entry: "shelf.py", meshes: ["foot.stl"] };

type Fields = Partial<Pick<BenchExplorer, "projects" | "current" | "files" | "front" | "readOnly" | "root">>;

async function mounted(fields: Fields = {}): Promise<BenchExplorer> {
  const explorer = document.createElement("bench-explorer");
  Object.assign(explorer, {
    projects: KEPT,
    current: "shelf",
    files: FILES,
    front: "shelf.py",
    root: "/home/maker/projects",
    ...fields,
  });
  document.body.append(explorer);
  await explorer.updateComplete;
  return explorer;
}

const inside = <T extends Element = HTMLElement>(explorer: BenchExplorer, selector: string): T | null =>
  explorer.shadowRoot?.querySelector<T>(selector) ?? null;

const all = (explorer: BenchExplorer, selector: string): HTMLButtonElement[] =>
  Array.from(explorer.shadowRoot?.querySelectorAll<HTMLButtonElement>(selector) ?? []);

const said = (buttons: HTMLButtonElement[]): string[] =>
  buttons.map((one) => one.querySelector(".name")?.textContent?.trim() ?? one.textContent?.trim() ?? "");

/** The button in `explorer` whose text is `text`, under `within` when given. */
function button(explorer: BenchExplorer, text: string, within = ""): HTMLButtonElement {
  const found = all(explorer, `${within} button`).find((one) => one.textContent?.trim() === text);
  if (found === undefined) throw new Error(`no button reading ${text}`);
  return found;
}

async function clicked(explorer: BenchExplorer, target: HTMLElement | null): Promise<void> {
  if (target === null) throw new Error("nothing to click");
  target.click();
  await explorer.updateComplete;
}

/** Show the actions of the row `name` - its `⋯`. */
async function actions(explorer: BenchExplorer, name: string): Promise<void> {
  await clicked(explorer, inside(explorer, `[aria-label="Actions for ${name}"]`));
}

/** The next `type` event to reach the document, from whatever `act` does. */
function caught<T>(type: string, act: () => void): T | null {
  let detail: T | null = null;
  const listener = (event: Event): void => {
    detail = (event as CustomEvent<T>).detail;
  };
  document.addEventListener(type, listener);
  act();
  document.removeEventListener(type, listener);
  return detail;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-explorer, the tree", () => {
  it("shows the open project's own files, not the other projects", async () => {
    const explorer = await mounted();
    expect(said(all(explorer, ".file"))).toEqual(["bench.toml", "shelf.py", "parts.py", "foot.stl"]);
    expect(inside(explorer, "#meshes-head")?.textContent).toBe("References");
    expect(inside(explorer, "#projects")?.hidden).toBe(true);
    expect(all(explorer, ".file .tag").map((one) => one.textContent)).toEqual(["entry"]);
  });

  it("marks the file in front, and asks for any row - a second script included - to be opened", async () => {
    const explorer = await mounted();
    const front = all(explorer, ".file").filter((one) => one.getAttribute("aria-current") === "true");
    expect(said(front)).toEqual(["shelf.py"]);
    for (const name of ["parts.py", "bench.toml", "foot.stl"]) {
      const detail = caught<NameDetail>("file-open", () => {
        inside(explorer, `.file[data-file="${name}"]`)?.click();
      });
      expect(detail).toEqual({ name });
    }
  });

  it("acts on the row a person chose, not on whatever is open", async () => {
    const explorer = await mounted();
    await actions(explorer, "parts.py");
    const copy = caught<NameDetail>("file-duplicate", () => {
      button(explorer, "Duplicate").click();
    });
    expect(copy).toEqual({ name: "parts.py" });

    await actions(explorer, "parts.py");
    await clicked(explorer, button(explorer, "Rename…"));
    const box = inside<HTMLInputElement>(explorer, "#file-name");
    if (box === null) throw new Error("no name box");
    expect(box.value).toBe("parts.py");
    box.value = "bits";
    box.dispatchEvent(new Event("input"));
    await explorer.updateComplete;
    const renamed = caught<RenameDetail>("file-rename", () => {
      inside<HTMLFormElement>(explorer, "form")?.requestSubmit();
    });
    expect(renamed).toEqual({ from: "parts.py", to: "bits.py" });
  });

  it("says why a script's name will not do", async () => {
    const explorer = await mounted();
    await actions(explorer, "parts.py");
    await clicked(explorer, button(explorer, "Rename…"));
    const box = inside<HTMLInputElement>(explorer, "#file-name");
    if (box === null) throw new Error("no name box");
    box.value = "shelf";
    box.dispatchEvent(new Event("input"));
    await explorer.updateComplete;
    expect(inside(explorer, "#file-problem")?.textContent).toContain("already a shelf.py");
    expect(inside<HTMLButtonElement>(explorer, "#file-rename-confirm")?.disabled).toBe(true);
  });

  it("does not offer to delete a project's last script", async () => {
    const explorer = await mounted({ files: { scripts: ["shelf.py"], entry: "shelf.py", meshes: [] } });
    await actions(explorer, "shelf.py");
    expect(button(explorer, "Delete…").disabled).toBe(true);
  });

  it("offers no action that would write on a project open read-only, and still opens its files", async () => {
    const explorer = await mounted({ readOnly: true });
    expect(said(all(explorer, ".file"))).toEqual(["bench.toml", "shelf.py", "parts.py", "foot.stl"]);
    expect(all(explorer, ".list[aria-label^='Files'] .more")).toHaveLength(0);
    const detail = caught<NameDetail>("file-open", () => {
      inside(explorer, '.file[data-file="parts.py"]')?.click();
    });
    expect(detail).toEqual({ name: "parts.py" });
    // Only duplicating the open project - a project of one's own - is left for it.
    await actions(explorer, "shelf");
    expect(all(explorer, ".acts button").map((one) => one.textContent?.trim())).toEqual(["Duplicate"]);
  });
});

describe("bench-explorer, deleting", () => {
  it("says a project's directory goes into the trash under the root, before sending anything", async () => {
    const explorer = await mounted();
    await actions(explorer, "untitled");
    await clicked(explorer, button(explorer, "Delete…"));
    const what = inside(explorer, "#file-delete-what")?.textContent?.replace(/\s+/g, " ") ?? "";
    expect(what).toContain("Delete untitled?");
    expect(what).toContain("moves on the host into /home/maker/projects/.trash/");
    expect(what).toContain("bench.toml and any meshes");
    expect(explorer.shadowRoot?.textContent).toContain("Nothing is erased");
    const detail = caught<NameDetail>("project-delete", () => {
      inside(explorer, "#file-delete-confirm")?.click();
    });
    expect(detail).toEqual({ name: "untitled" });
  });

  it("says a file goes into the trash too, and names the file", async () => {
    const explorer = await mounted();
    await actions(explorer, "foot.stl");
    await clicked(explorer, button(explorer, "Delete…"));
    const what = inside(explorer, "#file-delete-what")?.textContent?.replace(/\s+/g, " ") ?? "";
    expect(what).toContain("Delete foot.stl from shelf?");
    expect(what).toContain("/home/maker/projects/.trash/");
    const detail = caught<NameDetail>("file-delete", () => {
      inside(explorer, "#file-delete-confirm")?.click();
    });
    expect(detail).toEqual({ name: "foot.stl" });
  });

  it("sends nothing when the asking is cancelled", async () => {
    const explorer = await mounted();
    await actions(explorer, "parts.py");
    await clicked(explorer, button(explorer, "Delete…"));
    let asked = false;
    document.addEventListener("file-delete", () => (asked = true), { once: true });
    await clicked(explorer, button(explorer, "Cancel"));
    expect(asked).toBe(false);
    expect(all(explorer, ".file")).toHaveLength(4);
  });

  it("shows where the page says a delete put what it moved", async () => {
    const explorer = await mounted();
    explorer.said = "parts.py moved to /home/maker/projects/.trash/";
    await explorer.updateComplete;
    expect(inside(explorer, ".said")?.hidden).toBe(false);
    expect(inside(explorer, ".said")?.textContent).toBe("parts.py moved to /home/maker/projects/.trash/");
  });
});

describe("bench-explorer, the switcher", () => {
  it("is one control naming the open project, and opens on the others", async () => {
    const explorer = await mounted();
    expect(inside(explorer, "#project-switcher")?.textContent?.trim()).toBe("shelf");
    await clicked(explorer, inside(explorer, "#project-switcher"));
    expect(inside(explorer, "#projects")?.hidden).toBe(false);
    expect(said(all(explorer, ".project"))).toEqual(KEPT);
    const detail = caught<NameDetail>("project-open", () => {
      all(explorer, ".project")[0]?.click();
    });
    expect(detail).toEqual({ name: "gridfinity_cabinet" });
    await explorer.updateComplete;
    expect(inside(explorer, "#projects")?.hidden).toBe(true);
  });

  it("makes, downloads and renames a project from the switcher", async () => {
    const explorer = await mounted();
    let made = false;
    document.addEventListener("project-new", () => (made = true), { once: true });
    inside(explorer, "#project-new")?.click();
    expect(made).toBe(true);
    const saved = caught<NameDetail>("project-download", () => {
      inside(explorer, "#project-download")?.click();
    });
    expect(saved).toEqual({ name: "shelf" });

    await actions(explorer, "gridfinity_cabinet");
    await clicked(explorer, button(explorer, "Rename…"));
    const box = inside<HTMLInputElement>(explorer, "#file-name");
    if (box === null) throw new Error("no name box");
    box.value = "shelf";
    box.dispatchEvent(new Event("input"));
    await explorer.updateComplete;
    expect(inside(explorer, "#file-problem")?.textContent).toContain("already a project");
    box.value = "drawer.py";
    box.dispatchEvent(new Event("input"));
    await explorer.updateComplete;
    const renamed = caught<RenameDetail>("project-rename", () => {
      inside<HTMLFormElement>(explorer, "form")?.requestSubmit();
    });
    expect(renamed).toEqual({ from: "gridfinity_cabinet", to: "drawer" });
  });

  it("goes back to the list on Escape rather than leaving the container", async () => {
    const explorer = await mounted();
    await actions(explorer, "shelf");
    await clicked(explorer, button(explorer, "Rename…"));
    inside(explorer, "#file-name")?.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await explorer.updateComplete;
    expect(all(explorer, ".file")).toHaveLength(4);
  });

  it("hands up the files picked to open, unread, and nothing for an empty pick", async () => {
    const explorer = await mounted();
    const picker = inside<HTMLInputElement>(explorer, "#project-pick");
    if (picker === null) throw new Error("no picker");
    const picked = new DataTransfer();
    picked.items.add(new File(["from bench import *\n"], "plate.py"));
    picked.items.add(new File(["[values]\nw = 40\n"], "plate.toml"));
    picker.files = picked.files;
    const detail = caught<ImportDetail>("project-import", () => {
      picker.dispatchEvent(new Event("change"));
    });
    expect(detail?.files.map((file) => file.name)).toEqual(["plate.py", "plate.toml"]);
    expect(picker.value).toBe("");

    picker.files = new DataTransfer().files;
    const nothing = caught<ImportDetail>("project-import", () => {
      picker.dispatchEvent(new Event("change"));
    });
    expect(nothing).toBeNull();
  });
});
