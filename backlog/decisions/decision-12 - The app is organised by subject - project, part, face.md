---
id: decision-12
title: The app is organised by subject - project, part, face
date: '2026-09-28 02:00'
status: accepted
---

# The app is organised by subject - project, part, face

Asked 2026-09-27: the app feels messy; should it have FreeCAD-style workbenches (a sketch
bench, and so on)? No sketcher - bench has no constraint solver and is not getting one - and no
workbenches either. Workbenches are FreeCAD's most criticised idea: a maker has to know which
bench holds a tool, tools are duplicated between them, and parts belong to the bench that made
them. bench has one source of truth, the script, and every view of it runs the same script.

## Why it feels messy

Each task added its control where it was needed that day, and everything is on screen at once.
Measured against the app as it stands (2026-09-27):

- **Findings in two places.** A Problems button on the rail, and a Problems tab in the panel.
- **Outputs in three.** A Sheets rail tab, a Files panel tab, and the export menu.
- **Tools floating over the view.** Insert ref, survey, detect faces, remove body and the pick
  panel sit on the 3D view whether or not a reference mesh is in play.
- **Looking mixed with doing.** One toolbar holds zoom, section and colour faces - ways of
  looking - beside survey and insert ref - actions.
- **Refs far from their subject.** The refs tree is its own rail tab, though every ref is a
  ref of a part.
- **Knobs far from the model.** Parameters are a sidebar tab, so turning a knob hides the
  file tree.
- **Findings as a wall of text.** Since task-78 a warning names five places in one sentence.
- **The lease banner** - "open for writing elsewhere" - takes a third of the editor's height.
- **The view cannot show a fit.** The bed grid runs through an assembly at z = 0, a section
  clips only the script's parts and not the reference, and nothing can be drawn for context
  without being exported (found building projects/tower's fit view).

## The rule

**Every thing has one home, and an action lives next to its subject.** bench shows three kinds
of thing: the **source** (scripts and their values), the **result** (parts, faces, what the
checks found) and the **outputs** (files). The subject is whatever is selected:

- **Nothing selected - the project.** The inspector shows the knobs, the parts - each with a
  status badge (fits, warnings, errors) - and Export all.
- **A part.** Its findings as a list of places (each clickable, lighting the place in the
  view), how it prints (orientation, bed fit), its fits with the parts it mates, its faces as a
  tree (what the refs tab was), and Export this part.
- **A face.** Its ref and Insert in code, its area and normal, the findings that name it.
- **A reference mesh.** Survey, detect faces, placement (origin, corner, up, write) - the
  controls that float over the view today, shown only when a reference is the subject.

Clicking empty space goes back to the project. Selection is by ref, so it survives a re-run
when the ref still exists.

## The layout

- **Left: the project** - its switcher and its files. Nothing else.
- **Centre: editor and view**, with a **Code | Split | View** control: Code for writing, View
  for checking and printing, Split as today. It replaces what workbenches would have done for
  screen space.
- **Right: the inspector**, about 280 px, following the selection.
- **Bottom: Output** (print, log, stderr), folded by default. Problems leave the panel: they
  live on their part in the inspector, and the status bar's count selects the worst part.
- **The view keeps only ways of looking**: the view mode, Fit and zoom, colour faces, and the
  section axis and position. Every action moves into the inspector beside its subject.

## View modes

- **Assembled** - where the script puts the parts. No bed grid: an assembly has no bed.
- **On bed** - each part laid the way it prints on the chosen printer's bed, the build volume
  drawn, overhang places painted. Python lays the parts down (the rule export and check_fits
  already share) and sends the placements with the scene; the UI does no 3D maths.
- **Section** - today's clipping, promoted to a mode, and clipping the reference and context
  bodies too, so a foot in its pocket shows in section.

## Context bodies

A script can show a body for context - a reference in its seated pose, a ghost of a module's
body between two couplings - without exporting it. It is drawn translucent and never reaches
an STL, a 3MF or the part list.

## What this does not decide

The exact visual design is the implementer's, inside this structure, following the existing
component layers (atoms, molecules, organisms) and Web Components with no framework. Where the
structure and a detail disagree, the structure wins; where it is silent, the simpler thing.

## Order (m-13)

1. The inspector, and the duplicates removed - no new features.
2. View modes: Assembled without the grid, On bed, Section that cuts everything.
3. Context bodies.
4. Code | Split | View, and the lease banner made a compact chip.
5. Selection that survives a re-run, and the status bar jumping to the worst finding.
6. Open in slicer (task-86), as an action in the inspector's export.
