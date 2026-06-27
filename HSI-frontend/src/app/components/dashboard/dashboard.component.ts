import {
  AfterViewInit, ChangeDetectorRef, Component,
  OnDestroy, OnInit, PLATFORM_ID, inject
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin, interval, of, Subscription } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Chart, registerables } from 'chart.js';
import { ApiService } from '../../services/api.service';
import {
  DashboardMetrics, ForecastResponse, AlertData,
  MAX_FORECAST_DAYS, GenericForecastResponse
} from '../../models/dashboard.models';
import { OccupancyDigChartsComponent } from '../occupancy-dig-charts/occupancy-dig-charts.component';
import { DashboardCopilotComponent } from '../dashboard-copilot/dashboard-copilot.component';
import { BedRequirementsVisualComponent } from '../dashboard-forecast-mini/bed-requirements-visual.component';

Chart.register(...registerables);

// ─── Ward metadata from ml_pipeline.py output ────────────────────
export interface WardStat {
  key:   string;
  name:  string;
  type:  string;
  icon:  string;
  mape:  number;
  r2:    number;
  mae:   number;
  rmse:  number;
  // mock trend data for sparkline (actual values come from ML output)
  trend: number[];
}

// ─── Leaderboard row ──────────────────────────────────────────────
export interface LeaderboardRow {
  model: string;
  mape:  number;
  mae:   number;
  rmse:  number;
  r2:    number;
}

const EMPTY_FORECAST: ForecastResponse = {
  forecast_data: [],
  confidence_interval: { lower: [], upper: [] },
  model_metrics: { mape: 0, rmse: 0, trend: 0, backtest_days: 0, engine: '' },
  forecast_model: { name: '', summary: '', confidence_intervals: '', accuracy_note: '', insights: [] },
};

// Leaderboard from ml_pipeline.py run output (hardcoded from actual results)
const LEADERBOARD_DATA: LeaderboardRow[] = [
  { model: 'Prophet',          mape: 29.173, mae: 4.061, rmse: 4.885, r2: -1.0323 },
  { model: 'ARIMA',            mape: 37.233, mae: 5.035, rmse: 5.554, r2: -1.6267 },
  { model: 'LinearRegression', mape: 50.080, mae: 1.245, rmse: 1.616, r2:  0.5137 },
  { model: 'CatBoost',         mape: 55.121, mae: 1.266, rmse: 1.668, r2:  0.4819 },
  { model: 'LightGBM',         mape: 58.300, mae: 1.313, rmse: 1.795, r2:  0.4000 },
  { model: 'RandomForest',     mape: 59.994, mae: 1.289, rmse: 1.698, r2:  0.4626 },
  { model: 'XGBoost',          mape: 60.447, mae: 1.306, rmse: 1.775, r2:  0.4128 },
  { model: 'ExtraTrees',       mape: 63.550, mae: 1.326, rmse: 1.704, r2:  0.4593 },
];

// Note: These metrics are from training on the original dataset. 
// Rerun ml_pipeline.py with hospital_enhanced_full_dataset.csv to get updated metrics.

