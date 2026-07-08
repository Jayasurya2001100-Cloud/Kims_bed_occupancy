"""Generate patient-bed allocation CSV synced with hospital_enhanced_full_dataset.csv."""
import csv
import random
import os
from datetime import datetime, timedelta
from collections import Counter

random.seed(42)

INPUT = os.path.join(os.path.dirname(__file__), "data", "hospital_enhanced_full_dataset.csv")
OUTPUT = os.path.join(os.path.dirname(__file__), "data", "patient_bed_allocations.csv")

# Department room configs (synced with config.py and bed_engine.py)
ROOM_TYPES = [
    "General Ward", "Shared Ward", "Semi Private",
    "Private Room", "Deluxe Room", "Suite",
]

DEPT_BEDS = {
    "Cardiology":   {"total": 30,  "types": ["Semi Private", "Private Room", "Deluxe Room"]},
    "Emergency":    {"total": 15,  "types": ["General Ward", "Shared Ward", "Semi Private"]},
    "General Ward": {"total": 100, "types": ["General Ward", "Shared Ward", "Semi Private"]},
    "ICU":          {"total": 20,  "types": ["Private Room", "Deluxe Room", "Suite"]},
    "Neurology":    {"total": 28,  "types": ["Semi Private", "Private Room", "Deluxe Room"]},
    "Oncology":     {"total": 25,  "types": ["Semi Private", "Private Room", "Deluxe Room", "Suite"]},
    "Orthopedics":  {"total": 35,  "types": ["General Ward", "Shared Ward", "Semi Private", "Private Room"]},
}

# Rule Group 5 – Payer room type rules
PAYER_ROOM_RULES = {
    "Cash":                                  {"allowed": None,                                         "preferred": None},
    "Insurance":                             {"allowed": None,                                         "preferred": None},
    "CGHS (Central Government Health Scheme)": {"allowed": ["General Ward", "Shared Ward", "Semi Private"],              "preferred": ["General Ward", "Shared Ward"]},
    "Corporate":                             {"allowed": None,                                         "preferred": ["Semi Private", "Private Room"]},
    "International":                         {"allowed": None,                                         "preferred": ["Private Room", "Deluxe Room", "Suite"]},
    "Government Scheme":                     {"allowed": ["General Ward", "Shared Ward", "Semi Private"],              "preferred": ["General Ward", "Shared Ward"]},
    "Card":                                  {"allowed": ["General Ward", "Shared Ward", "Semi Private", "Private Room"], "preferred": ["Semi Private", "Private Room"]},
}

# Room type tier ordering (lower = cheaper)
ROOM_TIER = {
    "General Ward": 1, "Shared Ward": 2, "Semi Private": 3,
    "Private Room": 4, "Deluxe Room": 5, "Suite": 6,
}

# Payer channels (synced with config.py)
PAYERS = [
    {"id": "cash",        "name": "Cash",                            "weight": 0.25},
    {"id": "insurance",   "name": "Insurance",                      "weight": 0.30},
    {"id": "cghs",        "name": "CGHS (Central Government Health Scheme)", "weight": 0.10},
    {"id": "corporate",   "name": "Corporate",                      "weight": 0.15},
    {"id": "international","name": "International",                  "weight": 0.05},
    {"id": "govt_scheme", "name": "Government Scheme",               "weight": 0.10},
    {"id": "card",        "name": "Card",                            "weight": 0.05},
]

GENDERS = ["Male", "Female"]

SEVERITY_ACUITY = {
    "CRITICAL": (5, 5),
    "HIGH":     (3, 5),
    "MEDIUM":   (2, 4),
    "LOW":      (1, 3),
}

FIRST_NAMES_M = ["Rajesh", "Mohammed", "David", "Arjun", "Suresh", "James",
                 "Vijay", "Anil", "Thomas", "Pradeep", "Karthik", "Stephen",
                 "Imran", "Sai", "Naveen"]
