from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import logging
from config import config_service
from llm_explainer import get_bed_recommendation_reasoning

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
ALLOCATION_CSV = BACKEND_DIR / "data" / "patient_bed_allocations.csv"

# Department bed configurations (synced with config.py)
DEPT_BED_CONFIG = {
    "Cardiology":   {"total": 30,  "types": ["Semi Private", "Private Room", "Deluxe Room"]},
    "Emergency":    {"total": 15,  "types": ["General Ward", "Shared Ward", "Semi Private"]},
    "General Ward": {"total": 100, "types": ["General Ward", "Shared Ward", "Semi Private"]},
    "ICU":          {"total": 20,  "types": ["Private Room", "Deluxe Room", "Suite"]},
    "Neurology":    {"total": 28,  "types": ["Semi Private", "Private Room", "Deluxe Room"]},
    "Oncology":     {"total": 25,  "types": ["Semi Private", "Private Room", "Deluxe Room", "Suite"]},
    "Orthopedics":  {"total": 35,  "types": ["General Ward", "Shared Ward", "Semi Private", "Private Room"]},
}

DEPT_CODES = {
    "Cardiology": "CAR", "Emergency": "EMG", "General Ward": "GW",
    "ICU": "ICU", "Neurology": "NEU", "Oncology": "ONC", "Orthopedics": "ORT",
}

