# Heat Dissipation Failure — Maintenance Procedure

**Failure Code**: HDF  
**Risk Level**: High — can escalate to thermal runaway if not addressed  
**Typical Sensor Signature**: High process temperature relative to air temperature; rotational speed within range; moderate torque

---

## 1. Immediate Actions (First 15 minutes)

1. **Reduce machine load by 50%** or halt the machining cycle if safe to do so.
2. **Check the temperature delta**: Process temperature minus air temperature should not exceed 8.6 K under normal operation. Values above 12 K indicate cooling failure.
3. **Do not power off suddenly** — allow the spindle to decelerate gradually to avoid bearing shock.
4. **Alert the maintenance supervisor** and log the machine ID and timestamp.

---

## 2. Diagnostic Checklist

### 2.1 Cooling Fan Inspection
- [ ] Visually confirm all cooling fans are spinning (no stalled blades).
- [ ] Measure fan RPM with a tachometer — compare to nameplate spec (typically 1200–2400 RPM).
- [ ] Check fan blade condition: cracks, bent blades, or debris buildup reduce airflow by up to 40%.
- [ ] Inspect fan motor bearings: replace if audible grinding or vibration detected.

### 2.2 Heat Exchanger / Radiator
- [ ] Check fins for debris accumulation (metal chips, coolant residue, dust).
- [ ] Use compressed air at 60 PSI to blow out fins — direct airflow from clean side to dirty side.
- [ ] Inspect coolant lines for kinks, blockages, or mineral scaling.
- [ ] Verify coolant level in reservoir — top up with manufacturer-specified coolant mix.

### 2.3 Thermal Paste / Interface Material (applies to spindle motor)
- [ ] If fan and heat exchanger are clear, the thermal interface may have dried out.
- [ ] Shut down and lock out/tag out before disassembly.
- [ ] Clean mating surfaces with isopropyl alcohol (99%).
- [ ] Apply fresh thermal paste (5 W/m·K or better) — pea-sized bead, centre spread method.

### 2.4 Ambient Temperature
- [ ] Verify facility HVAC is operating — ambient above 30°C degrades cooling efficiency significantly.
- [ ] Check that machine is not positioned in a hot zone (direct sunlight, near furnaces).

---

## 3. Repair Procedure

### Parts Required
| Part | Qty | Part Number (example) |
|---|---|---|
| Cooling fan assembly | 1–2 | Refer to machine BOM |
| Coolant (5L) | 1 | ISO 15 or OEM spec |
| Thermal paste | 1 tube | Arctic MX-4 or equivalent |
| Fan motor bearings | 2 | 6202-2RS (verify with BOM) |

### Steps
1. Isolate machine: turn off power, apply lockout/tagout.
2. Open rear panel (4× M6 bolts, 10 mm socket).
3. Disconnect fan connectors (mark with tape to avoid swap).
4. Remove fans (2× M4 screws each) — note orientation arrow on housing.
5. If replacing fan motor: extract snap ring, press out bearing with bearing puller.
6. Install new bearing (press fit, ensure flush seating).
7. Reinstall fans — orientation must match original airflow direction.
8. Flush coolant circuit: drain, flush with clean water, refill with fresh coolant.
9. Clean heat exchanger fins with compressed air.
10. Reassemble, restore power, run 10-minute warm-up cycle.
11. Monitor temperature delta: should stabilise below 9 K within 5 minutes.

---

## 4. Verification & Sign-Off

- [ ] Process temperature delta < 9 K at operational load.
- [ ] All fans spinning at rated RPM.
- [ ] Coolant level at MAX mark.
- [ ] No coolant leaks visible after 30-minute run.
- [ ] Log repair in CMMS with parts used and technician ID.

---

## 5. Preventive Schedule

| Interval | Action |
|---|---|
| Weekly | Visual check: fan rotation, coolant level |
| Monthly | Clean heat exchanger fins with compressed air |
| Quarterly | Flush and replace coolant |
| Annually | Replace cooling fans (or at first sign of bearing noise) |
| 3 years | Full thermal interface material replacement |
