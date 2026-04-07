# HVAC Energy Wastage Detection (Infralytix – Proof of Concept)

## Overview

This project is an initial proof-of-concept developed as part of the **Infralytix (EnergyLens)** idea, which aims to identify potential inefficiencies in HVAC system operation using data-driven analysis.

In large facilities, HVAC systems often operate correctly according to control logic but may still consume energy during periods where operational demand is low.

This project explores how such **potentially unnecessary energy usage** can be identified using historical operational data.

---

## Problem Statement

Building Management Systems (BMS) ensure that HVAC systems operate according to schedules and control logic.

Energy Management Systems (EMS) measure energy consumption.

However, neither system answers the key question:

> **Was the energy usage operationally necessary?**

This creates a visibility gap between:

* system operation
* actual energy demand

---

## Objective

To develop a simple analytical approach that:

* Identifies potential extended HVAC runtime
* Compares actual behaviour with expected schedules
* Estimates energy, cost, and carbon impact
* Demonstrates how operational inefficiencies can be detected using data

---

## Approach

The analysis follows a simple logic:

### 1. Data Inputs

* HVAC runtime data
* Scheduled operating hours
* Energy consumption (kW)
* (Optional) weather and occupancy data

---

### 2. Runtime Deviation Detection

```text
If HVAC is ON outside scheduled hours → flag as potential deviation
```

---

### 3. Energy Impact Calculation

```text
Extra Runtime (hours) × HVAC Load (kW) = Energy Impact (kWh)
```

---

### 4. Cost Estimation

```text
Energy (kWh) × Electricity Rate = Cost Impact
```

---

## Example Scenario

* Scheduled runtime: 18 hours
* Actual runtime: 24 hours
* Extra runtime: 6 hours

HVAC Load: 100 kW

Energy impact:
600 kWh

Estimated cost:
$150 per day
≈ $54,000 annually

---

## Output

The system highlights:

* periods of extended HVAC runtime
* estimated energy waste
* cost implications

This provides an initial view into **operational inefficiencies that are not visible in traditional systems**.

---

## Key Insight

> **Correct operation does not necessarily imply necessary operation.**

This project demonstrates how an additional analytics layer can help bridge the gap between:

* control systems (BMS)
* energy reporting (EMS)

---

## Future Work

* Incorporate weather-normalized baseline models
* Use machine learning for anomaly detection
* Integrate occupancy data
* Apply to real building datasets
* Develop a scalable analytics platform (Infralytix)

---

## About

This project is part of an early-stage exploration of the **Infralytix / EnergyLens** concept, which aims to provide a read-only analytics layer for building energy optimisation.

---

## Author

Ravi Raj
Master of Artificial Intelligence
University of Auckland
