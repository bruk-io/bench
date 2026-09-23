import { describe, expect, it } from "vitest";

import { clientLabel, identity } from "./leasing";
import { holderProblem } from "./lease";
import { KEYS } from "./storage";

const MAC_CHROME =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";
const MAC_SAFARI =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";
const IPHONE_CHROME =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/140.0 Mobile/15E148 Safari/604.1";
const WINDOWS_EDGE =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0";
const LINUX_FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0";

describe("clientLabel", () => {
  it("says which browser on which kind of machine, the way a person would", () => {
    expect(clientLabel(MAC_CHROME, 0)).toBe("Chrome on a Mac");
    expect(clientLabel(MAC_SAFARI, 0)).toBe("Safari on a Mac");
    expect(clientLabel(IPHONE_CHROME, 5)).toBe("Chrome on an iPhone");
    expect(clientLabel(WINDOWS_EDGE, 0)).toBe("Edge on Windows");
    expect(clientLabel(LINUX_FIREFOX, 0)).toBe("Firefox on Linux");
  });

  it("tells an iPad asking for the desktop site from a Mac by its touch points", () => {
    expect(clientLabel(MAC_SAFARI, 5)).toBe("Safari on an iPad");
  });

  it("says less rather than guessing at what it does not know", () => {
    expect(clientLabel("curl/8.0", 0)).toBe("A browser");
  });
});

describe("identity", () => {
  it("is one id for this tab, kept across a reload, in the shape the route takes", () => {
    window.sessionStorage.removeItem(KEYS.holder);
    const first = identity();
    expect(holderProblem(first.id)).toBeNull();
    expect(identity().id).toBe(first.id);
    expect(window.sessionStorage.getItem(KEYS.holder)).toBe(first.id);
    expect(window.localStorage.getItem(KEYS.holder)).toBeNull();
  });
});
