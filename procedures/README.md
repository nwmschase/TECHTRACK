# Guided Diagnostics procedure trees

Hard flowchart trees live here as JSON. `guided_flow_engine.py` loads every
`*.json` in this folder except files that start with `_`.

Do **not** invent OEM steps, blink LEDs, voltages, or a second brand’s tree.
Copy only decision diamonds that exist on a shop Document Library service manual.

## File contract

Required top-level keys:

- `id` — stable snake_case id (filename should match)
- `title` — shop library manual title (same string used in 📖 Source)
- `brand` — pinned on the job
- `family` — model family shown on the pin
- `models` — tokens used for matching / display
- `categories` — substrings that may appear in the job category
- `manual.document_code` — OEM doc number when the SM has one
- `match` — see engine (`any` contains/regex, optional `or_category_and_model`)
- `flags` + `start_rules` + `default_start` — pick the first gate from tech text
- `nodes` — every node must have `id`, `type`, `prompt`, `source_title`, `source_page`, `edges`

Node types: `binary` (Yes/No or Pass/Fail), `multi` (named results), `gate`, `end`.

Optional on a node:

- `reading` — parse a meter value (`unit`, `regex`, `compare`, edges)
- `map_hints.pre_alias` / `map_hints.rules` — phrase/regex → edge key
- `reask_preface` — shown when the tech answer does not match an edge

## Adding a tree

See `NEXT_MANUAL_TREE.md`. If the SM flowchart is not in the library with page
numbers, stop. Do not scaffold fake nodes.
