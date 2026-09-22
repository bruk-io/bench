---
id: decision-9
title: A project is a directory, and what a maker drops is in it
date: '2026-09-22 10:00'
status: accepted
---

# Proposal - a project is a directory, and what a maker drops is in it

Successor to decision-3, which said in its second sentence "*a project is a directory: one
script, and one `bench.toml` beside it*" and then, under **Still the owner's call**, left the
tie-break open:

> **`bench.toml` or `<script>.toml`?** One file per script argues for the second, and it is
> what makes two cabinets in one folder possible. `bench.toml` reads better if a project is
> ever more than one script.

*Amended before review, twice. The question "can we use the host's filesystem?" has a better
answer than this first gave, and "the iPad is a viewer **and** an editor" rules out the
browser-side ways of reaching one. A project's files now live on the host, reached over a route
on the server that already serves the page - which retires this proposal's first open question
instead of deferring it, and changes what bench is: a tool you run, not a page you can put
anywhere.*

It shipped as `<script>.toml`, and the app's file model stayed what decision-3 called "named
`localStorage` entries with a source string" - because the directory half was the expensive
half and was rightly deferred. This proposal takes the other branch, and says what the sidebar
looks like when it does.

## Why

**The Projects container lists the wrong thing.** It is a list of `.py` names with a six-button
toolbar under it, and every one of those buttons acts on *the current file* - rename, delete,
duplicate, download. But a project has not been one file since decision-3: it is a script and a
values document, and the app already knows that, which is why *Download* writes a zip of two
files and *Open…* takes two back in. The container shows one of the two and names the whole
thing after it. That is the oddness: the list is a switcher pretending to be an explorer.

**It is about to be three files.** A maker drops an STL on the view; `[reference]` in the
values document names it by file name; and the app holds the bytes in a `let reference: string
| null` in `main.ts` that nothing keeps. So `main.ts` carries `matchedReference()`, whose whole
job is the guard decision-4 asked for - *"a placement for one file is never applied because a
different one happened to be dropped"* - because the table names a file the app does not hold.
Reload the page and the placement survives while the body it places does not. **If the project
contains the mesh, the dangling case goes away**: a table naming a file the app has never held
cannot happen, because naming it is how it got into the project. What is left is narrower and
answerable - is the file the table names the one that is *active* (see below) - which is a
question about selection inside a project rather than about what happened to land on the view.
For a host-backed project the sentence stops being an app's bookkeeping altogether: `file =
"drawer-slide.stl"` names a file in the directory, and it is the same file whether the app,
`tools.build` or the maker's own editor is the one reading it.

**VS Code's split is the right one, and bench does not have it.** An explorer shows what is in
the open folder. Which folder is open is a different control, used a hundred times less often.
Today bench has the rare control filling the container and the common one - what is in this
project - nowhere at all.

## The shape

A project is a directory:

```
gridfinity-cabinet/
  bench.toml          the values, the reference table, and which script is the entry
  cabinet.py          the script
  parts.py            a module cabinet.py imports        (later; see Sequencing)
  drawer-slide.stl    a body somebody else made, dropped on the view
```

That is a real directory: `uv run python -m tools.build gridfinity-cabinet/` runs it, `git`
sees it, and the maker's own editor opens it. The rule stays what decision-3 wrote: **the
dataclass declares and provides the fallback; the TOML says which instance you are building; a
panel edit writes the TOML.**

### The projects live on the host, and the host says where

**The host designates one directory, and every project is a subdirectory of it.** Not a folder
the maker picks in the browser, per project - a root the *server* is started with, the way
`vite.config.ts` already resolves `PY` and `EXAMPLES` from where it sits:

```
$BENCH_PROJECTS/           the root the host designated
  gridfinity-cabinet/      a project
  pipe-bracket/            another
