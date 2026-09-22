# bench

Python 3.15 floor. Plain parts: frozen dataclasses, NamedTuples, enums, unions,
functions; no inheritance in domain code; private by default. Exceptions are
exceptional and every direct raise is documented (ruff DOC501/502). Functional
core: modules take data and return data; I/O lives at the edges only.

Read README.md for the layer model before adding anything. New operations go
in a module named for what they do, never in `__init__.py` (imports and
`__all__` only).

Add an import in the same edit as the first line that uses it. A hook formats
and fixes every file the moment it is written, so an import that arrives one
edit ahead of its use is unused when that runs, and ruff used to delete it -
leaving an undefined name that only the gate catches, several steps later.
`unfixable = ["F401"]` now stops the deleting; writing the two together stops
the confusion.

<!-- BACKLOG.MD MCP GUIDELINES START -->

<CRITICAL_INSTRUCTION>

## BACKLOG WORKFLOW INSTRUCTIONS

This project uses Backlog.md MCP for all task and project management activities.

**CRITICAL GUIDANCE**

- If your client supports MCP resources, read `backlog://workflow/overview` to understand when and how to use Backlog for this project.
- If your client only supports tools or the above request fails, call `backlog.get_workflow_overview()` tool to load the tool-oriented overview (it lists the matching guide tools).

- **First time working here?** Read the overview resource IMMEDIATELY to learn the workflow
- **Already familiar?** You should have the overview cached ("## Backlog.md Overview (MCP)")
- **When to read it**: BEFORE creating tasks, or when you're unsure whether to track work

These guides cover:
- Decision framework for when to create tasks
- Search-first workflow to avoid duplicates
- Links to detailed guides for task creation, execution, and completion
- MCP tools reference

You MUST read the overview resource to understand the complete workflow. The information is NOT summarized here.

</CRITICAL_INSTRUCTION>

<!-- BACKLOG.MD MCP GUIDELINES END -->
