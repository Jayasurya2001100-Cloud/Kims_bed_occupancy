import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import {
  PatientRegistration, PayerChannel, BedRecommendation,
  BedRecommendationResponse, AdmissionResponse, BusinessRule, ModelMetadata, BedType
} from '../../models/registration.models';

@Component({
  selector: 'app-registration',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './registration.component.html',
  styleUrl: './registration.component.scss'
})
export class RegistrationComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private refreshInterval: any;

  // Wizard step
  step = 1; // 1=patient info, 2=recommendations, 3=confirmation

  patient: PatientRegistration = this.getEmptyPatient();
  payerChannels: PayerChannel[] = [];
  specialties: string[] = [];
  businessRules: Record<string, BusinessRule> = {};
  bedTypes: BedType[] = [];
  modelMetadata: ModelMetadata | null = null;
  recommendations: BedRecommendation[] = [];
  patientSummary: { predicted_los: number; payer_channel: string; priority: string } | null = null;
  selectedBed: BedRecommendation | null = null;
  loading = false;
  loadingConfig = true;
  admissionResponse: AdmissionResponse | null = null;
  recentAdmissions: AdmissionResponse[] = [];
  error: string | null = null;

  ngOnInit() {
    this.loadConfig();
    this.loadRecentAdmissions();
    this.refreshInterval = setInterval(() => this.loadRecentAdmissions(), 30000);
  }

  ngOnDestroy() {
    if (this.refreshInterval) clearInterval(this.refreshInterval);
  }

  loadConfig() {
    this.loadingConfig = true;
    let loaded = 0;
    const checkDone = () => { loaded++; if (loaded >= 5) { this.loadingConfig = false; this.cdr.markForCheck(); } };

    this.api.getPayerChannels().subscribe({
      next: (res) => { this.payerChannels = res.payer_channels; checkDone(); },
      error: () => checkDone()
    });
    this.api.getSpecialties().subscribe({
      next: (res) => { this.specialties = res.specialties; checkDone(); },
      error: () => checkDone()
    });
    this.api.getBusinessRules().subscribe({
      next: (res) => { this.businessRules = res.business_rules; checkDone(); },
      error: () => checkDone()
    });
    this.api.getBedTypes().subscribe({
      next: (res) => { this.bedTypes = res.bed_types; checkDone(); },
      error: () => checkDone()
    });
    this.api.getModelMetadata().subscribe({
      next: (res) => { this.modelMetadata = res; checkDone(); },
      error: () => checkDone()
    });
  }

  loadRecentAdmissions() {
    this.api.getRecentAdmissions(5).subscribe({
      next: (res) => { this.recentAdmissions = res.admissions; this.cdr.markForCheck(); },
      error: () => {}
    });
  }

  isPatientFormValid(): boolean {
    const p = this.patient;
    return !!(p.first_name && p.last_name && p.age > 0 && p.gender && p.condition && p.specialty && p.payer_channel);
  }

  getAppliedRules(): { key: string; rule: BusinessRule }[] {
    const applied: { key: string; rule: BusinessRule }[] = [];
    const p = this.patient;
    // Rule Group 1 – Clinical Priority
    if (p.is_critical && this.businessRules['critical']) applied.push({ key: 'Critical Priority', rule: this.businessRules['critical'] });
    if (p.requires_ventilator && this.businessRules['ventilator']) applied.push({ key: 'Ventilator', rule: this.businessRules['ventilator'] });
    if (p.requires_isolation && this.businessRules['isolation']) applied.push({ key: 'Isolation', rule: this.businessRules['isolation'] });
    if (p.requires_dialysis && this.businessRules['dialysis']) applied.push({ key: 'Dialysis', rule: this.businessRules['dialysis'] });
    // Rule Group 3 – Pediatric
    if (p.age > 0 && p.age < (this.businessRules['pediatric']?.age_threshold ?? 14) && this.businessRules['pediatric']) {
      applied.push({ key: 'Pediatric', rule: this.businessRules['pediatric'] });
    }
    // Rule Group 4 – Gender
    if (this.businessRules['gender_restriction']) {
      applied.push({ key: 'Gender', rule: this.businessRules['gender_restriction'] });
    }
    // Rule Group 5 – Payer
    const payerName = this.getPayerName(p.payer_channel);
    const payerRules = this.businessRules['payer_rules'] as any;
    if (payerRules && payerRules[payerName]) {
      applied.push({ key: 'Payer: ' + payerName, rule: payerRules[payerName] });
    }
    // Rule Group 6 – Length of Stay
    if (this.businessRules['long_stay']) {
      applied.push({ key: 'LOS Rules', rule: this.businessRules['long_stay'] });
    }
    // Rule Group 7 – Availability
    if (this.businessRules['availability']) {
      applied.push({ key: 'Availability', rule: this.businessRules['availability'] });
    }
    // Rule Group 8 – Occupancy Optimization
    if (this.businessRules['occupancy_optimization']) {
      applied.push({ key: 'Occupancy Optimization', rule: this.businessRules['occupancy_optimization'] });
    }
    // Rule Group 9 – Revenue Optimization
    if (this.businessRules['revenue_optimization']) {
      applied.push({ key: 'Revenue Optimization', rule: this.businessRules['revenue_optimization'] });
    }
    return applied;
  }

  getAvailableRoomTypes(): string[] {
    const payerName = this.getPayerName(this.patient.payer_channel);
    const payerRules = this.businessRules['payer_rules'] as any;
    if (payerRules && payerRules[payerName]?.allowed_room_types) {
      return payerRules[payerName].allowed_room_types;
    }
    return this.bedTypes.map(bt => bt.name);
  }

  getRoomTypeDescription(name: string): string {
    const bt = this.bedTypes.find(b => b.name === name);
    if (!bt) return '';
    const caps: Record<string, string> = {
      'General Ward': '6 beds in a large hall',
      'Shared Ward': '4 beds per room',
      'Semi Private': '2 beds per room',
      'Private Room': '1 bed, attached bathroom',
      'Deluxe Room': '1 bed, sofa, TV, attendant space',
      'Suite': '1 bed, separate living area',
    };
    return caps[name] || bt.description || '';
  }

  getPayerName(id: string): string {
    return this.payerChannels.find(p => p.id === id)?.name ?? id;
  }

  goToRecommendations() {
    if (!this.isPatientFormValid()) return;
    this.step = 2;
    this.loading = true;
    this.error = null;
    this.cdr.markForCheck();
    this.api.recommendBeds(this.patient).subscribe({
      next: (res: BedRecommendationResponse) => {
        this.recommendations = res.recommendations;
        this.patientSummary = res.patient_summary;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.error = 'Failed to get bed recommendations. Please try again.';
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
  }

  selectBed(rec: BedRecommendation) {
    this.selectedBed = rec;
  }

  confirmAdmission() {
    if (!this.selectedBed) return;
    this.loading = true;
    this.error = null;
    this.cdr.markForCheck();
    this.api.registerAdmission(this.patient, this.selectedBed.bed_id).subscribe({
      next: (res: AdmissionResponse) => {
        this.admissionResponse = res;
        this.step = 3;
        this.loading = false;
        this.loadRecentAdmissions();
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.error = 'Failed to register admission. Please try again.';
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
  }

  goBack() {
    if (this.step === 2) {
      this.step = 1;
      this.recommendations = [];
      this.selectedBed = null;
      this.error = null;
    }
  }

  reset() {
    this.patient = this.getEmptyPatient();
    this.recommendations = [];
    this.selectedBed = null;
    this.patientSummary = null;
    this.admissionResponse = null;
    this.error = null;
    this.step = 1;
  }

  getScoreClass(score: number): string {
    if (score >= 90) return 'high';
    if (score >= 70) return 'medium';
    return 'low';
  }

  private getEmptyPatient(): PatientRegistration {
    return {
      first_name: '',
      last_name: '',
      age: 0,
      gender: '',
      condition: '',
      specialty: '',
      payer_channel: '',
      room_preference: '',
      is_critical: false,
      requires_ventilator: false,
      requires_isolation: false,
      requires_dialysis: false,
      notes: ''
    };
  }
}
