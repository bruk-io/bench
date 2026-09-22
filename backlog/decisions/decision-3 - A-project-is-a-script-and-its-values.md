---
id: decision-3
title: A project is a script and its values
date: '2026-09-22 19:30'
status: proposed
---

# Proposal - a project is a script and its values

Successor to decision-2, which ended on exactly this question and deferred it: "*writing a
panel value back into the script... not in this proposal; this one only makes it possible.*"
This is that step, and it turns out the answer is not to write back into the script at all.

## Why

A script declares its settings as a dataclass and the panel edits them. Where do the edited
values *go*?

Today: into `localStorage`, as part of a kept file - `{ name, source, overrides }` in
`web/src/files.ts`. That is the whole of it. So the values a maker arrived at by turning
knobs for an hour are:

- **not versioned** - no history, no diff, no way to see what changed;
- **not shareable** - they exist in one browser on one machine;
- **not visible** - nothing on screen says "this cabinet is the 6-drawer one";
- **gone** if the browser's storage is cleared, while the script survives in the repository.

The split between *what a thing is* and *which one you are building* already exists in the
code. It is just that one half is a first-class file and the other is a hidden string in a
browser. This proposal does not introduce a split; it promotes the half that is hiding.

There is a second pressure arriving. Reverse-engineering a dropped mesh (task-14) produces
measurements a maker takes by hand - this face to that face is 12.00 mm - and those are
neither geometry nor code. They have nowhere to live either, and they want the same home for
the same reason.

## The shape

A project is a directory: one script, and one `bench.toml` beside it.

```toml
# gridfinity_cabinet.toml

[values]
units_x = 4
units_y = 2
height_u = 3
drawers = 6
kerf = 0.25
baseplate = true
labels = "bits, taps, drivers"
```

That is it for step one. The file is the panel's table, written down.

### The rule that keeps two defaults from becoming a fight

- **The dataclass declares, and provides the fallback.** `knob(4, min=1, max=7)` says a
  parameter exists, what kind it is, what range it holds, and what it is when nothing else
  says otherwise.
- **The TOML says which instance you are building.** A value in `[values]` replaces the
  field's default. A field absent from the TOML keeps the dataclass's.
- **A panel edit writes back to the TOML.** The parameters container stops being a scratchpad
  and becomes an editor for a file. That is the whole point: the knob you turned is now a
  line somebody can read in a diff.

### Why this is smaller than it looks

`configured(cls, values)` already takes "an untrusted mapping - the panel's table, JSON off a
wire - into an instance, coerced to each field's type and held at the nearer end of its
range". **A TOML table is that mapping.** `tomllib` is standard library at bench's 3.15
floor, so:

- `params.py` does not change;
- `script.py` does not change - the values arrive as the `overrides` argument `run()` already
  takes;
- **no new dependency**, which is the first sentence of the README and not negotiable.

The script never reads the file. Reading it is I/O and belongs at the edge, the way `extras`,
`reference` and the kernel are all handed in by the host rather than imported in the middle.
A script that read its own configuration would also not work in the browser, where there is
no filesystem at all.

### What annotations look like, later

Measurements from a surveyed mesh are a second table, not more parameters:

```toml
[[measured]]
name = "wall"
between = ["plane-3", "plane-7"]
value = 2.41

[[measured]]
name = "boss-spacing"
between = ["axis-1", "axis-2"]
value = 42.00
```

A measurement is data a maker collected; a parameter is an input the script consumes. Keeping
them in separate tables in one file is what makes "promote this measurement to a parameter" a
move from one table to the other rather than a special case.

This part is **not** in the first step. It is here so the file is named for what it will
hold - a project, not a params file - rather than being renamed later.

## Rules

- **The TOML is optional.** A script with no file beside it behaves exactly as today: the
  dataclass's defaults, and the panel edits them. Paste-and-run does not die.
- **An unknown key is not an error.** `configured` already ignores names it does not know, so
  a file kept from an older version of the script still opens. This matches the existing
  pruning behaviour rather than inventing a stricter one.
- **A value its field cannot read still raises**, naming the field, exactly as it does now
  from the panel. The TOML is untrusted input like any other.
- **One file per script**, named for it. Not one file for a folder of scripts: a project is a
  thing you are building, and two cabinets are two projects.

## What this costs, honestly

- **A project becomes a directory, and the browser has no filesystem.** The app's file model
  is named `localStorage` entries with a source string. Script-plus-sidecar means a folder
  model: the files menu, `files.ts`, `storage.ts`, the export path and a good part of the e2e
  suite. **This is the real expense, and all of it is in `web/`.**
- **Paste-and-run gets weaker.** Today a script is the whole thing and that has been a
  virtue. It survives - the TOML is optional - but "here is my project" becomes two files.
- **Two places to look** when a value is not what you expected. The rule above is what keeps
  that answerable, and the panel showing the file's values is what keeps it visible.

## What changes

- `src/bench/` - **nothing.** That is the argument for this shape.
- `tools/` or the host - reads the TOML, hands `run()` the mapping it already takes.
- `web/` - the file model becomes a project model; the parameters container edits a file; the
  TOML is readable as a tab in the editor group, being a document like a cut sheet.
- `examples/` - a `.toml` beside the scripts that want one, showing the shape.

## There is no host to put this in yet

Found while sequencing this, and worth saying plainly because it changes step 1: **nothing
runs a script from disk.** `tools/` holds `check`, `qa`, `kernel_timing`, `preview` and
`stack` - a gate, a screenshotter, a timer, a server and a Pyodide harness. The only real
hosts `run()` has are `bench.worker`, which is the browser, and the test suites.

So "the host reads the TOML" has nowhere to live. Two ways out:

- **Step 1 creates the host**: a small `tools/` entry that takes a script path, reads a TOML
  beside it, and prints or writes what the run produced. Chosen, because reading a file is
  exactly what a command-line host is for, it makes the TOML useful before any browser work,
  and the repository is missing this anyway - there is currently no way to run a script and
  get its cut sheets without opening a browser.
- Start in `web/`, which puts the first step inside the file-model change this proposal is
  trying to defer. Rejected for that reason.

## Sequencing

1. A command-line host: run a script from disk, read a TOML beside it, hand its `[values]` to
   `run()`. Nothing in the app changes yet; a file on disk drives a run.
2. The app's kept file grows from `{ name, source, overrides }` to a project: the same three
   things, with the values serialised as TOML rather than as a JSON blob in storage.
3. A panel edit writes the file. The parameters container is now an editor.
4. The TOML opens as a tab beside the script.
5. `[[measured]]`, once task-14 produces measurements worth writing down.

Steps 1 and 2 are independently useful and independently reviewable. Step 5 does not start
until there is something to put in it.

## Still the owner's call

- **`bench.toml` or `<script>.toml`?** One file per script argues for the second, and it is
  what makes two cabinets in one folder possible. `bench.toml` reads better if a project is
  ever more than one script.
- **Does the panel write on every edit, or on a save?** Writing on every edit makes the file
  the truth and the panel a view of it, which is the cleaner model and a noisier diff.
- **Does a value the TOML holds and the dataclass clamps get written back clamped?** The
  scene already reports what was actually built; the file saying something the run did not do
  would be a quiet lie.
