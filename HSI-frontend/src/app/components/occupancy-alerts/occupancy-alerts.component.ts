import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { OccupancyAlert } from '../../models/registration.models';

@Component({
  selector: 'app-occupancy-alerts',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="alerts-container">
      <h1>Occupancy Alerts & Capacity Monitoring</h1>

      <div class="controls">
        <label>
          Filter by Severity:
          <select [(ngModel)]="severityFilter" (change)="loadAlerts()">
            <option [value]="null">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <button (click)="loadAlerts()" class="btn-refresh">🔄 Refresh</button>
      </div>

      <div class="summary" *ngIf="!loading && alerts.length > 0">
        <div class="summary-card critical">
          <div class="count">{{ getCriticalCount() }}</div>
          <div class="label">Critical Alerts</div>
        </div>
        <div class="summary-card high">
          <div class="count">{{ getHighCount() }}</div>
          <div class="label">High Priority</div>
        </div>
        <div class="summary-card medium">
          <div class="count">{{ getMediumCount() }}</div>
          <div class="label">Requires Attention</div>
        </div>
        <div class="summary-card total">
          <div class="count">{{ alerts.length }}</div>
          <div class="label">Total Alerts</div>
        </div>
      </div>

      <div class="alerts-list" *ngIf="!loading && alerts.length > 0">
        <div *ngFor="let alert of alerts" class="alert-card" [class]="alert.severity">
          <div class="alert-icon">
            <span *ngIf="alert.severity === 'critical'">🚨</span>
            <span *ngIf="alert.severity === 'high'">⚠️</span>
            <span *ngIf="alert.severity === 'medium'">⚡</span>
            <span *ngIf="alert.severity === 'low'">ℹ️</span>
          </div>
          <div class="alert-content">
            <div class="alert-header">
              <span class="alert-type">{{ alert.type }}</span>
              <span class="alert-severity">{{ alert.severity }}</span>
            </div>
            <div class="alert-message">{{ alert.message }}</div>
            <div class="alert-meta">
              <span *ngIf="alert.department">🏥 {{ alert.department }}</span>
              <span>🕐 {{ formatTimestamp(alert.timestamp) }}</span>
            </div>
          </div>
          <div class="alert-actions">
            <button class="btn-action">View Details</button>
            <button class="btn-action">Acknowledge</button>
          </div>
        </div>
      </div>

      <div class="no-alerts" *ngIf="!loading && alerts.length === 0">
        ✓ No active alerts - All systems nominal
      </div>

      <div class="loading" *ngIf="loading">Loading alerts...</div>
      <div class="error" *ngIf="error">{{ error }}</div>
    </div>
  `,
  styles: [`
    .alerts-container {
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
      min-width: 150px;
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
    .summary {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .summary-card {
      background: white;
      padding: 1.5rem;
      border-radius: 8px;
      text-align: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      border-left: 4px solid;
    }
    .summary-card.critical { border-color: #e74c3c; }
    .summary-card.high { border-color: #f39c12; }
    .summary-card.medium { border-color: #3498db; }
    .summary-card.total { border-color: var(--blue-dk); }
    .summary-card .count {
      font-size: 2rem;
      font-weight: 700;
      color: var(--blue-dk);
    }
    .summary-card .label {
      margin-top: 0.5rem;
      font-size: 0.875rem;
      color: var(--text-secondary);
    }
    .alerts-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .alert-card {
      background: white;
      border-radius: 8px;
      padding: 1.5rem;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      display: flex;
      gap: 1rem;
      border-left: 4px solid;
    }
    .alert-card.critical { border-color: #e74c3c; }
    .alert-card.high { border-color: #f39c12; }
    .alert-card.medium { border-color: #3498db; }
    .alert-card.low { border-color: #95a5a6; }
    .alert-icon {
      font-size: 2rem;
      display: flex;
      align-items: center;
    }
    .alert-content {
      flex: 1;
    }
    .alert-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 0.5rem;
    }
    .alert-type {
      font-weight: 700;
      color: var(--blue-dk);
    }
    .alert-severity {
      padding: 0.25rem 0.75rem;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .alert-card.critical .alert-severity { background: #ffe5e5; color: #e74c3c; }
    .alert-card.high .alert-severity { background: #fff3e0; color: #f39c12; }
    .alert-card.medium .alert-severity { background: #e3f2fd; color: #3498db; }
    .alert-card.low .alert-severity { background: #f5f5f5; color: #95a5a6; }
    .alert-message {
      font-size: 1rem;
      margin-bottom: 0.5rem;
      color: var(--text);
    }
    .alert-meta {
      display: flex;
      gap: 1rem;
      font-size: 0.875rem;
      color: var(--text-secondary);
    }
    .alert-actions {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .btn-action {
      padding: 0.5rem 1rem;
      background: var(--bg-gray);
      border: 1px solid var(--border);
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.875rem;
      transition: all 0.2s;
    }
    .btn-action:hover {
      background: var(--blue);
      color: white;
      border-color: var(--blue);
    }
    .no-alerts {
      text-align: center;
      padding: 3rem;
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      color: var(--green-dk);
      font-size: 1.25rem;
      font-weight: 600;
    }
    .loading, .error {
      text-align: center;
      padding: 2rem;
      color: var(--text-secondary);
    }
    .error { color: var(--red); }
  `]
})
export class OccupancyAlertsComponent implements OnInit {
  private api = inject(ApiService);

  alerts: OccupancyAlert[] = [];
  severityFilter: string | null = null;
  loading = false;
  error: string | null = null;

  ngOnInit() {
    this.loadAlerts();
    // Auto-refresh every 60 seconds
    setInterval(() => this.loadAlerts(), 60000);
  }

  loadAlerts() {
    this.loading = true;
    this.error = null;
    this.api.getAlerts(this.severityFilter || undefined).subscribe({
      next: (res) => {
        this.alerts = res.alerts;
        this.loading = false;
      },
      error: (err) => {
        this.error = 'Failed to load alerts';
        this.loading = false;
        console.error(err);
      }
    });
  }

  getCriticalCount() {
    return this.alerts.filter(a => a.severity === 'critical').length;
  }

  getHighCount() {
    return this.alerts.filter(a => a.severity === 'high').length;
  }

  getMediumCount() {
    return this.alerts.filter(a => a.severity === 'medium').length;
  }

  formatTimestamp(timestamp: string): string {
    const date = new Date(timestamp);
    return date.toLocaleString();
  }
}
