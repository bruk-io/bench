/** Saving things: a file at a time, or everything in one store-only zip.
 *
 * The zip writer is a few dozen lines of the format rather than a dependency: the files a
 * run produces are SVG, DXF and SCAD text, and a laser cutter's software only cares that
 * the archive is well formed, not that it is small.
 *
 * A scene is JSON, so every file in it is a string - but an STL and a 3MF are bytes, carried
 * as base64. `bench.transport.binary` is the one place that says which, and `isBinary` below is
 * its twin: a name that matches is decoded before it is written, here and in the archive, so
 * a slicer gets a mesh and not a wall of letters.
 */

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  return table;
})();

function crc32(bytes: Uint8Array<ArrayBuffer>): number {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc = (CRC_TABLE[(crc ^ byte) & 0xff] ?? 0) ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/** A growable little-endian byte sink. */
class Bytes {
  private parts: Uint8Array<ArrayBuffer>[] = [];
  private size = 0;

  get length(): number {
    return this.size;
  }

  push(chunk: Uint8Array<ArrayBuffer>): void {
    this.parts.push(chunk);
    this.size += chunk.length;
  }

  u16(value: number): void {
    this.push(new Uint8Array([value & 0xff, (value >>> 8) & 0xff]));
  }

  u32(value: number): void {
    this.push(
      new Uint8Array([
        value & 0xff,
        (value >>> 8) & 0xff,
        (value >>> 16) & 0xff,
        (value >>> 24) & 0xff,
      ]),
    );
  }

  done(): Uint8Array<ArrayBuffer> {
    const out = new Uint8Array(this.size);
    let at = 0;
    for (const part of this.parts) {
      out.set(part, at);
      at += part.length;
    }
    return out;
  }
}

const encoder = new TextEncoder();

const BINARY = /\.(?:stl|3mf)$/i;

/** Whether a scene's file of that name is bytes written as base64 - `transport.binary`'s twin. */
export const isBinary = (name: string): boolean => BINARY.test(name);

/** A base64 string as the bytes it stands for. */
function bytes(text: string): Uint8Array<ArrayBuffer> {
  const raw = atob(text);
  const out = new Uint8Array(raw.length);
  for (let at = 0; at < raw.length; at += 1) out[at] = raw.charCodeAt(at);
  return out;
}

/** One file of a scene as the bytes to write, decoded if the name says it is bytes. */
const contentOf = (name: string, text: string): Uint8Array<ArrayBuffer> =>
  isBinary(name) ? bytes(text) : encoder.encode(text);

/** How big the file called `name` really is, in bytes - not how long its string is. */
export const sizeOf = (name: string, text: string): number =>
  isBinary(name) ? bytes(text).length : encoder.encode(text).length;

/** The DOS date and time pair for `when`. */
function stamp(when: Date): { time: number; date: number } {
  const time =
    (Math.floor(when.getSeconds() / 2) & 0x1f) |
    ((when.getMinutes() & 0x3f) << 5) |
    ((when.getHours() & 0x1f) << 11);
  const date =
    (when.getDate() & 0x1f) |
    (((when.getMonth() + 1) & 0x0f) << 5) |
    ((Math.max(when.getFullYear() - 1980, 0) & 0x7f) << 9);
  return { time, date };
}

/** `files` as one uncompressed zip archive. */
export function zip(files: Readonly<Record<string, string>>): Blob {
  const when = stamp(new Date());
  const body = new Bytes();
  const directory = new Bytes();
  let count = 0;

  for (const [name, text] of Object.entries(files)) {
    const nameBytes = encoder.encode(name);
    const data = contentOf(name, text);
    const sum = crc32(data);
    const offset = body.length;

    body.u32(0x04034b50);
    body.u16(20);
    body.u16(0x0800); // names are UTF-8
    body.u16(0); // stored
    body.u16(when.time);
    body.u16(when.date);
    body.u32(sum);
    body.u32(data.length);
    body.u32(data.length);
    body.u16(nameBytes.length);
    body.u16(0);
    body.push(nameBytes);
    body.push(data);

    directory.u32(0x02014b50);
    directory.u16(20);
    directory.u16(20);
    directory.u16(0x0800);
    directory.u16(0);
    directory.u16(when.time);
    directory.u16(when.date);
    directory.u32(sum);
    directory.u32(data.length);
    directory.u32(data.length);
    directory.u16(nameBytes.length);
    directory.u16(0);
    directory.u16(0);
    directory.u16(0);
    directory.u16(0);
    directory.u32(0);
    directory.u32(offset);
    directory.push(nameBytes);
    count += 1;
  }

  const end = new Bytes();
  const table = directory.done();
  end.u32(0x06054b50);
  end.u16(0);
  end.u16(0);
  end.u16(count);
  end.u16(count);
  end.u32(table.length);
  end.u32(body.length);
  end.u16(0);

  return new Blob([body.done(), table, end.done()], { type: "application/zip" });
}

const MIME: Readonly<Record<string, string>> = {
  svg: "image/svg+xml",
  dxf: "application/dxf",
  scad: "text/plain",
  py: "text/x-python",
  json: "application/json",
  stl: "model/stl",
  "3mf": "model/3mf",
};

/** Hand `data` to the browser as a download called `name`.
 *
 * A string whose name says it is bytes - an STL, a 3MF - is base64 and is decoded on the way
 * out; every other string is text and goes as it is, in UTF-8.
 */
export function save(name: string, data: Blob | string): void {
  const extension = name.slice(name.lastIndexOf(".") + 1).toLowerCase();
  const type = MIME[extension] ?? "text/plain";
  const blob =
    typeof data !== "string"
      ? data
      : isBinary(name)
        ? new Blob([bytes(data)], { type })
        : new Blob([data], { type: `${type};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
