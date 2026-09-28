import { describe, expect, it } from "vitest";

import { MAC_DEFAULT, SLICER_VARIABLE, launch, unlaunched } from "./slicer";

const FILE = "/Users/maker/projects/cabinet/prints/cabinet.3mf";

describe("launch: which slicer, and the command that opens the file in it", () => {
  it("opens Bambu Studio as an application on macOS when the host names no slicer", () => {
    expect(launch({}, "darwin", FILE)).toEqual({
      argv: ["open", "-a", MAC_DEFAULT, FILE],
      slicer: "BambuStudio",
      said: "default",
    });
  });

  it("hands the file to the desktop's own opener anywhere else", () => {
    expect(launch({}, "linux", FILE)).toEqual({
      argv: ["xdg-open", FILE],
      slicer: "the desktop's default for the file",
      said: "default",
    });
  });

  it("takes the slicer the host's environment names over its default", () => {
    expect(launch({ [SLICER_VARIABLE]: "/opt/slicers/prusa-slicer" }, "linux", FILE)).toEqual({
      argv: ["/opt/slicers/prusa-slicer", FILE],
      slicer: "prusa-slicer",
      said: "environment",
    });
    expect(launch({ [SLICER_VARIABLE]: "OrcaSlicer" }, "darwin", FILE)).toEqual({
      argv: ["open", "-a", "OrcaSlicer", FILE],
      slicer: "OrcaSlicer",
      said: "environment",
    });
  });

  it("reads a blank name as no name at all", () => {
    expect(launch({ [SLICER_VARIABLE]: "  " }, "darwin", FILE).said).toBe("default");
  });

  it("runs a path to a program on macOS, and opens a path to an .app as the application", () => {
    const program = "/usr/local/bin/record-argv";
    expect(launch({ [SLICER_VARIABLE]: program }, "darwin", FILE).argv).toEqual([program, FILE]);
    expect(launch({ [SLICER_VARIABLE]: "/Applications/OrcaSlicer.app" }, "darwin", FILE)).toEqual({
      argv: ["open", "-a", "/Applications/OrcaSlicer.app", FILE],
      slicer: "OrcaSlicer",
      said: "environment",
    });
  });

  it("keeps a name with spaces or a shell's punctuation in it one argument, never a command", () => {
    const sly = "Bambu Studio; rm -rf ~";
    const file = "/tmp/a b/$(touch x).3mf";
    expect(launch({ [SLICER_VARIABLE]: sly }, "darwin", file).argv).toEqual(["open", "-a", sly, file]);
    expect(launch({ [SLICER_VARIABLE]: sly }, "linux", file).argv).toEqual([sly, file]);
  });
});

describe("unlaunched: what went wrong, in words to act on", () => {
  it("says plainly that no slicer was found when the default is not installed", () => {
    const chosen = launch({}, "darwin", FILE);
    const said = unlaunched(chosen, { exit: 1, stderr: "Unable to find application named 'BambuStudio'\n" });
    expect(said).toMatch(/^No slicer was found: BambuStudio \(the host's default\) is not installed\./);
    expect(said).toContain(SLICER_VARIABLE);
    expect(said).not.toContain("bench.toml");
  });

  it("names a program that is not there, and who named it", () => {
    const chosen = launch({ [SLICER_VARIABLE]: "/nowhere/slicer" }, "linux", FILE);
    expect(unlaunched(chosen, { code: "ENOENT" })).toMatch(
      /^No slicer was found: \/nowhere\/slicer \(BENCH_SLICER on the host\) is not there\./,
    );
    expect(unlaunched(chosen, { code: "EACCES" })).toContain("is there but cannot be run");
  });

  it("gives a slicer that started and said no its exit status and its first line of complaint", () => {
    const chosen = launch({ [SLICER_VARIABLE]: "/opt/slicer" }, "linux", FILE);
    expect(unlaunched(chosen, { exit: 3, stderr: "cannot read file\nmore\n" })).toMatch(
      /^\/opt\/slicer \(BENCH_SLICER on the host\) would not open the file: \/opt\/slicer exited 3 - cannot read file\./,
    );
  });
});
