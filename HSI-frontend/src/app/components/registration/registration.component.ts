import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { PatientRegistration, PayerChannel, BedRecommendation } from '../../models/registration.models';

@Component({
  selector: 'app-registration',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './registration.component.html',
  styleUrl: './registration.component.scss'
})
export class RegistrationComponent implements OnInit {
  private api = inject(ApiService);

  patient: PatientRegistration = this.getEmptyPatient();
  payerChannels: PayerChannel[] = [];
  specialties: string[] = [];
  recommendations: BedRecommendation[] = [];
  selectedBed: string | null = null;
  loading = false;
  admissionConfirmed = false;
  admissionResponse: any = null;

  ngOnInit() {
    this.loadConfig();
  }

  loadConfig() {
    this.api.getPayerChannels().subscribe({
      next: (res) => this.payerChannels = res.payer_channels,
      error: (err) => console.error('Failed to load payer channels', err)
    });

    this.api.getSpecialties().subscribe({
      next: (res) => this.specialties = res.specialties,
      error: (err) => console.error('Failed to load specialties', err)
    });
  }

  getRecommendations() {
    this.loading = true;
    this.api.recommendBeds(this.patient).subscribe({
      next: (res) => {
        this.recommendations = res.recommendations;
        this.loading = false;
      },
      error: (err) => {
        console.error('Failed to get recommendations', err);
        this.loading = false;
      }
    });
  }

  selectBed(rec: BedRecommendation) {
    this.selectedBed = rec.bed_id;
  }

  onSubmit() {
    if (!this.selectedBed) return;
    
    this.loading = true;
    this.api.registerAdmission(this.patient, this.selectedBed).subscribe({
      next: (res) => {
        this.admissionResponse = res;
        this.admissionConfirmed = true;
        this.loading = false;
      },
      error: (err) => {
        console.error('Failed to register admission', err);
        this.loading = false;
      }
    });
  }

  reset() {
    this.patient = this.getEmptyPatient();
    this.recommendations = [];
    this.selectedBed = null;
    this.admissionConfirmed = false;
    this.admissionResponse = null;
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
      is_critical: false,
      requires_ventilator: false,
      requires_isolation: false,
      requires_dialysis: false,
      notes: ''
    };
  }
}
