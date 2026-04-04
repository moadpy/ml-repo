# Tool Wear Failure — Maintenance Procedure

**Failure Code**: TWF  
**Risk Level**: Medium — worn tools degrade part quality and can damage spindle if tool breaks  
**Typical Sensor Signature**: High tool_wear_min (>200 min); process temperature elevated; torque trending upward over time

---

## 1. Immediate Actions

1. **Stop the current machining cycle** at the end of the current pass (do not stop mid-cut if possible — abrupt stops can cause tool breakage or gouge the workpiece).
2. **Retract and inspect the tool** — look for flank wear, built-up edge, chipping, or breakage.
3. **Quarantine the last produced part** for dimensional inspection before resuming production.
4. **Log the tool wear time** from the CNC controller's tool life management system.

---

## 2. Tool Condition Assessment

### Wear Indicators

| Indicator | Acceptable | Marginal — Replace Soon | Failed — Replace Now |
|---|---|---|---|
| Flank wear (Vb) | < 0.2 mm | 0.2–0.3 mm | > 0.3 mm |
| Crater depth | < 0.1 mm | 0.1–0.15 mm | > 0.15 mm |
| Surface finish (Ra) | ≤ design spec | 110–130% of spec | > 130% of spec |
| Tool wear time | < 80% of rated life | 80–100% | > 100% |

Use a pocket tool magnifier (10×) or tool measurement microscope for accurate assessment.

---

## 3. Tool Replacement Procedure

### 3.1 Standard Indexable Insert Replacement (most common)

1. Lock out / tag out — or use safe tool change mode on the CNC (if supported).
2. Clean the tool holder with a lint-free cloth — remove chips and coolant residue.
3. Remove worn insert: use the correct torx/hex key (typically T15 or T20).
4. Inspect the insert seat and shim: replace shim if deformed or cracked.
5. Install new insert: align correctly with the locating notch/pin.
6. Torque the clamping screw to manufacturer spec — typically 2–4 N·m (do not overtighten).
7. Update the tool life counter in the CNC tool management system (reset to 0 minutes).

### 3.2 Solid Carbide End Mill Replacement

1. Use appropriate collet wrench and collet spanner — do not grip on flutes.
2. Clean collet chuck bore with a bore brush before installing new tool.
3. Insert tool to the correct gauge length (refer to setup sheet).
4. Torque collet nut to spec (typically 30–50 N·m for ER collets — refer to collet size chart).
5. Measure tool runout at the tip with a dial indicator (< 0.005 mm required).

### 3.3 Drill Replacement

1. Check drill point geometry — if not resharpened, use new drill.
2. For centre-lock drills: align flat before tightening set screw.
3. Ensure drill depth stop is set correctly for the new drill (length may vary slightly).

---

## 4. Toolpath Recalibration (if changing tool grade or geometry)

When switching to a different insert grade or geometry:
- Update the feed rate and cutting speed in the NC programme (consult new tool's cutting data).
- Run a first-part inspection with dimensional measurement before resuming full production.
- Monitor torque for the first 10 minutes — new sharp tools typically show lower torque than the failed tool.

---

## 5. Tool Life Management

### CNC Tool Life Setup
- Set maximum tool life (in minutes) per tool station — use 90% of manufacturer's rated life as a safe threshold.
- Enable automatic tool change (ATC) when life limit is reached, if machine supports it.
- Configure duplicate tool stations for high-frequency tools to enable unattended operation.

### Tracking
- Record all tool changes in the CMMS: tool ID, machine, station, wear time at replacement.
- Review monthly tool consumption data to identify premature wear patterns — may indicate cutting parameter issues or material hardness variability.

---

## 6. Verification & Sign-Off

- [ ] New tool installed and torqued correctly.
- [ ] Tool life counter reset in CNC controller.
- [ ] First part dimensional inspection passed.
- [ ] Torque and surface finish within specification during first 10-minute run.
- [ ] Tool change logged in CMMS.

---

## 7. Preventive Schedule

| Interval | Action |
|---|---|
| Per tool life cycle | Inspect at 80% of rated life — replace or index insert |
| Daily | Review tool life monitor for tools approaching limit |
| Monthly | Audit tool consumption report for anomalies |
| Quarterly | Review and update tool life parameters based on historical data |
