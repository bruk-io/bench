import { afterEach, describe, expect, it } from "vitest";

import "./lease-chip";
import { readOnlyWords } from "../../status";
import type { BenchLeaseChip } from "./lease-chip";

const DESK = { label: "Chrome on a Mac", address: "192.168.1.10", forMs: 300_000, heardAgoMs: 4000 };

async function mounted(lost = false): Promise<BenchLeaseChip> {
  const chip = document.createElement("bench-lease-chip");
  chip.words = readOnlyWords("cabinet", DESK, lost);
  chip.lost = lost;
  document.body.append(chip);
  await chip.updateComplete;
  return chip;
}

const inside = <T extends HTMLElement = HTMLElement>(chip: BenchLeaseChip, selector: string): T | null =>
  chip.shadowRoot?.querySelector<T>(selector) ?? null;

const isOpen = (chip: BenchLeaseChip): boolean =>
  inside(chip, "#lease-badge")?.getAttribute("aria-expanded") === "true" && inside(chip, "#lease-pop")?.hidden === false;

async function click(chip: BenchLeaseChip, selector: string): Promise<void> {
  inside(chip, selector)?.click();
  await chip.updateComplete;
}

afterEach(() => {
  document.body.replaceChildren();
});

describe("bench-lease-chip", () => {
  it("is a short chip, shut, until it is opened", async () => {
    const chip = await mounted();
    expect(chip.hidden).toBe(false);
    expect(inside(chip, "#lease-badge")?.textContent?.trim()).toBe("read-only · held elsewhere");
    expect(isOpen(chip)).toBe(false);
    await click(chip, "#lease-badge");
    expect(isOpen(chip)).toBe(true);
    await click(chip, "#lease-badge");
    expect(isOpen(chip)).toBe(false);
  });

  for (const lost of [false, true]) {
    it(`loses nothing the notice said${lost ? ", when it was taken over" : ""}`, async () => {
      const chip = await mounted(lost);
      const words = readOnlyWords("cabinet", DESK, lost);
      if (!isOpen(chip)) await click(chip, "#lease-badge");
      expect(inside(chip, "#lease-title")?.textContent).toBe(words.title);
      expect(inside(chip, "#lease-why")?.textContent).toBe(words.text);
      expect(inside(chip, "#lease-take")?.textContent?.trim()).toBe("Take over writing…");
      await click(chip, "#lease-take");
      expect(inside(chip, "#lease-confirm-text")?.textContent).toBe(words.confirm);
      // Drawn, not only flagged: the question replaces the button that asked for it.
      expect(inside(chip, "#lease-confirm-text")?.checkVisibility()).toBe(true);
      expect(inside(chip, "#lease-take-yes")?.checkVisibility()).toBe(true);
      expect(inside(chip, "#lease-take")?.checkVisibility()).toBe(false);
      // And it is said to a screen reader as the notice was, without being opened.
      expect(inside(chip, '[role="status"]')?.textContent).toBe(words.title);
    });
  }

  it("opens by itself when this tab's project was taken over, and shows it", async () => {
    const chip = await mounted(true);
    expect(isOpen(chip)).toBe(true);
    expect(chip.hasAttribute("lost")).toBe(true);
    expect(inside(chip, "#lease-badge")?.textContent?.trim()).toBe("read-only · taken over");
  });

  it("stays open, and keeps asking, through a renewal's new words", async () => {
    const chip = await mounted();
    await click(chip, "#lease-badge");
    await click(chip, "#lease-take");
    chip.words = readOnlyWords("cabinet", { ...DESK, forMs: 360_000, heardAgoMs: 1000 }, false);
    await chip.updateComplete;
    expect(isOpen(chip)).toBe(true);
    expect(inside(chip, "#lease-confirm")?.hidden).toBe(false);
    expect(inside(chip, "#lease-why")?.textContent).toContain("held it for 6 minutes");
  });

  it("asks twice, and sends the take-over up only on the second", async () => {
    const chip = await mounted();
    let asked = 0;
    document.body.addEventListener("lease-take-over", () => {
      asked += 1;
    });
    await click(chip, "#lease-badge");
    await click(chip, "#lease-take");
    expect(asked).toBe(0);
    await click(chip, "#lease-take-no");
    expect(inside(chip, "#lease-confirm")?.hidden).toBe(true);
    expect(isOpen(chip)).toBe(true);
    await click(chip, "#lease-take");
    await click(chip, "#lease-take-yes");
    expect(asked).toBe(1);
    expect(isOpen(chip)).toBe(false);
  });

  it("shuts on a click outside it, and forgets it was asking", async () => {
    const chip = await mounted();
    await click(chip, "#lease-badge");
    await click(chip, "#lease-take");
    document.body.click();
    await chip.updateComplete;
    expect(isOpen(chip)).toBe(false);
    await click(chip, "#lease-badge");
    expect(inside(chip, "#lease-confirm")?.hidden).toBe(true);
  });

  it("goes away, shut, once this tab may write", async () => {
    const chip = await mounted();
    await click(chip, "#lease-badge");
    chip.words = null;
    await chip.updateComplete;
    expect(chip.hidden).toBe(true);
    chip.words = readOnlyWords("cabinet", DESK, false);
    await chip.updateComplete;
    expect(chip.hidden).toBe(false);
    expect(isOpen(chip)).toBe(false);
  });
});