// Ward stats from ml_pipeline.py ward-level results
const WARD_DATA: WardStat[] = [
  {
    key: 'icu', name: 'ICU', type: 'Intensive Care Unit', icon: '🚑',
    mape: 97.15, r2: -1.2222, mae: 3.8, rmse: 5.1,
    trend: [18,20,22,19,25,23,28,30,26,24,27,29,32,31,28,25,30,33,35,32,29,31,34,36,33,30,28,32,35,37]
  },
  {
    key: 'general', name: 'General Ward', type: 'General Admission', icon: '🛏',
    mape: 27.23, r2: 0.0607, mae: 4.2, rmse: 5.8,
    trend: [40,42,45,44,47,50,48,46,49,52,55,53,50,48,51,54,57,55,52,50,53,56,59,57,54,52,55,58,60,58]
  },
  {
    key: 'cardiology', name: 'Cardiology', type: 'Cardiovascular Care', icon: '❤️',
    mape: 45.8, r2: 0.2, mae: 2.8, rmse: 3.5,
    trend: [22,24,26,25,27,28,26,25,27,29,31,30,28,27,29,31,33,32,30,29,31,33,35,34,32,31,33,35,37,36]
  },
  {
    key: 'emergency', name: 'Emergency', type: 'Emergency Department', icon: '🆘',
    mape: 41.01, r2: -3.2297, mae: 3.1, rmse: 4.3,
    trend: [10,12,11,13,14,13,15,14,13,14,15,16,15,14,15,16,18,17,16,15,16,18,19,18,17,16,17,19,20,19]
  },
  {
    key: 'neurology', name: 'Neurology', type: 'Neurological Care', icon: '🧠',
    mape: 52.3, r2: 0.15, mae: 2.5, rmse: 3.2,
    trend: [19,21,20,22,23,22,24,23,22,23,24,25,24,23,24,25,27,26,25,24,25,27,28,27,26,25,26,28,29,28]
  },
  {
    key: 'oncology', name: 'Oncology', type: 'Cancer Care', icon: '🎗️',
    mape: 48.5, r2: 0.18, mae: 2.6, rmse: 3.3,
    trend: [17,19,18,20,21,20,22,21,20,21,22,23,22,21,22,23,25,24,23,22,23,25,26,25,24,23,24,26,27,26]
  },
  {
    key: 'orthopedics', name: 'Orthopedics', type: 'Orthopedic Surgery', icon: '🦴',
    mape: 38.7, r2: 0.25, mae: 2.4, rmse: 3.0,
    trend: [24,26,25,27,28,27,29,28,27,28,29,30,29,28,29,30,32,31,30,29,30,32,33,32,31,30,31,33,34,33]
  },
];

// Model color map for leaderboard dots
const MODEL_COLORS: Record<string, string> = {
  Prophet:          '#007DB0',
  ARIMA:            '#0099D6',
  LinearRegression: '#005A80',
  CatBoost:         '#FF0000',
  LightGBM:         '#6C6E71',
  RandomForest:     '#00B4D8',
  XGBoost:          '#48CAE4',
  ExtraTrees:       '#90E0EF',
};

@Component({
  selector:    'app-dashboard',
  standalone:  true,
  imports:     [CommonModule, FormsModule, OccupancyDigChartsComponent, DashboardCopilotComponent, BedRequirementsVisualComponent],
  templateUrl: './dashboard.component.html',
  styleUrls:   ['./dashboard.component.scss'],
})
export class DashboardComponent implements OnInit, AfterViewInit, OnDestroy {
  private readonly platformId = inject(PLATFORM_ID);
  private readonly cdr        = inject(ChangeDetectorRef);

  constructor(private apiService: ApiService) {}

  // ── State ────────────────────────────────────────────────────
  dashboardMetrics: DashboardMetrics | null = null;
  lastUpdated   = new Date();
  loading       = true;
  error: string | null = null;
  forecastDays  = MAX_FORECAST_DAYS;
  selectedModel: string | null = 'prophet';
  selectedAsOfDate: string | null = null;

  forecastData: ForecastResponse = EMPTY_FORECAST;
  staffingForecastData: GenericForecastResponse = {
    forecast_data: [], confidence_interval: { lower: [], upper: [] },
    model_metrics: { mape: 0, rmse: 0, trend: 0, backtest_days: 0, engine: '' },
    forecast_model: { name: '', summary: '', confidence_intervals: '', accuracy_note: '', insights: [] },
  };
  alerts: AlertData[] = [];

  // ── Data from ml_pipeline ─────────────────────────────────────
  readonly wardStats:   WardStat[]       = WARD_DATA;
  readonly leaderboard: LeaderboardRow[] = LEADERBOARD_DATA;

  private sparkCharts: Chart[] = [];
  private refreshSub: Subscription | null = null;
  private sparksBuilt = false;

  // ── Lifecycle ─────────────────────────────────────────────────
  ngOnInit(): void {
    this.loadDashboardData();
    this.refreshSub = interval(45_000).subscribe(() => this.refreshMetrics());
  }

  ngAfterViewInit(): void {
    // Sparklines are built once data arrives; see clearLoadingDeferred
  }

  ngOnDestroy(): void {
    this.refreshSub?.unsubscribe();
    this.sparkCharts.forEach(c => { try { c.destroy(); } catch {} });
  }

