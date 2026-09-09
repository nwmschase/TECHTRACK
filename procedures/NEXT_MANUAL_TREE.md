# Next hard flowchart tree (do not invent)

TechTrack encodes **only** shop-library service-manual decision diamonds.
This repo does **not** contain a second OEM flowchart. Do not add a Norcold,
Dometic, Lippert, Suburban, or Atwood tree from memory.

## What is encoded today

| Procedure id | Brand / family | Shop library title | Flowchart pages used |
|---|---|---|---|
| `furrion_fcr_ccd_0008122` | Furrion FCR08 / FCR10 / FCR10DCGTA | Furrion FCR08/FCR10 SM CCD-0008122 | Sec1 fuse **p.19**; supply volts **p.20**; dial **p.23**; Gen TS battery ≥10.5V **p.12**; paper + operating? **p.33**; Not Cooling **p.34**; Fan Fault F+/F− **p.27 only** |

Fan F+/F− supply volts live on the Fan Fault flash-code path (p.27) only — never after the paper test.

## What is not a tree (yet)

- **Furnace OEM order** (thermostat bypass → sail-switch IN/OUT) lives in the AI coach prompt and in the open `furnace-oem-order` PR notes. That is shop coaching, **not** a page-cited hard diamond tree.
- Slides / awnings / leveling / water heater / LP / brakes / electrical have **no** in-repo flowchart and no library-catalog metadata in git (library PDFs live in R2, not this repo).
- Skip microwaves and entertainment.

## What to add next

Encode the **next shop-mainstay** only after a real SM flowchart is in the Document Library and you can name:

1. **Brand + model family** (example: Lippert Level-Up / OneControl Unity, or Dometic furnace).
2. **Exact Document Library title** as indexed (not “the PDF the tech uploaded”).
3. **Page numbers of the diagnostic flowchart** (decision diamonds / Pass-Fail gates), not a spec sheet or parts list.

Preferred shop-mainstay order once those cites exist:

1. Lippert leveling / slides / awnings (OneControl / Unity) — high floor volume; Unity gate already exists in chat.
2. Dometic / Atwood / Suburban furnace — AI already coaches bypass + sail; needs the SM diamond pages to become a hard tree.
3. Water heater, LP, brakes, or 12V/120V electrical — same cite rule.

Drop a new `procedures/<id>.json` that matches `README.md`. The engine loads every `*.json` in this folder except `_*.json`. No Python rewrite is required for a second real tree.
