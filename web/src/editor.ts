/** The script editor: CodeMirror 6 with Python, an error line, and refs.
 *
 * It knows three things the rest of the app asks of it: the text, where the error is, and
 * whether the cursor sits inside a string that names a ref.
 */
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { python } from "@codemirror/lang-python";
import {
  HighlightStyle,
  bracketMatching,
  indentOnInput,
  indentUnit,
  syntaxHighlighting,
  syntaxTree,
} from "@codemirror/language";
import { highlightSelectionMatches, searchKeymap } from "@codemirror/search";
import { Compartment, EditorState, Prec, StateEffect, StateField } from "@codemirror/state";
import {
  Decoration,
  EditorView,
  GutterMarker,
  drawSelection,
  gutter,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
  rectangularSelection,
} from "@codemirror/view";
import { tags } from "@lezer/highlight";

export interface EditorHooks {
  /** The document changed (every keystroke); the caller debounces. */
  onChange(): void;
  /** The cursor moved into, or out of, a string naming a known ref. */
  onCursorRef(ref: string | null): void;
  /** Ctrl/Cmd+Enter. */
  onRun(): void;
  /** Ctrl/Cmd+I. */
  onInsert(): void;
}

export interface Editor {
  text(): string;
  replace(text: string): void;
  /** Put `ref("…")` at the cursor and leave the cursor after it. */
  insertRef(ref: string): void;
  /** Mark one line as the failing one, or clear the mark with `null`. */
  showError(line: number | null): void;
  /** The refs a cursor-in-string is matched against. */
  knowRefs(refs: readonly string[]): void;
  /** Put the cursor on one line and scroll it into view - what a finding's line number does. */
  goTo(line: number): void;
  focus(): void;
}

const setErrorLine = StateEffect.define<number | null>();

const errorLine = StateField.define<number | null>({
  create: () => null,
  update(value, transaction) {
    let line = value;
    for (const effect of transaction.effects) {
      if (effect.is(setErrorLine)) line = effect.value;
    }
    return line;
  },
});

const errorDecorations = EditorView.decorations.compute([errorLine, "doc"], (state) => {
  const line = state.field(errorLine);
  if (line === null || line < 1 || line > state.doc.lines) return Decoration.none;
  const info = state.doc.line(line);
  return Decoration.set([Decoration.line({ class: "cm-errorLine" }).range(info.from)]);
});

class ErrorMarker extends GutterMarker {
  override toDOM(): Node {
    return document.createTextNode("●");
  }
}

const MARKER = new ErrorMarker();

const errorGutter = gutter({
  class: "cm-errorGutter",
  lineMarker: (view, line) => {
    const failing = view.state.field(errorLine);
    if (failing === null) return null;
    return view.state.doc.lineAt(line.from).number === failing ? MARKER : null;
  },
  // Without this the gutter would not know the failing line moved.
  lineMarkerChange: (update) =>
    update.transactions.some((transaction) =>
      transaction.effects.some((effect) => effect.is(setErrorLine)),
    ),
  initialSpacer: () => MARKER,
});

const highlight = HighlightStyle.define([
  { tag: tags.keyword, color: "var(--syn-keyword)" },
  { tag: [tags.controlKeyword, tags.moduleKeyword], color: "var(--syn-keyword)" },
  { tag: [tags.string, tags.special(tags.string)], color: "var(--syn-string)" },
  { tag: [tags.number, tags.bool, tags.null], color: "var(--syn-number)" },
  { tag: [tags.comment, tags.lineComment, tags.blockComment], color: "var(--syn-comment)" },
  { tag: [tags.definition(tags.variableName), tags.function(tags.variableName)], color: "var(--syn-def)" },
  { tag: [tags.className, tags.typeName], color: "var(--syn-def)" },
  { tag: tags.operator, color: "var(--fg-dim)" },
  { tag: [tags.meta, tags.standard(tags.variableName)], color: "var(--syn-builtin)" },
]);