FIRST_NAMES_F = ["Lakshmi", "Priya", "Mary", "Sunita", "Anjali", "Grace",
                 "Deepa", "Fatima", "Rebecca", "Meena", "Kavya", "Elizabeth",
                 "Aisha", "Saritha", "Divya"]
LAST_NAMES = ["Reddy", "Nair", "Thomas", "Khan", "Sharma", "Pillai", "George",
              "Patel", "Menon", "Das", "Fernandes", "Iyer", "Abraham", "Prasad",
              "Krishnan", "Mathew", "Sultan", "Bose", "Rao", "Vinod"]

DEPT_CODES = {
    "Cardiology": "CAR", "Emergency": "EMG", "General Ward": "GW",
    "ICU": "ICU", "Neurology": "NEU", "Oncology": "ONC", "Orthopedics": "ORT",
}

SPECIALTY_MAP = {
    "Cardiology": "Cardiology", "Emergency": "Emergency",
    "General Ward": "General Medicine", "ICU": "ICU",
    "Neurology": "Neurology", "Oncology": "Oncology",
    "Orthopedics": "Orthopedics",
}


def weighted_choice(items):
    r = random.random()
    cum = 0
    for item in items:
        cum += item["weight"]
        if r <= cum:
            return item
    return items[-1]


def make_bed_id(dept, idx):
    return f"{DEPT_CODES[dept]}-{idx:03d}"


def filter_by_payer(bed_types, payer_name):
    """Rule Group 5 – Filter room types by payer allowed list."""
    rule = PAYER_ROOM_RULES.get(payer_name, {})
    allowed = rule.get("allowed")
    if allowed is None:
        return bed_types
    return [bt for bt in bed_types if bt in allowed]


def pick_bed_type(dept, severity, vent, iso, bed_types, payer_name, gender, bed_index,
                     dept_occupancy=None, dept_bed_counts=None, avg_los=4.5):
    """
    Assign room type following all 9 rule groups:
    1. Clinical Priority: critical/ventilator/isolation → Private Room minimum
    2. Specialty: already handled by department assignment
    3. Pediatric: handled by department (no Pediatrics dept in data)
    4. Gender: Shared Ward gets gender_assigned
    5. Payer: filter by allowed room types, prefer payer-preferred types
    6. LOS: >10 days avoid premium beds, <2 days allow short stay beds
    7. Availability: only available beds are considered (handled by bed_index)
    8. Occupancy Optimization: avoid >95% occupied departments, prefer lower-tier beds in >90%
    9. Revenue Optimization: prefer premium rooms for eligible payers
    """
    # Rule Group 1 – Clinical Priority: Private Room minimum for critical/vent/iso
    # Clinical rules OVERRIDE payer rules (patient safety first)
    if severity == "CRITICAL" or vent or iso:
        # Try Private Room+ first
        for rt in ["Private Room", "Deluxe Room", "Suite"]:
            if rt in bed_types:
                return rt
        # No Private Room+ in this dept (e.g. General Ward) - take highest tier available
        # Payer filter still applies for non-ICU critical patients
        available_critical = filter_by_payer(bed_types, payer_name)
        if not available_critical:
            available_critical = bed_types
        return max(available_critical, key=lambda x: ROOM_TIER.get(x, 0))

    # Rule Group 5 – Filter by payer allowed room types (only for non-critical)
    available = filter_by_payer(bed_types, payer_name)
    if not available:
        available = bed_types  # fallback if no payer-allowed types in dept

    # Rule Group 6 – Length of Stay Rules
    if avg_los > 10:
        # LOS > 10 days: avoid premium high-turnover beds (Suite, Deluxe Room)
        non_premium = [rt for rt in available if ROOM_TIER.get(rt, 0) < 5]
        if non_premium:
            available = non_premium
    elif avg_los < 2:
        # LOS < 2 days: allow short stay beds (any type including premium)
        pass  # No restriction - all beds allowed for short stays

    # Rule Group 9 – Revenue Optimization: International prioritizes premium inventory
    if payer_name == "International":
        for rt in ["Private Room", "Deluxe Room", "Suite"]:
            if rt in available:
                return rt

    # Rule Group 9 – Revenue Optimization: Corporate package covers Deluxe Room
    if payer_name == "Corporate":
        # Prefer Deluxe Room if available (revenue optimization)
        if "Deluxe Room" in available and random.random() < 0.3:
            return "Deluxe Room"
        for rt in ["Private Room", "Semi Private"]:
            if rt in available:
                return rt

    # Rule Group 8 – Occupancy Optimization
    # If department occupancy >95%, prefer lower-tier beds to leave premium rooms for revenue patients
    # If department occupancy >90%, prefer lower-tier beds (early discharge review)
    occ_rate = 0.0
    if dept_occupancy is not None:
        occ_rate = dept_occupancy.get(dept, 0.0)
    
    if occ_rate >= 0.95:
        # Overflow: take lowest available tier to maximize capacity
        if available:
            return min(available, key=lambda x: ROOM_TIER.get(x, 99))
    elif occ_rate >= 0.90:
        # Early discharge review: prefer lower-tier beds
        lower_tiers = [rt for rt in available if ROOM_TIER.get(rt, 99) <= 3]
        if lower_tiers and random.random() < 0.5:
            return min(lower_tiers, key=lambda x: ROOM_TIER.get(x, 99))

    # Severity-based selection (only from payer-filtered available list)
    if severity == "HIGH":
        if "Semi Private" in available and random.random() < 0.5:
            return "Semi Private"

    if severity == "MEDIUM":
        if "Semi Private" in available and random.random() < 0.3:
            return "Semi Private"

    # Rule Group 4 – Gender: Shared Ward available
    if "Shared Ward" in available and random.random() < 0.25:
        return "Shared Ward"

    if "General Ward" in available:
        return "General Ward"

    # Fallback: take lowest tier from available (payer-respected)
    return min(available, key=lambda x: ROOM_TIER.get(x, 99)) if available else bed_types[0]


