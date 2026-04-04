# Power Failure — Maintenance Procedure

**Failure Code**: PWF  
**Risk Level**: High — electrical faults can cause fire, arc flash, or data loss  
**Typical Sensor Signature**: Rotational speed drops sharply; torque fluctuates abnormally; temperature within range

---

## 1. Immediate Actions

> **SAFETY FIRST**: All electrical work requires qualified personnel. Do not probe live circuits without appropriate PPE (arc flash rated gloves, face shield, insulated tools).

1. **Do not attempt to restart** the machine immediately — cycling power on a faulted PSU can worsen damage.
2. **Check for visible signs**: burning smell, tripped breakers, LED fault codes on the control panel.
3. **Isolate the machine**: open the main disconnect switch (lockout/tagout before any inspection).
4. **Call the electrical maintenance team** if any arc marks, melted insulation, or tripped GFCI breakers are found.

---

## 2. Diagnostic Checklist

### 2.1 Facility Power Supply
- [ ] Check the distribution board: confirm circuit breaker for this machine is not tripped.
- [ ] Measure input voltage at the machine's main terminal block — should be within ±10% of rated voltage (typically 400 V ± 40 V three-phase).
- [ ] Check all three phases: single-phase loss causes motors to overheat and stall.

### 2.2 Power Supply Unit (PSU) / Servo Drive
- [ ] Check PSU status LED: solid red = internal fault; flashing = overload; no light = no input power.
- [ ] Measure PSU output DC rails with a multimeter (typically +24 VDC, +5 VDC for control logic).
- [ ] Check for blown fuses on the PSU input board — replace with identical rated fuse only.
- [ ] Inspect capacitors on PSU board for bulging, leaking, or burn marks.

### 2.3 Wiring and Connectors
- [ ] Inspect all terminal connections for looseness — torque to spec (typically 1–2 N·m for M4 terminals).
- [ ] Look for chafed cable insulation around moving parts (cable chains, drag chains).
- [ ] Measure insulation resistance between phase conductors and earth ground (>1 MΩ = acceptable).

### 2.4 Motor Windings
- [ ] Measure winding resistance of all three phases — values should be balanced within 5% of each other.
- [ ] Megger test at 500 VDC: >10 MΩ = healthy; <1 MΩ = winding failure risk.

---

## 3. Repair Procedure

### Common Repairs

#### Blown Fuse
1. Identify fuse rating from control panel documentation (do NOT upsize).
2. Replace with exact same type (ceramic, fast-blow, or slow-blow as specified).
3. If fuse blows again immediately after replacement: investigate upstream fault before replacing again.

#### PSU Replacement
1. Photograph all wiring connections before disconnecting.
2. Disconnect input and output terminals (label wires with masking tape).
3. Remove PSU from DIN rail or mounting bracket.
4. Install replacement PSU — verify model compatibility.
5. Reconnect wiring per documentation/photograph.
6. Power up and measure output voltages before reconnecting load.

#### Loose Terminal / Connector
1. Re-torque terminal screws to manufacturer specification.
2. Apply contact cleaner spray to corroded connectors.
3. Replace crimp terminals if wire strands show corrosion or breakage.

---

## 4. Verification & Sign-Off

- [ ] Input voltage within ±10% of rated.
- [ ] All three phases balanced within 3%.
- [ ] PSU output rails within ±5% of rated DC voltage.
- [ ] No fault codes on CNC/PLC control panel.
- [ ] Machine runs 5-minute test cycle without interruption.
- [ ] Log repair in CMMS: fault code, parts replaced, technician ID.

---

## 5. Preventive Schedule

| Interval | Action |
|---|---|
| Monthly | Inspect cable chains for wear; check breaker panel for signs of heat |
| Quarterly | Torque-check all terminal connections in control cabinet |
| Annually | Megger test motor windings; check PSU capacitor condition |
| 5 years | Replace electrolytic capacitors in PSU (service life limit) |