  // ── Data loading ──────────────────────────────────────────────
  loadDashboardData(): void {
    this.loading = true;
    this.error   = null;
    this.sparksBuilt = false;

    forkJoin({
      metrics: this.apiService.getDashboardMetrics(this.selectedAsOfDate),
      forecast: this.apiService.generateForecast({
        days: this.forecastDays, model_preference: this.selectedModel, as_of_date: this.selectedAsOfDate,
      }).pipe(catchError(() => of(EMPTY_FORECAST))),
      deptForecasts: this.apiService.getDepartmentForecasts(this.forecastDays, this.selectedModel, this.selectedAsOfDate)
        .pipe(catchError(() => of(null as any))),
    }).subscribe({
      next: ({ metrics, forecast, deptForecasts }) => {
        this.selectedAsOfDate = metrics.data_as_of_date ?? this.selectedAsOfDate;
        this.dashboardMetrics = metrics;
        this.alerts           = metrics.alerts;
        this.lastUpdated      = new Date();
        this.forecastData     = forecast;

        // If department forecasts are available, merge latest occupied series into ward sparklines
        if (deptForecasts && Array.isArray(deptForecasts.departments)) {
          for (const d of deptForecasts.departments) {
            const name = (d.department || '').toLowerCase();
            const match = this.wardStats.find(w => name.includes(w.name.toLowerCase()) || w.name.toLowerCase().includes(name));
            if (!match) continue;
            if (Array.isArray(d.points) && d.points.length > 0) {
              // use occupied counts for sparklines
              match.trend = d.points.map((p: any) => p.occupied ?? Math.round((p.rate_pct ?? 0) / 100 * (d.total_beds ?? 1)));
            }
          }
        }

        this.clearLoadingDeferred();
      },
      error: (err) => {
        console.error(err);
        this.error = 'Could not connect to the API. Ensure the backend is running on port 8000.';
        this.clearLoadingDeferred();
      },
    });
  }

