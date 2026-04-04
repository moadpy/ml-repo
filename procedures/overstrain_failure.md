# Overstrain Failure — Maintenance Procedure

**Failure Code**: OSF  
**Risk Level**: Medium-High — mechanical overload can damage spindle, drive belt, or gearbox  
**Typical Sensor Signature**: Torque significantly above rated value; rotational speed lower than set point; tool wear may be within normal range

---

## 1. Immediate Actions

1. **Stop the machining cycle immediately** — do not attempt to complete the current pass.
2. **Retract the tool** to a safe home position before powering down.
3. **Do not apply manual force** to a jammed spindle — this can shear keys or snap shafts.
4. **Record the torque reading** at time of fault from the CNC controller fault log.

---

## 2. Root Cause Categories

| Root Cause | Symptoms | Corrective Action |
|---|---|---|
| Excessive cutting depth/feed rate | Torque spike at start of cut | Reduce feed rate / depth of cut |
| Dull/broken cutting tool | Torque rises progressively | Replace tool (see Tool Wear Failure procedure) |
| Workpiece material harder than expected | Torque consistently high | Adjust cutting parameters for material grade |
| Drive belt slipping | Torque reported high but actual cut is light | Inspect and tension drive belt |
| Gearbox damage | Grinding noise + high torque | Inspect gearbox — may require overhaul |
| Incorrect tool holder runout | Vibration + torque oscillation | Check runout with dial indicator |

---

## 3. Diagnostic Checklist

### 3.1 Cutting Parameters Audit
- [ ] Review the NC programme: confirm feed rate (mm/min) and depth of cut (mm) are within the tool manufacturer's recommended range for the material being cut.
- [ ] Compare torque demand at fault to machine rated torque — if fault torque > 110% of rated, overload is genuine; if < 90% rated, sensor or drive issue is more likely.

### 3.2 Drive Belt / Chain Inspection
- [ ] Open the belt cover with machine locked out.
- [ ] Measure belt tension with a belt tension meter — refer to machine BOM for target Hz.
- [ ] Inspect belt for cracking, fraying, oil contamination, or tooth shear (for toothed belts).
- [ ] Check drive and driven pulleys for wear grooves.

### 3.3 Gearbox Inspection
- [ ] Check gearbox oil level via sight glass — low oil = increased wear and overload.
- [ ] Listen for abnormal noise during no-load run: whining = gear wear; knocking = broken tooth.
- [ ] Sample gearbox oil for metal particle analysis (ferrography) if noise is present.

### 3.4 Spindle and Bearings
- [ ] Rotate spindle by hand with machine locked out — should be smooth, no grittiness.
- [ ] Measure spindle runout with a dial indicator — should be < 0.005 mm (5 microns) for precision machines.
- [ ] Listen for bearing noise during low-speed run (100–200 RPM) — rumbling indicates bearing wear.

---

## 4. Repair Procedure

### Drive Belt Replacement
1. Lock out / tag out machine.
2. Remove belt cover (note all bolt sizes and locations).
3. Loosen motor mounting bolts to release belt tension.
4. Remove worn belt — photograph routing before removal.
5. Install new belt (same part number — do not substitute).
6. Adjust motor position to achieve target belt tension.
7. Torque motor mounting bolts to spec.
8. Run 5-minute warm-up at reduced feed; re-check belt tension after warm-up (belts seat during first use).

### Gearbox Oil Service
1. Drain gearbox via drain plug (capture oil for disposal — do not pour down drain).
2. Flush with flushing oil if contamination is suspected.
3. Refill with OEM-specified gear oil (ISO VG 220 or as specified) to the MAX mark on sight glass.
4. Run at low speed for 10 minutes and re-check oil level.

---

## 5. Programme Correction (if root cause is cutting parameters)

Update the NC programme:
- Reduce feed rate by 20–30% for the affected operation.
- Reduce depth of cut to a maximum of 2× tool diameter for end milling.
- Add a roughing pass before finishing if material is hard.
- Consult the tool manufacturer's cutting data guide for the specific material grade (ISO designation).

---

## 6. Verification & Sign-Off

- [ ] Torque reading at rated cutting conditions is within 80–100% of rated torque.
- [ ] No abnormal noise from gearbox or spindle at operating speed.
- [ ] Belt tension within spec (verify with tension meter after 30-minute run).
- [ ] Machine completes a full test cycle without fault.
- [ ] Log repair in CMMS with root cause, parts replaced, and parameter changes.

---

## 7. Preventive Schedule

| Interval | Action |
|---|---|
| Daily | Review CNC torque monitor — flag runs >90% of rated |
| Monthly | Check belt tension; inspect belt for wear |
| Quarterly | Change gearbox oil (or per OEM interval) |
| Annually | Full spindle runout measurement; bearing noise assessment |
