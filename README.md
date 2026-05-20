# EnergyLens — Operational Intelligence for Buildings

> **Buildings don't just waste energy when they fail. They waste energy even when everything is working perfectly.**

EnergyLens is an operational analytics platform that identifies energy your building didn't need to use — by asking a question that no existing system asks:

**Was this energy operationally necessary?**

---

## The Problem

Building Management Systems (BMS) control HVAC and building systems according to schedules and logic rules. Energy Management Systems (EMS) measure and report consumption. Fault Detection and Diagnostics (FDD) tools flag equipment failures.

But none of them evaluate *necessity*.

The result: buildings routinely waste energy with **zero alarms, zero faults, and zero visibility** — because the system was operating exactly as programmed, just not as needed.

Common examples:
- HVAC running for 6 hours after a building empties — no fault triggered
- Simultaneous heating and cooling in adjacent zones — no alarm raised
- Systems operating through public holidays and weekend shutdowns — completely invisible

This is what EnergyLens is built to find.

---

## How It Works

EnergyLens sits as a **read-only analytics layer** on top of existing BMS/EMS infrastructure. No new hardware. No system changes. No IT risk.

```
Step 1 — Ingest
BMS operational data + optional contextual inputs (schedules, occupancy, weather)

Step 2 — Detect
Cross-reference actual system behaviour against operational demand
Flag periods of unjustified runtime, overcooling, simultaneous heating/cooling, and schedule drift

Step 3 — Report
Plain-language findings prioritised by dollar, kWh, and carbon impact
```

### Detection Logic (Current Implementation)

```python
# Core pattern: Schedule Drift Detection
if hvac_status == "ON" and hour not in scheduled_hours:
    flag_as_ghost_runtime()
    calculate_energy_and_cost_impact()
    estimate_carbon_footprint()
```

The current prototype implements multiple waste detection scenarios including:
- **Schedule Drift** — HVAC operating outside occupancy hours
- **Excessive Cooling** — Sub-setpoint hunting consuming energy beyond comfort requirements
- **Ghost Runtime** — Systems active with zero occupancy demand

---

## Example Impact

Conservative estimate for a standard 10,000m² commercial facility:

| Scenario | Daily | Monthly | Annual |
|----------|-------|---------|--------|
| 6hrs unnecessary HVAC runtime | $150 | $4,500 | **$54,000** |
| Carbon impact (NZ grid avg) | 72 kg CO₂e | 2.2t CO₂e | **~26t CO₂e** |

*No faults. No alarms. No flags. Operating as programmed — not as needed.*

---

## What's Built

This repository contains the working proof-of-concept dashboard built with Python and Streamlit:

| File | Description |
|------|-------------|
| `HVAC_Scenarios_final_v5.py` | Core scenario detection engine (latest) |
| `HVAC_Scenarios_final_v*_NZ.py` | NZ electricity rate and carbon factor variants |
| `command_center.py` | Multi-scenario operational dashboard |
| `wallboard.py` | Live operational display view |
| `HVAC_Scenarios_real_time_alerts.py` | Real-time alert detection prototype |
| `report_utils.py` | Findings report generation |
| `app_utils.py` | Shared utilities |

### Tech Stack
- Python, Streamlit
- Operational pattern detection logic
- NZ-specific carbon and electricity rate modelling
- CSV-based data ingestion (BMS export format)

---

## Current Status

✅ Working proof-of-concept dashboard  
✅ Multiple waste detection scenarios implemented  
✅ NZ electricity and carbon factor modelling  
✅ Scenario-based findings with cost, kWh, and CO₂e outputs  
✅ Selected for University of Auckland Velocity Ideas Challenge  
✅ Reviewed by Auckland Momentum Investment Committee  

🔄 Seeking first pilot partner for real building data validation  
🔜 BMS/EMS API integration (next phase)  
🔜 Weather-normalised baseline modelling  
🔜 Multi-building portfolio view  

---

## Differentiation

| Tool | What it does | What it misses |
|------|-------------|----------------|
| BMS | Controls systems | Doesn't question necessity |
| EMS | Reports energy usage | Doesn't evaluate operational context |
| FDD | Detects equipment faults | Misses operational inefficiency |
| **EnergyLens** | **Asks: was this necessary?** | — |

---

## Running the Prototype

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main dashboard
streamlit run command_center.py

# Or run a specific scenario
streamlit run HVAC_Scenarios_final_v5.py
```

---

## Pilot Opportunities

EnergyLens is actively seeking pilot partners — universities, hospitals, commercial building operators, or facilities management teams — willing to share anonymised BMS export data for a no-cost 4-week analysis.

**What's involved:** Read-only access to existing BMS/EMS data exports. No system access. No hardware. You receive a full findings report regardless of outcome.

If this is relevant to your organisation, reach out: **rvij007@aucklanduni.ac.nz**

---

## About

EnergyLens is an early-stage operational intelligence startup focused on reducing unnecessary energy use in commercial buildings across New Zealand and beyond.

**Founder:** Ravi Raj — background in industrial automation, real-time operational systems, and AI.  
**Website:** [energylens.co.nz]()
