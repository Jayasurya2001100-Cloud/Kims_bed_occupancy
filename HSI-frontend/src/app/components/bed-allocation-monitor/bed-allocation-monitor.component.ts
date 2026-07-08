import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { BedStatus, BedStatusSummary, ModelMetadata, AdmissionResponse } from '../../models/registration.models';

@Component({
  selector: 'app-bed-allocation-monitor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="monitor-container">
      <div class="page-header">
        <h1>Bed Allocation Monitor</h1>
        <span class="auto-refresh-badge">Auto-refresh: 30s</span>
      </div>

      <div class="controls">
        <label>
          Department:
          <select [(ngModel)]="departmentFilter" (change)="loadBedStatus()">
            <option value="">All Departments</option>
            <option *ngFor="let dept of departments" [value]="dept">{{ dept }}</option>
          </select>
        </label>
        <button (click)="loadBedStatus()" class="btn-refresh" [disabled]="loading">
          {{ loading ? 'Refreshing...' : 'Refresh Now' }}
        </button>
      </div>

      <!-- Hospital-wide KPIs -->
      <div class="kpi-row" *ngIf="summary && !loading">
        <div class="kpi-card">
          <div class="kpi-value">{{ summary.total_beds }}</div>
          <div class="kpi-label">Total Beds</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ summary.total_occupied }}</div>
          <div class="kpi-label">Occupied</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-value">{{ summary.total_available }}</div>
          <div class="kpi-label">Available</div>
        </div>
        <div class="kpi-card" [class.kpi-warning]="summary.hospital_occupancy_rate > 85">
          <div class="kpi-value">{{ summary.hospital_occupancy_rate.toFixed(1) }}%</div>
          <div class="kpi-label">Hospital Occupancy</div>
        </div>
      </div>

      <!-- ML Model Metadata -->
      <div class="ml-metadata" *ngIf="modelMetadata">
        <div class="metadata-card">
          <div class="metadata-grid">
            <div class="meta-item">
              <div class="meta-label">Model</div>
              <div class="meta-value">{{ modelMetadata.model_name }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Engine</div>
              <div class="meta-value">{{ modelMetadata.engine }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">MAPE</div>
              <div class="meta-value">{{ (modelMetadata.mape * 100).toFixed(1) }}%</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Version</div>
              <div class="meta-value">{{ modelMetadata.version }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Last Trained</div>
              <div class="meta-value">{{ formatDate(modelMetadata.last_trained) }}</div>
            </div>
            <div class="meta-item">
              <div class="meta-label">Data Range</div>
              <div class="meta-value">{{ modelMetadata.data_range.start }} to {{ modelMetadata.data_range.end }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bed Status Grid -->
      <div class="beds-grid" *ngIf="!loading && bedStatuses.length > 0">
        <div *ngFor="let status of bedStatuses" class="bed-status-card" 
             [class.card-critical]="status.overflow_risk === 'high'"
             [class.card-selected]="selectedDepartment === status.department"
             (click)="selectDepartment(status.department)">
          <div class="card-header">
            <h3>{{ status.department }}</h3>
            <span class="risk-badge" [class]="status.overflow_risk">
              {{ status.overflow_risk }} risk
            </span>
          </div>

          <!-- Occupancy Rate Circle -->
          <div class="occupancy-display">
            <div class="occ-circle" [class]="getOccupancyClass(status)">
              <span class="occ-pct">{{ getOccupiedPercentage(status) }}%</span>
              <span class="occ-sub">occupied</span>
            </div>
          </div>

          <!-- Capacity Bar -->
          <div class="capacity-summary">
            <div class="capacity-bar">
              <div class="occupied" [style.width.%]="getOccupiedPercentage(status)"></div>
              <div class="cleaning" [style.width.%]="getCleaningPercentage(status)"></div>
              <div class="maintenance" [style.width.%]="getMaintenancePercentage(status)"></div>
            </div>
            <div class="capacity-legend">
              <span class="legend-item occupied">Occupied</span>
              <span class="legend-item cleaning">Cleaning</span>
              <span class="legend-item maintenance">Maint.</span>
              <span class="legend-item available">Available</span>
            </div>
          </div>

          <div class="metrics-grid">
            <div class="metric">
              <div class="metric-value avail">{{ status.available }}</div>
              <div class="metric-label">Available</div>
            </div>
            <div class="metric">
              <div class="metric-value">{{ status.occupied }}</div>
              <div class="metric-label">Occupied</div>
            </div>
            <div class="metric">
              <div class="metric-value warn">{{ status.cleaning }}</div>
              <div class="metric-label">Cleaning</div>
            </div>
            <div class="metric">
              <div class="metric-value danger">{{ status.maintenance }}</div>
              <div class="metric-label">Maint.</div>
            </div>
          </div>

          <div class="prediction">
            <div class="pred-row">
              <div>
                <div class="prediction-label">Tomorrow's Forecast</div>
                <div class="prediction-value">{{ status.predicted_occupancy_tomorrow }}%</div>
              </div>
              <div class="trend-indicator" [class.rising]="status.predicted_occupancy_tomorrow > getOccupiedPercentage(status)">
                <span class="trend-arrow">{{ status.predicted_occupancy_tomorrow > getOccupiedPercentage(status) ? '&uarr;' : '&darr;' }}</span>
                <span>{{ getTrendDelta(status) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bed Inventory for Selected Department -->
      <div class="bed-inventory-section" *ngIf="selectedDepartment && bedInventory.length > 0">
        <div class="inventory-header">
          <h3>{{ selectedDepartment }} - Bed Inventory</h3>
          <div class="inventory-controls">
            <label>
              Room Type:
              <select [(ngModel)]="roomTypeFilter" (ngModelChange)="onRoomTypeFilterChange()">
                <option value="">All Rooms</option>
                <option *ngFor="let rt of availableRoomTypes" [value]="rt">{{ rt }}</option>
              </select>
            </label>
            <div class="inventory-count">
              {{ filteredBedInventory.length }} of {{ bedInventory.length }} beds
            </div>
          </div>
          <button (click)="selectDepartment(selectedDepartment)" class="btn-close">&times;</button>
        </div>
        <div class="inventory-grid">
          <div *ngFor="let bed of filteredBedInventory" class="bed-item" [class]="bed.status">
            <div class="bed-id">{{ bed.id }}</div>
            <div class="bed-type">{{ bed.type }}</div>
            <div class="bed-room">Room {{ bed.room }}</div>
            <div class="bed-status">{{ bed.status }}</div>
          </div>
        </div>
      </div>

      <!-- Recent Admissions -->
      <div class="recent-section" *ngIf="recentAdmissions.length > 0">
        <h3>Recent Admissions (Live)</h3>
        <div class="recent-table">
          <div class="recent-row header">
            <span>Patient</span>
            <span>Bed</span>
            <span>Department</span>
            <span>LOS</span>
            <span>Status</span>
          </div>
          <div *ngFor="let adm of recentAdmissions" class="recent-row">
            <span class="patient-name">{{ adm.patient.first_name }} {{ adm.patient.last_name }}</span>
            <span class="bed-id">{{ adm.allocated_bed.bed_id }}</span>
            <span>{{ adm.allocated_bed.department }}</span>
            <span>{{ adm.predicted_los }}d</span>
            <span class="status-badge confirmed">{{ adm.status }}</span>
          </div>
        </div>
      </div>

      <!-- Patient-Bed Allocations from CSV -->
      <div class="allocations-section" *ngIf="bedAllocations.length > 0">
        <div class="allocations-header" (click)="toggleAllocations()">
          <h3>Patient-Bed Allocations</h3>
          <span class="allocations-meta">
            {{ allocationsTotal }} patients on {{ allocationsDate }}
            <span class="toggle-icon">{{ showAllocations ? '&#9650;' : '&#9660;' }}</span>
          </span>
        </div>
        <div class="allocations-table" *ngIf="showAllocations">
          <div class="alloc-row header">
            <span>Patient ID</span>
            <span>Patient Name</span>
            <span>Age</span>
            <span>Gender</span>
            <span>Department</span>
            <span>Bed ID</span>
            <span>Bed Type</span>
            <span>Room</span>
            <span>Severity</span>
            <span>LOS</span>
            <span>Payer</span>
            <span>Status</span>
          </div>
          <div *ngFor="let alloc of bedAllocations" class="alloc-row">
            <span class="alloc-pid">{{ alloc.patient_id }}</span>
            <span class="alloc-name">{{ alloc.patient_name }}</span>
            <span>{{ alloc.age }}</span>
            <span>{{ alloc.gender }}</span>
            <span>{{ alloc.department }}</span>
            <span class="alloc-bed">{{ alloc.bed_id }}</span>
            <span class="alloc-btype">{{ alloc.bed_type }}</span>
            <span>{{ alloc.room_number }}</span>
            <span class="alloc-sev" [class]="alloc.severity?.toLowerCase()">{{ alloc.severity }}</span>
            <span>{{ alloc.length_of_stay_days }}d</span>
            <span>{{ alloc.payer_channel }}</span>
            <span class="alloc-status" [class]="alloc.status?.toLowerCase().replace(' ', '-')">{{ alloc.status }}</span>
          </div>
        </div>
      </div>

      <div class="loading" *ngIf="loading">Loading bed status...</div>
      <div class="error" *ngIf="error">{{ error }}</div>
    </div>
  `,
  styles: [`
    .monitor-container { padding: 2rem; max-width: 1400px; margin: 0 auto; }
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }
    h1 { margin: 0; color: var(--blue-dk); font-size: 2rem; }
    .auto-refresh-badge {
      padding: 0.375rem 0.75rem; background: var(--surface); border-radius: 6px;
      font-size: 0.75rem; color: var(--text-secondary); font-weight: 600;
    }
    .controls {
      display: flex; gap: 1rem; align-items: flex-end; margin-bottom: 1.5rem;
      padding: 1rem 1.25rem; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .controls label { display: flex; flex-direction: column; gap: 0.5rem; font-weight: 600; font-size: 0.875rem; }
    .controls select { padding: 0.625rem; border: 1px solid var(--border); border-radius: 6px; min-width: 200px; }
    .btn-refresh {
      margin-left: auto; padding: 0.625rem 1.25rem; background: var(--blue); color: white;
      border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 0.875rem;
    }
    .btn-refresh:hover:not(:disabled) { background: var(--blue-dk); }
    .btn-refresh:disabled { opacity: 0.6; cursor: not-allowed; }

    .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .kpi-card {
      background: white; padding: 1.25rem; border-radius: 8px; text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-top: 3px solid var(--blue);
    }
    .kpi-card.kpi-warning { border-top-color: #e74c3c; }
    .kpi-value { font-size: 2rem; font-weight: 700; color: var(--blue-dk); }
    .kpi-card.kpi-warning .kpi-value { color: #e74c3c; }
    .kpi-label { margin-top: 0.25rem; font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; }

    .ml-metadata { margin-bottom: 1.5rem; }
    .metadata-card {
      background: linear-gradient(135deg, var(--blue-dk), var(--blue)); color: white;
      padding: 1.25rem 1.5rem; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .metadata-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; }
    .meta-item { text-align: center; }
    .meta-label { font-size: 0.625rem; opacity: 0.8; text-transform: uppercase; margin-bottom: 0.25rem; letter-spacing: 0.03em; }
    .meta-value { font-size: 0.9375rem; font-weight: 700; }

    .beds-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
    .bed-status-card {
      background: white; border-radius: 8px; padding: 1.5rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: transform 0.2s;
      cursor: pointer;
    }
    .bed-status-card:hover { transform: translateY(-3px); box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
    .bed-status-card.card-critical { border: 2px solid #e74c3c; }
    .bed-status-card.card-selected { border: 3px solid var(--blue); background: var(--blue-lt, #e3f2fd); }
    .card-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid var(--border);
    }
    .card-header h3 { margin: 0; color: var(--blue-dk); font-size: 1.125rem; }
    .risk-badge {
      padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.6875rem; font-weight: 700; text-transform: uppercase;
    }
    .risk-badge.low { background: var(--green-lt); color: var(--green-dk); }
    .risk-badge.medium { background: var(--yellow-lt); color: var(--yellow-dk); }
    .risk-badge.high { background: #ffe5e5; color: #e74c3c; }

    .occupancy-display { display: flex; justify-content: center; margin-bottom: 1rem; }
    .occ-circle {
      width: 80px; height: 80px; border-radius: 50%; display: flex; flex-direction: column;
      align-items: center; justify-content: center; border: 4px solid var(--blue);
    }
    .occ-circle.occ-high { border-color: #e74c3c; }
    .occ-circle.occ-medium { border-color: #f39c12; }
    .occ-circle.occ-low { border-color: var(--green); }
    .occ-pct { font-size: 1.25rem; font-weight: 700; color: var(--blue-dk); line-height: 1; }
    .occ-circle.occ-high .occ-pct { color: #e74c3c; }
    .occ-circle.occ-medium .occ-pct { color: #f39c12; }
    .occ-circle.occ-low .occ-pct { color: var(--green-dk); }
    .occ-sub { font-size: 0.5625rem; color: var(--text-secondary); text-transform: uppercase; }

    .capacity-summary { margin-bottom: 1rem; }
    .capacity-bar {
      height: 24px; border-radius: 4px; overflow: hidden; display: flex;
      background: var(--bg-gray); margin-bottom: 0.5rem;
    }
    .capacity-bar > div { transition: width 0.3s ease; }
    .capacity-bar .occupied { background: var(--blue); }
    .capacity-bar .cleaning { background: var(--yellow); }
    .capacity-bar .maintenance { background: var(--red); }
    .capacity-legend { display: flex; gap: 0.75rem; font-size: 0.6875rem; flex-wrap: wrap; }
    .legend-item { display: flex; align-items: center; gap: 0.25rem; }
    .legend-item::before { content: ''; width: 10px; height: 10px; border-radius: 2px; }
    .legend-item.occupied::before { background: var(--blue); }
    .legend-item.cleaning::before { background: var(--yellow); }
    .legend-item.maintenance::before { background: var(--red); }
    .legend-item.available::before { background: var(--green); }

    .metrics-grid {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem;
      margin-bottom: 1rem; padding: 0.75rem 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border);
    }
    .metric { text-align: center; }
    .metric-value { font-size: 1.5rem; font-weight: 700; color: var(--blue-dk); }
    .metric-value.avail { color: var(--green-dk); }
    .metric-value.warn { color: #f39c12; }
    .metric-value.danger { color: #e74c3c; }
    .metric-label { font-size: 0.625rem; color: var(--text-secondary); margin-top: 0.125rem; text-transform: uppercase; }

    .prediction {
      background: var(--surface); padding: 0.75rem 1rem; border-radius: 6px;
    }
    .pred-row { display: flex; justify-content: space-between; align-items: center; }
    .prediction-label { font-size: 0.625rem; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 0.125rem; }
    .prediction-value { font-size: 1.5rem; font-weight: 700; color: var(--blue-dk); }
    .trend-indicator {
      display: flex; flex-direction: column; align-items: center; gap: 0.125rem;
      font-size: 0.75rem; font-weight: 600; color: var(--green-dk);
    }
    .trend-indicator.rising { color: #e74c3c; }
    .trend-arrow { font-size: 1.25rem; }

    .recent-section { margin-top: 0.5rem; }
    .recent-section h3 { color: var(--blue-dk); margin-bottom: 1rem; font-size: 1.125rem; }
    .recent-table {
      background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden;
    }
    .recent-row {
      display: grid; grid-template-columns: 1.5fr 1fr 1.5fr 0.5fr 0.75fr;
      padding: 0.75rem 1.25rem; font-size: 0.8125rem; border-bottom: 1px solid var(--border);
      align-items: center;
    }
    .recent-row.header {
      background: var(--surface); font-weight: 700; font-size: 0.6875rem;
      text-transform: uppercase; color: var(--text-secondary);
    }
    .recent-row:last-child { border-bottom: none; }
    .patient-name { font-weight: 600; }
    .bed-id { font-weight: 600; color: var(--blue); }
    .status-badge {
      display: inline-block; padding: 0.125rem 0.5rem; border-radius: 12px;
      font-size: 0.6875rem; font-weight: 700; text-transform: uppercase;
    }
    .status-badge.confirmed { background: var(--green-lt); color: var(--green-dk); }

    .loading, .error { text-align: center; padding: 3rem; color: var(--text-secondary); }
    .error { color: var(--red); }

    .allocations-section { margin-top: 1.5rem; }
    .allocations-header {
      display: flex; justify-content: space-between; align-items: center;
      cursor: pointer; padding: 0.75rem 1.25rem; background: white;
      border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 0.75rem;
    }
    .allocations-header h3 { margin: 0; color: var(--blue-dk); font-size: 1.125rem; }
    .allocations-meta { font-size: 0.8125rem; color: var(--text-secondary); font-weight: 600; display: flex; align-items: center; gap: 0.5rem; }
    .toggle-icon { font-size: 0.625rem; }
    .allocations-table {
      background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden;
      overflow-x: auto;
    }
    .alloc-row {
      display: grid; grid-template-columns: 1.2fr 1.5fr 0.4fr 0.6fr 1fr 0.8fr 0.7fr 0.5fr 0.6fr 0.4fr 0.8fr 0.7fr;
      padding: 0.625rem 1rem; font-size: 0.75rem; border-bottom: 1px solid var(--border); align-items: center;
      min-width: 900px;
    }
    .alloc-row.header {
      background: var(--surface); font-weight: 700; font-size: 0.625rem;
      text-transform: uppercase; color: var(--text-secondary);
    }
    .alloc-row:last-child { border-bottom: none; }
    .alloc-pid { font-weight: 600; color: var(--text-secondary); font-size: 0.6875rem; }
    .alloc-name { font-weight: 600; }
    .alloc-bed { font-weight: 700; color: var(--blue); }
    .alloc-btype { font-size: 0.6875rem; color: var(--text-secondary); text-transform: capitalize; }
    .alloc-sev {
      display: inline-block; padding: 0.125rem 0.5rem; border-radius: 10px;
      font-size: 0.5625rem; font-weight: 700; text-transform: uppercase; text-align: center;
    }
    .alloc-sev.critical { background: #ffe5e5; color: #e74c3c; }
    .alloc-sev.high { background: #fff3e0; color: #f39c12; }
    .alloc-sev.medium { background: #e3f2fd; color: var(--blue); }
    .alloc-sev.low { background: var(--green-lt); color: var(--green-dk); }
    .alloc-status {
      display: inline-block; padding: 0.125rem 0.5rem; border-radius: 10px;
      font-size: 0.5625rem; font-weight: 700; text-transform: uppercase; text-align: center;
    }
    .alloc-status.admitted { background: var(--blue-lt, #e3f2fd); color: var(--blue-dk); }
    .alloc-status.discharged { background: var(--green-lt); color: var(--green-dk); }
    .alloc-status.in-observation { background: #fff3e0; color: #f39c12; }

    .bed-inventory-section { margin-bottom: 2rem; }
    .inventory-header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 0.75rem 1.25rem; background: white; border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08); margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem;
    }
    .inventory-header h3 { margin: 0; color: var(--blue-dk); font-size: 1.125rem; }
    .inventory-controls { display: flex; align-items: center; gap: 1rem; }
    .inventory-controls label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.75rem; font-weight: 600; color: var(--text-secondary); }
    .inventory-controls select { padding: 0.375rem 0.625rem; border: 1px solid var(--border); border-radius: 6px; font-size: 0.8125rem; min-width: 160px; }
    .inventory-count { font-size: 0.75rem; color: var(--text-secondary); font-weight: 600; }
    .btn-close {
      background: none; border: none; font-size: 1.5rem; color: var(--text-secondary);
      cursor: pointer; padding: 0; line-height: 1; width: 32px; height: 32px;
    }
    .btn-close:hover { color: var(--red); }
    .inventory-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 0.75rem;
    }
    .bed-item {
      background: white; border-radius: 6px; padding: 0.75rem;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08); text-align: center;
      border: 2px solid transparent; transition: all 0.2s;
    }
    .bed-item.available { border-color: var(--green); }
    .bed-item.occupied { border-color: var(--blue); }
    .bed-id { font-weight: 700; font-size: 0.875rem; color: var(--blue-dk); margin-bottom: 0.25rem; }
    .bed-type { font-size: 0.6875rem; color: var(--text-secondary); text-transform: capitalize; margin-bottom: 0.125rem; }
    .bed-room { font-size: 0.625rem; color: var(--text-secondary); margin-bottom: 0.25rem; }
    .bed-status {
      display: inline-block; padding: 0.125rem 0.5rem; border-radius: 10px;
      font-size: 0.5625rem; font-weight: 700; text-transform: uppercase;
    }
    .bed-item.available .bed-status { background: var(--green-lt); color: var(--green-dk); }
    .bed-item.occupied .bed-status { background: var(--blue-lt, #e3f2fd); color: var(--blue-dk); }
  `]
})
export class BedAllocationMonitorComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private refreshTimer: any;

  bedStatuses: BedStatus[] = [];
  summary: BedStatusSummary | null = null;
  departments: string[] = [];
  departmentFilter = '';
  modelMetadata: ModelMetadata | null = null;
  recentAdmissions: AdmissionResponse[] = [];
  bedAllocations: any[] = [];
  allocationsTotal = 0;
  allocationsDate = '';
  showAllocations = false;
  bedInventory: any[] = [];
  selectedDepartment: string | null = null;
  roomTypeFilter = '';
  loading = true;
  error: string | null = null;

  ngOnInit() {
    this.loadDepartments();
    this.loadModelMetadata();
    this.loadBedStatus();
    this.loadRecentAdmissions();
    this.loadBedAllocations();
    this.refreshTimer = setInterval(() => {
      this.loadBedStatus();
      this.loadRecentAdmissions();
      this.loadBedAllocations();
    }, 30000);
  }

  ngOnDestroy() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
  }

  loadDepartments() {
    this.api.getDepartments().subscribe({
      next: (depts) => { this.departments = depts; this.cdr.markForCheck(); },
      error: () => {}
    });
  }

  loadModelMetadata() {
    this.api.getModelMetadata().subscribe({
      next: (metadata) => { this.modelMetadata = metadata; this.cdr.markForCheck(); },
      error: () => {}
    });
  }

  loadBedStatus() {
    this.loading = true;
    this.error = null;
    this.cdr.markForCheck();
    this.api.getBedStatus(this.departmentFilter || undefined).subscribe({
      next: (res) => {
        this.bedStatuses = res.departments;
        if (res.summary) this.summary = res.summary;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = 'Failed to load bed status. Ensure backend is running.';
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
    this.loadBedAllocations();
  }

  loadRecentAdmissions() {
    this.api.getRecentAdmissions(5).subscribe({
      next: (res) => { this.recentAdmissions = res.admissions; this.cdr.markForCheck(); },
      error: () => {}
    });
  }

  loadBedAllocations() {
    this.api.getBedAllocations(this.departmentFilter || undefined, undefined, 50).subscribe({
      next: (res) => {
        this.bedAllocations = res.allocations;
        this.allocationsTotal = res.total;
        this.allocationsDate = res.date;
        this.cdr.markForCheck();
      },
      error: () => {}
    });
  }

  toggleAllocations() {
    this.showAllocations = !this.showAllocations;
    this.cdr.markForCheck();
  }

  selectDepartment(dept: string) {
    if (this.selectedDepartment === dept) {
      this.selectedDepartment = null;
      this.bedInventory = [];
    } else {
      this.selectedDepartment = dept;
      this.loadBedInventory(dept);
    }
    this.cdr.markForCheck();
  }

  loadBedInventory(department: string) {
    this.api.getBedInventory(department).subscribe({
      next: (res) => {
        this.bedInventory = res.beds;
        this.roomTypeFilter = '';
        this.cdr.markForCheck();
      },
      error: () => {}
    });
  }

  get availableRoomTypes(): string[] {
    return [...new Set(this.bedInventory.map(b => b.type))].sort();
  }

  get filteredBedInventory(): any[] {
    if (!this.roomTypeFilter) return this.bedInventory;
    return this.bedInventory.filter(b => b.type === this.roomTypeFilter);
  }

  onRoomTypeFilterChange() {
    this.cdr.markForCheck();
  }

  getOccupiedPercentage(status: BedStatus): number {
    if (!status.total_beds) return 0;
    return Math.round((status.occupied / status.total_beds) * 100);
  }

  getCleaningPercentage(status: BedStatus): number {
    if (!status.total_beds) return 0;
    return Math.round((status.cleaning / status.total_beds) * 100);
  }

  getMaintenancePercentage(status: BedStatus): number {
    if (!status.total_beds) return 0;
    return Math.round((status.maintenance / status.total_beds) * 100);
  }

  getOccupancyClass(status: BedStatus): string {
    const pct = this.getOccupiedPercentage(status);
    if (pct >= 90) return 'occ-high';
    if (pct >= 75) return 'occ-medium';
    return 'occ-low';
  }

  getTrendDelta(status: BedStatus): string {
    const current = this.getOccupiedPercentage(status);
    const delta = status.predicted_occupancy_tomorrow - current;
    const sign = delta >= 0 ? '+' : '';
    return sign + delta.toFixed(0) + '%';
  }

  formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  }
}
