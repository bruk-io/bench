# bench/web

The browser app: a Python script on the left, its parts on the right, and the whole of
`bench` running in the page. Vite + TypeScript, no framework, Pyodide in a Web Worker -
with Manifold's WASM build beside it in that same worker, so a printed part is *built* in
the browser and not merely described. Nothing is fetched from a CDN at run time: the Python
runtime, the solid modeller and the `bench` sources are all served by this app.

## Run it

```sh
cd web
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc --noEmit && vite build -> dist/
npm run preview    # serve dist/
```

`predev` and `prebuild` run `npm run generate`, which is three node scripts:

- `scripts/copy-pyodide.mjs` copies `pyodide.mjs`, `pyodide.asm.mjs`, `pyodide.asm.wasm`,
  `python_stdlib.zip` and `pyodide-lock.json` out of `node_modules/pyodide` into
  `public/pyodide/`.
- `scripts/copy-manifold.mjs` does the same for `manifold.js` and `manifold.wasm` out of
  `node_modules/manifold-3d` into `public/manifold/` - 540 kB of solid modeller, loaded by
  URL rather than bundled so the glue and its wasm stay together.
- `scripts/bundle-py.mjs` reads `../src/bench/**/*.py` and `../examples/*.py` and writes
  `src/generated/pysources.ts` (`PY_SOURCES`, keyed like `bench/library/gridfinity.py`, and
  `EXAMPLES`, keyed by filename).

Both copy scripts keep the package's own modification time on what they copy, and `postbuild`
runs `scripts/keep-runtime-times.mjs`, which carries that time on to the copies Vite puts in
`dist/`. The ETag `vite preview` sends is a file's size and modification time, so without
this every build gave thirteen megabytes of unchanged runtime a new ETag and every browser
that had it cached - a tablet on the same network, say - downloaded all of it again. Now the
ETag changes when Pyodide or Manifold does, and a rebuild costs a returning browser nothing.

Both outputs are generated, so both are in `.gitignore`. A `npm run build` regenerates both
at `prebuild`; in `npm run dev` a small plugin in `vite.config.ts` watches `../src/bench` and
`../examples` through `server.watcher` and re-runs `bundle-py.mjs` when a `.py` file there
changes, so editing Python and reloading the page gets the Python you just wrote rather than
whatever `predev` happened to bundle.

**A `git pull` or merge does not regenerate anything on its own** - `pysources.ts` is
gitignored, so a script that lands on `main` sits invisibly on disk until something runs
`npm --prefix web run generate` (or `npm run dev`/`npm run build`, which run it for you) and
the server that serves the page is restarted. A `vite preview` in particular can go on
serving a `dist/` built days earlier and say nothing about it. `bundle-py.mjs` freezes the
newest mtime under `../src/bench` and `../examples` into `pysources.ts` as `GENERATED_AT`;
`bench:staleness`, the other plugin in `vite.config.ts`, answers a small route
(`/__bench/generated-at`) with the same number recomputed live off those two trees, in both
`npm run dev` and `npm run preview`. `src/staleness.ts` compares the two on boot and, if the
bundle is behind, lights up **stale examples** in the status bar rather than letting a two-day-old
example list pass as current - a static deploy has no such route behind it, so the check is
silent there instead of guessing. Pulling `main` and wanting the new examples: run
`npm ci --prefix web && npm --prefix web run generate`, then (re)start `npm run dev` or
rebuild with `npm run build && npm run preview`.

Node: `^20.19 || >=22.12`, as `package.json`'s `engines` says and `.nvmrc` pins (`nvm use`).

## Check it

```sh
npm run typecheck   # tsc --noEmit
npm test            # the components, in a real headless chromium (vitest run)
uv run pytest -m e2e
```

The components under `src/components/` - atoms, molecules, organisms - are Lit elements, and
each is tested beside itself (`*.test.ts`) with Vitest's browser mode, driven by the npm
`playwright`'s chromium (`npx playwright install chromium` once). A custom element is
shadow roots and `:host` and adopted stylesheets, so the tests run where those are real
rather than against a simulated DOM. `uv run tools/check.py` runs both scripts.