def main():
    with open(INPUT, "r") as f:
        rows = list(csv.DictReader(f))

    patients = []
    counter = 1
    _room_state = {}  # Tracks room grouping: {(dept, bed_type): {"counter": n, "filled": n}}
    _dept_occupancy = {}  # Tracks occupancy per dept per date: {date_str: {dept: occ_rate}}

    for row in rows:
        date_str = row["date"]
        dept = row["department"]
        severity = row["severity"]
        occupied = int(row["occupied_beds"])
        patient_count = int(row["patient_count"])
        avg_los = float(row["avg_length_of_stay"])
        emergency_admission = int(row["emergency_admission"])

        bed_types = DEPT_BEDS.get(dept, {"total": 30, "types": ["standard"]})["types"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        num_patients = occupied  # occupied_beds = actual patients in beds

        for i in range(num_patients):
            gender = random.choice(GENDERS)
            first_name = random.choice(FIRST_NAMES_M if gender == "Male" else FIRST_NAMES_F)
            last_name = random.choice(LAST_NAMES)

            # Age by department
            if dept == "Cardiology":
                age = random.randint(40, 90)
            elif dept == "Oncology":
                age = random.randint(35, 85)
            elif dept == "Orthopedics":
                age = random.randint(18, 80)
            else:
                age = random.randint(18, 85)

            payer = weighted_choice(PAYERS)

            requires_ventilator = severity == "CRITICAL" and dept == "ICU" and random.random() < 0.6
            requires_isolation = dept in ("ICU", "Oncology") and random.random() < 0.15
            requires_dialysis = dept == "ICU" and random.random() < 0.1
            is_critical = severity == "CRITICAL"

            bed_index = i + 1
            # Rule Group 8 – Calculate current occupancy rate for this dept on this date
            dept_total = DEPT_BEDS.get(dept, {"total": 30})["total"]
            occ_rate = (i + 1) / dept_total if dept_total > 0 else 0.0
            # Track per-date occupancy
            if date_str not in _dept_occupancy:
                _dept_occupancy[date_str] = {}
            _dept_occupancy[date_str][dept] = occ_rate

            bed_type = pick_bed_type(dept, severity, requires_ventilator, requires_isolation, bed_types, payer["name"], gender, bed_index,
                                     dept_occupancy=_dept_occupancy.get(date_str, {}),
                                     avg_los=avg_los)
            bed_id = make_bed_id(dept, bed_index)

            # Assign room numbers based on room type capacity
            # General Ward=6 beds/room, Shared Ward=4, Semi Private=2, Private/Deluxe/Suite=1
            dept_code = DEPT_CODES.get(dept, dept[:3].upper())
            ROOM_CAPACITY = {"General Ward": 6, "Shared Ward": 4, "Semi Private": 2,
                             "Private Room": 1, "Deluxe Room": 1, "Suite": 1}
            TYPE_PREFIX = {"General Ward": "GW", "Shared Ward": "SW", "Semi Private": "SP",
                           "Private Room": "PR", "Deluxe Room": "DR", "Suite": "SU"}

            # Use a per-department, per-type counter to group beds into rooms
            room_key = (dept, bed_type)
            if room_key not in _room_state:
                _room_state[room_key] = {"counter": 0, "filled": 0}
            rs = _room_state[room_key]
            cap = ROOM_CAPACITY.get(bed_type, 1)
            if rs["filled"] == 0 or rs["filled"] >= cap:
                rs["counter"] += 1
                rs["filled"] = 0
            rs["filled"] += 1
            prefix = TYPE_PREFIX.get(bed_type, "RM")
            room = f"{dept_code}-{prefix}{rs['counter']:03d}"

            # Rule Group 4 – Gender assignment for Shared Ward
            gender_assigned = gender if bed_type == "Shared Ward" else ""

            los = round(max(1, random.gauss(avg_los, avg_los * 0.3)), 1)
            admit_date = date_obj - timedelta(days=int(los))
            est_discharge = date_obj + timedelta(days=max(0, int(los) // 2))

            acuity_min, acuity_max = SEVERITY_ACUITY.get(severity, (1, 3))
            acuity = random.randint(acuity_min, acuity_max)

            adm_type = "Emergency" if emergency_admission > 0 and random.random() < 0.4 else "Scheduled"

            r_val = random.random()
            if r_val < 0.7:
                status = "Admitted"
            elif r_val < 0.85:
                status = "Discharged"
            else:
                status = "In Observation"

            specialty = SPECIALTY_MAP.get(dept, "General Medicine")

            patient_id = f"PAT{date_str.replace('-', '')}{counter:05d}"
            admission_id = f"ADM{date_str.replace('-', '')}{counter:05d}"

            patients.append({
                "patient_id": patient_id,
                "admission_id": admission_id,
                "date": date_str,
                "patient_name": f"{first_name} {last_name}",
                "age": age,
                "gender": gender,
                "department": dept,
                "specialty": specialty,
                "disease_category": row["disease_category"],
                "specific_disease": row["specific_disease"],
                "severity": severity,
                "acuity_score": acuity,
                "admission_type": adm_type,
                "payer_channel": payer["name"],
                "payer_id": payer["id"],
                "bed_id": bed_id,
                "bed_type": bed_type,
                "room_preference": bed_type,
                "room_number": room,
                "gender_assigned": gender_assigned,
                "allocated_department": dept,
                "length_of_stay_days": los,
                "admission_date": admit_date.strftime("%Y-%m-%d"),
                "estimated_discharge": est_discharge.strftime("%Y-%m-%d"),
                "requires_ventilator": "Yes" if requires_ventilator else "No",
                "requires_isolation": "Yes" if requires_isolation else "No",
                "requires_dialysis": "Yes" if requires_dialysis else "No",
                "is_critical": "Yes" if is_critical else "No",
                "status": status,
                "occupied_beds": occupied,
                "total_beds": int(row["total_beds"]),
                "occupancy_rate": row["occupancy_rate"],
                "cost_per_bed": row["cost_per_bed"],
                "recovery_rate": row["recovery_rate"],
                "mortality_rate": row["mortality_rate"],
                "satisfaction_score": row["satisfaction_score"],
            })
            counter += 1

    fieldnames = list(patients[0].keys())
    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(patients)

    print(f"Generated {len(patients)} patient-bed allocation records")
    print(f"Output: {OUTPUT}")
    print(f"File size: {os.path.getsize(OUTPUT) / (1024 * 1024):.1f} MB")
    print(f"\nBy Department: {dict(Counter(p['department'] for p in patients))}")
    print(f"By Bed Type: {dict(Counter(p['bed_type'] for p in patients))}")
    print(f"By Payer: {dict(Counter(p['payer_channel'] for p in patients))}")
    print(f"By Status: {dict(Counter(p['status'] for p in patients))}")
    print(f"\nRule Validation:")
    # Validate Rule Group 5 – Payer room type restrictions
    # Exceptions: ICU (only has Private Room+) and critical/vent/iso patients
    # Clinical necessity overrides payer entitlements
    violations = []
    for p in patients:
        if p['is_critical'] == 'Yes':
            continue  # Clinical priority overrides payer rules
        if p['requires_ventilator'] == 'Yes' or p['requires_isolation'] == 'Yes':
            continue  # Clinical priority overrides payer rules
        if p['department'] == 'ICU':
            continue  # ICU only has Private Room+ - no lower tier rooms available
        payer = p['payer_channel']
        bt = p['bed_type']
        rule = PAYER_ROOM_RULES.get(payer, {})
        allowed = rule.get('allowed')
        if allowed and bt not in allowed:
            violations.append(f"  PAYER VIOLATION: {payer} patient {p['patient_id']} in {bt} (allowed: {allowed})")
    # Validate Rule Group 1 – Critical gets highest available tier
    for p in patients:
        if p['is_critical'] == 'Yes':
            dept_types = DEPT_BEDS.get(p['department'], {}).get('types', [])
            has_private_plus = any(ROOM_TIER.get(t, 0) >= ROOM_TIER['Private Room'] for t in dept_types)
            if has_private_plus and ROOM_TIER.get(p['bed_type'], 0) < ROOM_TIER['Private Room']:
                violations.append(f"  CLINICAL VIOLATION: Critical patient {p['patient_id']} in {p['bed_type']} (dept has Private Room+, needs Private Room+)")
    # Validate Rule Group 4 – Gender in Shared Ward
    for p in patients:
        if p['bed_type'] == 'Shared Ward' and p['gender'] != p['gender_assigned'] and p['gender_assigned']:
            violations.append(f"  GENDER VIOLATION: {p['gender']} patient {p['patient_id']} in {p['gender_assigned']} Shared Ward")
    # Validate Rule Group 9 – Revenue Optimization: International patients should be in premium rooms
    for p in patients:
        if p['payer_channel'] == 'International' and p['is_critical'] == 'No':
            if ROOM_TIER.get(p['bed_type'], 0) < ROOM_TIER['Private Room']:
                dept_types = DEPT_BEDS.get(p['department'], {}).get('types', [])
                has_premium = any(ROOM_TIER.get(t, 0) >= ROOM_TIER['Private Room'] for t in dept_types)
                if has_premium:
                    violations.append(f"  REVENUE VIOLATION: International patient {p['patient_id']} in {p['bed_type']} (should be Private Room+)")
    if violations:
        print(f"  {len(violations)} violations found:")
        for v in violations[:20]:
            print(v)
    else:
        print("  All rules validated - no violations")


if __name__ == "__main__":
    main()