```

The app reaches it over a small route on the server that is already serving the page -
`/__bench/projects/…` beside the `/__bench/generated-at` that `bench:staleness` answers on
today. One middleware, registered in `configureServer` and `configurePreviewServer`, so
`npm run dev` and `npm run preview` both have it and `tools/preview.py` inherits it by
spawning the second. `tools/build.py` takes the same root from the same variable, so the
command line and the app can never disagree about where a project is.

**Why this and not the browser's own file APIs.** Both of the browser-side answers fail exactly
where they are needed most - a person authoring on an iPad against files that live on the
workshop machine:

- `showDirectoryPicker()` is **Chromium only, and "we always use Chrome" does not rescue it**:
  on iPadOS every browser is WebKit, Chrome included, because Apple requires it. So the tablet
  has no picker whatever is installed on it, and no shim can add a dialog the engine will not
  show. Desktop Chrome has one; the device that needed it does not.
- The origin private filesystem is **secure-context only**. A tablet on the LAN reaches the
  host as `http://192.168.x.x:5173`, which is not a secure context, so `navigator.storage` is
  not even defined there. The cross-browser fallback is absent in the one case it existed for.

And the argument that settles it: **the iPad already cannot work without a host machine serving
the page.** The bytes are coming from a server on the network before any of this. A read/write
route on that same server costs nothing in the only scenario where a tablet authors at all -
whereas the picker asks the maker to re-grant permission every session, and only on the
browsers they were not using.

**What it costs.** The app stops being a page you can put anywhere and starts being a tool you
run. That is a real change in what bench *is*, and it is taken deliberately rather than
absorbed - see "There is no fallback" below.

### What the route has to get right

- **It is a workshop tool on a trusted network, not an authenticated service**, and the doc says
  so rather than leaving it implied. It reads and writes files on somebody's machine.
- **Confined to the root**: no `..`, no absolute paths, no following a symlink out, and only
  `.py`, `.toml` and `.stl` written. A path is a project name and a file name, checked, not a
  string joined onto the root.
- **Bound deliberately.** The npm scripts pass no `--host` today, so the tablet case needs one
  by hand - and the moment it is passed, a *write* endpoint is reachable by everything on the
  network. The route checks `Origin`/`Sec-Fetch-Site` so a page in another tab cannot POST to
  `localhost:5173` on the maker's behalf, and binding wide stays something a person does on
  purpose.
- **The maker's own editor can now race the app.** This is genuinely new: until this, a project
  lived in `localStorage` and nothing else could touch it. Now `cabinet.py` is a file two
  things have open. A read carries the file's mtime, a write whose base has moved is **refused
  and says so** rather than overwriting, and the explorer says which file went stale. A watcher
  that notices and offers to reload is the VS Code answer and is out of scope here. The lock
  below does **not** cover this: `vim` does not ask the route for permission.
- **A panel edit is a network write.** The README's "a line in it at once" becomes a PUT per
  knob turn; they coalesce on the 300 ms cadence the run already debounces at.
- **Adopting what is in `localStorage` writes real files onto a real disk.** It asks first,
  naming the directory it is about to create. It does not happen because the page loaded.

### An open project is locked to one writer

The host grants a **write lease on a project**, and holds it for one client. Everyone else may
open it, read it, run it and look at it; nobody else may write to it. One project, one writer,
decided by the only thing that sees every client.

**It is a lease, not a lock, because clients vanish.** A tab closed, a lid shut, a tablet
backgrounded, a crash - a plain lock outlives all of them and leaves a project held by nobody,
which is how every design like this actually fails. So: the lease carries a client id and an
expiry, the holder renews it while it is alive, and it lapses on its own if the renewals stop.
An explicit release on `pagehide` makes the common case instant rather than a wait, and is
never *relied* on - iOS in particular is free to discard a backgrounded page without running
anything, and the expiry is what makes that merely slow instead of wrong.

**The reload case has to be free.** A client id kept per tab means a refresh reclaims its own
lease immediately rather than queueing behind the ghost of itself.

**And a person can take it.** The maker standing at the desktop, whose only other device is an
iPad asleep in another room, must not be told to wait for a machine they cannot reach. Taking a
lease that is still live is a thing they can do, having been told whose it is. Rare, loud, and
better than a project nobody can open.

**Read-only is a real mode, and a good one.** It is the tablet-as-viewer case made explicit:
open the project, run it, orbit it, read the report, export files. Running is entirely
client-side and needs no write at all. What it cannot do is edit the script, rename, delete, or
drop a mesh. **Knobs are the interesting middle**: a panel edit writes the TOML, so it is a
write - but *turning* one without keeping it is how a person explores a parametric model, which
is exactly what a tablet is good for. A reader gets knobs whose values are not persisted, and
is told that is what they are.

