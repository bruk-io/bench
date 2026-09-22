/** The files a run made, grouped the way a person looks for them.
 *
 * Pure data over a scene's sheets and files: the sheets first, each with a picture of its own
 * drawing and the formats it can be taken in, then what a printer reads, then everything else.
 * Nothing here touches the DOM or saves anything - the panel that lists the rows decides what
 * a click does, and the page is what writes a file.
 */
import { isBinary, sizeOf } from "./downloads";
import type { SheetView } from "./scene";

/** One way to take one file: what the button says, and the file it hands over. */
export interface Download {
  readonly label: string;
  readonly name: string;
  readonly data: string;
}

/** One file, or one sheet, as a row: what it is called, a quiet note on what it is, the ways
 * to take it, and a picture when there is one to show. */
export interface Row {
  readonly name: string;
  readonly meta: string;
  readonly downloads: readonly Download[];
  /** A `data:` URL an `<img>` shows - which also keeps whatever is in the SVG from running. */
  readonly preview?: string;
}

export interface Layout {
  readonly sheets: readonly Row[];
  readonly printed: readonly Row[];
  readonly others: readonly Row[];
}

/** An SVG as the address of an image of it. */
export const pictured = (svg: string): string =>
  `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

const plural = (count: number, one: string): string => (count === 1 ? one : `${one}s`);

/** How big a file really is - an STL's bytes, not its base64. */
const kB = (name: string, data: string): string => `${(sizeOf(name, data) / 1024).toFixed(1)} kB`;

/** A file's format, as its button names it - "SVG", "STL", "3MF" - so every row reads the same
 * way, whether it is a sheet with two formats or a body with one. */
export const format = (name: string): string => {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "Save" : name.slice(dot + 1).toUpperCase();
};

const single = ([name, data]: readonly [string, string]): Row => ({
  name,
  meta: kB(name, data),
  downloads: [{ label: format(name), name, data }],
});

/** The three groups, from the scene's sheets and files. */
export function layout(
  sheets: readonly SheetView[],
  files: Readonly<Record<string, string>>,
): Layout {
  const bySheet = sheets.map((sheet): Row => {
    const svg = `${sheet.name}.svg`;
    const dxf = `${sheet.name}.dxf`;
    const drawn = files[dxf];
    const drawing = files[svg] ?? sheet.svg;
    return {
      name: sheet.name,
      preview: pictured(sheet.preview),
      // Pieces, not parts: a sheet lists every copy it cuts, and the status bar's "14 parts"
      // counts each part once - six drawer sides are one part and six pieces.
      meta: `${sheet.thickness} mm · ${sheet.parts.length} ${plural(sheet.parts.length, "piece")}`,
      downloads: [
        { label: format(svg), name: svg, data: drawing },
        ...(drawn === undefined ? [] : [{ label: format(dxf), name: dxf, data: drawn }]),
      ],
    };
  });
  const listed = new Set(bySheet.flatMap((row) => row.downloads.map((one) => one.name)));
  const rest = Object.entries(files).filter(([name]) => !listed.has(name));
  return {
    sheets: bySheet,
    printed: rest.filter(([name]) => isBinary(name)).map(single),
    others: rest.filter(([name]) => !isBinary(name)).map(single),
  };
}
