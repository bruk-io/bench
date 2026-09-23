import { describe, expect, it } from "vitest";

import { EXPIRY_MS, type Leases, heldAgainst, holderProblem, labelled, leased, pruned, renewEvery } from "./lease";

const DESK = { id: "desk-0123456789abcdef", label: "Chrome on a Mac", address: "127.0.0.1" };
const TABLET = { id: "tablet-0123456789abcdef", label: "Safari on an iPad", address: "192.168.1.20" };
const NONE: Leases = new Map();

describe("leased", () => {
  it("takes a lease nobody holds, and tells the taker it is theirs", () => {
    const { leases, standing } = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS);
    expect(standing).toEqual({
      project: "cabinet",
      yours: true,
      holder: null,
      expiryMs: EXPIRY_MS,
      renewMs: renewEvery(EXPIRY_MS),
    });
    expect(leases.get("cabinet")).toMatchObject({ id: DESK.id, sinceMs: 1000, heardMs: 1000 });
  });

  it("tells a second client whose it is - never the holder's id - and changes nothing", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const { leases, standing } = leased(first, "cabinet", "take", TABLET, 6000, EXPIRY_MS);
    expect(leases).toBe(first);
    expect(standing.yours).toBe(false);
    expect(standing.holder).toEqual({ label: DESK.label, address: DESK.address, forMs: 5000, heardAgoMs: 5000 });
    expect(JSON.stringify(standing)).not.toContain(DESK.id);
  });

  it("renews a lease its holder takes again, keeping when it was first taken", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const again = leased(first, "cabinet", "take", DESK, 16_000, EXPIRY_MS).leases;
    expect(again.get("cabinet")).toMatchObject({ sinceMs: 1000, heardMs: 16_000 });
  });

  it("lets a lease whose holder stopped renewing lapse, and the next client take it", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const late = 1000 + EXPIRY_MS;
    expect(pruned(first, late - 1, EXPIRY_MS).size).toBe(1);
    expect(pruned(first, late, EXPIRY_MS).size).toBe(0);
    const { standing } = leased(first, "cabinet", "take", TABLET, late, EXPIRY_MS);
    expect(standing.yours).toBe(true);
  });

  it("takes over a live lease when asked to, and the old holder is told whose it is now", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const taken = leased(first, "cabinet", "take-over", TABLET, 2000, EXPIRY_MS);
    expect(taken.standing.yours).toBe(true);
    const told = leased(taken.leases, "cabinet", "take", DESK, 3000, EXPIRY_MS).standing;
    expect(told.yours).toBe(false);
    expect(told.holder?.label).toBe(TABLET.label);
  });

  it("lets go only of a lease the asker holds", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    expect(leased(first, "cabinet", "release", TABLET, 2000, EXPIRY_MS).leases.size).toBe(1);
    expect(leased(first, "cabinet", "release", DESK, 2000, EXPIRY_MS).leases.size).toBe(0);
  });

  it("keeps one project's lease apart from another's", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    expect(leased(first, "bracket", "take", TABLET, 2000, EXPIRY_MS).standing.yours).toBe(true);
  });

  it("only looks when asked to look", () => {
    const first = leased(NONE, "cabinet", "look", DESK, 1000, EXPIRY_MS);
    expect(first.leases.size).toBe(0);
    expect(first.standing).toMatchObject({ yours: false, holder: null });
  });

  it("renews four times to a lease, so a lost renewal or two does not lose it", () => {
    expect(renewEvery(EXPIRY_MS)).toBe(15_000);
    expect(renewEvery(4000)).toBe(1000);
  });

  it("extends a lease its holder renews, keeping when it was first taken", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const again = leased(first, "cabinet", "renew", DESK, 16_000, EXPIRY_MS);
    expect(again.leases.get("cabinet")).toMatchObject({ sinceMs: 1000, heardMs: 16_000 });
    expect(again.standing.yours).toBe(true);
  });

  it("never creates a lease with a renew - task-55: a release then a renew leaves it free", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const released = leased(first, "cabinet", "release", DESK, 2000, EXPIRY_MS).leases;
    expect(released.size).toBe(0);
    const { leases, standing } = leased(released, "cabinet", "renew", DESK, 2100, EXPIRY_MS);
    expect(leases.size).toBe(0);
    expect(standing).toEqual({
      project: "cabinet",
      yours: false,
      holder: null,
      expiryMs: EXPIRY_MS,
      renewMs: renewEvery(EXPIRY_MS),
    });
    expect(leased(leases, "cabinet", "take", TABLET, 2200, EXPIRY_MS).standing.yours).toBe(true);
  });

  it("tells a renewal from a client that never held it whose the lease is, and changes nothing", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const { leases, standing } = leased(first, "cabinet", "renew", TABLET, 2000, EXPIRY_MS);
    expect(leases).toBe(first);
    expect(standing.yours).toBe(false);
    expect(standing.holder?.label).toBe(DESK.label);
  });

  it("does not renew a lease that has already lapsed - it is free, not extended", () => {
    const first = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;
    const late = 1000 + EXPIRY_MS;
    const { leases, standing } = leased(first, "cabinet", "renew", DESK, late, EXPIRY_MS);
    expect(leases.size).toBe(0);
    expect(standing).toMatchObject({ yours: false, holder: null });
  });
});

describe("heldAgainst", () => {
  const held = leased(NONE, "cabinet", "take", DESK, 1000, EXPIRY_MS).leases;

  it("lets the holder write, and any client write a project nobody holds", () => {
    expect(heldAgainst(held, "cabinet", DESK.id, 2000, EXPIRY_MS)).toBeNull();
    expect(heldAgainst(held, "bracket", null, 2000, EXPIRY_MS)).toBeNull();
    expect(heldAgainst(held, "bracket", TABLET.id, 2000, EXPIRY_MS)).toBeNull();
  });

  it("refuses anybody else - a holder of nothing included - until the lease lapses", () => {
    expect(heldAgainst(held, "cabinet", TABLET.id, 2000, EXPIRY_MS)?.label).toBe(DESK.label);
    expect(heldAgainst(held, "cabinet", null, 2000, EXPIRY_MS)?.label).toBe(DESK.label);
    expect(heldAgainst(held, "cabinet", TABLET.id, 1000 + EXPIRY_MS, EXPIRY_MS)).toBeNull();
  });
});

describe("what a client says about itself", () => {
  it("is one short line, and something even when it said nothing", () => {
    expect(labelled("Chrome on a Mac")).toBe("Chrome on a Mac");
    expect(labelled("two\nlines")).toBe("twolines");
    expect(labelled("x".repeat(200))).toHaveLength(80);
    expect(labelled(undefined)).toBe("a client that did not say what it is");
    expect(labelled("  ")).toBe("a client that did not say what it is");
  });

  it("names its holder id in a shape a header carries and nobody guesses", () => {
    expect(holderProblem("0123456789abcdef")).toBeNull();
    expect(holderProblem("short")).not.toBeNull();
    expect(holderProblem("0123456789abcdef/../x")).not.toBeNull();
  });
});
