# Random Failure — Maintenance Procedure

**Failure Code**: RNF  
**Risk Level**: Variable — requires full diagnostic to assess  
**Typical Sensor Signature**: No clear dominant sensor anomaly; prediction confidence often lower (orange/red boundary); stochastic pattern

---

## 1. Understanding Random Failures

Random failures (RNF) are stochastic faults with no clear deterministic root cause from sensor data alone. They may represent:
- Intermittent component defects (connection, relay, sensor)
- Environmental anomalies (vibration from adjacent equipment, power line transients)
- Random software/firmware faults in CNC controller
- Sensor noise flagged as a pattern

**Do not assume the machine is fine just because no obvious cause is found.** A full diagnostic inspection is mandatory.

---

## 2. Immediate Actions

1. **Stop the machine** and retract the tool to home position.
2. **Document everything**: capture the fault code, sensor readings, time, machine ID, and the current operation being performed.
3. **Do not restart without completing at least the Level 1 diagnostic** (Section 3.1).
4. **Inform the maintenance supervisor** — random failures that recur within 24 hours indicate a systemic issue.

---

## 3. Diagnostic Protocol — Three Levels

### Level 1: Quick Checks (15–30 min) — Do First

- [ ] Check all CNC fault codes and alarm history (Settings → Alarm Log on controller).
- [ ] Inspect all external connections: Ethernet, encoder cables, servo drive connectors — reseat if any feel loose.
- [ ] Check for environmental interference: is another nearby machine creating vibration or EMI?
- [ ] Verify coolant level and pressure — low coolant causes thermal sensors to trip false alarms.
- [ ] Run a 5-minute dry cycle (air cut, no workpiece) and observe if fault recurs.

**If dry cycle passes without fault**: likely a workpiece interaction or one-time transient. Resume with monitoring. Log the occurrence.

**If fault recurs during dry cycle**: proceed to Level 2.

### Level 2: Component Inspection (1–3 hours)

- [ ] Inspect all sensor cables for chafing (especially near cable chains).
- [ ] Check servo drive status LEDs and error codes — consult drive manufacturer's fault code table.
- [ ] Measure control logic supply voltages (+24 VDC, +5 VDC) — voltage sag below ±5% of rated indicates PSU issue.
- [ ] Check the machine earth ground continuity — poor earth causes intermittent noise-induced faults.
- [ ] Inspect the control cabinet interior: any signs of moisture, insect ingress, or heat damage.
- [ ] Review the vibration profile if an accelerometer is fitted — compare to baseline.

### Level 3: Full Diagnostic (engineer + specialised tools required)

- [ ] Request service report from CNC manufacturer using the downloaded fault log.
- [ ] Perform thermal imaging of control cabinet to identify hot spots.
- [ ] Perform insulation resistance test on all motors and drive outputs.
- [ ] Check all PLC I/O modules for failed channels (use diagnostic mode).
- [ ] Engage OEM field service if fault is not identified within Level 2.

---

## 4. Escalation Path

```
Level 1 fails → Level 2 diagnostic
Level 2 fails → Level 3 + OEM escalation
OEM identifies root cause → Targeted repair
Root cause not found after OEM → Consider machine replacement/refurbishment
```

---

## 5. Recurring Random Failure Protocol

If RNF occurs more than **3 times within 30 days**:
1. Escalate immediately to reliability engineer.
2. Install temporary vibration/power quality monitoring equipment.
3. Review operational context: shift changes, new operators, recent maintenance, new material batches.
4. Consider reliability-centred maintenance (RCM) analysis for this machine.
5. Evaluate MTBF (Mean Time Between Failures) — if declining trend, plan replacement.

---

## 6. Verification & Sign-Off

- [ ] Fault not reproducible after diagnostic.
- [ ] Machine passes 30-minute test run under normal production conditions.
- [ ] All findings documented in CMMS with fault code, diagnostic steps taken, and outcome.
- [ ] If no root cause found: flag machine as "under observation" in CMMS for 7-day monitoring period.

---

## 7. Documentation Requirements

For every random failure event, the CMMS record must include:
- Machine ID, timestamp, operator on shift
- Sensor readings at time of fault (from CNC log)
- ML prediction confidence score
- All diagnostic steps performed and their outcomes
- Parts replaced (if any)
- Resolution: fixed / no fault found / escalated