class BedRecommendationEngine:
    """AI-powered bed recommendation engine with dynamic business rules."""
    
    def __init__(self, historical_data: pd.DataFrame):
        self.historical_data = historical_data
        self.rules = config_service.get_business_rules()
        self.bed_types = config_service.get_bed_types()
        self.payer_channels = config_service.get_payer_channels()
        self._allocation_data: Optional[pd.DataFrame] = None
        self._bed_inventory: Optional[List[Dict[str, Any]]] = None
        self._load_allocation_data()

    def _load_allocation_data(self):
        """Load patient-bed allocation CSV and build bed inventory."""
        try:
            if ALLOCATION_CSV.exists():
                self._allocation_data = pd.read_csv(str(ALLOCATION_CSV))
                logger.info(f"Loaded {len(self._allocation_data)} patient-bed allocation records")
            else:
                logger.warning(f"Allocation CSV not found at {ALLOCATION_CSV}")
                self._allocation_data = None
        except Exception as e:
            logger.error(f"Error loading allocation CSV: {e}")
            self._allocation_data = None

    def _get_latest_date(self) -> str:
        """Get the latest date from allocation data or historical data."""
        if self._allocation_data is not None and not self._allocation_data.empty:
            return str(self._allocation_data["date"].max())
        if not self.historical_data.empty:
            return str(self.historical_data["date"].max())
        return datetime.now().strftime("%Y-%m-%d")

    def _get_occupied_bed_ids(self, date_str: Optional[str] = None) -> set:
        """Get set of bed_ids that are occupied on a given date."""
        if self._allocation_data is None or self._allocation_data.empty:
            return set()
        target_date = date_str or self._get_latest_date()
        day_data = self._allocation_data[self._allocation_data["date"] == target_date]
        return set(day_data["bed_id"].unique())

    def _build_bed_inventory(self) -> List[Dict[str, Any]]:
        """Build full bed inventory from department configs, marking occupied beds."""
        if self._bed_inventory is not None:
            return self._bed_inventory

        occupied_ids = self._get_occupied_bed_ids()
        inventory = []

        # Room capacity per room type
        ROOM_CAPACITY = {
            "General Ward": 6,
            "Shared Ward": 4,
            "Semi Private": 2,
            "Private Room": 1,
            "Deluxe Room": 1,
            "Suite": 1,
        }

        for dept, config in DEPT_BED_CONFIG.items():
            total = config["total"]
            bed_types = config["types"]
            code = DEPT_CODES.get(dept, dept[:3].upper())

            # Track room counters per room type for this department
            room_counters = {}  # room_type -> {"counter": int, "filled": int}

            for i in range(1, total + 1):
                bed_id = f"{code}-{i:03d}"
                bed_type = bed_types[(i - 1) % len(bed_types)]
                cap = ROOM_CAPACITY.get(bed_type, 1)

                # Get or init room counter for this bed type
                if bed_type not in room_counters:
                    room_counters[bed_type] = {"counter": 0, "filled": 0}

                rc = room_counters[bed_type]
                if rc["filled"] == 0 or rc["filled"] >= cap:
                    rc["counter"] += 1
                    rc["filled"] = 0
                rc["filled"] += 1

                # Build room number with type prefix
                type_prefix = {
                    "General Ward": "GW",
                    "Shared Ward": "SW",
                    "Semi Private": "SP",
                    "Private Room": "PR",
                    "Deluxe Room": "DR",
                    "Suite": "SU",
                }.get(bed_type, "RM")
                room = f"{code}-{type_prefix}{rc['counter']:03d}"

                status = "occupied" if bed_id in occupied_ids else "available"

                inventory.append({
                    "id": bed_id,
                    "department": dept,
                    "type": bed_type,
                    "room": room,
                    "status": status,
                })

        self._bed_inventory = inventory
        return inventory
    
    def predict_los(self, patient_data: Dict[str, Any]) -> float:
        """Predict length of stay using payer channel and condition."""
        base_los = self._calculate_base_los(patient_data.get("condition", "General"))
        payer = patient_data.get("payer_channel", "self_pay")
        
        payer_config = next((p for p in self.payer_channels if p["id"] == payer), None)
        multiplier = payer_config["avg_los_multiplier"] if payer_config else 1.0
        
        return round(base_los * multiplier, 1)
    
    def _calculate_base_los(self, condition: str) -> float:
        """Calculate base LOS from historical data or defaults."""
        if self.historical_data.empty or "avg_length_of_stay" not in self.historical_data.columns:
            return 4.5
        return float(self.historical_data["avg_length_of_stay"].mean())
    
    def recommend_beds(self, patient_data: Dict[str, Any], forecast_data: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Recommend beds using weighted percentage scoring model.
        
        Score Breakdown (Total = 100):
          Clinical Match       = 40 pts
          Specialty Match      = 20 pts
          Severity Match       = 15 pts
          Payer Match          = 10 pts
          LOS Match            = 5 pts
          Occupancy Optimization = 5 pts
          Revenue Optimization   = 5 pts
        
        The highest scoring available bed is recommended first.
        """
        recommendations = []
        
        # Rule Group 1 – Clinical Priority
        required_dept = self._get_required_department(patient_data)
        required_room_type = self._get_required_room_type(patient_data)
        avoid_room_types = self._get_avoid_room_types(patient_data)
        
        # Rule Group 2 – Specialty preference
        preferred_dept = self._get_specialty_department(patient_data)
        
        # Rule Group 5 – Payer rules
        payer_room_types = self._get_payer_allowed_room_types(patient_data)
        payer_preferred_types = self._get_payer_preferred_room_types(patient_data)
        
        # Rule Group 9 – Revenue Optimization: payer name for revenue rules
        payer_name = self._get_payer_name(patient_data)
        
        # Get available beds
        available_beds = self._get_available_beds()
        
        # Build department occupancy map for Rule Group 8
        dept_occupancy = self._get_department_occupancy_map()
        
        for bed in available_beds:
            score, breakdown = self._calculate_bed_score(
                bed, patient_data, required_dept, required_room_type, avoid_room_types,
                preferred_dept, payer_room_types, payer_preferred_types,
                dept_occupancy, payer_name
            )
            
            if score > 0:
                recommendations.append({
                    "bed_id": bed["id"],
                    "department": bed["department"],
                    "bed_type": bed["type"],
                    "room": bed["room"],
                    "score": round(score, 1),
                    "score_breakdown": breakdown,
                    "predicted_los": self.predict_los(patient_data),
                    "occupancy_impact": self._calculate_occupancy_impact(bed, forecast_data),
                    "reasoning": self._generate_reasoning(bed, patient_data, score, breakdown, dept_occupancy, payer_name)
                })
        
        # Sort by score descending
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        top_5 = recommendations[:5]
        
        # Generate LLM-based reasoning for the top recommendation
        if top_5:
            try:
                top = top_5[0]
                bed_info = {"id": top["bed_id"], "department": top["department"],
                           "type": top["bed_type"], "room": top["room"]}
                llm_reasoning = get_bed_recommendation_reasoning(
                    patient_data, bed_info, top["score"], top["score_breakdown"],
                    dept_occupancy, payer_name
                )
                top["llm_reasoning"] = llm_reasoning
            except Exception as e:
                logger.warning(f"LLM reasoning generation failed: {e}")
        
        return top_5
    
    def _get_required_department(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Rule Group 1 – Clinical Priority: determine required department."""
        if patient_data.get("is_critical"):
            return self.rules["critical"]["required_department"]
        if patient_data.get("requires_ventilator"):
            return self.rules["ventilator"]["required_department"]
        if patient_data.get("requires_dialysis"):
            return self.rules["dialysis"]["required_department"]
        # Rule Group 3 – Pediatric
        if patient_data.get("age", 99) < self.rules["pediatric"]["age_threshold"]:
            return self.rules["pediatric"]["required_department"]
        return None
    
    def _get_specialty_department(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Rule Group 2 – Specialty: get preferred department from specialty."""
        specialty = patient_data.get("specialty", "")
        specialty_map = self.rules.get("specialty_preference", {})
        return specialty_map.get(specialty)
    
    def _get_required_room_type(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Rule Group 1 – Clinical Priority: determine required room type."""
        if patient_data.get("requires_ventilator"):
            return self.rules["ventilator"].get("required_room_type")
        if patient_data.get("requires_isolation"):
            return self.rules["isolation"].get("required_room_type")
        return None
    
    def _get_avoid_room_types(self, patient_data: Dict[str, Any]) -> List[str]:
        """Determine room types to avoid based on business rules."""
        avoid = []
        predicted_los = self.predict_los(patient_data)
        
        if predicted_los > self.rules["long_stay"]["los_threshold"]:
            avoid.append(self.rules["long_stay"].get("avoid_room_type", "Suite"))
        
        return avoid
    
    def _get_payer_allowed_room_types(self, patient_data: Dict[str, Any]) -> Optional[List[str]]:
        """Rule Group 5 – Payer: get allowed room types for patient's payer.
        Resolves payer_channel ID to payer name for rules lookup.
        """
        payer_name = self._get_payer_name(patient_data)
        payer_rules = self.rules.get("payer_rules", {})
        rule = payer_rules.get(payer_name)
        if rule and "allowed_room_types" in rule:
            return rule["allowed_room_types"]
        return None
    
    def _get_payer_preferred_room_types(self, patient_data: Dict[str, Any]) -> Optional[List[str]]:
        """Rule Group 5 – Payer: get preferred room types for patient's payer.
        Resolves payer_channel ID to payer name for rules lookup.
        """
        payer_name = self._get_payer_name(patient_data)
        payer_rules = self.rules.get("payer_rules", {})
        rule = payer_rules.get(payer_name)
        if rule and "prefer_room_types" in rule:
            return rule["prefer_room_types"]
        return None
    
    def _get_payer_name(self, patient_data: Dict[str, Any]) -> str:
        """Get the payer name from patient data using payer channel ID."""
        payer_id = patient_data.get("payer_channel", "")
        payer = next((p for p in self.payer_channels if p["id"] == payer_id), None)
        return payer["name"] if payer else payer_id
    
    def _get_department_occupancy_map(self) -> Dict[str, float]:
        """Get current occupancy rate per department from inventory."""
        inventory = self._build_bed_inventory()
        dept_map = {}
        for bed in inventory:
            dept = bed["department"]
            if dept not in dept_map:
                dept_map[dept] = {"total": 0, "occupied": 0}
            dept_map[dept]["total"] += 1
            if bed["status"] == "occupied":
                dept_map[dept]["occupied"] += 1
        return {dept: v["occupied"] / v["total"] for dept, v in dept_map.items() if v["total"] > 0}
    
    def _get_available_beds(self) -> List[Dict[str, Any]]:
        """Get list of available beds from real inventory data.
        Rule Group 7 – Availability: exclude beds that are not available,
        cleaning pending, under maintenance, or reserved.
        """
        inventory = self._build_bed_inventory()
        excluded_statuses = {"occupied", "cleaning", "maintenance", "reserved"}
        return [bed for bed in inventory if bed["status"] not in excluded_statuses]
    
    def _calculate_bed_score(
        self, 
        bed: Dict[str, Any], 
        patient_data: Dict[str, Any],
        required_dept: Optional[str],
        required_room_type: Optional[str],
        avoid_room_types: List[str],
        preferred_dept: Optional[str] = None,
        payer_allowed_types: Optional[List[str]] = None,
        payer_preferred_types: Optional[List[str]] = None,
        dept_occupancy: Optional[Dict[str, float]] = None,
        payer_name: Optional[str] = None,
    ) -> tuple:
        """
        Calculate weighted suitability score for a bed (max 100).
        
        Returns (total_score, breakdown_dict).
        
        Weight Model:
          Clinical Match       = 40 pts (hard exclusion if unmet)
          Specialty Match      = 20 pts
          Severity Match       = 15 pts
          Payer Match          = 10 pts (hard exclusion if not allowed)
          LOS Match            = 5 pts
          Occupancy Optimization = 5 pts
          Revenue Optimization   = 5 pts
        """
        ROOM_TIER = {"General Ward": 1, "Shared Ward": 2, "Semi Private": 3,
                     "Private Room": 4, "Deluxe Room": 5, "Suite": 6}
        
        breakdown = {}
        
        # === 1. Clinical Match (40 pts) ===
        clinical_score = 40.0
        has_clinical_req = bool(required_dept or required_room_type or
                                patient_data.get("is_critical") or
                                patient_data.get("requires_ventilator") or
                                patient_data.get("requires_isolation") or
                                patient_data.get("requires_dialysis"))
        
        if required_dept and bed["department"] != required_dept:
            return 0.0, {"clinical": 0, "specialty": 0, "severity": 0, "payer": 0,
                         "los": 0, "occupancy": 0, "revenue": 0}
        if required_room_type and bed["type"] != required_room_type:
            return 0.0, {"clinical": 0, "specialty": 0, "severity": 0, "payer": 0,
                         "los": 0, "occupancy": 0, "revenue": 0}
        
        # Gender mismatch in Shared Ward = hard exclusion
        if bed["type"] == "Shared Ward":
            bed_gender = bed.get("gender_assigned")
            patient_gender = patient_data.get("gender")
            if bed_gender and patient_gender and bed_gender != patient_gender:
                return 0.0, {"clinical": 0, "specialty": 0, "severity": 0, "payer": 0,
                             "los": 0, "occupancy": 0, "revenue": 0}
        
        if not has_clinical_req:
            clinical_score = 40.0  # No clinical requirements = full score
        else:
            # Partial credit: meets dept but room type is lower than ideal
            if required_room_type and bed["type"] == required_room_type:
                clinical_score = 40.0
            elif required_dept and bed["department"] == required_dept:
                clinical_score = 35.0  # Correct dept, acceptable room
            else:
                clinical_score = 30.0  # Meets minimum clinical needs
        
        # Penalize avoid_room_types (e.g., long-stay avoiding Suite)
        if bed["type"] in avoid_room_types:
            clinical_score -= 10.0
        
        breakdown["clinical"] = max(0.0, clinical_score)
        
        # === 2. Specialty Match (20 pts) ===
        specialty_score = 10.0  # Neutral baseline
        if preferred_dept:
            if bed["department"] == preferred_dept:
                specialty_score = 20.0
            elif not required_dept:
                specialty_score = 5.0  # Mismatch penalty (only if no hard dept constraint)
        breakdown["specialty"] = specialty_score
        
        # === 3. Severity Match (15 pts) ===
        severity = patient_data.get("severity", "MEDIUM")
        if isinstance(severity, str):
            severity = severity.upper()
        bed_tier = ROOM_TIER.get(bed["type"], 3)
        
        if severity == "CRITICAL":
            # Critical needs highest available tier
            dept_types = DEPT_BED_CONFIG.get(bed["department"], {}).get("types", [])
            max_tier = max((ROOM_TIER.get(t, 0) for t in dept_types), default=3)
            if bed_tier >= max_tier:
                severity_score = 15.0
            elif bed_tier >= max_tier - 1:
                severity_score = 10.0
            else:
                severity_score = 5.0
        elif severity == "HIGH":
            if bed_tier >= 3:  # Semi Private or higher
                severity_score = 15.0
            elif bed_tier >= 2:  # Shared Ward
                severity_score = 10.0
            else:
                severity_score = 5.0
        elif severity == "MEDIUM":
            if bed_tier >= 2:
                severity_score = 15.0
            else:
                severity_score = 12.0
        else:  # LOW
            severity_score = 15.0
        breakdown["severity"] = severity_score
        
        # === 4. Payer Match (10 pts) ===
        # Rule Group 1 (Clinical Priority) overrides Rule Group 5 (Payer):
        # If patient has clinical requirements (critical/ventilator/isolation/dialysis),
        # payer room type restrictions become a soft penalty instead of a hard exclusion.
        # Patient safety always comes first.
        payer_score = 10.0  # Default: no restrictions
        has_clinical_override = bool(required_dept or required_room_type)
        if payer_allowed_types:
            if bed["type"] not in payer_allowed_types:
                if has_clinical_override:
                    # Clinical need overrides payer restriction - soft penalty only
                    payer_score = 3.0
                else:
                    # No clinical override - hard exclusion
                    return 0.0, {"clinical": breakdown["clinical"], "specialty": specialty_score,
                                 "severity": severity_score, "payer": 0,
                                 "los": 0, "occupancy": 0, "revenue": 0}
            else:
                payer_score = 7.0  # Allowed but not necessarily preferred
        if payer_preferred_types:
            if bed["type"] in payer_preferred_types:
                payer_score = 10.0  # Preferred match
        breakdown["payer"] = payer_score
        
        # === 5. LOS Match (5 pts) ===
        predicted_los = self.predict_los(patient_data)
        los_threshold = self.rules.get("long_stay", {}).get("los_threshold", 10)
        if predicted_los > los_threshold and bed["type"] == "Suite":
            los_score = 0.0  # Long-stay patients should avoid Suite
        elif predicted_los > los_threshold and bed_tier >= 5:
            los_score = 2.0  # Long-stay in high-tier = suboptimal
        else:
            los_score = 5.0  # Good LOS fit
        breakdown["los"] = los_score
        
        # === 6. Occupancy Optimization (5 pts) ===
        occ_score = 5.0
        if dept_occupancy:
            occ_rate = dept_occupancy.get(bed["department"], 0.0)
            occ_rules = self.rules.get("occupancy_optimization", {})
            overflow_threshold = occ_rules.get("overflow_threshold", 0.95)
            icu_alert_threshold = occ_rules.get("icu_capacity_alert_threshold", 0.98)
            early_discharge_threshold = occ_rules.get("early_discharge_threshold", 0.90)
            
            if bed["department"] == "ICU" and occ_rate >= icu_alert_threshold:
                occ_score = 0.0
            elif occ_rate >= overflow_threshold:
                occ_score = 1.0
            elif occ_rate >= early_discharge_threshold:
                occ_score = 3.0
            else:
                occ_score = 5.0
        breakdown["occupancy"] = occ_score
        
        # === 7. Revenue Optimization (5 pts) ===
        rev_score = 2.0  # Default: no revenue match
        revenue_rules = self.rules.get("revenue_optimization", {})
        if payer_name:
            international_premium = revenue_rules.get("international_premium_types", [])
            corporate_deluxe = revenue_rules.get("corporate_deluxe_types", [])
            private_eligible = revenue_rules.get("private_room_eligible_types", [])
            
            if payer_name == "International" and bed["type"] in international_premium:
                rev_score = 5.0
            elif payer_name == "Corporate" and bed["type"] in corporate_deluxe:
                rev_score = 5.0
            elif bed["type"] in private_eligible:
                rev_score = 4.0
        breakdown["revenue"] = rev_score
        
        # === Soft penalties ===
        total = (breakdown["clinical"] + breakdown["specialty"] + breakdown["severity"] +
                 breakdown["payer"] + breakdown["los"] + breakdown["occupancy"] + breakdown["revenue"])
        
        if bed["status"] == "cleaning":
            total -= 5.0
        if bed.get("maintenance_scheduled"):
            total -= 3.0
        
        return max(0.0, total), breakdown
    
    def _calculate_occupancy_impact(self, bed: Dict[str, Any], forecast_data: Optional[Dict]) -> str:
        """Calculate impact on department occupancy based on real data."""
        inventory = self._build_bed_inventory()
        dept_beds = [b for b in inventory if b["department"] == bed["department"]]
        if not dept_beds:
            return "unknown"
        total = len(dept_beds)
        occupied = sum(1 for b in dept_beds if b["status"] == "occupied")
        occ_rate = occupied / total if total > 0 else 0
        if occ_rate >= 0.90:
            return "high"
        elif occ_rate >= 0.75:
            return "medium"
        return "low"
    
    def _generate_reasoning(self, bed: Dict[str, Any], patient_data: Dict[str, Any], score: float,
                             breakdown: Optional[Dict[str, float]] = None,
                             dept_occupancy: Optional[Dict[str, float]] = None,
                             payer_name: Optional[str] = None) -> str:
        """Generate human-readable reasoning for recommendation."""
        reasons = []
        
        # Rule Group 1 – Clinical Priority
        if patient_data.get("is_critical"):
            reasons.append(f"Critical patient - ICU required")
        if patient_data.get("requires_ventilator"):
            reasons.append("Ventilator support - Private Room in ICU")
        if patient_data.get("requires_isolation"):
            reasons.append("Isolation required - Private Room allocated")
        if patient_data.get("requires_dialysis"):
            reasons.append("Dialysis required - ICU department")
        
        # Rule Group 2 – Specialty
        specialty = patient_data.get("specialty", "")
        if specialty and bed["department"] == specialty:
            reasons.append(f"Specialty match - {specialty} department")
        
        # Rule Group 3 – Pediatric
        if patient_data.get("age", 99) < 14:
            reasons.append("Pediatric patient - Pediatrics department")
        
        # Rule Group 4 – Gender
        if bed["type"] == "Shared Ward":
            gender = patient_data.get("gender", "")
            if gender:
                reasons.append(f"Gender-matched Shared Ward ({gender})")
        
        # Rule Group 5 – Payer
        if payer_name:
            payer_rules = self.rules.get("payer_rules", {})
            rule = payer_rules.get(payer_name)
            if rule:
                if "prefer_room_types" in rule and bed["type"] in rule["prefer_room_types"]:
                    reasons.append(f"{payer_name} preferred room type")
                elif "allowed_room_types" in rule and bed["type"] in rule["allowed_room_types"]:
                    reasons.append(f"{payer_name} eligible room type")
                elif "allowed_room_types" in rule and bed["type"] not in rule["allowed_room_types"]:
                    if patient_data.get("is_critical") or patient_data.get("requires_ventilator") or patient_data.get("requires_isolation") or patient_data.get("requires_dialysis"):
                        reasons.append(f"CLINICAL OVERRIDE: {payer_name} normally restricted to {rule['allowed_room_types']} but clinical priority overrides")
        
        # Rule Group 6 – Length of Stay
        predicted_los = self.predict_los(patient_data)
        los_threshold = self.rules.get("long_stay", {}).get("los_threshold", 10)
        short_stay_threshold = self.rules.get("short_stay", {}).get("los_threshold", 2)
        if predicted_los > los_threshold:
            reasons.append(f"Long stay ({predicted_los} days) - avoiding premium high-turnover beds")
        elif predicted_los < short_stay_threshold:
            reasons.append(f"Short stay ({predicted_los} days) - short stay bed allocated")
        
        # Rule Group 7 – Availability (all recommended beds are available by filter)
        reasons.append("Bed available - not under cleaning/maintenance/reserved")
        
        # Rule Group 8 – Occupancy Optimization
        if dept_occupancy:
            occ_rate = dept_occupancy.get(bed["department"], 0.0)
            occ_pct = round(occ_rate * 100)
            occ_rules = self.rules.get("occupancy_optimization", {})
            overflow_threshold = occ_rules.get("overflow_threshold", 0.95)
            icu_alert_threshold = occ_rules.get("icu_capacity_alert_threshold", 0.98)
            early_discharge_threshold = occ_rules.get("early_discharge_threshold", 0.90)
            
            if bed["department"] == "ICU" and occ_rate >= icu_alert_threshold:
                reasons.append(f"ICU capacity alert: {occ_pct}% occupied")
            elif occ_rate >= overflow_threshold:
                reasons.append(f"Overflow capacity: {occ_pct}% occupied in {bed['department']}")
            elif occ_rate >= early_discharge_threshold:
                reasons.append(f"Early discharge review: {occ_pct}% occupied in {bed['department']}")
        
        # Rule Group 9 – Revenue Optimization
        if payer_name:
            revenue_rules = self.rules.get("revenue_optimization", {})
            if payer_name == "International" and bed["type"] in revenue_rules.get("international_premium_types", []):
                reasons.append("Revenue optimization: International patient - premium inventory prioritized")
            elif payer_name == "Corporate" and bed["type"] in revenue_rules.get("corporate_deluxe_types", []):
                reasons.append("Revenue optimization: Corporate package covers Deluxe Room")
            elif bed["type"] in revenue_rules.get("private_room_eligible_types", []):
                reasons.append("Revenue optimization: Private Room eligible and available")
        
        # Score breakdown summary
        if breakdown:
            parts = []
            if breakdown.get("clinical", 0) >= 35:
                parts.append("Clinical: excellent")
            elif breakdown.get("clinical", 0) >= 25:
                parts.append("Clinical: good")
            if breakdown.get("specialty", 0) >= 20:
                parts.append("Specialty: exact match")
            if breakdown.get("severity", 0) >= 15:
                parts.append("Severity: optimal tier")
            if breakdown.get("payer", 0) >= 10:
                parts.append("Payer: preferred match")
            if parts:
                reasons.append("Score: " + " | ".join(parts))
        
        if score >= 90:
            reasons.append("Optimal match for patient requirements")
        elif score >= 70:
            reasons.append("Good match with minor considerations")
        
        # Add real-time availability info
        inventory = self._build_bed_inventory()
        dept_beds = [b for b in inventory if b["department"] == bed["department"]]
        total = len(dept_beds)
        available = sum(1 for b in dept_beds if b["status"] == "available")
        reasons.append(f"{available}/{total} beds available in {bed['department']}")
        
        return " | ".join(reasons) if reasons else "Standard bed assignment"

    def get_bed_inventory_summary(self) -> Dict[str, Any]:
        """Get bed inventory summary for all departments."""
        inventory = self._build_bed_inventory()
        departments = {}
        for bed in inventory:
            dept = bed["department"]
            if dept not in departments:
                departments[dept] = {"total": 0, "occupied": 0, "available": 0, "by_type": {}}
            departments[dept]["total"] += 1
            if bed["status"] == "occupied":
                departments[dept]["occupied"] += 1
            else:
                departments[dept]["available"] += 1
            bt = bed["type"]
            if bt not in departments[dept]["by_type"]:
                departments[dept]["by_type"][bt] = {"total": 0, "occupied": 0, "available": 0}
            departments[dept]["by_type"][bt]["total"] += 1
            departments[dept]["by_type"][bt][bed["status"]] += 1

        return {
            "departments": departments,
            "total_beds": len(inventory),
            "total_occupied": sum(1 for b in inventory if b["status"] == "occupied"),
            "total_available": sum(1 for b in inventory if b["status"] == "available"),
            "latest_date": self._get_latest_date(),
        }

    def get_department_beds(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bed-level details for a department or all departments."""
        inventory = self._build_bed_inventory()
        if department:
            inventory = [b for b in inventory if b["department"] == department]
        return inventory

    def get_allocated_patients(self, department: Optional[str] = None, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get patient-bed allocation details from CSV."""
        if self._allocation_data is None or self._allocation_data.empty:
            return []
        target_date = date_str or self._get_latest_date()
        day_data = self._allocation_data[self._allocation_data["date"] == target_date].copy()
        if department:
            day_data = day_data[day_data["department"] == department]
        records = day_data.to_dict("records")
        # Sanitize NaN values to None for JSON serialization
        import math
        for rec in records:
            for key, val in rec.items():
                if isinstance(val, float) and math.isnan(val):
                    rec[key] = None
        return records

def create_bed_engine(historical_data: pd.DataFrame) -> BedRecommendationEngine:
    """Factory function to create bed recommendation engine."""
    return BedRecommendationEngine(historical_data)
