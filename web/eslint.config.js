/** Lint for the web components: Lit's and the custom-elements spec's own rules, so a
 * best practice is something the gate checks rather than something a reviewer remembers.
 *
 * Scoped to `src/components/` - the Lit elements - for now. The rest of `src/` is plain
 * TypeScript that `tsc --strict` already holds to account, and moves under here piece by
 * piece as it becomes components.
 */
import lit from "eslint-plugin-lit";
import wc from "eslint-plugin-wc";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    files: ["src/components/**/*.ts"],
    extends: [
      tseslint.configs.recommended,
      wc.configs["flat/recommended"],
      wc.configs["flat/best-practice"],
      lit.configs["flat/recommended"],
    ],
    rules: {
      // Beyond Lit's recommended set: the ones that turn a quiet re-render bug into an error.
      "lit/no-classfield-shadowing": "error",
      "lit/no-native-attributes": "error",
      "lit/no-property-change-update": "error",
      "lit/no-this-assign-in-render": "error",
      "lit/prefer-nothing": "error",
      "lit/prefer-static-styles": "error",
      "lit/lifecycle-super": "error",
      "lit/no-legacy-imports": "error",
      "lit/attribute-names": "error",
      // Every listener a component adds to something outside itself is taken off again.
      "wc/require-listener-teardown": "error",
      // For a bare HTMLElement, whose base may not have the callback. LitElement always does,
      // and Lit needs `super.connectedCallback()` called plainly - `lit/lifecycle-super`.
      "wc/guard-super-call": "off",
    },
  },
);
