import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { BedStatus, ModelMetadata } from '../../models/registration.models';

@Component({
  selector: 'app-bed-allocation-monitor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="monitor-container">
      <h1>Bed Allocation Monitor</h1>

      <div class="controls">
        <label>
          Filter by Department:
          <select [(ngModel)]="departmentFilter" (change)="loadBedStatus()">
            <option [value]="null">All Departments</option>
            <option *ngFor="let dept of departments" [value]="dept">{{ dept }}</option>
          </select>
        </label>
        <button (click)="loadBedStatus()" class="btn-refresh">🔄 Refresh</button>
      </div>

      <div class="ml-metadata" *ngIf="modelMetadata">
        <div class="metadata-card">
          <h3>ML Model Status</h3>
          <div class="metadata-grid">
            <div><strong>Model:</strong> {{ modelMetadata.model_name }}</div>
            <div><strong>Engine:</strong> {{ modelMetadata.engine }}</div>
            <div><strong>MAPE:</strong> {{ modelMetadata.mape.toFixed(2) }}%</div>
            <div><strong>Version:</strong> {{ modelMetadata.version }}</div>
          </div>
          <div class="metadata-footer">
            Last trained: {{ formatDate(modelMetadata.last_trained) }}
          </div>
        </div>
      </div>

      <div class="beds-grid" *ngIf="!loading && bedStatuses.length > 0">
        <div *ngFor="let status of bedStatuses" class="bed-status-card">
          <div class="card-header">
            <h3>{{ status.department }}</h3>
            <span class="risk-badge" [class]="status.overflow_risk">
              {{ status.overflow_risk }} risk
            </span>
          </div>

          <div class="capacity-summary">
            <div class="capacity-bar">
              <div class="occupied" [style.width.%]="getOccupiedPercentage(status)"></div>
              <div class="cleaning" [style.width.%]="getCleaningPercentage(status)"></div>
              <div class="maintenance" [style.width.%]="getMaintenancePercentage(status)"></div>
            </div>
            <div class="capacity-legend">
              <span class="legend-item occupied">Occupied</span>
              <span class="legend-item cleaning">Cleaning</span>
              <span class="legend-item maintenance">Maintenance</span>
              <span class="legend-item available">Available</span>
            </div>
          </div>

          <div class="metrics-grid">
            <div class="metric">
              <div class="metric-value">{{ status.available }}</div>
              <div class="metric-label">Available</div>
            </div>
            <div class="metric">
              <div class="metric-value">{{ status.occupied }}</div>
              <div class="metric-label">Occupied</div>
            </div>
            <div class="metric">
              <div class="metric-value">{{ status.cleaning }}</div>
              <div class="metric-label">Cleaning</div>
            </div>
            <div class="metric">
              <div class="metric-value">{{ status.maintenance }}</div>
              <div class="metric-label">Maintenance</div>
            </div>
          </div>

          <div class="prediction">
            <div class="prediction-label">Tomorrow's Predicted Occupancy</div>
            <div class="prediction-value">{{ status.predicted_occupancy_tomorrow }}%</div>
            <div class="prediction-trend" [class.rising]="status.predicted_occupancy_tomorrow > getOccupiedPercentage(status)">
              {{ status.predicted_occupancy_tomorrow > getOccupiedPercentage(status) ? '📈 Rising' : '📉 Stable/Falling' }}
            </div>
          </div>

          <div class="actions">
            <button class="btn-action">View Details</button>
            <button class="btn-action">Allocate Bed</button>
          </div>
        </div>
      </div>

      <div class="loading" *ngIf="loading">Loading bed status...</div>
      <div class="error" *ngIf="error">{{ error }}</div>
    </div>
  `,
  styles: [`
    .monitor-container {
      padding: 2rem;
      max-width: 1400px;
      margin: 0 auto;
    }
    h1 { margin-bottom: 2rem; color: var(--blue-dk); }
    .controls {
      display: flex;
      gap: 1rem;
      align-items: flex-end;
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
      min-width: 200px;
    }
    .btn-refresh {
      padding: 0.5rem 1rem;
      background: var(--blue);
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 600;
    }
    .btn-refresh:hover { background: var(--blue-dk); }
    .ml-metadata {
      margin-bottom: 2rem;
    }
    .metadata-card {
      background: linear-gradient(135deg, var(--blue-dk), var(--blue));
      color: white;
      padding: 1.5rem;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .metadata-card h3 {
      margin: 0 0 1rem 0;
      font-size: 1.25rem;
    }
    .metadata-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin-bottom: 1rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid rgba(255,255,255,0.2);
    }
    .metadata-footer {
      font-size: 0.875rem;
      opacity: 0.9;
    }
    .beds-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
      gap: 1.5rem;
    }
    .bed-status-card {
      background: white;
      border-radius: 8px;
      padding: 1.5rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      transition: transform 0.2s;
    }
    .bed-status-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
      padding-bottom: 1rem;
      border-bottom: 2px solid var(--border);
    }
    .card-header h3 {
      margin: 0;
      color: var(--blue-dk);
      font-size: 1.25rem;
    }
    .risk-badge {
      padding: 0.25rem 0.75rem;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .risk-badge.low { background: var(--green-lt); color: var(--green-dk); }
    .risk-badge.medium { background: var(--yellow-lt); color: var(--yellow-dk); }
    .risk-badge.high { background: #ffe5e5; color: #e74c3c; }
    .capacity-summary {
      margin-bottom: 1rem;
    }
    .capacity-bar {
      height: 32px;
      border-radius: 4px;
      overflow: hidden;
      display: flex;
      background: var(--bg-gray);
      margin-bottom: 0.5rem;
    }
    .capacity-bar > div {
      transition: width 0.3s ease;
    }
    .capacity-bar .occupied { background: var(--blue); }
    .capacity-bar .cleaning { background: var(--yellow); }
    .capacity-bar .maintenance { background: var(--red); }
    .capacity-legend {
      display: flex;
      gap: 1rem;
      font-size: 0.75rem;
      flex-wrap: wrap;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 0.25rem;
    }
    .legend-item::before {
      content: '';
      width: 12px;
      height: 12px;
      border-radius: 2px;
    }
    .legend-item.occupied::before { background: var(--blue); }
    .legend-item.cleaning::before { background: var(--yellow); }
    .legend-item.maintenance::before { background: var(--red); }
    .legend-item.available::before { background: var(--green); }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin-bottom: 1rem;
      padding: 1rem 0;
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
    }
    .metric {
      text-align: center;
    }
    .metric-value {
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--blue-dk);
    }
    .metric-label {
      font-size: 0.75rem;
      color: var(--text-secondary);
      margin-top: 0.25rem;
      text-transform: uppercase;
    }
    .prediction {
      background: var(--bg-gray);
      padding: 1rem;
      border-radius: 4px;
      margin-bottom: 1rem;
      text-align: center;
    }
    .prediction-label {
      font-size: 0.75rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      margin-bottom: 0.5rem;
    }
    .prediction-value {
      font-size: 2rem;
      font-weight: 700;
      color: var(--blue-dk);
      margin-bottom: 0.25rem;
    }
    .prediction-trend {
      font-size: 0.875rem;
      color: var(--text-secondary);
    }
    .prediction-trend.rising { color: var(--red); }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.5rem;
    }
    .btn-action {
      padding: 0.75rem 1rem;
      background: white;
      border: 2px solid var(--blue);
      color: var(--blue);
      border-radius: 4px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.2s;
    }
    .btn-action:hover {
      background: var(--blue);
      color: white;
    }
    .loading, .error {
      text-align: center;
      padding: 2rem;
      color: var(--text-secondary);
    }
    .error { color: var(--red); }
  `]
})
export class BedAllocationMonitorComponent implements OnInit {
  private api = inject(ApiService);

  bedStatuses: BedStatus[] = [];
  departments: string[] = [];
  departmentFilter: string | null = null;
  modelMetadata: ModelMetadata | null = null;
  loading = false;
  error: string | null = null;

  ngOnInit() {
    this.loadDepartments();
    this.loadModelMetadata();
    this.loadBedStatus();
    // Auto-refresh every 30 seconds
    setInterval(() => this.loadBedStatus(), 30000);
  }

  loadDepartments() {
    this.api.getDepartments().subscribe({
      next: (depts) => this.departments = depts,
      error: (err) => console.error('Failed to load departments', err)
    });
  }

  loadModelMetadata() {
    this.api.getModelMetadata().subscribe({
      next: (metadata) => this.modelMetadata = metadata,
      error: (err) => console.error('Failed to load model metadata', err)
    });
  }

  loadBedStatus() {
    this.loading = true;
    this.error = null;
    this.api.getBedStatus(this.departmentFilter || undefined).subscribe({
      next: (res) => {
        this.bedStatuses = res.departments;
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Failed to load bed status';
        this.loading = false;
        console.error(err);
      }
    });
  }

  getOccupiedPercentage(status: BedStatus): number {
    return Math.round((status.occupied / status.total_beds) * 100);
  }

  getCleaningPercentage(status: BedStatus): number {
    return Math.round((status.cleaning / status.total_beds) * 100);
  }

  getMaintenancePercentage(status: BedStatus): number {
    return Math.round((status.maintenance / status.total_beds) * 100);
  }

  formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleString();
  }
}
