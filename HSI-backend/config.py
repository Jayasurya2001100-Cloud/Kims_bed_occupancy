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
            {"id": "insurance", "name": "Insurance", "avg_los_multiplier": 1.0, "priority": 2},
            {"id": "government", "name": "Government", "avg_los_multiplier": 1.1, "priority": 3},
            {"id": "corporate", "name": "Corporate", "avg_los_multiplier": 0.9, "priority": 1},
            {"id": "self_pay", "name": "Self Pay", "avg_los_multiplier": 0.8, "priority": 4},
        ]
    
    @staticmethod
    def get_business_rules() -> Dict[str, Any]:
        """Return dynamic business rules for bed allocation."""
        return {
            "critical": {"required_department": "ICU", "priority": 1},
            "ventilator": {"required_bed_type": "ventilator", "required_department": "ICU", "priority": 1},
            "isolation": {"required_bed_type": "isolation", "priority": 2},
            "dialysis": {"required_department": "Dialysis", "priority": 2},
            "long_stay": {"los_threshold": 10, "avoid_bed_type": "premium", "priority": 3},
            "pediatric": {"age_threshold": 14, "required_department": "Pediatrics", "priority": 2},
            "gender_restriction": {"applies_to": ["shared_room"], "priority": 4}
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
        """Return available bed types."""
        return [
            {"id": "standard", "name": "Standard", "base_rate": 1.0},
            {"id": "icu", "name": "ICU", "base_rate": 2.5},
            {"id": "ventilator", "name": "Ventilator", "base_rate": 3.0},
            {"id": "isolation", "name": "Isolation", "base_rate": 1.8},
            {"id": "premium", "name": "Premium", "base_rate": 1.5},
            {"id": "shared", "name": "Shared", "base_rate": 0.7}
        ]
    
    @staticmethod
    def get_specialty_list() -> List[str]:
        """Return list of medical specialties."""
        return [
            "Cardiology", "Neurology", "Orthopedics", "Pediatrics",
            "Oncology", "General Medicine", "Surgery", "Emergency",
            "ICU", "Dialysis", "Maternity"
        ]

config_service = ConfigService()