const look = (dark: boolean) =>
  EditorView.theme(
    {
      "&": { backgroundColor: "var(--panel)", color: "var(--fg)", height: "100%" },
      ".cm-content": { caretColor: "var(--fg)", padding: "8px 0" },
      ".cm-gutters": {
        backgroundColor: "var(--panel)",
        color: "var(--fg-dim)",
        borderRight: "1px solid var(--line)",
      },
      ".cm-activeLine": { backgroundColor: "color-mix(in srgb, var(--accent) 6%, transparent)" },
      ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--fg)" },
      ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--fg)" },
      "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
        backgroundColor: "var(--accent-soft)",
      },
      ".cm-selectionMatch": { backgroundColor: "color-mix(in srgb, var(--accent) 18%, transparent)" },
      ".cm-errorGutter": { width: "10px", paddingLeft: "2px" },
      ".cm-scroller": { overflow: "auto" },
    },
    { dark },
  );

/** Strip a Python string literal down to what it says. */
function literal(text: string): string | null {
  const match = /^[rbufRBUF]{0,2}('''|"""|'|")([\s\S]*)\1$/.exec(text);
  return match ? (match[2] ?? null) : null;
}

/** The string literal the cursor is inside, or `null`. */
function cursorString(view: EditorView): string | null {
  const head = view.state.selection.main.head;
  const tree = syntaxTree(view.state);
  for (const side of [-1, 1] as const) {
    let node = tree.resolveInner(head, side);
    while (node.parent !== null && !node.name.endsWith("String")) node = node.parent;
    if (node.name.endsWith("String")) {
      const said = literal(view.state.sliceDoc(node.from, node.to));
      if (said !== null) return said;
    }
  }
  return null;
}

export function mount(parent: HTMLElement, doc: string, hooks: EditorHooks): Editor {
  const appearance = new Compartment();
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  let known = new Set<string>();
  let announced: string | null = null;

  const announce = (view: EditorView): void => {
    const said = cursorString(view);
    const found = said !== null && known.has(said) ? said : null;
    if (found === announced) return;
    announced = found;
    hooks.onCursorRef(found);
  };

  const view = new EditorView({
    parent,
    state: EditorState.create({
      doc,
      extensions: [
        lineNumbers(),
        errorGutter,
        highlightActiveLine(),
        highlightActiveLineGutter(),
        history(),
        drawSelection(),
        rectangularSelection(),
        indentOnInput(),
        bracketMatching(),
        highlightSelectionMatches(),
        indentUnit.of("    "),
        python(),
        syntaxHighlighting(highlight),
        errorLine,
        errorDecorations,
        Prec.high(
          keymap.of([
            {
              key: "Mod-Enter",
              preventDefault: true,
              run: () => {
                hooks.onRun();
                return true;
              },
            },
            {
              // Mod-I, not Mod-Shift-I: that one opens DevTools everywhere but headless.
              key: "Mod-i",
              preventDefault: true,
              run: () => {
                hooks.onInsert();
                return true;
              },
            },
          ]),
        ),
        keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap, indentWithTab]),
        EditorView.lineWrapping,
        appearance.of(look(dark.matches)),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) hooks.onChange();
          if (update.docChanged || update.selectionSet) announce(update.view);
        }),
      ],
    }),
  });

  dark.addEventListener("change", (event) => {
    view.dispatch({ effects: appearance.reconfigure(look(event.matches)) });
  });

  return {
    text: () => view.state.doc.toString(),
    replace(text) {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: text },
        selection: { anchor: 0 },
      });
    },
    insertRef(ref) {
      const insert = `ref(${JSON.stringify(ref)})`;
      const at = view.state.selection.main;
      view.dispatch({
        changes: { from: at.from, to: at.to, insert },
        selection: { anchor: at.from + insert.length },
        scrollIntoView: true,
      });
      view.focus();
    },
    showError(line) {
      view.dispatch({ effects: setErrorLine.of(line) });
    },
    knowRefs(refs) {
      known = new Set(refs);
      announce(view);
    },
    goTo(line) {
      // A line a run named can be past the end of a document edited since; clamp rather than
      // throw, because being taken to the last line beats being taken nowhere.
      const at = view.state.doc.line(Math.min(Math.max(line, 1), view.state.doc.lines));
      view.dispatch({ selection: { anchor: at.from }, scrollIntoView: true });
      view.focus();
    },
    focus: () => view.focus(),
  };
}