The end-to-end checks live with the rest of the suite, in `tests/e2e/` at the repository
root, and are the only layer excluded from a default `uv run pytest` - ask for them by
marker. They drive this app with Playwright (`playwright.sync_api`, chromium): the session
fixtures run `npm run build` when `dist/` is older than anything under `src/` or
`../src/bench`, serve the build with `npx vite preview` on a free port, and open one page.
The checks wait for the first render, change a parameter and check the geometry changed, click
a plate and insert its ref with `Ctrl+I`, check that a cursor inside `ref("drawer-front-1/pull")`
lights up the pull's wall on the drawer front's plate, download a sheet and the zip (and open the zip with `zipfile` to
prove the hand-written writer is honest), and type a syntax error and check the failing line
and gutter are marked. Then, each on a page of its own: an override set while a run is in
flight survives the scene that lands mid-debounce (the run is given a one-second sleep and
timed first, so the window is hit on purpose rather than by luck); `while True: pass` is
stopped by the watchdog, is not replayed by a reload, and the app works afterwards; `Stop`
does the same by hand; the boot says what it is loading; the zoom buttons move the camera;
hovering a plate names its part, its stock and its sheet; and a press the browser cancels
does not land as a click. The light, error, dark, narrow, running, stopped, recovered and
booting views are shot into `e2e/out/`. Then, on one more page, the printed story: the
Gridfinity bin is built by the browser's own Manifold and drawn as a solid, a face of it
answers to a ref on hover and on click, `Ctrl+I` writes that ref into the script, the
`.stl` comes down and is checked byte for byte (80-byte header, a count, 50 bytes a
triangle) and the `.3mf` is opened as a zip, a laser example is drawn as plates, and the
enclosure's wall check is driven to failure and reported with its refs and its line marked
in the editor. The module skips itself, with the reason, if Playwright's Python package,
`node_modules/` or `npx` is missing.

One more page has the modeller taken away from it - every request under `/manifold/` is
refused - and checks that a laser example is completely unaffected and a printed one comes
back named but unbuilt, with the pane saying why and the check that needed a measurement
reading **not checked**.

The kernel itself is checked a layer down rather than here: `tests/adapter/` bundles
`src/modeller.ts` with the app's own esbuild, boots Pyodide under Node beside the real
`manifold.wasm` (`tools/stack.py`), runs the Python kernel against it, and measures what
comes back against arithmetic done by hand. `src/modeller.test.ts` drives the handle table
itself in the component test browser.

## Using it

