from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging
from config import config_service

logger = logging.getLogger(__name__)

class BedRecommendationEngine:
    """AI-powered bed recommendation engine with dynamic business rules."""
    
    def __init__(self, historical_data: pd.DataFrame):
        self.historical_data = historical_data
        self.rules = config_service.get_business_rules()
        self.bed_types = config_service.get_bed_types()
        self.payer_channels = config_service.get_payer_channels()
    
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
        Recommend beds based on patient requirements and dynamic rules.
        
        Args:
            patient_data: Patient information including condition, age, payer, etc.
            forecast_data: Current occupancy forecast (optional)
        
        Returns:
            List of recommended beds with scores and reasoning
        """
        recommendations = []
        
        # Apply business rules
        required_dept = self._get_required_department(patient_data)
        required_bed_type = self._get_required_bed_type(patient_data)
        avoid_bed_types = self._get_avoid_bed_types(patient_data)
        
        # Get available beds
        available_beds = self._get_available_beds()
        
        for bed in available_beds:
            score = self._calculate_bed_score(bed, patient_data, required_dept, required_bed_type, avoid_bed_types)
            
            if score > 0:
                recommendations.append({
                    "bed_id": bed["id"],
                    "department": bed["department"],
                    "bed_type": bed["type"],
                    "room": bed["room"],
                    "score": score,
                    "predicted_los": self.predict_los(patient_data),
                    "occupancy_impact": self._calculate_occupancy_impact(bed, forecast_data),
                    "reasoning": self._generate_reasoning(bed, patient_data, score)
                })
        
        # Sort by score descending
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        return recommendations[:5]  # Top 5 recommendations
    
    def _get_required_department(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Determine required department from business rules."""
        if patient_data.get("is_critical"):
            return self.rules["critical"]["required_department"]
        if patient_data.get("requires_ventilator"):
            return self.rules["ventilator"]["required_department"]
        if patient_data.get("requires_dialysis"):
            return self.rules["dialysis"]["required_department"]
        if patient_data.get("age", 99) < self.rules["pediatric"]["age_threshold"]:
            return self.rules["pediatric"]["required_department"]
        return None
    
    def _get_required_bed_type(self, patient_data: Dict[str, Any]) -> Optional[str]:
        """Determine required bed type from business rules."""
        if patient_data.get("requires_ventilator"):
            return self.rules["ventilator"]["required_bed_type"]
        if patient_data.get("requires_isolation"):
            return self.rules["isolation"]["required_bed_type"]
        return None
    
    def _get_avoid_bed_types(self, patient_data: Dict[str, Any]) -> List[str]:
        """Determine bed types to avoid based on business rules."""
        avoid = []
        predicted_los = self.predict_los(patient_data)
        
        if predicted_los > self.rules["long_stay"]["los_threshold"]:
            avoid.append(self.rules["long_stay"]["avoid_bed_type"])
        
        return avoid
    
    def _get_available_beds(self) -> List[Dict[str, Any]]:
        """Get list of available beds (mock implementation)."""
        # In production, this would query real-time bed inventory
        return [
            {"id": "B101", "department": "ICU", "type": "icu", "room": "101", "status": "available"},
            {"id": "B102", "department": "ICU", "type": "ventilator", "room": "102", "status": "available"},
            {"id": "B201", "department": "General Ward", "type": "standard", "room": "201", "status": "available"},
            {"id": "B202", "department": "General Ward", "type": "premium", "room": "202", "status": "available"},
            {"id": "B301", "department": "Emergency", "type": "standard", "room": "301", "status": "available"},
        ]
    
    def _calculate_bed_score(
        self, 
        bed: Dict[str, Any], 
        patient_data: Dict[str, Any],
        required_dept: Optional[str],
        required_bed_type: Optional[str],
        avoid_bed_types: List[str]
    ) -> float:
        """Calculate suitability score for a bed."""
        score = 100.0
        
        # Hard constraints
        if required_dept and bed["department"] != required_dept:
            return 0.0
        if required_bed_type and bed["type"] != required_bed_type:
            return 0.0
        if bed["type"] in avoid_bed_types:
            score -= 30.0
        
        # Gender restrictions for shared rooms
        if bed["type"] == "shared" and patient_data.get("gender") != bed.get("gender_assigned"):
            return 0.0
        
        # Soft preferences
        if bed["status"] == "cleaning":
            score -= 20.0
        if bed.get("maintenance_scheduled"):
            score -= 15.0
        
        return max(0.0, score)
    
    def _calculate_occupancy_impact(self, bed: Dict[str, Any], forecast_data: Optional[Dict]) -> str:
        """Calculate impact on department occupancy."""
        if not forecast_data:
            return "unknown"
        
        # Simple impact calculation
        dept = bed["department"]
        return "low"  # Placeholder
    
    def _generate_reasoning(self, bed: Dict[str, Any], patient_data: Dict[str, Any], score: float) -> str:
        """Generate human-readable reasoning for recommendation."""
        reasons = []
        
        if patient_data.get("is_critical"):
            reasons.append(f"Critical patient - {bed['department']} required")
        if patient_data.get("requires_ventilator"):
            reasons.append(f"Ventilator support available")
        if score >= 90:
            reasons.append("Optimal match for patient requirements")
        elif score >= 70:
            reasons.append("Good match with minor considerations")
        
        return " | ".join(reasons) if reasons else "Standard bed assignment"

def create_bed_engine(historical_data: pd.DataFrame) -> BedRecommendationEngine:
    """Factory function to create bed recommendation engine."""
    return BedRecommendationEngine(historical_data)
