# Preventive Maintenance — Scheduled Maintenance Programme

**Document Type**: Scheduled maintenance intervals for all machine types (L/M/H)  
**Review Cycle**: Annually or after any major repair  
**Applies To**: All machines monitored by the Predictive Maintenance Platform

---

## 1. Daily Checks (Operator Responsibility — 10 min per shift)

| Check | Action | Threshold |
|---|---|---|
| Coolant level | Check reservoir sight glass | Above MIN mark |
| Lubrication | Check central lube oil level | Above MIN mark |
| Air pressure | Read pneumatic pressure gauge | Within green zone (typically 5–7 bar) |
| Chip conveyor | Clear chips from conveyor and collection bin | No overflow |
| Spindle warm-up | Run 5-min warm-up programme | No unusual noise or vibration |
| Fault codes | Check controller alarm history | No active alarms |

---

## 2. Weekly Checks (Maintenance Technician — 1 hour)

| Check | Action |
|---|---|
| Coolant concentration | Measure with refractometer — adjust to 6–8% (consult SDS) |
| Coolant pH | Measure with pH strips — should be 8.5–9.5; discard if below 8.0 |
| Way lubrication | Inspect linear guide lubrication nipples; apply grease if dry |
| Chip conveyor belt | Inspect belt condition; tension if slack |
| Cooling fans | Verify all fans spinning; clean debris from fan grilles |
| Electrical cabinet | Inspect door seal; check for moisture or heat |

---

## 3. Monthly Checks (Maintenance Technician — 2–3 hours)

| Check | Action |
|---|---|
| Belt tension | Check all drive belts with tension meter; tension to spec |
| Filter replacement | Replace hydraulic filter, coolant filter, and air filter elements |
| Heat exchanger | Clean fins with compressed air |
| Tool holders | Inspect all tool holder bores and retention knobs for wear |
| Spindle runout | Measure with dial indicator — should be < 0.005 mm |
| Axis backlash | Run backlash compensation test cycle |
| Terminal connections | Re-torque all control cabinet terminals to spec |

---

## 4. Quarterly Checks (Maintenance Engineer — 4–6 hours)

| Check | Action |
|---|---|
| Gearbox oil | Drain and refill with OEM-specified oil |
| Linear guide lubrication | Full re-greasing of all linear guides and ball screws |
| Motor insulation | Megger test all servo motors (>10 MΩ target) |
| Hydraulic oil | Sample for particle count analysis; replace if ISO 18/16/13 exceeded |
| CNC battery | Check backup battery voltage (> 3.0 V); replace if below 2.8 V |
| Servo drive calibration | Run axis calibration cycle from controller diagnostic menu |
| Tool life database | Audit tool life records — update thresholds based on 3-month data |

---

## 5. Annual Overhaul (Maintenance Engineer + Specialist — 2 days)

| Check | Action |
|---|---|
| Full coolant system flush | Drain, flush with biocide, clean reservoir, refill with fresh coolant |
| Spindle bearing inspection | Measure bearing preload; replace if play detected |
| Ball screw inspection | Measure positioning accuracy with laser interferometer |
| Complete lubrication overhaul | Full stripdown and regreasing of all moving joints |
| Electrical wiring audit | Inspect all wiring for insulation condition; replace suspect cables |
| PSU capacitor check | Measure capacitance of electrolytic capacitors; replace if >20% degraded |
| Safety system test | Full function test of all E-stops, light curtains, and interlocks |
| Calibration certificate | Annual dimensional calibration; issue calibration certificate |

---

## 6. Sensor Calibration Schedule

The predictive maintenance ML model depends on accurate sensor readings. Calibrate sensors on the following schedule:

| Sensor | Calibration Method | Interval |
|---|---|---|
| Temperature (air + process) | Compare to calibrated reference thermometer | Semi-annually |
| Rotational speed | Compare to optical tachometer | Annually |
| Torque | Compare to torque reference cell | Annually |
| Tool wear counter | Reset after each tool change (manual verification) | Per tool change |

If a calibrated sensor drifts by more than 2% from reference, replace the sensor and re-baseline the ML model with corrected data.

---

## 7. Machine Type Specific Notes

### Type L (Light Duty)
- Primarily high-speed operations — prioritise spindle bearing checks.
- Cooling demand is lower but thermal cycling is faster — check thermal interface material annually.

### Type M (Medium Duty)
- Standard maintenance intervals as described above.
- Monitor torque trending monthly — medium-duty machines most often show overstrain failure patterns.

### Type H (Heavy Duty)
- Increase gearbox oil change to monthly during heavy production periods.
- Check drive belt condition bi-weekly (higher load = faster belt fatigue).
- Annual ball screw replacement if positioning error exceeds 0.01 mm.

---

## 8. Maintenance Records

All preventive maintenance activities must be recorded in the CMMS (Computerised Maintenance Management System) with:
- Machine ID
- Date and technician ID
- Items checked and outcome
- Parts replaced (part number, quantity, cost)
- Next due date

Failure to log completed maintenance removes the machine from the predictive model's trusted baseline — sensor readings from unlogged machines are flagged as unreliable.