**What the lease does not cover, and must not be read as covering:** the maker's own editor.
`vim` does not ask the route for permission, and neither does `git checkout`. The lock is
between clients of this app; the mtime check above is what stands between the app and
everything else on the machine. Both, for different writers.

Where the lease lives: in the server, not in a file under the project. A restart legitimately
voids every lease - no client holds anything across it - and there is no `.bench-lock` left
behind for somebody to delete by hand.

### There is no fallback, and that is the decision

The route is not an enhancement the app works without. **bench is served by a host, always**,
and a build behind a dumb file server with no `/__bench/projects` behind it is not a degraded
bench - it is a bench that says it has no host and stops. One code path, one place a project
can be, nothing in the app that has to ask which mode it is in.

This retires a promise the web README makes today - *"Everything is static: `dist/` behind any
file server, nothing at run time but the files in it"* - and that sentence has to be rewritten
rather than quietly left standing. What stays true is the part that costs the most: nothing is
fetched from a CDN, the runtime and the modeller are still served by this app, and the host is
a static file server *plus one middleware*, not an application server. Deploying it is still
copying a directory and starting something that serves it.

It also retires `localStorage` as a place projects live. It keeps what it is actually good at -
which container the rail had open, the log level, the hang fingerprint - and a browser holding
projects from before this is adopted once, on the first connect, with the directory it is about
to write named before it writes it.

### The browser's own storage is an outbox, not a mirror

Asked while this was being written: could the app keep writing to browser storage and sync that
to the host - and if `localStorage` is too small, could it be IndexedDB? The answers are **yes
to IndexedDB** as the store and **no to a mirror** as the shape, and those are two separate
questions that are easy to run together.

**IndexedDB is the right store, and `localStorage` is not.** It has no 5 MiB wall, it holds a
`Blob` or an `ArrayBuffer` without the third-again that base64 costs, and - unlike the origin
private filesystem - it is **not** restricted to secure contexts, so it is there on the tablet
over `http://` on the LAN, which is the case that decided everything else in this document.
`storage.ts` also could not have carried this: its written contract is *"the app still works
when it does; it just forgets"*, which is right for which tab was open and inverted for
anything holding work.

**But the store is not the question; what it is *for* is.** A mirror puts the files back in the
browser and makes the host directory a lagging replica - `tools.build`, `git` and the maker's
editor all reading whatever the last sync left behind. That is the thing this document set out
to stop, and a bigger, faster browser store does not change it.

**The lease does weaken the strongest objection, and that is worth saying plainly.** Before it,
the case against a mirror was lost updates: two devices, two copies, automatic writes on every
panel edit and every 300 ms debounce, and no Save button to make a person the one who decides -
so a tablet left open on yesterday's state could push it over the desktop's work silently. One
writer at a time removes that. What is left is not nothing, though: how far the host may lag
behind the truth, and what happens to work that never got there. **The tablet answers it** -
WebKit deletes all script-writable storage, IndexedDB included, after seven days without a
first-party interaction, and an iPad is exactly the device left untouched for a fortnight. That
is survivable for a queue that drains in seconds and fatal for a store somebody is treating as
where their project lives.

**So: the host is the truth, and IndexedDB holds what has not got there yet.** One sentence, no
merge, no conflict resolution, no sync section in this document. Bounded by what is in flight,
coalesced on the cadence the run already debounces at, drained on reconnect, and the stale-write
refusal above is what catches a queue that drained onto a file that moved.

The window it covers is small by construction: the app is always hosted, so "the host is down"
is not an offline story - the page did not load. What is left is a restart mid-session,
measured in seconds.

**A dropped mesh could queue now and still should not.** IndexedDB would hold it as a `Blob`
without complaint, but a mesh arrives as a `File` and is never edited, so there is nothing to
buffer: it is posted straight through and either lands or says it did not.

### `bench.toml`, not `<script>.toml`

The stem is no longer unique or meaningful: a directory holds one values document however many
`.py` files are in it. The `[project]` table is where the directory says things about itself
that no script can:

```toml
[project]
entry = "cabinet.py"

[values]
units_x = 4
drawers = 6

[reference]
file = "drawer-slide.stl"
origin = "low"
up = "+Z"
along = "+X"
```

`[project]` costs nothing in compatibility: `values.ts` already *"passes over unread"* any table
it does not know, so a build from before this opens a new `bench.toml`, reads its values and its
reference table, and falls back on the entry rather than failing on it.