- **Run**: edits re-run after 300 ms; `Ctrl/Cmd+Enter` runs now. `Stop` is live while a run
  is, and a run that passes 15 s is stopped for you - the worker is killed, a fresh one
  takes its place, and the error panel says so. A script stopped that way is remembered
  (`bench.lastHang`, the source's hash) and is *not* replayed on the next load: the panel
  explains and waits for you to press `Run`.
- **Viewer**: one view of every part. A laser part is the plate it is cut from - its stock's
  thickness, with its engraved lines and lettering on top - and a printed part is its solid;
  they lie in rows on a grid, a row wrapping before it runs past 600 mm. Drag to orbit,
  right-drag to pan, wheel or pinch to dolly; `+`/`−` and `Fit` move the camera, which keeps
  following the work until you move it yourself. The nest is not in the view: each sheet is a
  thumbnail in the `Export` menu, beside its SVG and DXF.
- **Refs**: click any face - a plate's wall or hole, a printed part's face - or an engraved
  line or line of lettering to select it: the bar over the viewer shows its ref, and hovering
  shows it with the part's quantity, stock and sheet under it. A plate's walls answer to the
  refs their cut paths carry in the SVG, so `drawer-front-1/pull` is the pull's wall.
  `Insert ref` or `Ctrl/Cmd+I` puts `ref("…")` at the editor cursor - and brings the Code tab
  to the front if the Parameters tab was, so you see it land; `Escape` clears it. Put the
  cursor inside a `ref("…")` string and what it names lights up. (`Ctrl/Cmd+Shift+I`, which
  this used to be, is DevTools in Chrome, Edge and Firefox.)
- **Checks**: what `check_fits`, `check_wall`, `check_clearance` and `check_overhangs`
  found is listed in the report over the viewer with its severity, the refs it is about and
  the line that asked, and an `error` marks that line in the editor exactly as a raised exception does.
  A check nothing could answer reads **not checked**, never as a pass.
- **Code | Parameters**: the left pane is the script seen one way at a time - its code, or
  the panel generated from what it declares - as two tabs, and the app remembers which was
  in front. The Parameters tab shows how many there are. A parameter edit re-runs the script
  with overrides instead of rewriting its text; `reset`, on that tab, drops them. While the
  script has a failing line and the Parameters tab is in front, the Code tab carries a red
  dot rather than taking the pane away.
- **Export and the report**: the viewer has the whole right column, and nothing sits under
  it. The files are in the `Export` menu on the viewer bar - SVG and DXF per nested sheet;
  then, for the printer, one `.stl` per body and one `.3mf` with every body in it named; then
  every extra file the build made (per-part SVGs, `baseplate.scad`), more than four of them
  folded under their count; and `Download all` for the lot as a zip. What the run said is a
  card over the bottom of the view, there only while there is something to read: a
  failure, a check's finding, a nest warning or a line on stderr brings it up by itself,
  `hide` puts it away until it says something new, and output on stdout alone waits behind a
  small button that names it. The STL and the 3MF
  are bytes, carried through the scene as base64 - `transport.binary(name)` says which
  entries those are - and decoded on the way out, in the archive as well as on their own.
- **Projects**: a project is a script and its values (decision-3), kept in `localStorage`
  together. The values are the TOML `tools/build.py` reads from beside a script on disk -
  `[values]`, one line per knob you turned - written on every panel edit, and written as the
  run *built* it: a number the script's range held at its end comes back from the scene and
  replaces what was sent, so the file never claims a cabinet the run did not make. It opens
  as `<script>.toml`, a tab beside the script that cannot be closed any more than the script
  can. The Projects container on the rail makes a new one from `templates/untitled.py`, and
  opens, renames, deletes and duplicates them; `Download` is the two files in one archive,
  and `Open…` takes a `.py` back in with the `.toml` beside it - or a `.toml` alone, for the
  project that is open. A pick with a values file that cannot be read opens nothing and
  names the line. An example opens as a project of its own, so it never replaces the script
  being written; the first visit opens `gridfinity_cabinet.py`.

## How it fits together

```
index.html          the layout: header, editor pane, viewer, params and output panels
src/main.ts         wiring and state (the workspace, overrides, the last scene)
src/files.ts        the scripts kept as data: named files, the open one, each with its
                    overrides - new, rename, delete, an example as a file of its own
src/bridge.ts       the worker seen from the page: one run at a time, latest wins, a
                    15 s watchdog that replaces a hung worker, and the scene check
src/worker.ts       Pyodide and Manifold in one thread: /lib from PY_SOURCES, then one call
                    into bench.worker.start, which gives back the runner; each scene is
                    posted as JSON beside its mesh buffers, transferred rather than copied
src/modeller.ts     Manifold's WASM as a table of handles: sweeps, booleans, hulls and
                    meshes on request, freed on release - no geometry of its own
src/editor.ts       CodeMirror 6: Python, error line and gutter, cursor-in-ref detection
src/status.ts       the status line and hints in words, from the counts the scene carries
src/staleness.ts    whether the bundled examples are older than what's on disk right now
src/storage.ts      what the browser remembers, under which keys, never throwing
src/deferred3d.ts   the view's stand-in until three.js has loaded
src/viewer3d.ts     every part in three.js - plates, solids, engraved lines and lettering -
                    drawn where the scene's stage put them: orbit, picking, highlight
src/overrides.ts    the override table as data: read back from storage, set, pruned to
                    what the script declares - the page owns the one copy
src/components/     the Lit elements, atoms up: a callout; a violation, a file row and a
                    parameter field; the report, the Files, Examples and Export menus and the parameters panel,
                    each with its *.test.ts beside it
src/downloads.ts    a file at a time, or a store-only zip written by hand
src/scene.ts        the contract of bench.script as TypeScript types, and `received`, which
                    checks a payload and its buffers before the UI reads them
src/route.ts        what the projects route will and will not do, decided from the request
                    alone - the names, the host, the origin, the version a write names
src/host.ts         the route as typed calls - list, read, write, create, rename, delete -
                    for task-52's store; nothing in the app uses it yet
server/projects.ts  the route's edge in Node: the root, symlinks resolved, the disk itself
```

**The projects route.** decision-9 moves a person's projects onto the host: one directory per
project under a root, and `bench:projects` in `vite.config.ts` serves it at
`/__bench/projects/<project>/<file>` in both `npm run dev` and `npm run preview`. The root is
`$BENCH_PROJECTS`, which must be an absolute path; unset, it is `projects/` at the top of the
repository (gitignored, made on first start). `tools.build --project NAME` reads the same
root by the same rule (`tools/projects.py`). A read carries the file's modification time and
a version (a SHA-256 of its bytes, as the `ETag`); a write names the version it was made from
in `If-Match`, and a create says `If-None-Match: *`. What it refuses, each with a one-word
reason in a JSON body:

- a name that is not one plain name - `..`, `%2e%2e`, an encoded or doubled `/`, a
  backslash, a NUL, a hidden file, anything deeper than a project and a file (`name`);
- a file or project that resolves, through a symlink, outside the root (`outside`), and any
  write, rename or delete aimed at a symlink at all (`link`);
- a write, rename or delete of anything but `.py`, `.toml` and `.stl`, in any case (`type`);
- a page on another origin - `Origin` not this server's own scheme and `Host`, or a browser's
  `Sec-Fetch-Site` other than `same-origin` (`origin`). A request with no `Origin` is let
  through: browsers always send one on a write, so its absence is a client that is not a page;
- a `Host` that is not an address, `localhost` or in `allowedHosts` (`host`) - Vite's own
  host check runs *after* a plugin's middleware and never sees this route, so the route keeps
  the same rule itself, against DNS rebinding;
- a write or delete whose file has changed since that version (`moved`, naming the file), a
  create or rename onto a name that is taken (`exists`), and a write that names no version
  at all (`precondition`).

A delete is a plain unlink for now; task-48 makes it recoverable.

Nothing that crosses the worker boundary is trusted: `scene.ts`'s `received` checks exactly
the keys and kinds the app reads, and that every mesh's buffers are the typed arrays of the
lengths its JSON promises, and `bridge.ts` turns a payload that fails into
`onFailure("unexpected scene shape: …")` rather than a half-drawn viewer.

The page resolves the runtime as `import.meta.env.BASE_URL + "pyodide/"` against the
document and sends that to the worker, which has no base of its own, so a build with
`base: "./"` works from any sub-path; the modeller is found at `../manifold/` beside it.

**One worker, two runtimes, one kernel.** The worker loads Manifold first (half a megabyte,
about twenty milliseconds), binds it as a table of handles, and hands that to
`bench.script.run` inside `JsKernel`, which is the kernel: Python walks each body's tree,
names every face, and calls the modeller *synchronously* - no message, no `await` - with
bulk numbers crossing as buffers. So `check_wall` and `check_clearance` run in the browser on
a body that was built there, and every decision about that body was made in Python. If
Manifold will not load, the run is given no kernel at all: every ref, parameter and cut sheet
comes back exactly as before, every laser part is still drawn as its plate - swept in Python,
with no kernel - every printed part's `mesh` is `null`, and the view says why one is missing.

**Telemetry.** `src/telemetry.ts` is where every log record and span in the app ends up -
the page's, the worker's, and the ones Python's `logging` and `bench.telemetry` make inside
the worker, which it posts to the page as they happen. Two sinks are attached in `main.ts`:
the console, at the level `localStorage["bench.log"]` names (`debug`, `info`, `warn`,
`error`; `info` by default), and User Timing, so every span is a `performance.measure` in
DevTools' Performance panel with its attributes as `detail`. Datadog RUM, Grafana Faro or an
OpenTelemetry exporter is one more `attach(sink)` beside them, and the span names -
`bench.run`, `bench.boot.python`, `bench.script.exec`, `bench.kernel.mesh`,
`bench.view.geometry` - follow OpenTelemetry's conventions. `tools/qa.py` writes the spans
into its log after every example.

`three.js` is *not* in the main bundle. `viewer3d.ts` is behind a dynamic import and is
fetched the first time a scene actually has a printed part in it, so a person opening the
app to draw a laser-cut box never downloads a renderer. The entry chunk is ~448 kB
(~153 kB gzipped) and the 3D chunk another ~549 kB (~138 kB gzipped).

## Deploying it

Everything is static: `dist/` behind any file server, nothing at run time but the files in
it - except the projects route, which only `npm run dev` and `npm run preview` answer, and
which a plain file server does not have. Two things are worth setting up.

**Caching.** `public/_headers` is read by Netlify and Cloudflare Pages and asks for
`/pyodide/*`, `/manifold/*` and `/assets/*` `immutable` for a year, and `index.html`
`no-cache`. The
runtime is 13 MB of one pinned release and Vite's own output is content-hashed, so both are
safe to pin forever; the entry point is the only thing that must be re-fetched for a deploy
to reach anybody. On a host that ignores `_headers` (S3, nginx, GitHub Pages) set the same
two rules by hand - without them every visit re-downloads the runtime, which is the whole
of the first-load cost.

**Sub-paths need the trailing slash.** `base: "./"` means every URL in the page is relative
to the document, so the app works under `https://host/bench/` - but *not* under
`https://host/bench`. Without the trailing slash the browser resolves `assets/index.js`
against `/` and asks for `/assets/index.js`, which is not there; the page comes up blank.
Serve the directory with a redirect to its slashed form (most static hosts do this by
default; nginx wants `try_files $uri $uri/ =404` plus the usual directory redirect), or set
`base` to the absolute path you deploy to and drop the relative-path trick.

Millimetres, Z up, as in `bench`: the view tells its camera that Z is up, so a part lies the
way it lies on the bed. A selected face is teal and the editor's cursor amber, engravings are
drawn in ink, and the sheet thumbnails keep the cut files' red cut and blue engrave lines on
white; everything else follows `prefers-color-scheme`.
