import { Component, OnInit, OnDestroy, inject, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { OccupancyAlert, AlertRule } from '../../models/registration.models';

@Component({
  selector: 'app-occupancy-alerts',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="alerts-container">
      <div class="page-header">
        <h1>Occupancy Alerts & Capacity Monitoring</h1>
        <span class="auto-refresh-badge">Auto-refresh: 60s</span>
      </div>

      <div class="controls">
        <label>
          Severity:
          <select [(ngModel)]="severityFilter" (change)="loadAlerts()">
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>
        <button class="refresh-btn" (click)="loadAlerts()" [disabled]="loading">
          {{ loading ? 'Refreshing...' : 'Refresh Now' }}
        </button>
      </div>

      <!-- Summary Cards -->
      <div class="summary-grid" *ngIf="!loading">
        <div class="summary-card critical">
          <div class="count">{{ getAlertCount('critical') }}</div>
          <div class="label">Critical</div>
        </div>
        <div class="summary-card high">
          <div class="count">{{ getAlertCount('high') }}</div>
          <div class="label">High</div>
        </div>
        <div class="summary-card medium">
          <div class="count">{{ getAlertCount('medium') }}</div>
          <div class="label">Medium</div>
        </div>
        <div class="summary-card total">
          <div class="count">{{ allAlerts.length }}</div>
          <div class="label">Total Active</div>
        </div>
      </div>

      <!-- Threshold Config Display -->
      <div class="thresholds-bar" *ngIf="thresholds">
        <span class="threshold-item" *ngFor="let t of thresholdEntries">
          <span class="th-dot" [class]="t[0]"></span>
          {{ t[0] }}: {{ t[1] * 100 }}%
        </span>
      </div>

      <!-- Alert List -->
      <div class="alerts-list" *ngIf="!loading && filteredAlerts.length > 0">
        <div *ngFor="let alert of filteredAlerts; let i = index"
             class="alert-item"
             [class]="'severity-' + alert.severity"
             [class.acknowledged]="acknowledgedSet.has(i)">
          <div class="alert-icon">{{ getAlertIcon(alert.severity) }}</div>
          <div class="alert-content">
            <div class="alert-message">{{ alert.message }}</div>
            <div class="alert-meta">
              <span class="department-badge">{{ alert.department }}</span>
              <span *ngIf="alert.available_beds != null" class="beds-badge">
                {{ alert.available_beds }} beds avail.
              </span>
              <span *ngIf="alert.current_rate" class="rate-badge">
                {{ (alert.current_rate * 100).toFixed(1) }}% occ.
              </span>
              <span class="timestamp">{{ alert.timestamp | date:'shortTime' }}</span>
            </div>
            <!-- Occupancy bar -->
            <div class="alert-bar" *ngIf="alert.current_rate">
              <div class="alert-bar-fill"
                   [style.width.%]="alert.current_rate * 100"
                   [class.bar-critical]="alert.severity === 'critical'"
                   [class.bar-high]="alert.severity === 'high'"
                   [class.bar-medium]="alert.severity === 'medium'">
              </div>
            </div>
          </div>
          <div class="alert-actions">
            <button class="action-btn" (click)="acknowledge(i)" *ngIf="!acknowledgedSet.has(i)">Acknowledge</button>
            <span class="ack-label" *ngIf="acknowledgedSet.has(i)">Acknowledged</span>
          </div>
        </div>
      </div>

      <div class="no-alerts" *ngIf="!loading && filteredAlerts.length === 0 && !error">
        All departments within normal parameters. No active alerts.
      </div>

      <!-- Alert Rules Reference -->
      <div class="rules-section" *ngIf="alertRules.length > 0">
        <h3>Active Alert Rules</h3>
        <div class="rules-grid">
          <div *ngFor="let rule of alertRules" class="rule-card" [class]="'rule-' + rule.severity">
            <div class="rule-label">{{ rule.label }}</div>
            <div class="rule-detail">{{ rule.description }}</div>
            <div class="rule-threshold">Threshold: {{ rule.threshold * 100 }}%</div>
          </div>
        </div>
      </div>

      <div class="loading" *ngIf="loading">Loading alerts...</div>
      <div class="error" *ngIf="error">{{ error }}</div>
    </div>
  `,
  styles: [`
    .alerts-container { padding: 2rem; max-width: 1200px; margin: 0 auto; }
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
    .controls select { padding: 0.625rem; border: 1px solid var(--border); border-radius: 6px; min-width: 160px; }
    .refresh-btn {
      margin-left: auto; padding: 0.625rem 1.25rem; background: var(--blue); color: white;
      border: none; border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 0.875rem;
    }
    .refresh-btn:hover:not(:disabled) { background: var(--blue-dk); }
    .refresh-btn:disabled { opacity: 0.6; cursor: not-allowed; }
    .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .summary-card { padding: 1.25rem; border-radius: 8px; text-align: center; color: white; }
    .summary-card.critical { background: linear-gradient(135deg, #e74c3c, #c0392b); }
    .summary-card.high { background: linear-gradient(135deg, #f39c12, #e67e22); }
    .summary-card.medium { background: linear-gradient(135deg, #3498db, #2980b9); }
    .summary-card.total { background: linear-gradient(135deg, var(--blue-dk), var(--blue)); }
    .summary-card .count { font-size: 2.5rem; font-weight: 700; }
    .summary-card .label { font-size: 0.8125rem; opacity: 0.9; }
    .thresholds-bar {
      display: flex; gap: 1.5rem; padding: 0.75rem 1.25rem; margin-bottom: 1.5rem;
      background: white; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
      font-size: 0.8125rem; font-weight: 600;
    }
    .th-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 0.375rem; }
    .th-dot.critical { background: #e74c3c; }
    .th-dot.high { background: #f39c12; }
    .th-dot.moderate { background: #3498db; }
    .th-dot.normal { background: #27ae60; }
    .alerts-list { display: flex; flex-direction: column; gap: 0.75rem; margin-bottom: 2rem; }
    .alert-item {
      display: flex; align-items: flex-start; gap: 1rem; padding: 1.25rem;
      background: white; border-radius: 8px; border-left: 4px solid; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      transition: opacity 0.3s;
    }
    .alert-item.acknowledged { opacity: 0.5; }
    .alert-item.severity-critical { border-left-color: #e74c3c; }
    .alert-item.severity-high { border-left-color: #f39c12; }
    .alert-item.severity-medium { border-left-color: #3498db; }
    .alert-item.severity-low { border-left-color: #27ae60; }
    .alert-icon { font-size: 1.5rem; margin-top: 0.125rem; }
    .alert-content { flex: 1; }
    .alert-message { font-weight: 600; margin-bottom: 0.5rem; font-size: 0.9375rem; }
    .alert-meta {
      display: flex; flex-wrap: wrap; gap: 0.5rem; font-size: 0.75rem; color: var(--text-secondary); margin-bottom: 0.5rem;
    }
    .department-badge { padding: 0.125rem 0.5rem; background: var(--surface); border-radius: 4px; font-weight: 600; }
    .beds-badge { padding: 0.125rem 0.5rem; border-radius: 4px; font-weight: 600; background: #e8f5e9; color: #2e7d32; }
    .rate-badge { padding: 0.125rem 0.5rem; border-radius: 4px; font-weight: 600; background: #fff3e0; color: #e65100; }
    .alert-bar { position: relative; height: 6px; background: #eee; border-radius: 3px; overflow: hidden; margin-top: 0.25rem; }
    .alert-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
    .bar-critical { background: #e74c3c; }
    .bar-high { background: #f39c12; }
    .bar-medium { background: #3498db; }
    .action-btn {
      padding: 0.375rem 0.75rem; border: 1px solid var(--border); border-radius: 6px;
      background: white; font-size: 0.75rem; cursor: pointer; font-weight: 600; white-space: nowrap;
    }
    .action-btn:hover { background: var(--surface); }
    .ack-label { font-size: 0.75rem; color: var(--green-dk); font-weight: 600; }
    .no-alerts {
      text-align: center; padding: 3rem; background: white; border-radius: 8px;
      color: var(--green-dk); font-weight: 600; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .rules-section { margin-top: 2rem; }
    .rules-section h3 { color: var(--blue-dk); margin-bottom: 1rem; font-size: 1.125rem; }
    .rules-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }
    .rule-card {
      background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid var(--border);
      box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .rule-card.rule-critical { border-left-color: #e74c3c; }
    .rule-card.rule-high { border-left-color: #f39c12; }
    .rule-card.rule-medium { border-left-color: #3498db; }
    .rule-label { font-weight: 700; font-size: 0.875rem; margin-bottom: 0.25rem; }
    .rule-detail { font-size: 0.8125rem; color: var(--text-secondary); margin-bottom: 0.25rem; }
    .rule-threshold { font-size: 0.75rem; font-weight: 600; color: var(--blue); }
    .loading, .error { text-align: center; padding: 3rem; color: var(--text-secondary); }
    .error { color: var(--red); }
  `]
})
export class OccupancyAlertsComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private cdr = inject(ChangeDetectorRef);
  private refreshTimer: any;

  allAlerts: OccupancyAlert[] = [];
  alertRules: AlertRule[] = [];
  thresholds: Record<string, number> | null = null;
  severityFilter = '';
  loading = true;
  error: string | null = null;
  acknowledgedSet = new Set<number>();

  get filteredAlerts(): OccupancyAlert[] {
    if (!this.severityFilter) return this.allAlerts;
    return this.allAlerts.filter(a => a.severity === this.severityFilter);
  }

  get thresholdEntries(): [string, number][] {
    if (!this.thresholds) return [];
    return Object.entries(this.thresholds) as [string, number][];
  }

  ngOnInit() {
    this.loadAlerts();
    this.loadAlertRules();
    this.refreshTimer = setInterval(() => this.loadAlerts(), 60000);
  }

  ngOnDestroy() {
    if (this.refreshTimer) clearInterval(this.refreshTimer);
  }

  loadAlerts() {
    this.loading = true;
    this.error = null;
    this.cdr.markForCheck();
    this.api.getAlerts(this.severityFilter || undefined).subscribe({
      next: (res: any) => {
        this.allAlerts = res.alerts;
        if (res.thresholds) this.thresholds = res.thresholds;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = 'Failed to load alerts. Ensure backend is running.';
        this.loading = false;
        this.cdr.markForCheck();
      }
    });
  }

  loadAlertRules() {
    this.api.getAlertRules().subscribe({
      next: (res) => { this.alertRules = res.alert_rules; this.cdr.markForCheck(); },
      error: () => {}
    });
  }

  getAlertCount(severity: string): number {
    return this.allAlerts.filter(a => a.severity === severity).length;
  }

  getAlertIcon(severity: string): string {
    switch (severity) {
      case 'critical': return '🚨';
      case 'high': return '⚠️';
      case 'medium': return 'ℹ️';
      default: return '✅';
    }
  }

  acknowledge(index: number) {
    this.acknowledgedSet.add(index);
  }
}
