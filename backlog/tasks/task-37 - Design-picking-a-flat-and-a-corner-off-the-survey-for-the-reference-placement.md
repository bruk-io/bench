---
id: task-37
title: 'Design picking a flat and a corner off the survey, for the reference placement'
status: Done
assignee: []
created_date: '2026-09-22 16:09'
updated_date: '2026-09-22 01:46'
labels:
  - feature
  - web
dependencies:
  - task-26
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decision-4 (`backlog/decisions/decision-4 - A-reference-is-placed-and-the-placement-is-written-down.md`, task-26) named this as its step 4 and explicitly deferred it: "A pick: choose a flat and a corner off the survey in the view, and the app writes the resolved numbers. ... does not begin until the question of picking on the reference is designed."

Today (decision-4 steps 1-3, all merged) a maker writes `[reference]`'s `origin`/`up`/`along` by hand - as a word (`"low"`, `"+Z"`) or a numeric triple - in the project's TOML, outside the app. The app reads it, applies it, and shows a `placed` chip, but cannot compose one itself. This task is that missing composition: letting a maker click a flat and a corner in the 3D view (off the raw, unplaced survey) and having the app write the resolved `[reference]` table back.

This is explicitly a design task first, not an implementation task - decision-4 says so, and decision-3's own still-open question (whether the project TOML is "a rendering the app owns rather than a document the maker owns", task-18.2) bears on it directly: writing a `[reference]` table from a UI pick is the app authoring a file it currently only reads. Read decision-3 and decision-4 in full, and decision-3's "Still the owner's call" section, before designing anything.

Questions a decision document for this would need to answer, at minimum:
- What "a flat" and "a corner" mean as pickable targets off `bench.survey`'s own output (which planes/vertices/features does the survey already name that a pick could resolve to a `Point`/`Vector`?).
- Whether a pick writes the *named* form (`"low"`, `"+Z"`) when it happens to match one exactly, or always writes a resolved triple - decision-4's own text prefers named forms for readability but a picked point rarely lands exactly on a survey extremum.
- How a pick interacts with decision-3's open question about who owns the TOML - does writing a table from a pick require resolving that question first, or can it be scoped narrowly enough not to?
- What the UI actually is (click two things in the 3D view? a guided flow? a form referencing survey-reported features by name?) - out of scope for a decision document to fully design, but the shape of the interaction affects the data question above.

Not small, and not yet scoped into an implementation plan - this task is to produce that plan (most likely a new decision document, decision-4-style) before any code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A document (or an explicit, argued conclusion that no document is needed) answers what a maker picks and what gets written to [reference] as a result
- [x] #2 It resolves, or explicitly scopes around, decision-3's still-open question about who owns the project TOML
- [x] #3 It says whether a pick prefers a named form or always writes a resolved triple, and why
- [x] #4 What it deliberately leaves out of a first step is named, as decision-3, decision-4 and decision-6 all do
<!-- AC:END -->
