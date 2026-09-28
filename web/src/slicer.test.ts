import { describe, expect, it } from "vitest";

import { MAC_DEFAULT, SLICER_VARIABLE, launch, unlaunched } from "./slicer";

const FILE = "/Users/maker/projects/cabinet/prints/cabinet.3mf";

describe("launch: which slicer, and the command that opens the file in it", () => {
  it("opens Bambu Studio as an application on macOS when nobody named a slicer", () => {
    expect(launch(null, {}, "darwin", FILE)).toEqual({
      argv: ["open", "-a", MAC_DEFAULT, FILE],
      slicer: "BambuStudio",
      said: "default",
    });
  });

  it("hands the file to the desktop's own opener anywhere else", () => {
    expect(launch(null, {}, "linux", FILE)).toEqual({
      argv: ["xdg-open", FILE],
      slicer: "the desktop's default for the file",
      said: "default",
    });
  });

  it("takes the host's environment over its default, and the project over both", () => {
    const env = { [SLICER_VARIABLE]: "/opt/slicers/prusa-slicer" };
    expect(launch(null, env, "linux", FILE)).toEqual({
      argv: ["/opt/slicers/prusa-slicer", FILE],
      slicer: "/opt/slicers/prusa-slicer",
      said: "environment",
    });
    expect(launch("OrcaSlicer", env, "darwin", FILE)).toEqual({
      argv: ["open", "-a", "OrcaSlicer", FILE],
      slicer: "OrcaSlicer",
      said: "project",
    });
  });

  it("reads a blank name, anywhere, as no name at all", () => {
    expect(launch("  ", { [SLICER_VARIABLE]: "" }, "darwin", FILE).said).toBe("default");
  });

  it("runs a path to a program on macOS, and opens a path to an .app as the application", () => {
    expect(launch("/usr/local/bin/record-argv", {}, "darwin", FILE).argv).toEqual(["/usr/local/bin/record-argv", FILE]);
    expect(launch("/Applications/OrcaSlicer.app", {}, "darwin", FILE).argv).toEqual([
      "open",
      "-a",
      "/Applications/OrcaSlicer.app",
      FILE,
    ]);
  });

  it("keeps a name with spaces or a shell's punctuation in it one argument, never a command", () => {
    const sly = "Bambu Studio; rm -rf ~";
    const file = "/tmp/a b/$(touch x).3mf";
    expect(launch(sly, {}, "darwin", file).argv).toEqual(["open", "-a", sly, file]);
    expect(launch(sly, {}, "linux", file).argv).toEqual([sly, file]);
  });
});

describe("unlaunched: what went wrong, in words to act on", () => {
  it("says plainly that no slicer was found when the default is not installed", () => {
    const chosen = launch(null, {}, "darwin", FILE);
    const said = unlaunched(chosen, { exit: 1, stderr: "Unable to find application named 'BambuStudio'\n" });
    expect(said).toMatch(/^No slicer was found: BambuStudio \(the host's default\) is not installed\./);
    expect(said).toContain("[print] slicer");
    expect(said).toContain(SLICER_VARIABLE);
  });

  it("names a program that is not there, and who named it", () => {
    const chosen = launch(null, { [SLICER_VARIABLE]: "/nowhere/slicer" }, "linux", FILE);
    expect(unlaunched(chosen, { code: "ENOENT" })).toMatch(
      /^No slicer was found: \/nowhere\/slicer \(BENCH_SLICER on the host\) is not there\./,
    );
    expect(unlaunched(chosen, { code: "EACCES" })).toContain("is there but cannot be run");
  });

  it("gives a slicer that started and said no its exit status and its first line of complaint", () => {
    const chosen = launch("/opt/slicer", {}, "linux", FILE);
    expect(unlaunched(chosen, { exit: 3, stderr: "cannot read file\nmore\n" })).toMatch(
      /^\/opt\/slicer \(the project's bench.toml \(\[print\] slicer\)\) would not open the file: \/opt\/slicer exited 3 - cannot read file\./,
    );
  });
});
