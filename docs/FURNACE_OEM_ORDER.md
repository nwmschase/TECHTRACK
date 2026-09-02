# Furnace OEM order (TechTrack)

When category is **Furnaces** or the item/model/concern is a furnace (especially Dometic / Atwood / Suburban), Guided Diagnostics and Ask TechTrack must start almost first with these checks. Do not wait for the tech to type "sail switch".

## Mandatory first sequence

1. **Bypass the wall thermostat at the furnace**
   - Jumper the furnace thermostat terminals, or apply a known-good heat call at the furnace.
   - Purpose: take a bad wall t-stat / AC climate board / t-stat wiring out of the path.
   - Confirm the furnace blower starts from that local call.

2. **Sail-switch power IN vs OUT while the blower is running**
   - Typical circuit is 12 VDC. Sail and high-limit are often in series.
   - **IN present, OUT absent** with blower running = sail not closed (bad/mis-set switch, paddle not in the airstream, or not enough airflow).
   - **IN absent** = do not condemn the sail yet (call circuit, wiring, board, or open high-limit).

3. **If IN is good and OUT is dead**
   - Watch the paddle move.
   - Dirty squirrel-cage blower, restricted return or exhaust, low voltage under load (need about 10.5–13.5 VDC at the furnace while running).
   - Then high-limit in series.
   - Replace the sail only after those checks or a failed manual-actuate / continuity test.

4. **Temporary sail jumper is diagnostic only**
   - Jump only after the blower is already running.
   - Never jump before the motor starts (board lockout).
   - Never leave a safety switch jumped.

5. **Only after the t-stat-bypass + sail/limit path is proven**
   - Electrode / igniter, gas pressure / valve, flame sense.

## Trigger concerns

Fan runs / will not light / no heat / airflow fault / 1-flash limit on a Dometic furnace must get steps 1–2 as the first recommended inspections even if the tech did not name the sail switch.

## Code

Implemented in `rv_techtrack.py` (Guided Diagnostics system prompt rule 5b, Ask TechTrack rule 11, search-term boost, and furnace context injection). Apply `furnace-oem-order.patch` on `main` if the full file was not merged yet.
