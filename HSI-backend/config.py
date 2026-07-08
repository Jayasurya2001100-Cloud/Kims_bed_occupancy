from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ConfigService:
    """Dynamic configuration provider for payer channels, business rules, and thresholds."""
    
    @staticmethod
    def get_payer_channels() -> List[Dict[str, Any]]:
        """Return dynamic payer channel configuration."""
        return [
            {"id": "cash", "name": "Cash", "avg_los_multiplier": 0.8, "priority": 4, "color": "#e74c3c", "revenue_weight": 0.25},
            {"id": "insurance", "name": "Insurance", "avg_los_multiplier": 1.0, "priority": 2, "color": "#007DB0", "revenue_weight": 0.30},
            {"id": "cghs", "name": "CGHS (Central Government Health Scheme)", "avg_los_multiplier": 1.1, "priority": 3, "color": "#27ae60", "revenue_weight": 0.10},
            {"id": "corporate", "name": "Corporate", "avg_los_multiplier": 0.9, "priority": 1, "color": "#f39c12", "revenue_weight": 0.15},
            {"id": "international", "name": "International", "avg_los_multiplier": 1.2, "priority": 1, "color": "#9b59b6", "revenue_weight": 0.05},
            {"id": "govt_scheme", "name": "Government Scheme", "avg_los_multiplier": 1.15, "priority": 3, "color": "#2ecc71", "revenue_weight": 0.10},
            {"id": "card", "name": "Card", "avg_los_multiplier": 0.85, "priority": 4, "color": "#3498db", "revenue_weight": 0.05},
        ]
    
    @staticmethod
    def get_business_rules() -> Dict[str, Any]:
        """Return dynamic business rules for bed allocation."""
        return {
            "critical": {"required_department": "ICU", "priority": 1, "description": "Critical patients must be placed in ICU"},
            "ventilator": {"required_department": "ICU", "required_room_type": "Private Room", "priority": 1, "description": "Patients requiring ventilator support go to ICU Private Rooms"},
            "isolation": {"required_room_type": "Private Room", "priority": 2, "description": "Isolation-required patients get Private Rooms"},
            "dialysis": {"required_department": "ICU", "priority": 2, "description": "Dialysis patients go to ICU"},
            "long_stay": {"los_threshold": 10, "avoid_room_type": "Suite", "priority": 3, "description": "Long-stay patients (>10 days) avoid Suite rooms for turnover"},
            "short_stay": {"los_threshold": 2, "description": "Short-stay patients (<2 days) can use any bed type including premium"},
            "availability": {"exclude_statuses": ["occupied", "cleaning", "maintenance", "reserved"], "priority": 0, "description": "Rule Group 7: Beds not available/cleaning/maintenance/reserved are excluded from allocation"},
            "pediatric": {"age_threshold": 14, "required_department": "Pediatrics", "priority": 2, "description": "Patients under 14 go to Pediatrics"},
            "gender_restriction": {"applies_to": ["Shared Ward"], "priority": 4, "description": "Shared Ward rooms must respect gender restrictions"},
            "maintenance_exclusion": {"exclude_status": ["maintenance", "cleaning", "reserved"], "priority": 0, "description": "Beds under maintenance/cleaning/reserved are excluded"},
            # Rule Group 2 – Specialty preference rules
            "specialty_preference": {
                "Cardiology": "Cardiology",
                "Neurology": "Neurology",
                "Oncology": "Oncology",
                "Orthopedics": "Orthopedics",
                "Emergency": "Emergency",
                "General Medicine": "General Ward",
            },
            # Rule Group 5 – Payer rules
            "payer_rules": {
                "International": {"prefer_room_types": ["Private Room", "Deluxe Room", "Suite"], "description": "International patients prefer Private/Deluxe/Suite rooms"},
                "Corporate": {"validate_eligibility": True, "prefer_room_types": ["Semi Private", "Private Room"], "description": "Corporate patients - validate eligibility, prefer Semi Private/Private"},
                "Insurance": {"validate_eligibility": True, "description": "Insurance patients - validate eligibility"},
                "CGHS (Central Government Health Scheme)": {"validate_entitlement": True, "allowed_room_types": ["General Ward", "Shared Ward", "Semi Private"], "description": "CGHS patients - validate room entitlement, limited to Semi Private or below"},
                "Cash": {"patient_preference": True, "description": "Cash patients - allocate based on patient preference"},
                "Government Scheme": {"allowed_room_types": ["General Ward", "Shared Ward", "Semi Private"], "description": "Government Scheme - limited to Semi Private or below"},
                "Card": {"allowed_room_types": ["General Ward", "Shared Ward", "Semi Private", "Private Room"], "description": "Card patients - up to Private Room"},
            },
            # Rule Group 8 – Occupancy Optimization
            "occupancy_optimization": {
                "overflow_threshold": 0.95,
                "icu_capacity_alert_threshold": 0.98,
                "early_discharge_threshold": 0.90,
                "priority": 3,
                "description": "Occupancy optimization: overflow at >95%, ICU alert at >98%, early discharge review at >90%",
            },
            # Rule Group 9 – Revenue Optimization
            "revenue_optimization": {
                "private_room_eligible_types": ["Private Room", "Deluxe Room", "Suite"],
                "corporate_deluxe_types": ["Deluxe Room"],
                "international_premium_types": ["Private Room", "Deluxe Room", "Suite"],
                "priority": 5,
                "description": "Revenue optimization: recommend premium rooms when eligible and available",
            },
        }
    
    @staticmethod
    def get_occupancy_thresholds() -> Dict[str, float]:
        """Return dynamic occupancy alert thresholds."""
        return {
            "critical": 0.90,
            "high": 0.85,
            "moderate": 0.75,
            "normal": 0.60
        }
    
    @staticmethod
    def get_forecast_windows() -> List[int]:
        """Return supported forecast windows in days."""
        return [7, 14, 30, 60, 90]
    
    @staticmethod
    def get_bed_types() -> List[Dict[str, Any]]:
        """Return available room types."""
        return [
            {"id": "general_ward", "name": "General Ward", "base_rate": 1.0, "capacity": 6, "description": "6 beds in a large hall with shared facilities"},
            {"id": "shared_ward", "name": "Shared Ward", "base_rate": 0.8, "capacity": 4, "description": "4 beds per room shared with other patients"},
            {"id": "semi_private", "name": "Semi Private", "base_rate": 1.5, "capacity": 2, "description": "2 beds per room with curtain partitions"},
            {"id": "private_room", "name": "Private Room", "base_rate": 2.0, "capacity": 1, "description": "Single occupancy with attached bathroom"},
            {"id": "deluxe_room", "name": "Deluxe Room", "base_rate": 3.0, "capacity": 1, "description": "Single occupancy with sofa, TV, attendant space"},
            {"id": "suite", "name": "Suite", "base_rate": 5.0, "capacity": 1, "description": "Premium room with separate living area"},
        ]
    
    @staticmethod
    def get_specialty_list() -> List[str]:
        """Return list of medical specialties."""
        return [
            "Cardiology", "Neurology", "Orthopedics", "Pediatrics",
            "Oncology", "General Medicine", "Surgery", "Emergency",
            "ICU", "Dialysis", "Maternity", "Pulmonology",
            "Gastroenterology", "Nephrology", "Dermatology",
        ]

    @staticmethod
    def get_alert_rules() -> List[Dict[str, Any]]:
        """Return dynamic alert rules with thresholds."""
        return [
            {"id": "icu_capacity", "label": "ICU Capacity Risk", "department": "ICU", "threshold": 0.85, "severity": "critical", "description": "ICU occupancy exceeds safe threshold"},
            {"id": "hospital_high", "label": "Hospital High Occupancy", "department": None, "threshold": 0.90, "severity": "critical", "description": "Hospital-wide occupancy critical"},
            {"id": "hospital_moderate", "label": "Hospital Moderate Occupancy", "department": None, "threshold": 0.85, "severity": "high", "description": "Hospital-wide occupancy elevated"},
            {"id": "emergency_surge", "label": "Emergency Surge", "department": "Emergency", "threshold": 0.80, "severity": "high", "description": "Emergency department nearing capacity"},
            {"id": "premium_shortage", "label": "Premium Room Shortage", "department": "Private Room", "threshold": 0.90, "severity": "medium", "description": "Premium/private rooms running low"},
        ]

config_service = ConfigService()