  private clearLoadingDeferred(): void {
    queueMicrotask(() => {
      this.loading = false;
      this.cdr.markForCheck();
      if (isPlatformBrowser(this.platformId) && !this.sparksBuilt) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => this.buildSparklines());
        });
      }
    });
  }

  private refreshMetrics(): void {
    this.apiService.getDashboardMetrics(this.selectedAsOfDate).subscribe({
      next: (m) => { this.dashboardMetrics = m; this.alerts = m.alerts; this.lastUpdated = new Date(); this.cdr.markForCheck(); },
    });
  }

  refreshData(): void { this.loadDashboardData(); }

  // ── Sparkline rendering ───────────────────────────────────────
  private buildSparklines(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.sparkCharts.forEach(c => { try { c.destroy(); } catch {} });
    this.sparkCharts = [];

    for (const ward of this.wardStats) {
      const el = document.getElementById(`ward-spark-${ward.key}`) as HTMLCanvasElement | null;
      if (!el) continue;

      const labels = Array.from({ length: ward.trend.length }, (_, i) => `D${i + 1}`);
      const color  = ward.mape > 80 ? '#FF0000' : ward.mape > 30 ? '#e67e22' : '#007DB0';

      const ctx = el.getContext('2d');
      let grad: CanvasGradient | string = color + '22';
      if (ctx) {
        const g = ctx.createLinearGradient(0, 0, 0, 70);
        g.addColorStop(0, color + '55');
        g.addColorStop(1, color + '05');
        grad = g;
      }

      const c = new Chart(el, {
        type: 'line',
        data: {
          labels,
          datasets: [{
            data:            ward.trend,
            borderColor:     color,
            backgroundColor: grad,
            fill:            true,
            tension:         0.4,
            pointRadius:     0,
            borderWidth:     2,
          }],
        },
        options: {
          responsive:          false,
          maintainAspectRatio: false,
          animation:           { duration: 600 },
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: {
            x: { display: false },
            y: { display: false },
          },
        },
      });
      this.sparkCharts.push(c);
    }
    this.sparksBuilt = true;
  }

  // ── Leaderboard helpers ───────────────────────────────────────
  modelColor(model: string): string { return MODEL_COLORS[model] ?? '#6C6E71'; }

  mapeToWidth(mape: number): number {
    // 0% MAPE → 100% bar width, 100% MAPE → 0%
    return Math.max(0, Math.min(100, 100 - mape));
  }

  mapeLabel(mape: number): string {
    if (mape < 20)  return 'Excellent';
    if (mape < 30)  return 'Good';
    if (mape < 50)  return 'Fair';
    if (mape < 70)  return 'Moderate';
    return 'High error';
  }

  // ── Metric helpers ────────────────────────────────────────────
  currentOccupancyPct(): number {
    if (!this.dashboardMetrics) return 0;
    return Math.round(this.dashboardMetrics.current_occupancy_rate * 1000) / 10;
  }

  roundPredictedOccupiedBeds(): number {
    if (!this.dashboardMetrics) return 0;
    return Math.round(this.dashboardMetrics.predicted_occupancy_7_days * this.dashboardMetrics.total_beds);
  }

  hospitalForecastHorizonRatePct(): number | null {
    const rows = this.forecastData?.forecast_data ?? [];
    if (!rows.length) return null;
    return Math.round(rows[rows.length - 1].predicted_occupancy_rate * 1000) / 10;
  }

  hospitalForecastHorizonBeds(): number | null {
    const rows = this.forecastData?.forecast_data ?? [];
    if (!rows.length) return null;
    return rows[rows.length - 1]?.predicted_occupied_beds ?? null;
  }

  forecastEndDate(): string {
    const rows = this.forecastData?.forecast_data ?? [];
    const dateStr = rows.length ? rows[rows.length - 1].date : null;
    const d = dateStr ? new Date(`${dateStr}T00:00:00`) : new Date();
    if (!dateStr) d.setDate(d.getDate() + this.forecastDays);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  getForecastTrend(): number { return this.forecastData.model_metrics?.trend ?? 0; }

  formatPercentage(v: number): string { return `${(v * 100).toFixed(1)}%`; }
  formatNumber(v: number):     string { return v.toLocaleString(); }

  formatDashboardDate(v: string | null | undefined): string {
    if (!v) return 'latest available';
    return new Date(`${v}T00:00:00`).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
  }

  getOccupancyColor(rate: number): string {
    if (rate >= 0.9) return '#FF0000';
    if (rate >= 0.75) return '#e67e22';
    return '#007DB0';
  }

  // ── Ward projection helpers ──────────────────────────────
  wardProjectedDelta(ward: WardStat): number {
    const t = ward.trend ?? [];
    if (t.length < 8) return 0;
    const last = t[t.length - 1];
    const prevSlice = t.slice(Math.max(0, t.length - 8), t.length - 1);
    const prevAvg = prevSlice.reduce((a, b) => a + b, 0) / Math.max(1, prevSlice.length);
    if (prevAvg === 0) return 0;
    const deltaPct = Math.round(((last - prevAvg) / prevAvg) * 100);
    return deltaPct;
  }

  wardProjectedBeds(ward: WardStat): number {
    const t = ward.trend ?? [];
    if (t.length === 0) return 0;
    return Math.round(t[t.length - 1]);
  }

  wardCurrentBeds(ward: WardStat): number {
    const t = ward.trend ?? [];
    if (t.length < 2) return 0;
    return Math.round(t[0]);
  }

  wardTotalBeds(ward: WardStat): number {
    // Approximate total beds based on typical occupancy
    const currentBeds = this.wardCurrentBeds(ward);
    // Assume current is about 80% occupancy for capacity estimate
    return Math.round(currentBeds / 0.8);
  }

  wardsProjectedIncreasing(thresholdPct = 5): WardStat[] {
    return this.wardStats.filter(w => this.wardProjectedDelta(w) >= thresholdPct);
  }

  trackWardByKey(index: number, ward: WardStat): string {
    return ward.key;
  }

  trackWardByName(index: number, ward: WardStat): string {
    return ward.name;
  }

  trackLeaderboardByModel(index: number, row: LeaderboardRow): string {
    return row.model;
  }

  trackAlertByTimestamp(index: number, alert: AlertData): string {
    return alert.timestamp;
  }

  getAlertSeverityColor(sev: string): string {
    switch (sev.toUpperCase()) {
      case 'HIGH':   return '#FF0000';
      case 'MEDIUM': return '#e67e22';
      case 'LOW':    return '#007DB0';
      default:       return '#6C6E71';
    }
  }

  formatAlertType(t: string): string { return t.replace(/_/g, ' '); }
}
