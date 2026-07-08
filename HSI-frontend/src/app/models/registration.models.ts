export interface PayerChannel {
  id: string;
  name: string;
  avg_los_multiplier: number;
  priority: number;
  color?: string;
  revenue_weight?: number;
}

export interface BusinessRule {
  required_department?: string;
  required_bed_type?: string;
  required_room_type?: string;
  avoid_bed_type?: string;
  avoid_room_type?: string;
  los_threshold?: number;
  age_threshold?: number;
  priority: number;
  description?: string;
  applies_to?: string[];
  allowed_room_types?: string[];
  prefer_room_types?: string[];
  validate_eligibility?: boolean;
  validate_entitlement?: boolean;
  patient_preference?: boolean;
}

export interface BedType {
  id: string;
  name: string;
  base_rate: number;
  capacity?: number;
  description?: string;
}

export interface PatientRegistration {
  first_name: string;
  last_name: string;
  age: number;
  gender: string;
  condition: string;
  specialty: string;
  payer_channel: string;
  room_preference?: string;
  is_critical: boolean;
  requires_ventilator: boolean;
  requires_isolation: boolean;
  requires_dialysis: boolean;
  notes?: string;
}

export interface BedRecommendation {
  bed_id: string;
  department: string;
  bed_type: string;
  room: string;
  score: number;
  score_breakdown?: {
    clinical: number;
    specialty: number;
    severity: number;
    payer: number;
    los: number;
    occupancy: number;
    revenue: number;
  };
  predicted_los: number;
  occupancy_impact: string;
  reasoning: string;
  llm_reasoning?: string;
}

export interface BedRecommendationResponse {
  recommendations: BedRecommendation[];
  timestamp: string;
  patient_summary: {
    predicted_los: number;
    payer_channel: string;
    priority: string;
  };
}

export interface AdmissionResponse {
  admission_id: string;
  patient: PatientRegistration;
  allocated_bed: BedRecommendation;
  predicted_los: number;
  estimated_discharge?: string;
  status: string;
  timestamp: string;
}

export interface PayerForecast {
  payer_channel: string;
  payer_name: string;
  color?: string;
  expected_admissions: number;
  avg_los: number;
  predicted_occupancy_impact: number;
  bed_utilization?: number;
  revenue_contribution?: number;
  confidence: string;
  forecast_accuracy?: number;
}

export interface OccupancyAlert {
  type: string;
  severity: string;
  message: string;
  department: string;
  threshold?: number;
  current_rate?: number;
  available_beds?: number | null;
  timestamp: string;
}

export interface AlertRule {
  id: string;
  label: string;
  department: string | null;
  threshold: number;
  severity: string;
  description: string;
}

export interface BedStatus {
  department: string;
  total_beds: number;
  available: number;
  occupied: number;
  cleaning: number;
  maintenance: number;
  reserved: number;
  occupancy_rate?: number;
  predicted_occupancy_tomorrow: number;
  overflow_risk: string;
}

export interface BedStatusSummary {
  total_beds: number;
  total_occupied: number;
  total_available: number;
  hospital_occupancy_rate: number;
}

export interface ModelMetadata {
  model_name: string;
  engine: string;
  mape: number;
  rmse: number;
  last_trained: string;
  data_range: {
    start: string;
    end: string;
  };
  version: string;
}