`entry` answers the question the VS Code analogy does not: **which script runs.** A folder has
no entry point; bench does. The proposal's answer is that `entry` names the default, and the
script you have open runs - so opening `parts.py` and pressing Run runs `parts.py`, which is
what a person who clicked on it expects, while a fresh open of the project runs `entry`.

### The sidebar

Two controls where there is one:

- **A switcher, one line, above the tree**: the open project's name, and a menu of the others,
  with *New*, *Open…* and *Download* on it. This is the rare control, sized like one.
- **An explorer, the rest of the container**: the open project's own files. `bench.toml` and
  the scripts as tabs-in-waiting - click one and it opens in the editor group, exactly as the
  values document already does - and the references as their own group. Per-row actions
  (rename, delete, duplicate) replace the toolbar that acted on "the current file", because
  now there is a row under the pointer that says which file is meant.

Nothing here needs a new tab kind: the editor group already draws a script, a document, a cut
sheet and a report, and a second `.py` is the first of those.

### A reference in the refs container

The second half of the ask. One row per mesh the project holds, in a **References** group in
the refs container, selectable: clicking it lights the body up in the view and makes it the
active reference - the one `survey`, *detect faces* and the pick panel are about.

**Selection has to widen before this works.** Today `selected` is one string and `showSelection`
enables *Insert ref* off it, so every selection is a thing `ref("…")` can name. A reference row
is not: a dropped body has no ref path, and `ref("drawer-slide.stl")` resolves to nothing. So
the round-trip's payload grows from a ref to a selection that is *either* a ref or a reference,
and *Insert ref* stays disabled for the second. That is a small change in `main.ts` and
`refs-tree.ts` and it is the whole of the work in step 1 - not the row, which is trivial.

The container's empty state changes with it. `refs-tree.ts` draws "This run named nothing yet."
whenever it has no roots; with a body dropped and no run yet, that is now false, and the
References group is the only thing there is to show.

**A reference gets one row and no subtree.** That is not a simplification, it is what two
shipped decisions already say. decision-8: an imported mesh *"names nothing under it the way a
hull does, because a file somebody else wrote has no names in it to keep."* decision-7: a pick
writes numbers, never a survey's own indexing, because `Survey.flats` *"would move when the
survey did."* A face list under a dropped STL would be exactly the indexing decision-7 refused,
one document later.

And it is **a group beside the run's refs, not a branch inside them.** `refs-tree.ts` documents
its own property as *"every ref the newest run named."* A mesh that was merely dropped was
named by no run. Putting it in `treeOf(scene.refs)` makes that sentence false and makes a
dropped body indistinguishable from a built one; a sibling group keeps both true. A body the
script *imports* - decision-8's `imported(reference)` - does come back through the run's refs,
as the leaf it is, and that is the right asymmetry: the run named it because the script asked.

### One active, several held

Today `reference` is one base64 string, `bridge.survey` takes one, `[reference]` is one table.
The user's ask is plural - "any stls we drag in". The proposal: a project **holds** every mesh
dropped into it, and exactly one is **active** at a time. Selection in the References group is
what makes one active. `[reference]` stays a single table naming the active one, because a
placement is a placement of one body against one origin, and decision-4's grammar has no room
for two without being redesigned. Dropping a second STL adds a row and makes it active; it no
longer silently replaces the first.

## What changes

- **`src/bench/` - nothing.** decision-3's own argument for the shape, and it survives:
  `placement.py`, `imported.py` and `survey.py` all take a mesh handed in at the edge, and
  `run()` takes a mapping. If this proposal starts adding Python, the shape is wrong.
- **`web/src/files.ts`** - `Project` grows from `{name, source, overrides, reference}` to a
  directory of named files with a `[project]` table. This is the bulk of it.
- **`web/src/values.ts`** - `tomlName`/`stemOf` stop being how the values document is found;
  a `[project]` table joins `[values]` and `[reference]` in `toml`/`fromToml`.
- **`web/src/storage.ts`** - projects leave it entirely for the host, and `restored()` becomes
  the one-time adoption rather than the way the app boots. What is left is the small remembered
  state it was always right for.
