/** Component tests: every `*.test.ts` under `src/`, run in a real headless chromium.
 *
 * A custom element is a browser thing - shadow roots, `adoptedStyleSheets`, `:host` - so the
 * components are tested where they run rather than against a simulated DOM that only
 * approximates those. This is its own config, not `vite.config.ts`, because that one bundles
 * the Python sources on start and no component needs them.
 */
import { playwright } from "@vitest/browser-playwright";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    browser: {
      enabled: true,
      headless: true,
      provider: playwright(),
      instances: [{ browser: "chromium" }],
    },
  },
});
