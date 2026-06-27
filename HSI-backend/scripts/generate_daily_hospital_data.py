#!/usr/bin/env python3
"""Generate dense daily hospital rows (one row per department per day) for charting."""
from __future__ import annotations

import csv
from datetime import date, timedelta
import math
import random

import numpy as np

random.seed(42)
np.random.seed(42)

DEPARTMENTS = [
    "ICU",
    "Emergency",
    "Cardiology",
    "Oncology",
    "Orthopedics",
    "Neurology",
    "General Ward",
]
TOTAL_BEDS = {
    "ICU": 20,
    "Emergency": 15,
    "Cardiology": 30,
    "Oncology": 25,
    "Orthopedics": 35,
    "Neurology": 28,
    "General Ward": 100,
}

DISEASES = {
    "ICU": ("Respiratory", "Critical Care Mix"),
    "Emergency": ("Trauma", "ED High Acuity Mix"),
    "Cardiology": ("Cardiovascular", "ACS & Heart Failure"),
    "Oncology": ("Cancer", "Chemo & Complications"),
    "Orthopedics": ("Musculoskeletal", "Fractures & Replacements"),
    "Neurology": ("Neurological", "Stroke & Seizure"),
    "General Ward": ("General", "Respiratory & Med-Surg"),
}


def base_rate(dept: str) -> float:
    return {
        "ICU": 0.86,
        "Emergency": 0.72,
        "Cardiology": 0.78,
        "Oncology": 0.76,
        "Orthopedics": 0.81,
        "Neurology": 0.77,
        "General Ward": 0.84,
    }[dept]


def severity_for(rate: float) -> str:
    if rate >= 0.97:
        return "CRITICAL"
    if rate >= 0.9:
        return "HIGH"
    if rate >= 0.78:
        return "MEDIUM"
    return "LOW"


def main() -> None:
    start = date(2025, 1, 1)
    end = date(2026, 5, 22)
    out_path = "data/hospital_disease_data.csv"
    rows: list[dict] = []

    # Pre-generate surge events: ~8 random multi-day surge periods across the year
    rng = random.Random(99)
    total_days = (end - start).days + 1
    surge_days: set[int] = set()
    for _ in range(8):
        surge_start = rng.randint(0, total_days - 1)
        surge_len = rng.randint(3, 10)
        for s in range(surge_len):
            surge_days.add(surge_start + s)

    d = start
    while d <= end:
        dow = d.weekday()
        day_i = (d - start).days

        # --- Richer temporal signals ---
        # Weekly: Mon/Tue high, Sat/Sun low (hospitals busier mid-week)
        dow_effect = [0.06, 0.05, 0.03, 0.0, -0.02, -0.07, -0.09][dow]
        # Monthly seasonal wave (~45-day cycle)
        wave = 0.08 * math.sin(day_i / 45.0)
        # Slower annual wave
        annual = 0.05 * math.sin(day_i / 180.0)
        # Winter boost
        winter = 0.05 if d.month in (12, 1, 2) else 0.0
        # Trend ramp
        trend_ramp = min(0.15, 0.0003 * float(day_i))
        # Surge event boost
        surge = 0.12 if day_i in surge_days else 0.0

        for dept in DEPARTMENTS:
            tb = TOTAL_BEDS[dept]
            # Per-department noise: much larger (8% std) so each dept has its own ups/downs
            dept_noise = random.gauss(0, 0.08)
            r = (
                base_rate(dept)
                + trend_ramp
                + dow_effect
                + wave
                + annual
                + winter
                + surge
                + dept_noise
            )
            r = max(0.30, min(0.995, r))
            occ = int(round(tb * r))
            occ = min(occ, tb)
            r = occ / tb

            # Patient volume
            patient_factor = 0.78 + 0.06 * (1 if dow < 5 else -0.5) + 0.02 * wave
            patients = max(1, int(round(occ * patient_factor + random.gauss(0, 1.5))))
            los = round(max(1.5, 3.2 + 4.5 * r + 0.5 * (1 if dow < 5 else 0) + random.gauss(0, 0.5)), 1)
            icu_req = min(patients, int(round(patients * (0.4 if dept != "ICU" else 0.85))))
            if dept == "Emergency":
                emerg = max(0, int(round(12 + 6 * (1 if dow < 5 else 0) + wave * 20 + surge * 15 + random.gauss(0, 2.5))))
                ed_wait = round(max(15.0, min(180.0, 35.0 + emerg * 2.8 + r * 45.0 + 12.0 * (1 if dow >= 5 else 0))), 1)
            else:
                emerg = max(0, int(round(2 + random.gauss(0, 1.2))))
                ed_wait = ""
            disch = max(0, int(round(patients * 0.32 + random.gauss(0, 1.0))))

            # Labour staffing (FTE): nurse-patient ratio varies by dept + DOW + noise
            ratio = {"ICU": 0.9, "Emergency": 0.7, "Cardiology": 0.45,
                     "Oncology": 0.50, "Orthopedics": 0.40,
                     "Neurology": 0.45, "General Ward": 0.35}[dept]
            dow_staff_bump = 0.08 if dow < 5 else -0.06   # more staff weekdays
            staff = max(1, round(
                occ * ratio * (1 + dow_staff_bump + surge * 0.15)
                + random.gauss(0, occ * 0.04), 1
            ))

            cat, spec = DISEASES[dept]
            rows.append(
                {
                    "date": d.isoformat(),
                    "department": dept,
                    "disease_category": cat,
                    "specific_disease": spec,
                    "patient_count": patients,
                    "occupied_beds": occ,
                    "total_beds": tb,
                    "occupancy_rate": round(r, 4),
                    "severity": severity_for(r),
                    "avg_length_of_stay": los,
                    "icu_required": icu_req,
                    "emergency_admission": emerg,
                    "discharges": disch,
                    "ed_wait_time_minutes": ed_wait if dept == "Emergency" else "",
                    "labour_staffing": staff,
                }
            )
        d += timedelta(days=1)

    fields = [
        "date",
        "department",
        "disease_category",
        "specific_disease",
        "patient_count",
        "occupied_beds",
        "total_beds",
        "occupancy_rate",
        "severity",
        "avg_length_of_stay",
        "icu_required",
        "emergency_admission",
        "discharges",
        "ed_wait_time_minutes",
        "labour_staffing",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
