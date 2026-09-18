# Level Up Advantage 807662 — Manual Mode flash-home / Firefly CAN

**Controller:** Lippert Level Up Advantage `807662` (similar Level Up pads)  
**Coach context:** Brinkley + Firefly/OneControl on coach CAN  
**Narrow path only** — not a Firefly encyclopedia.

## Complaint

Manual Mode on the Level Up / leveling pad flashes then dumps back to home.
Auto Level (or other pad functions) still work.

## Cheap proves first

- Power looks sane / no brownout.
- Auto Level (or other pad functions) still work.
- Dump is not sticky **Low Voltage** / **Excess Angle** / **External Sensor**.
  Clear those first if they are present.

Do not open board / LCD swap first when Auto Level still works.

## CAN prove

1. Leave the rubber-boot **terminator** plugged in.
2. Unplug only the **wired** coach CAN (Firefly/OneControl).
3. Retry Manual Mode.

### Manual stays (Firefly/CAN confirmed)

- Reconnect the wired CAN after this prove unless using the interim below.
- **Real fix:** Firefly USB firmware update.
  - Read **GUI** and **CCM** from Settings.
  - Call Firefly **574-825-4600**.
  - USB stick **4 GB or smaller**.
- **Interim:** front-bay main battery switch OFF (solar can stay ON) so Firefly drops,
  **or** leave wired CAN unplugged with the terminator in.

### Manual still dumps (not this issue)

- Stay on the Lippert sensor / harness / support path.
- Do **not** swap another 807662 for Firefly blame alone.
- Do **not** push a Firefly USB firmware update as the fix.

## Known bay prove (2026-09-16)

Board + LCD swapped — no change. Power / Zero Point / remote sensor — not root.
Wired coach CAN unplugged (terminator left in) → Manual Mode stays.
Wired CAN reconnected → Manual dump returns.
Root: Firefly/OneControl CAN conflict aborting Manual Mode only.