- **a new `web/src/host.ts`** - the route as functions: list, read, write, create, rename,
  delete, the mtime a write is checked against, and the lease with its renewal. Plain `fetch`
  over data, the way `bridge.ts` is plain `postMessage` over data, so nothing above it knows it
  is talking to a server.
- **a new `web/src/outbox.ts`** - writes that have not reached the host yet, in IndexedDB,
  coalesced and drained. The one place that is allowed to hold work the host has not got.
- **`web/vite.config.ts`** - the middleware, in `configureServer` and `configurePreviewServer`,
  beside `bench:staleness` and for the same reasons that one is written the way it is.
- **`web/README.md`** - "Everything is static" is no longer true and is rewritten, along with
  how a person serves this for a tablet on the same network (`--host`, and what that exposes).
- **`web/src/main.ts`** - `reference`/`referenceName` stop being module state and become the
  active file in the open project; `matchedReference()` collapses to a lookup; the tab
  machinery takes an arbitrary script; download writes a directory.
- **`web/src/components/organisms/explorer.ts`** (+ its 177-line test) - rewritten as the
  switcher and the tree.
- **`web/src/components/organisms/refs-tree.ts`** - a References group above the run's roots,
  a selection that may be a reference rather than a ref, and a new empty state.
- **`web/index.html`** - the rail's *Your scripts*, the container's *Projects* heading and the
  refs container's foot copy ("click a row to light it up in the view") all describe the old
  shape; the switcher and the tree are markup that is not there yet.
- **`tests/e2e/`** - the checks that drive `#file-new`, `#file-rename`, `#file-delete` by id.
- **`tools/build.py`** - takes a directory as readily as a script path.
- **`examples/`** - an example opens as a project of one script, which is what it already is.

## What this costs, honestly

