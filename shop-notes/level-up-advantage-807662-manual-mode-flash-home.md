# Level Up controller — Manual Mode flash-home / Firefly

**What to call it:** the Level Up controller (same job across several OEM part numbers)  
**Coach context:** Brinkley with a Firefly / OneControl panel on the same network  
**Narrow path only** — this is not a Firefly encyclopedia.

## Complaint

Manual Mode on the Level Up pad flashes, then dumps back to the home screen.
Auto Level (or the other pad functions) still work.

## Cheap proves first

Confirm power looks sane and there is no brownout.
Confirm Auto Level, or the other pad functions, still work.
Confirm the dump is not sticky Low Voltage, Excess Angle, or External Sensor text.
Clear those first if they are present.

Do not open a board or LCD swap first when Auto Level still works.

## Firefly-cable prove

The Level Up controller has two network plugs. One has a rubber boot on it — leave that one alone. The other has a cable running to the Firefly / OneControl system — unplug that cable only. Then try Manual Mode again.

### Manual Mode holds (Firefly / OneControl confirmed)

Reconnect the Firefly cable after this prove unless you are using the interim below.
The real fix is a Firefly USB firmware update.
Read GUI and CCM from Settings.
Call Firefly at 574-825-4600.
Use a USB stick 4 GB or smaller plus the interim file they specify.
Interim: turn the front-bay main battery switch OFF (solar can stay ON) so Firefly drops, or leave the Firefly cable unplugged with the rubber-boot plug still in.

### Manual Mode still dumps (not this issue)

Stay on the Level Up sensor and harness path.
Do not swap another Level Up controller for Firefly blame.
Do not push a Firefly USB firmware update as the fix.

## Known bay prove (2026-09-16)

Board and LCD were swapped with no change. Power, Zero Point, and the remote sensor were not the root.
Unplugging the Firefly cable (rubber-boot plug left in) made Manual Mode hold.
Reconnecting the Firefly cable brought the dump back.
Root: Firefly / OneControl conflict aborting Manual Mode only.
