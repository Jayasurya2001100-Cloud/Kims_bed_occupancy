import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { PayerForecast, PayerChannel } from '../../models/registration.models';

@Component({
  selector: 'app-payer-intelligence',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="payer-intelligence-container">
      <h1>Payer Intelligence & Demand Forecasting</h1>

      <div class="controls">
        <label>
          Forecast Days:
          <select [(ngModel)]="forecastDays" (change)="loadForecasts()">
            <option [value]="7">7 Days</option>
            <option [value]="14">14 Days</option>
            <option [value]="30">30 Days</option>
            <option [value]="60">60 Days</option>
            <option [value]="90">90 Days</option>
          </select>
        </label>
        <label>
          Filter by Payer:
          <select [(ngModel)]="selectedPayer" (change)="loadForecasts()">
            <option [value]="null">All Payers</option>
            <option *ngFor="let p of payerChannels" [value]="p.id">{{ p.name }}</option>
          </select>
        </label>
      </div>

      <div class="forecasts-grid" *ngIf="!loading && forecasts.length > 0">
        <div *ngFor="let forecast of forecasts" class="payer-card">
          <div class="payer-header">
            <h3>{{ forecast.payer_name }}</h3>
            <span class="badge" [class.high]="forecast.confidence === 'high'" [class.medium]="forecast.confidence === 'medium'">
              {{ forecast.confidence }} confidence
            </span>
          </div>
          <div class="metrics">
            <div class="metric">
              <label>Expected Admissions</label>
              <div class="value">{{ forecast.expected_admissions }}</div>
            </div>
            <div class="metric">
              <label>Avg. LOS</label>
              <div class="value">{{ forecast.avg_los.toFixed(1) }} days</div>
            </div>
            <div class="metric">
              <label>Occupancy Impact</label>
              <div class="value">{{ forecast.predicted_occupancy_impact }}%</div>
            </div>
          </div>
          <div class="impact-bar">
            <div class="fill" [style.width.%]="forecast.predicted_occupancy_impact"></div>
          </div>
        </div>
      </div>

      <div class="loading" *ngIf="loading">Loading payer forecasts...</div>
      <div class="error" *ngIf="error">{{ error }}</div>
    </div>
  `,
  styles: [`
    .payer-intelligence-container {
      padding: 2rem;
      max-width: 1400px;
      margin: 0 auto;
    }
    h1 { margin-bottom: 2rem; color: var(--blue-dk); }
    .controls {
      display: flex;
      gap: 1rem;
      margin-bottom: 2rem;
      padding: 1rem;
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .controls label {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      font-weight: 600;
    }
    .controls select {
      padding: 0.5rem;
      border: 1px solid var(--border);
      border-radius: 4px;
      min-width: 150px;
    }
    .forecasts-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
      gap: 1.5rem;
    }
    .payer-card {
      background: white;
      border-radius: 8px;
      padding: 1.5rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      transition: transform 0.2s;
    }
    .payer-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .payer-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      padding-bottom: 1rem;
      border-bottom: 2px solid var(--border);
    }
    .payer-header h3 {
      margin: 0;
      color: var(--blue-dk);
      font-size: 1.25rem;
    }
    .badge {
      padding: 0.25rem 0.75rem;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge.high { background: var(--green-lt); color: var(--green-dk); }
    .badge.medium { background: var(--yellow-lt); color: var(--yellow-dk); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1rem;
      margin-bottom: 1rem;
    }
    .metric {
      text-align: center;
    }
    .metric label {
      display: block;
      font-size: 0.75rem;
      color: var(--text-secondary);
      margin-bottom: 0.25rem;
      text-transform: uppercase;
    }
    .metric .value {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--blue-dk);
    }
    .impact-bar {
      height: 8px;
      background: var(--bg-gray);
      border-radius: 4px;
      overflow: hidden;
    }
    .impact-bar .fill {
      height: 100%;
      background: linear-gradient(90deg, var(--blue), var(--blue-lt));
      transition: width 0.3s ease;
    }
    .loading, .error {
      text-align: center;
      padding: 2rem;
      color: var(--text-secondary);
    }
    .error { color: var(--red); }
  `]
})
export class PayerIntelligenceComponent implements OnInit {
  private api = inject(ApiService);

  forecasts: PayerForecast[] = [];
  payerChannels: PayerChannel[] = [];
  forecastDays = 30;
  selectedPayer: string | null = null;
  loading = false;
  error: string | null = null;

  ngOnInit() {
    this.loadPayerChannels();
    this.loadForecasts();
  }

  loadPayerChannels() {
    this.api.getPayerChannels().subscribe({
      next: (res) => this.payerChannels = res.payer_channels,
      error: (err) => console.error('Failed to load payer channels', err)
    });
  }

  loadForecasts() {
    this.loading = true;
    this.error = null;
    this.api.getPayerForecast(this.forecastDays, this.selectedPayer || undefined).subscribe({
      next: (res) => {
        this.forecasts = res.payer_forecasts;
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Failed to load payer forecasts';
        this.loading = false;
        console.error(err);
      }
    });
  }
}
