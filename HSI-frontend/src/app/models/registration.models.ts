export interface PayerChannel {
  id: string;
  name: string;
  avg_los_multiplier: number;
  priority: number;
}

export interface BusinessRule {
  required_department?: string;
  required_bed_type?: string;
  avoid_bed_type?: string;
  los_threshold?: number;
  age_threshold?: number;
  priority: number;
}

export interface BedType {
  id: string;
  name: string;
  base_rate: number;
}

export interface PatientRegistration {
  first_name: string;
  last_name: string;
  age: number;
  gender: string;
  condition: string;
  specialty: string;
  payer_channel: string;
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
  predicted_los: number;
  occupancy_impact: string;
  reasoning: string;
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
  status: string;
  timestamp: string;
}

export interface PayerForecast {
  payer_channel: string;
  payer_name: string;
  expected_admissions: number;
  avg_los: number;
  predicted_occupancy_impact: number;
  confidence: string;
}

export interface OccupancyAlert {
  type: string;
  severity: string;
  message: string;
  department: string;
  timestamp: string;
}

export interface BedStatus {
  department: string;
  total_beds: number;
  available: number;
  occupied: number;
  cleaning: number;
  maintenance: number;
  reserved: number;
  predicted_occupancy_tomorrow: number;
  overflow_risk: string;
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
