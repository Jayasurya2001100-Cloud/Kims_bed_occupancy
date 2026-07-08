import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { PayerForecast, PayerChannel, ModelMetadata } from '../../models/registration.models';

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
            <option [value]="''">All Payers</option>
            <option *ngFor="let p of payerChannels" [value]="p.id">{{ p.name }}</option>
          </select>
        </label>
        <div class="model-info" *ngIf="modelMetadata">
          <span class="model-badge">{{ modelMetadata.engine }}</span>
          <span class="model-accuracy">MAPE: {{ (modelMetadata.mape * 100).toFixed(1) }}%</span>
        </div>
      </div>

      <!-- KPI Summary -->
      <div class="kpi-row" *ngIf="!loading && forecasts.length > 0">
        <div class="kpi-card">
          <div class="kpi-value">{{ getTotalAdmissions() }}</div>
          <div class="kpi-label">Total Expected Admissions</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ getAvgLOS() }}</div>
          <div class="kpi-label">Avg. Length of Stay (days)</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ getAvgOccupancyImpact() }}%</div>
          <div class="kpi-label">Avg. Occupancy Impact</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ forecasts.length }}</div>
          <div class="kpi-label">Active Payer Channels</div>
        </div>
      </div>

      <div class="forecasts-grid" *ngIf="!loading && forecasts.length > 0">
        <div *ngFor="let forecast of forecasts" class="payer-card" [style.border-top-color]="forecast.color || '#007DB0'">
          <div class="payer-header">
            <div class="payer-title">
              <div class="payer-color" [style.background]="forecast.color || '#007DB0'"></div>
              <h3>{{ forecast.payer_name }}</h3>
            </div>
            <span class="badge" [class]="forecast.confidence">
              {{ forecast.confidence }}
            </span>
          </div>

          <div class="metrics">
            <div class="metric">
              <div class="metric-label">Expected Admissions</div>
              <div class="metric-value">{{ forecast.expected_admissions }}</div>
            </div>
            <div class="metric">
              <div class="metric-label">Avg. LOS</div>
              <div class="metric-value">{{ forecast.avg_los.toFixed(1) }}d</div>
            </div>
            <div class="metric">
              <div class="metric-label">Occupancy Impact</div>
              <div class="metric-value">{{ forecast.predicted_occupancy_impact }}%</div>
            </div>
          </div>

          <div class="detail-rows">
            <div class="detail-row" *ngIf="forecast.bed_utilization != null">
              <span>Bed Utilization</span>
              <div class="bar-container">
                <div class="bar-fill" [style.width.%]="forecast.bed_utilization" [style.background]="forecast.color || '#007DB0'"></div>
              </div>
              <span class="bar-val">{{ forecast.bed_utilization }}%</span>
            </div>
            <div class="detail-row" *ngIf="forecast.revenue_contribution != null">
              <span>Revenue Share</span>
              <div class="bar-container">
                <div class="bar-fill revenue" [style.width.%]="forecast.revenue_contribution" [style.background]="forecast.color || '#007DB0'"></div>
              </div>
              <span class="bar-val">{{ forecast.revenue_contribution }}%</span>
            </div>
            <div class="detail-row" *ngIf="forecast.forecast_accuracy != null">
              <span>Forecast Accuracy</span>
              <div class="bar-container">
                <div class="bar-fill accuracy" [style.width.%]="forecast.forecast_accuracy"></div>
              </div>
              <span class="bar-val">{{ forecast.forecast_accuracy }}%</span>
            </div>
          </div>
        </div>
      </div>

      <div class="loading" *ngIf="loading">Loading payer forecasts...</div>
      <div class="empty-state" *ngIf="!loading && forecasts.length === 0 && !error">No payer data available.</div>
      <div class="error" *ngIf="error">{{ error }}</div>
    </div>
  `,
  styles: [`
    .payer-intelligence-container {
      padding: 2rem;
      max-width: 1400px;
      margin: 0 auto;
    }
    h1 { margin-bottom: 2rem; color: var(--blue-dk); font-size: 2rem; }
    .controls {
      display: flex;
      gap: 1.5rem;
      align-items: flex-end;
      margin-bottom: 2rem;
      padding: 1.25rem;
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .controls label {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      font-weight: 600;
      font-size: 0.875rem;
    }
    .controls select {
      padding: 0.625rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      min-width: 150px;
      font-size: 0.875rem;
    }
    .model-info {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .model-badge {
      padding: 0.375rem 0.75rem;
      background: linear-gradient(135deg, var(--blue-dk), var(--blue));
      color: white;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .model-accuracy {
      font-size: 0.8125rem;
      color: var(--text-secondary);
      font-weight: 600;
    }
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .kpi-card {
      background: white;
      padding: 1.25rem;
      border-radius: 8px;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      border-top: 3px solid var(--blue);
    }
    .kpi-value {
      font-size: 2rem;
      font-weight: 700;
      color: var(--blue-dk);
    }
    .kpi-label {
      margin-top: 0.25rem;
      font-size: 0.75rem;
      color: var(--text-secondary);
      text-transform: uppercase;
    }
    .forecasts-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
      gap: 1.5rem;
    }
    .payer-card {
      background: white;
      border-radius: 8px;
      padding: 1.5rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      transition: transform 0.2s;
      border-top: 4px solid var(--blue);
    }
    .payer-card:hover {
      transform: translateY(-3px);
      box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    }
    .payer-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.25rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border);
    }
    .payer-title {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .payer-color {
      width: 12px;
      height: 12px;
      border-radius: 3px;
    }
    .payer-header h3 {
      margin: 0;
      color: var(--blue-dk);
      font-size: 1.125rem;
    }
    .badge {
      padding: 0.25rem 0.75rem;
      border-radius: 12px;
      font-size: 0.6875rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .badge.high { background: var(--green-lt); color: var(--green-dk); }
    .badge.medium { background: var(--yellow-lt); color: var(--yellow-dk); }
    .badge.low { background: #f5f5f5; color: var(--gray); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.75rem;
      margin-bottom: 1.25rem;
    }
    .metric {
      text-align: center;
      padding: 0.5rem;
      background: var(--surface);
      border-radius: 6px;
    }
    .metric-label {
      font-size: 0.625rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      margin-bottom: 0.25rem;
      letter-spacing: 0.03em;
    }
    .metric-value {
      font-size: 1.375rem;
      font-weight: 700;
      color: var(--blue-dk);
    }
    .detail-rows {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }
    .detail-row {
      display: grid;
      grid-template-columns: 110px 1fr 50px;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.8125rem;
    }
    .bar-container {
      height: 8px;
      background: var(--bg-gray);
      border-radius: 4px;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      border-radius: 4px;
      transition: width 0.4s ease;
    }
    .bar-fill.accuracy { background: var(--green); }
    .bar-val {
      text-align: right;
      font-weight: 600;
      color: var(--blue-dk);
      font-size: 0.75rem;
    }
    .loading, .error, .empty-state {
      text-align: center;
      padding: 3rem;
      color: var(--text-secondary);
      font-size: 1rem;
    }
    .error { color: var(--red); }
  `]
})
export class PayerIntelligenceComponent implements OnInit {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);

  forecasts: PayerForecast[] = [];
  payerChannels: PayerChannel[] = [];
  modelMetadata: ModelMetadata | null = null;
  forecastDays = 30;
  selectedPayer = '';
  loading = true;
  error: string | null = null;

  ngOnInit() {
    this.loadPayerChannels();
    this.loadModelMetadata();
    this.loadForecasts();
  }

  loadPayerChannels() {
    this.api.getPayerChannels().subscribe({
      next: (res) => { this.payerChannels = res.payer_channels; this.cdr.markForCheck(); },
      error: () => {}
    });
  }

  loadModelMetadata() {
    this.api.getModelMetadata().subscribe({
      next: (res) => { this.modelMetadata = res; this.cdr.markForCheck(); },
      error: () => {}
    });
  }

  loadForecasts() {
    this.loading = true;
    this.error = null;
    this.cdr.markForCheck();
    this.api.getPayerForecast(this.forecastDays, this.selectedPayer || undefined).subscribe({
      next: (res) => {
        this.forecasts = res.payer_forecasts;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = 'Failed to load payer forecasts. Ensure backend is running.';
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
  }

  getTotalAdmissions(): number {
    return this.forecasts.reduce((sum, f) => sum + f.expected_admissions, 0);
  }

  getAvgLOS(): string {
    if (this.forecasts.length === 0) return '0';
    return (this.forecasts.reduce((sum, f) => sum + f.avg_los, 0) / this.forecasts.length).toFixed(1);
  }

  getAvgOccupancyImpact(): string {
    if (this.forecasts.length === 0) return '0';
    return (this.forecasts.reduce((sum, f) => sum + f.predicted_occupancy_impact, 0) / this.forecasts.length).toFixed(1);
  }
}
