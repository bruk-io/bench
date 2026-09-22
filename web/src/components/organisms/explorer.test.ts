import { afterEach, describe, expect, it } from "vitest";

import "./explorer";
import type { BenchExplorer, FileImportDetail, FileNameDetail, FileRenameDetail } from "./explorer";

const KEPT = ["gridfinity_cabinet.py", "shelf.py", "untitled.py"];

type Fields = Partial<Pick<BenchExplorer, "names" | "current">>;

async function mounted(fields: Fields = {}): Promise<BenchExplorer> {
  const explorer = document.createElement("bench-explorer");
  Object.assign(explorer, { names: KEPT, current: "shelf.py", ...fields });
  document.body.append(explorer);
  await explorer.updateComplete;
  return explorer;
}

const inside = <T extends Element = HTMLElement>(
  explorer: BenchExplorer,
  selector: string,
): T | null => explorer.shadowRoot?.querySelector<T>(selector) ?? null;

const files = (explorer: BenchExplorer): HTMLButtonElement[] =>
  Array.from(explorer.shadowRoot?.querySelectorAll<HTMLButtonElement>(".file") ?? []);

async function click(explorer: BenchExplorer, selector: string): Promise<void> {
  const button = inside(explorer, selector);
  if (button === null) throw new Error(`nothing to click at ${selector}`);
  button.click();
  await explorer.updateComplete;
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

describe("bench-explorer, the list", () => {
  it("lists every script kept, and marks the one that is open", async () => {
    const explorer = await mounted();
    expect(files(explorer).map((one) => one.textContent?.trim())).toEqual(KEPT);
    const open = files(explorer).filter((one) => one.getAttribute("aria-current") === "true");
    expect(open.map((one) => one.textContent?.trim())).toEqual(["shelf.py"]);
  });

  it("asks for a file to be opened, and says nothing about the one already open", async () => {
    const explorer = await mounted();
    const detail = caught<FileNameDetail>("file-open", () => {
      files(explorer)[0]?.click();
    });
    expect(detail).toEqual({ name: "gridfinity_cabinet.py" });

    const again = caught<FileNameDetail>("file-open", () => {
      files(explorer)[1]?.click();
    });
    expect(again).toBeNull();
  });

  it("asks for a new file", async () => {
    const explorer = await mounted();
    let asked = false;
    document.addEventListener("file-new", () => (asked = true), { once: true });
    await click(explorer, "#file-new");
    expect(asked).toBe(true);
  });
});

describe("bench-explorer, a project as a whole", () => {
  it("asks for the open project to be duplicated, and to be downloaded", async () => {
    const explorer = await mounted();
    const copy = caught<FileNameDetail>("file-duplicate", () => {
      inside(explorer, "#file-duplicate")?.click();
    });
    expect(copy).toEqual({ name: "shelf.py" });
    const saved = caught<FileNameDetail>("file-download", () => {
      inside(explorer, "#file-download")?.click();
    });
    expect(saved).toEqual({ name: "shelf.py" });
  });

  it("hands up the files picked to open, unread, and nothing for an empty pick", async () => {
    const explorer = await mounted();
    const picker = inside<HTMLInputElement>(explorer, "#file-pick");
    if (picker === null) throw new Error("no picker");
    const picked = new DataTransfer();
    picked.items.add(new File(["from bench import *\n"], "plate.py"));
    picked.items.add(new File(["[values]\nw = 40\n"], "plate.toml"));
    picker.files = picked.files;
    const detail = caught<FileImportDetail>("file-import", () => {
      picker.dispatchEvent(new Event("change"));
    });
    expect(detail?.files.map((file) => file.name)).toEqual(["plate.py", "plate.toml"]);
    // The same files picked again are still an opening, so the input forgets them.
    expect(picker.value).toBe("");

    picker.files = new DataTransfer().files;
    const nothing = caught<FileImportDetail>("file-import", () => {
      picker.dispatchEvent(new Event("change"));
    });
    expect(nothing).toBeNull();
  });
});

describe("bench-explorer, renaming", () => {
  it("says why a name will not do, and will not send it", async () => {
    const explorer = await mounted();
    await click(explorer, "#file-rename");
    const box = inside<HTMLInputElement>(explorer, "#file-name");
    if (box === null) throw new Error("no name box");
    box.value = "gridfinity_cabinet";
    box.dispatchEvent(new Event("input"));
    await explorer.updateComplete;
    expect(inside(explorer, "#file-problem")?.textContent).toContain("already a file");
    expect(inside<HTMLButtonElement>(explorer, "#file-rename-confirm")?.disabled).toBe(true);
  });

  it("sends a good name, with .py supplied", async () => {
    const explorer = await mounted();
    await click(explorer, "#file-rename");
    const box = inside<HTMLInputElement>(explorer, "#file-name");
    if (box === null) throw new Error("no name box");
    box.value = "drawer";
    box.dispatchEvent(new Event("input"));
    await explorer.updateComplete;
    const detail = caught<FileRenameDetail>("file-rename", () => {
      inside<HTMLFormElement>(explorer, "form")?.requestSubmit();
    });
    expect(detail).toEqual({ from: "shelf.py", to: "drawer.py" });
  });

  it("goes back to the list on Escape rather than leaving the container", async () => {
    const explorer = await mounted();
    await click(explorer, "#file-rename");
    inside(explorer, "#file-name")?.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
    await explorer.updateComplete;
    expect(files(explorer)).toHaveLength(3);
  });
});

describe("bench-explorer, deleting", () => {
  it("asks once, in place, before it sends anything", async () => {
    const explorer = await mounted();
    await click(explorer, "#file-delete");
    expect(inside(explorer, "#file-delete-confirm")).not.toBeNull();
    const detail = caught<FileNameDetail>("file-delete", () => {
      inside(explorer, "#file-delete-confirm")?.click();
    });
    expect(detail).toEqual({ name: "shelf.py" });
  });

  it("sends nothing when the asking is cancelled", async () => {
    const explorer = await mounted();
    await click(explorer, "#file-delete");
    let asked = false;
    document.addEventListener("file-delete", () => (asked = true), { once: true });
    const cancel = Array.from(
      explorer.shadowRoot?.querySelectorAll<HTMLButtonElement>("button") ?? [],
    ).find((one) => one.textContent?.trim() === "Cancel");
    cancel?.click();
    await explorer.updateComplete;
    expect(asked).toBe(false);
    expect(files(explorer)).toHaveLength(3);
  });
});
