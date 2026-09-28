/** Which slicer the host opens a file in, and how to say it could not (task-86).
 *
 * "Open in slicer" hands a file a run made to the program the maker slices with, on the machine
 * the host runs on. What program, and the exact command that opens it, is decided here as data -
 * a name and a fixed list of arguments - and `server/projects.ts` runs that list with `execFile`,
 * never through a shell: the file's path and the slicer's name are each one argument, whatever
 * is in them, so neither can become a second command.
 *
 * **Who says which slicer**, first to last: the project's `bench.toml` (`[print] slicer`, read
 * by `values.ts`), the host's environment (`BENCH_SLICER`, set where the server is started), and
 * otherwise the host's own default - Bambu Studio on macOS, opened the way Finder opens an app
 * (`open -a BambuStudio <file>`), and on anything else whatever the desktop opens the file with
 * (`xdg-open <file>`).
 *
 * **What a name means.** On macOS a bare name, or a path to an `.app`, is an application, and
 * `open -a` finds it the way Spotlight would; anything else - a path to a program - is run
 * with the file as its one argument, which is also what every name means on any other system.
 *
 * No DOM and no `node:` imports, like `route.ts`: the server runs it, and the page's tests do.
 */

/** The environment variable that names the host's slicer when the project names none. */
export const SLICER_VARIABLE = "BENCH_SLICER";

/** The application macOS opens a file in when nobody named one: Bambu Studio, as it installs
 * itself (`/Applications/BambuStudio.app`). */
export const MAC_DEFAULT = "BambuStudio";

/** Who chose the slicer: the project, the host's environment, or nobody. */
export type Said = "project" | "environment" | "default";

/** A slicer, chosen, and the command that opens `file` in it. */
export interface Launch {
  /** The program and its arguments, run as they are - never joined into a shell string. */
  readonly argv: readonly [string, ...string[]];
  /** The slicer as a person would name it. */
  readonly slicer: string;
  readonly said: Said;
}

/** How opening `file` - an absolute path on the host - goes, on `platform` (Node's
 * `process.platform`), given the slicer the project names (`null` for none) and the host's
 * environment. */
export function launch(
  project: string | null,
  env: Readonly<Record<string, string | undefined>>,
  platform: string,
  file: string,
): Launch {
  const fromEnv = env[SLICER_VARIABLE]?.trim() ?? "";
  const named = project?.trim() ?? "";
  const chosen = named !== "" ? named : fromEnv;
  const said: Said = named !== "" ? "project" : fromEnv !== "" ? "environment" : "default";
  if (chosen === "") {
    return platform === "darwin"
      ? { argv: ["open", "-a", MAC_DEFAULT, file], slicer: MAC_DEFAULT, said }
      : { argv: ["xdg-open", file], slicer: "the desktop's default for the file", said };
  }
  const app = platform === "darwin" && (!chosen.includes("/") || /\.app\/?$/i.test(chosen));
  return app
    ? { argv: ["open", "-a", chosen, file], slicer: chosen, said }
    : { argv: [chosen, file], slicer: chosen, said };
}

/** How a launch failed: the program was not there to start (`code`, Node's `ENOENT` or
 * `EACCES`), or it started and said no - its exit status and what it wrote to stderr. */
export type Failure =
  | { readonly code: string }
  | { readonly exit: number | null; readonly stderr: string };

const WHERE: Readonly<Record<Said, string>> = {
  project: "the project's bench.toml ([print] slicer)",
  environment: `${SLICER_VARIABLE} on the host`,
  default: "the host's default",
};

const HOW_TO_NAME =
  `Name the slicer as [print] slicer in the project's bench.toml, or set ${SLICER_VARIABLE} ` +
  "where the server is started.";

/** What went wrong opening a slicer, in words a person can act on: which slicer, who chose it,
 * what happened, and what to set to choose another. */
export function unlaunched(chosen: Launch, failed: Failure): string {
  const command = chosen.argv.slice(0, -1).join(" ");
  if ("code" in failed) {
    const why = failed.code === "EACCES" ? "is there but cannot be run" : "is not there";
    return `No slicer was found: ${chosen.slicer} (${WHERE[chosen.said]}) ${why}. ${HOW_TO_NAME}`;
  }
  const said = failed.stderr.trim().split(/\r?\n/)[0] ?? "";
  // `open -a` names an application it cannot find this way, and exits 1.
  if (chosen.argv[0] === "open" && /unable to find application/i.test(said)) {
    return `No slicer was found: ${chosen.slicer} (${WHERE[chosen.said]}) is not installed. ${HOW_TO_NAME}`;
  }
  const status = failed.exit === null ? "was stopped" : `exited ${String(failed.exit)}`;
  return `${chosen.slicer} (${WHERE[chosen.said]}) would not open the file: ${command} ${status}${
    said === "" ? "" : ` - ${said}`
  }. ${HOW_TO_NAME}`;
}