- **Migration, twice over.** `restored()` already carries one legacy shape ("a record kept
  before the values were a document"). This adds a second: every kept `{name, source, values}`
  becomes a one-script directory named for the script's stem. It is mechanical, and it must be
  written down in `files.ts` where the first one is, not discovered later.
- **bench stops being a page and becomes a tool you run.** This is the big one, and it is not
  a detail of the file model - it is a change in what the thing is. A static `dist/` no longer
  opens as a working bench. The README's deploying section is rewritten, not amended.
- **Opening a project is now a round trip that can fail.** Today reading a project cannot
  fail: it is a string in `localStorage` and `storage.ts` is written never to throw. Now the
  host can be down, the root can be missing, the directory can be unreadable. Every one of
  those needs a thing on screen that says which, and the app has no vocabulary for it yet.
  This is the cost that shows up in the most places.
- **Writes go somewhere real.** A rename moves a directory on somebody's disk; a delete removes
  files that the explorer's own copy says are *"not kept anywhere else, so it cannot be brought
  back"* - a sentence that was about `localStorage` and is now about their filesystem. Delete
  wants to be a move to a trash directory under the root rather than an unlink.
- **Two writers, one file.** The maker's editor and the app can now hold `cabinet.py` at once,
  which was impossible before. The write lease settles it between clients of the app; refusing
  a stale write is what is left for everything else on the machine, and it is the floor rather
  than the finish.
- **A lease is state the server holds**, which is the first such state there is: `bench:staleness`
  answers off the disk and keeps nothing. Small, and worth noticing, because it is what makes
  the route a thing with a lifetime rather than a pure function of the filesystem.
- **Paste-and-run gets weaker again**, in the way decision-3 predicted. A project is now a
  folder; "here is my script" stays possible (a one-script directory with no `bench.toml`) but
  is one more step from the thing the app shows you.
- **Two controls where a person had one.** The switcher is one more click to reach another
  project than the flat list was. That is the trade: the common thing gets the container.

## Sequencing

Each step is useful and reviewable on its own, and the cheap half of the ask is first.

1. **The References group in the refs container.** One row for the one dropped body, selectable,
   lighting it up in the view. No storage change, no file model change, no migration - it reads
   the `reference` state `main.ts` already has. The work in it is widening the selection so a
   reference can be selected without offering *Insert ref*, not the row.
2. **A protocol between the app and the place the projects are kept**, with this browser as
   its first implementation and no behaviour changed. Written while building: the page read
   and wrote `localStorage` at its own top level, synchronously, and both a host route and
   anything behind it are neither - so the seam comes before either, and the expensive,
   durable part of it is making the boot await an answer rather than have one. A *document*
   crosses it, never a `Workspace`, so `files.ts` stays the one pair of functions that parse
   and serialize projects and an implementation only shifts bytes. (`store.ts`, task-51.)
3. **The route**: the middleware beside `bench:staleness`, the root from `BENCH_PROJECTS`,
   path confinement, the origin check and the stale-write refusal.
   *This makes the e2e suite easier rather than harder*, which is worth saying because the
   picker would have made it worse. There is no dialog to drive and no handle to fake: the
   fixtures already spawn the server through `tools/preview.py`, so they point the root at a
   `tmp_path` and drive ordinary fetches. The existing drop helper builds a synthetic
   `DataTransfer` (`data.items.add(file)`) and keeps working unchanged, because an STL still
   arrives as a dropped file - it is only where it then goes that changed.
4. **The second implementation of the protocol, over that route, with the outbox** - which is
   the one thing a remote store needs that a local one did not, and which belongs here rather
   than in the file model below. (task-52.)
5. **The kept record becomes a directory** of named files with a `[project]` table, and
   whatever the browser is holding is adopted once, asked for rather than assumed. The
   explorer still looks like a list; only the model underneath changed.
6. **The explorer becomes the switcher and the tree**, the switcher listing what is under the
   root. The sidebar change a person can see.
7. **Several references held, one active**, selection in the tree choosing it. A dropped STL
   is written into the project's directory here, which is also where the stale-write refusal
   earns its keep, since a mesh is the one file a maker might replace from outside.
8. **`tools/build.py` takes a directory**, so the browser and the command line agree again.
9. **Project-local modules** - a second `.py` the entry imports. The worker already mounts
   `bench` into `/lib` from `PY_SOURCES`; mounting the project's own files beside it is the
   same move, and it is the first time a script in the browser could be more than one file.
   With the project on the host this is just fetching its `.py` files and writing them into
   `/lib` beside `PY_SOURCES` - no new mechanism at all, since that is what the worker already
   does with `bench` itself. Not part of this proposal's claim; listed because `[project] entry`
   is what makes it possible and it should not be re-litigated then.

## Still the owner's call

*Two of these were answered while this was being written, and are kept struck through rather
than deleted, because the reasons are what a reviewer will want.*

- ~~Is the tablet an authoring surface or a viewer?~~ **Answered: both.** Which is what settles
  the backing, since iPadOS has no picker and, on `http://` over the LAN, no origin private
  filesystem either - `navigator.storage` is secure-context only and is simply not there. A
  host route is the only mechanism that serves a tablet that writes.
- ~~Where do the mesh bytes live? IndexedDB, or held for the session.~~ **Answered:** in the
  project's directory on the host, as the file the `[reference]` table already names.
- **How far does the route go before it stops being a dev server?** Today it rides on
  `vite preview` through `tools/preview.py`. That is right for a workshop machine and wrong for
  anything a person would call a deployment, and the line between them is not drawn here.
- **How long is a lease, and how loud is taking one?** A short expiry makes a closed tab free
  its project quickly and makes a slow network look like a lost lease; a long one is the
  reverse. Somewhere around a minute, renewed every fifteen seconds, is the shape - but the
  number wants to be met rather than guessed, and taking a live lease wants a sentence written
  by somebody who has been on the losing end of one.
- **Does a reader get unsaved knobs, or no knobs?** The proposal gives them knobs that turn and
  are not kept, because exploring a parametric model is the best thing about a tablet. It is
  also the one place in the app where a control does something that is deliberately not
  persisted, which is a thing to be sure about rather than clever about.
- **Is `entry` declared, or is it just the script you last had open?** Declared is a fact in a
  file somebody can read in a diff; last-open is one less thing in the document. The proposal
  takes declared, weakly.
- **Do examples open as projects you can edit, or as read-only ones you duplicate?** Today an
  example becomes a project of its own on open, and that is good. A directory makes "the
  examples" a plausible read-only shelf in the switcher instead, which is a different feel.
- **Does a dropped STL land in the project at all, or only in the session?** Now that landing
  means writing a file to somebody's disk, this is worth asking rather than assuming: a maker
  measuring a body they are not copying may not want it kept. Keeping it is the proposal's
  default, because the `[reference]` table naming a file that is not there is the thing this
  whole document is trying to delete.
