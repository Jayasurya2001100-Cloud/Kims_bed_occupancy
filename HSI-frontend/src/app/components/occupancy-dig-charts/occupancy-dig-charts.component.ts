import {
  ChangeDetectorRef,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  SimpleChanges,
  ViewChild,
  inject,
  isDevMode,
  PLATFORM_ID,
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Chart, registerables, Chart as ChartType } from 'chart.js';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../services/api.service';
import { ChartPack, DepartmentForecastsPack } from '../../models/chart-pack.models';
import { ForecastResponse, GenericForecastResponse, DEFAULT_FORECAST_DAYS } from '../../models/dashboard.models';

Chart.register(...registerables);

const PAL = {
  primary:   '#007DB0',
  secondary: '#005A80',
  teal:      '#0099D6',
  coral:     '#FF0000',
  slate:     '#6C6E71',
  grid:      'rgba(0,125,176,0.08)',
};

@Component({
  selector: 'app-occupancy-dig-charts',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './occupancy-dig-charts.component.html',
  styleUrl: './occupancy-dig-charts.component.scss',
})
export class OccupancyDigChartsComponent implements OnInit, OnDestroy, OnChanges {
  private readonly platformId = inject(PLATFORM_ID);
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  @Input() forecast: ForecastResponse = {
    forecast_data: [],
    confidence_interval: { lower: [], upper: [] },
    model_metrics: { mape: 0, rmse: 0, trend: 0, backtest_days: 0, engine: '' },
    forecast_model: {
      name: '',
      summary: '',
      confidence_intervals: '',
      accuracy_note: '',
    },
  };
  @Input() forecastDays = DEFAULT_FORECAST_DAYS;
  @Input() selectedModel: string | null = null;
  @Input() asOfDate: string | null = null;

  modelPredictionForecast: ForecastResponse = {
    forecast_data: [],
    confidence_interval: { lower: [], upper: [] },
    model_metrics: { mape: 0, rmse: 0, trend: 0, backtest_days: 0, engine: '' },
    forecast_model: {
      name: '',
      summary: '',
      confidence_intervals: '',
      accuracy_note: '',
    },
  };

  @ViewChild('histCanvas') histCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('sparkCanvas') sparkCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('deptHorizonCanvas') deptHorizonCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('deptForecastCanvas') deptForecastCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('staffingCanvas') staffingCanvas?: ElementRef<HTMLCanvasElement>;

  chartPack: ChartPack | null = null;
  deptForecastPack: DepartmentForecastsPack | null = null;
  staffingForecast: GenericForecastResponse | null = null;
  staffingModelPrediction: GenericForecastResponse | null = null;
  expandingWindowForecast: GenericForecastResponse | null = null;
  deptForecastError: string | null = null;
  /** 'ICU' by default for CI deep-dive */
  deptForecastView: string = 'ICU';
  loadingCharts = false;
  loadError: string | null = null;
  historyWindowDays = 30;
  readonly historyWindowOptions = [30, 60, 90, 180, 365, 730];
  forecastMode: 'sliding' | 'expanding' = 'sliding';

  private charts: ChartType[] = [];
  private chartLayoutAttempts = 0;
  private lastDeptForecastRequestKey = '';

  ngOnChanges(changes: SimpleChanges): void {
    if (!isPlatformBrowser(this.platformId)) return;
    if (changes['forecast'] && this.chartPack) {
      this.scheduleChartBuild();
    }
    if (changes['asOfDate'] && !changes['asOfDate'].firstChange) {
      this.fetchPack();
      return;
    }
    if ((changes['forecastDays'] || changes['selectedModel']) && this.chartPack) {
      this.refetchDeptForecasts();
      this.refetchModelPrediction();
      this.refetchStaffingForecast();
    }
  }

  ngOnDestroy(): void {
    this.destroyCharts();
  }

  onDeptForecastViewChange(ev: Event): void {
    const v = (ev.target as HTMLSelectElement).value;
    this.deptForecastView = v;
    this.scheduleChartBuild();
  }

  deptForecastDepartmentNames(): string[] {
    return (this.deptForecastPack?.departments ?? [])
      .filter((x) => x.points?.length > 0)
      .map((x) => x.department);
  }

  occupancyMapeLabel(): string {
    const rollingMape = (this.modelPredictionForecast as any)?.model_metrics?.rolling_mape as number | undefined;
    if (rollingMape != null && rollingMape > 0) {
      return `Accuracy: ${rollingMape.toFixed(1)}%`;
    }
    const m = this.forecast?.model_metrics?.mape ?? 0;
    const pct = m <= 1 ? m * 100 : m;
    return `Accuracy: ${pct.toFixed(1)}%`;
  }

  staffingMapeLabel(): string {
    const m = this.staffingForecast?.model_metrics?.mape ?? 0;
    const pct = m <= 1 ? m * 100 : m;
    return `Accuracy: ${pct.toFixed(1)}%`;
  }

  selectedDeptForecastMeta(): string {
    if (!this.deptForecastPack || this.deptForecastView === 'all') {
      return '';
    }
    const d = this.deptForecastPack.departments.find(
      (x) => x.department === this.deptForecastView,
    );
    if (!d?.points?.length) return '';
    const last = d.points[d.points.length - 1];
    const mapePct = (d.mape ?? 0) <= 1 ? (d.mape ?? 0) * 100 : (d.mape ?? 0);
    const occPct = ((last.occupied / (d.total_beds || 1)) * 100).toFixed(1);
    return `Accuracy: ${mapePct.toFixed(1)}% · ${occPct}% occupancy (${last.occupied}/${d.total_beds} beds)`;
  }

  hasDepartmentSeries(): boolean {
    return !!this.chartPack?.department_series && Object.keys(this.chartPack.department_series).length > 0;
  }

  hasHistoricalData(): boolean {
    return !!this.chartPack?.daily && this.chartPack.daily.length > 0;
  }

  hasDeptHorizonData(): boolean {
    return !!this.deptForecastPack?.departments?.length;
  }

  hasDeptForecastDeepData(): boolean {
    return !!this.deptForecastPack?.departments?.some(d => d.points?.length > 0);
  }

  ngOnInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      this.fetchPack();
    }
  }

  /** Ensures `@if (chartPack)` canvases exist before Chart.js binds to them. */
  private scheduleChartBuild(): void {
    if (!isPlatformBrowser(this.platformId) || !this.chartPack) return;
    this.cdr.detectChanges();
    requestAnimationFrame(() => {
      requestAnimationFrame(() => this.buildCharts());
    });
  }

  /** Department forecast horizon synced with dashboard selector (default 14 days). */
  private forecastHorizonDays(): number {
    return this.forecastDays;
  }

  private refetchDeptForecasts(): void {
    if (!isPlatformBrowser(this.platformId) || !this.chartPack) return;
    const horizon = this.forecastHorizonDays();
    const requestKey = `${horizon}:${this.selectedModel ?? 'default'}:${this.asOfDate ?? 'latest'}`;
    if (requestKey === this.lastDeptForecastRequestKey && this.deptForecastPack) {
      return;
    }

    this.lastDeptForecastRequestKey = requestKey;
    this.deptForecastError = null;
    this.api.getDepartmentForecasts(horizon, this.selectedModel, this.asOfDate).pipe(
      catchError((err) => {
        this.deptForecastError =
          'Per-department forecasts failed (backend timeout or error). Other charts still apply.';
        if (isDevMode()) console.error(err);
        return of({ forecast_days: horizon, departments: [] });
      }),
    ).subscribe({
      next: (deptFc) => {
        this.deptForecastPack = deptFc;
        const names = this.deptForecastDepartmentNames();
        if (names.length > 0 && !names.includes(this.deptForecastView)) {
          this.deptForecastView = names.includes('ICU') ? 'ICU' : names[0];
        }
        this.scheduleChartBuild();
      },
    });
  }

  onForecastModeChange(mode: 'sliding' | 'expanding'): void {
    if (this.forecastMode === mode) return;
    this.forecastMode = mode;
    if (mode === 'expanding') {
      this.fetchExpandingWindowForecast();
    } else {
      this.refetchStaffingForecast();
    }
  }

  onHistoryWindowChange(days: number): void {
    if (this.historyWindowDays === days) return;
    this.historyWindowDays = days;
    this.fetchPack();
  }

  historyWindowLabel(days: number): string {
    if (days === 730) return '2 years';
    if (days === 365) return '1 year';
    if (days === 180) return '6 months';
    return `${days} days`;
  }

  private fetchPack(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.destroyCharts();
    this.loadingCharts = true;
    this.loadError = null;
    this.deptForecastError = null;
    this.chartPack = null;
    this.deptForecastPack = null;
    this.chartLayoutAttempts = 0;

    const horizon = this.forecastHorizonDays();
    forkJoin({
      pack: this.api.getChartPack(this.historyWindowDays, this.asOfDate),
      deptFc: this.api.getDepartmentForecasts(horizon, this.selectedModel, this.asOfDate).pipe(
        catchError((err) => {
          this.deptForecastError =
            'Per-department forecasts failed (backend timeout or error). Other charts still apply.';
          if (isDevMode()) console.error(err);
          return of({ forecast_days: horizon, departments: [] });
        }),
      ),
      staffingFc: this.api.getLabourStaffingForecast({
        days: horizon,
        model_preference: this.selectedModel,
        as_of_date: this.asOfDate,
      }).pipe(
        catchError(() => of(null as GenericForecastResponse | null)),
      ),
      staffingFit: this.api.getHistoricalStaffingForecast(
        this.historyWindowDays, 7, 60, this.selectedModel, this.asOfDate,
      ).pipe(
        catchError(() => of(null as GenericForecastResponse | null)),
      ),
    }).subscribe({
      next: ({ pack, deptFc, staffingFc, staffingFit }) => {
        this.chartPack = pack;
        this.deptForecastPack = deptFc;
        this.staffingForecast = staffingFc;
        this.staffingModelPrediction = staffingFit;
        this.loadingCharts = false;

        // Ensure ICU is default, or pick the first available if ICU isn't in the list
        const names = this.deptForecastDepartmentNames();
        if (names.length > 0) {
          if (!names.includes(this.deptForecastView)) {
            this.deptForecastView = names.includes('ICU') ? 'ICU' : names[0];
          }
        }

        this.refetchModelPrediction();
        this.scheduleChartBuild();
      },
      error: (err) => {
        this.loadingCharts = false;
        this.loadError =
          'Could not load chart data. Start the API (port 8000) and use `ng serve` so /api is proxied.';
        if (isDevMode()) console.error(err);
      },
    });
  }

  private destroyCharts(): void {
    for (const c of this.charts) {
      try {
        c.destroy();
      } catch {
        /* noop */
      }
    }
    this.charts = [];
  }

  private fetchExpandingWindowForecast(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.api.getExpandingWindowStaffingForecast(this.selectedModel, this.asOfDate).subscribe({
      next: (forecast) => {
        this.expandingWindowForecast = forecast;
        this.scheduleChartBuild();
      },
      error: (err) => {
        if (isDevMode()) console.error('Expanding window forecast error:', err);
        this.expandingWindowForecast = null;
      },
    });
  }

  private refetchStaffingForecast(): void {
    if (!isPlatformBrowser(this.platformId) || !this.chartPack) return;
    const horizon = this.forecastHorizonDays();
    forkJoin({
      future: this.api.getLabourStaffingForecast({
        days: horizon,
        model_preference: this.selectedModel,
        as_of_date: this.asOfDate,
      }).pipe(catchError(() => of(null as GenericForecastResponse | null))),
      modelFit: this.api.getHistoricalStaffingForecast(
        this.historyWindowDays, 7, 60, this.selectedModel, this.asOfDate,
      ).pipe(catchError(() => of(null as GenericForecastResponse | null))),
    }).subscribe({
      next: ({ future, modelFit }) => {
        this.staffingForecast = future;
        this.staffingModelPrediction = modelFit;
        this.scheduleChartBuild();
      },
    });
  }

  private refetchModelPrediction(): void {
    if (!isPlatformBrowser(this.platformId) || !this.chartPack) return;

    const daily = this.chartPack.daily ?? [];
    if (!daily.length) return;

    this.api.getHistoricalRollingForecast(this.historyWindowDays, 7, 60, this.selectedModel, this.asOfDate).pipe(
      catchError((err) => {
        if (isDevMode()) console.error(err);
        return of({
          forecast_data: [],
          confidence_interval: { lower: [], upper: [] },
          model_metrics: { mape: 0, rmse: 0, trend: 0, backtest_days: 0, engine: '' },
          forecast_model: { name: '', summary: '', confidence_intervals: '', accuracy_note: '' },
        });
      }),
    ).subscribe({
      next: (prediction) => {
        this.modelPredictionForecast = prediction;
        this.scheduleChartBuild();
      },
    });
  }

  private buildCharts(): void {
    if (!isPlatformBrowser(this.platformId) || !this.chartPack) return;
    if (!this.histCanvas?.nativeElement) {
      if (++this.chartLayoutAttempts > 40) {
        this.loadError =
          'Charts could not mount (layout timeout). Try a hard refresh, or confirm the API is running.';
        if (isDevMode()) console.error('[occupancy-charts] canvas #histCanvas never appeared');
        return;
      }
      if (isDevMode() && this.chartLayoutAttempts === 1) {
        console.warn('[occupancy-charts] Waiting for chart canvases in the DOM…');
      }
      requestAnimationFrame(() => this.buildCharts());
      return;
    }
    this.chartLayoutAttempts = 0;
    this.destroyCharts();
    const pack = this.chartPack;

    this.buildHistoricalForecast(pack);
    this.buildStaffingChart(pack);
    this.buildSparkMultiline(pack);
    this.buildDeptHorizonBar();
    this.buildDepartmentForecastDeep();
  }

  private pushChart(c: ChartType): void {
    this.charts.push(c);
  }

  private buildHistoricalForecast(pack: ChartPack): void {
    const el = this.histCanvas?.nativeElement;
    if (!el) return;

    const daily = [...pack.daily].sort((a, b) => a.date.localeCompare(b.date));
    const rateMap = new Map(
      daily.map((d) => [d.date, Math.round(d.occupancy_rate * 1000) / 10]),
    );
    const losMap = new Map(daily.map((d) => [d.date, Math.round(d.avg_los * 10) / 10]));

    const fc = this.forecast?.forecast_data ?? [];
    const fcPctMap = new Map(
      fc.map((f) => [f.date, Math.round(f.predicted_occupancy_rate * 1000) / 10]),
    );
    const ciLowerMap = new Map(
      fc.map((f) => [f.date, f.lower_bound != null ? Math.round(f.lower_bound * 1000) / 10 : null]),
    );
    const ciUpperMap = new Map(
      fc.map((f) => [f.date, f.upper_bound != null ? Math.round(f.upper_bound * 1000) / 10 : null]),
    );

    const mergedLabels = [...new Set([...rateMap.keys(), ...fcPctMap.keys()])].sort();
    const histSeries = mergedLabels.map((d) => rateMap.get(d) ?? null);
    
    // Join forecast line: add the last historical point to the forecast series
    const lastHistDate = daily.length > 0 ? daily[daily.length - 1].date : null;
    const lastHistRate = lastHistDate ? rateMap.get(lastHistDate) : null;
    
    const fcSeries = mergedLabels.map((d) => {
      if (d === lastHistDate && lastHistRate !== undefined) return lastHistRate;
      return fcPctMap.get(d) ?? null;
    });
    const ciLowerSeries = mergedLabels.map((d) => {
      if (d === lastHistDate && lastHistRate !== undefined) return lastHistRate;
      return ciLowerMap.get(d) ?? null;
    });
    const ciUpperSeries = mergedLabels.map((d) => {
      if (d === lastHistDate && lastHistRate !== undefined) return lastHistRate;
      return ciUpperMap.get(d) ?? null;
    });
    const losSeries = mergedLabels.map((d) => losMap.get(d) ?? null);
    const modelPredRaw = this.modelPredictionForecast as any;
    const rollingMape: number = modelPredRaw?.model_metrics?.rolling_mape ?? 0;
    const rollingEngine: string = modelPredRaw?.model_metrics?.engine ?? this.selectedModel ?? '';
    const modelPredictionMap = new Map(
      (this.modelPredictionForecast?.forecast_data ?? []).map((f) => [f.date, Math.round(f.predicted_occupancy_rate * 1000) / 10]),
    );
    const modelPredictionSeries = mergedLabels.map((d) => modelPredictionMap.get(d) ?? null);

    const grad = el.getContext('2d');
    let fillGrad: CanvasGradient | string = PAL.primary + '33';
    if (grad) {
      const g = grad.createLinearGradient(0, 0, 0, el.height || 220);
      g.addColorStop(0, 'rgba(102, 126, 234, 0.35)');
      g.addColorStop(1, 'rgba(102, 126, 234, 0.02)');
      fillGrad = g;
    }

    const c = new Chart(el, {
      type: 'line',
      data: {
        labels: mergedLabels,
        datasets: [
          {
            label: 'Confidence Range Lower',
            data: ciLowerSeries,
            borderColor: 'rgba(0,125,176,0.30)',
            borderDash: [3, 3],
            pointRadius: 0,
            tension: 0.25,
            fill: false,
            borderWidth: 1,
            spanGaps: false,
            yAxisID: 'y',
          },
          {
            label: 'Confidence Range Upper',
            data: ciUpperSeries,
            borderColor: 'rgba(0,125,176,0.30)',
            borderDash: [3, 3],
            pointRadius: 0,
            tension: 0.25,
            fill: '-1',
            backgroundColor: 'rgba(0,125,176,0.08)',
            borderWidth: 1,
            spanGaps: false,
            yAxisID: 'y',
          },
          {
            label: 'Actual Occupancy %',
            data: histSeries,
            borderColor: PAL.primary,
            backgroundColor: fillGrad,
            fill: true,
            tension: 0.35,
            spanGaps: false,
            pointRadius: 0,
            borderWidth: 3,
            yAxisID: 'y',
          },
          {
            label: 'Forecasted Occupancy %',
            data: fcSeries,
            borderColor: PAL.coral,
            borderDash: [6, 4],
            tension: 0.25,
            pointRadius: 3,
            borderWidth: 3,
            spanGaps: false,
            yAxisID: 'y',
          },
          {
            label: `Average Length of Stay (days)`,
            data: losSeries,
            borderColor: PAL.teal,
            backgroundColor: 'transparent',
            yAxisID: 'y1',
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 1.5,
            hidden: mergedLabels.length > 120,
          },
          {
            label: 'Historical Forecast Validation',
            data: modelPredictionSeries,
            borderColor: '#005A80',
            backgroundColor: 'transparent',
            borderDash: [5, 5],
            yAxisID: 'y',
            tension: 0.25,
            pointRadius: 2,
            borderWidth: 1.5,
            spanGaps: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          title: {
            display: true,
            text: 'Occupancy Analysis & Forecast',
            font: {
              size: 16,
              weight: 'bold'
            }
          },
          legend: { position: 'top' },
          tooltip: {
            callbacks: {
              title: (items) => {
                const lbl = (items[0]?.label as string) ?? '';
                if (!lbl) return lbl;
                const d = new Date(lbl + 'T00:00:00');
                const day = d.toLocaleDateString('en-US', { weekday: 'long' });
                return `${day} · ${lbl}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
            grid: { color: PAL.grid },
          },
          y: {
            position: 'left',
            min: 0,
            max: 100,
            title: { display: true, text: 'Occupancy %' },
            grid: { color: PAL.grid },
          },
          y1: {
            position: 'right',
            grid: { drawOnChartArea: false },
            title: { display: true, text: 'LOS (d)' },
            beginAtZero: false,
          },
        },
      },
    });
    this.pushChart(c);
  }

  private buildStaffingChart(pack: ChartPack): void {
    const el = this.staffingCanvas?.nativeElement;
    if (!el) return;

    const daily = [...pack.daily].sort((a, b) => a.date.localeCompare(b.date));
    const staffMap = new Map(daily.map((d) => [d.date, d.labour_staffing ?? 0]));

    const fc = this.staffingForecast?.forecast_data ?? [];
    const fcMap = new Map(fc.map((f) => [f.date, f.predicted_value]));
    const fcLoMap = new Map(
      (this.staffingForecast?.confidence_interval?.lower ?? []).map((v, i) => [fc[i]?.date, v]),
    );
    const fcHiMap = new Map(
      (this.staffingForecast?.confidence_interval?.upper ?? []).map((v, i) => [fc[i]?.date, v]),
    );
    const staffModelRaw = this.staffingModelPrediction as any;
    const staffRollingMape: number = staffModelRaw?.model_metrics?.rolling_mape ?? 0;
    const modelPredMap = new Map(
      (this.staffingModelPrediction?.forecast_data ?? []).map((f) => [f.date, f.predicted_value]),
    );
    const modelLoMap = new Map(
      (this.staffingModelPrediction?.confidence_interval?.lower ?? []).map((p: any) => [p.date, p.value]),
    );
    const modelHiMap = new Map(
      (this.staffingModelPrediction?.confidence_interval?.upper ?? []).map((p: any) => [p.date, p.value]),
    );

    const labels = [...new Set([...staffMap.keys(), ...fcMap.keys(), ...modelPredMap.keys()])].sort();
    const lastHistDate = daily.length ? daily[daily.length - 1].date : null;
    const lastHistVal = lastHistDate ? staffMap.get(lastHistDate) : null;

    const histSeries = labels.map((d) => (staffMap.has(d) ? (staffMap.get(d) ?? null) : null));
    const fcSeries = labels.map((d) => {
      if (d === lastHistDate && lastHistVal != null) return lastHistVal;
      return fcMap.has(d) ? (fcMap.get(d) ?? null) : null;
    });
    const loSeries = labels.map((d) => fcLoMap.get(d) ?? null);
    const hiSeries = labels.map((d) => fcHiMap.get(d) ?? null);
    const modelLoSeries = labels.map((d) => modelLoMap.get(d) ?? null);
    const modelHiSeries = labels.map((d) => modelHiMap.get(d) ?? null);
    const modelPredSeries = labels.map((d) => modelPredMap.get(d) ?? null);

    const mape = this.staffingForecast?.model_metrics?.mape ?? 0;
    const mapePct = (mape <= 1 ? mape * 100 : mape).toFixed(1);
    const engine = this.staffingForecast?.model_metrics?.engine ?? this.selectedModel ?? '';

    // Expanding window mode: show week-specific predictions
    const week1Map = new Map(
      (this.expandingWindowForecast?.week1_predictions ?? []).map((p: any) => [p.date, p.predicted_value])
    );
    const week2Map = new Map(
      (this.expandingWindowForecast?.week2_predictions ?? []).map((p: any) => [p.date, p.predicted_value])
    );
    const week3Map = new Map(
      (this.expandingWindowForecast?.week3_predictions ?? []).map((p: any) => [p.date, p.predicted_value])
    );
    const week1Mape = (this.expandingWindowForecast?.model_metrics as any)?.week1_mape ?? 0;
    const week2Mape = (this.expandingWindowForecast?.model_metrics as any)?.week2_mape ?? 0;
    const week3Mape = (this.expandingWindowForecast?.model_metrics as any)?.week3_mape ?? 0;
    const iterations = (this.expandingWindowForecast?.model_metrics as any)?.iterations_completed ?? 0;

    const week1Series = labels.map((d) => week1Map.get(d) ?? null);
    const week2Series = labels.map((d) => week2Map.get(d) ?? null);
    const week3Series = labels.map((d) => week3Map.get(d) ?? null);

    // Build datasets based on forecast mode
    const datasets = [
      {
        label: 'Confidence Range Lower',
        data: loSeries,
        borderColor: 'rgba(118, 75, 162, 0.35)',
        borderDash: [4, 3],
        pointRadius: 0,
        tension: 0.25,
        fill: false,
        borderWidth: 1,
        spanGaps: false,
      },
      {
        label: 'Confidence Range Upper',
        data: hiSeries,
        borderColor: 'rgba(118, 75, 162, 0.35)',
        borderDash: [4, 3],
        pointRadius: 0,
        tension: 0.25,
        fill: '-1',
        backgroundColor: 'rgba(118, 75, 162, 0.10)',
        borderWidth: 1,
        spanGaps: false,
      },
      {
        label: 'Actual Staffing (FTE)',
        data: histSeries,
        borderColor: PAL.primary,
        backgroundColor: 'rgba(102,126,234,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 3,
        spanGaps: false,
      },
    ];

    if (this.forecastMode === 'expanding') {
      // Week-specific predictions
      datasets.push(
        {
          label: `Week 1 (MAPE ${week1Mape.toFixed(1)}%)`,
          data: week1Series,
          borderColor: '#10b981',
          borderDash: [2, 2],
          tension: 0.25,
          pointRadius: 1,
          borderWidth: 1,
          fill: false,
          spanGaps: false,
        },
        {
          label: `Week 2 (MAPE ${week2Mape.toFixed(1)}%)`,
          data: week2Series,
          borderColor: '#f59e0b',
          borderDash: [4, 2],
          tension: 0.25,
          pointRadius: 1,
          borderWidth: 1,
          fill: false,
          spanGaps: false,
        },
        {
          label: `Week 3 (MAPE ${week3Mape.toFixed(1)}%)`,
          data: week3Series,
          borderColor: '#8b5cf6',
          borderDash: [6, 2],
          tension: 0.25,
          pointRadius: 1,
          borderWidth: 1,
          fill: false,
          spanGaps: false,
        }
      );
    } else {
      // Sliding window model predictions
      datasets.push(
        {
          label: 'Historical Validation Lower',
          data: modelLoSeries,
          borderColor: 'rgba(231, 111, 81, 0.30)',
          borderDash: [3, 2],
          pointRadius: 0,
          tension: 0.25,
          fill: false,
          borderWidth: 1,
          spanGaps: false,
        },
        {
          label: 'Historical Validation Upper',
          data: modelHiSeries,
          borderColor: 'rgba(231, 111, 81, 0.30)',
          borderDash: [3, 2],
          pointRadius: 0,
          tension: 0.25,
          fill: '-1',
          backgroundColor: 'rgba(231, 111, 81, 0.08)',
          borderWidth: 1,
          spanGaps: false,
        },
        {
          label: 'Historical Forecast Validation',
          data: modelPredSeries,
          borderColor: '#e76f51',
          borderDash: [5, 5],
          tension: 0.25,
          pointRadius: 2,
          borderWidth: 1.5,
          fill: false,
          spanGaps: false,
        }
      );
    }

    datasets.push({
      label: `Forecasted Staffing`,
      data: fcSeries,
      borderColor: PAL.coral,
      borderDash: [6, 4],
      tension: 0.25,
      pointRadius: 3,
      borderWidth: 3,
      fill: false,
      spanGaps: false,
    });

    const chartTitle = 'Staffing Requirements Analysis';

    const c = new Chart(el, {
      type: 'line',
      data: {
        labels,
        datasets: datasets as any,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          title: {
            display: true,
            text: chartTitle,
          },
          legend: { position: 'top' },
          tooltip: {
            callbacks: {
              title: (items) => {
                const lbl = (items[0]?.label as string) ?? '';
                if (!lbl) return lbl;
                const d = new Date(lbl + 'T00:00:00');
                const day = d.toLocaleDateString('en-US', { weekday: 'long' });
                return `${day} · ${lbl}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
            grid: { color: PAL.grid },
          },
          y: {
            beginAtZero: false,
            title: { display: true, text: 'Staff (FTE)' },
            grid: { color: PAL.grid },
          },
        },
      },
    });
    this.pushChart(c);
  }

  private buildSparkMultiline(pack: ChartPack): void {
    const el = this.sparkCanvas?.nativeElement;
    if (!el) return;

    const series = pack.department_series;
    if (!series) return;
    const keys = Object.keys(series);
    if (!keys.length) return;

    const refDates = [...series[keys[0]]!.dates];
    let step = 1;
    if (refDates.length > 90) {
      step = Math.ceil(refDates.length / 90);
    }
    const labels = refDates.filter((_, i) => i % step === 0);

    const colors = [
      '#007DB0',
      '#0099D6',
      '#005A80',
      '#48CAE4',
      '#00B4D8',
      '#90E0EF',
      '#6C6E71',
    ];

    const datasets = keys.map((k, i) => {
      const s = series[k];
      const m = new Map(s.dates.map((d, idx) => [d, s.rates[idx] as number]));
      return {
        label: k,
        data: labels.map((d) => m.get(d) ?? null),
        borderColor: colors[i % colors.length],
        backgroundColor: 'transparent',
        tension: 0.25,
        pointRadius: 0,
        borderWidth: 1.8,
        spanGaps: true,
      };
    });

    const c = new Chart(el, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: { display: true, text: 'Department occupancy % (multi-series)' },
          legend: { position: 'bottom' },
        },
        scales: {
          x: {
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
            grid: { color: PAL.grid },
          },
          y: {
            min: 35,
            max: 100,
            title: { display: true, text: 'Dept occupancy %' },
            grid: { color: PAL.grid },
          },
        },
      },
    });
    this.pushChart(c);
  }

  /** Horizontal bar: each department's predicted occupancy % on the last forecast day (14d horizon). */
  private buildDeptHorizonBar(): void {
    const el = this.deptHorizonCanvas?.nativeElement;
    const pack = this.deptForecastPack;
    if (!el || !pack?.departments?.length) return;

    const rows = pack.departments
      .filter((d) => (d.points?.length ?? 0) > 0 && !d.error)
      .map((d) => ({
        name: d.department,
        pct: d.points![d.points!.length - 1]!.rate_pct,
        occupied: d.points![d.points!.length - 1]!.occupied,
        totalBeds: d.total_beds ?? 0,
      }))
      .sort((a, b) => a.pct - b.pct);

    if (!rows.length) return;

    const c = new Chart(el, {
      type: 'bar',
      data: {
        labels: rows.map((r) => r.name),
        datasets: [
          {
            label: `Predicted occ. % (final day)`,
            data: rows.map((r) => r.pct),
            backgroundColor: rows.map((r) =>
              r.pct >= 90
                ? 'rgba(255,0,0,0.88)'
                : r.pct >= 85
                  ? 'rgba(255,0,0,0.55)'
                  : 'rgba(0,125,176,0.72)',
            ),
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: `Department Forecast — Day ${pack.forecast_days}`,
          },
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const row = rows[ctx.dataIndex];
                if (!row) return `${ctx.parsed.x?.toFixed(1) ?? ctx.formattedValue}%`;
                return `${row.pct.toFixed(1)}% · ${row.occupied}/${row.totalBeds} beds`;
              },
            },
          },
        },
        scales: {
          x: {
            min: 0,
            max: 100,
            title: { display: true, text: 'Predicted occupancy %' },
            grid: { color: PAL.grid },
          },
          y: { grid: { display: false } },
        },
      },
    });
    this.pushChart(c);
  }

  departmentHorizonRows(limit: number = 6): Array<{
    department: string;
    ratePct: number;
    occupied: number;
    totalBeds: number;
  }> {
    const departments = this.deptForecastPack?.departments ?? [];
    return departments
      .filter((d) => (d.points?.length ?? 0) > 0 && !d.error)
      .map((d) => {
        const last = d.points[d.points.length - 1];
        return {
          department: d.department,
          ratePct: last.rate_pct,
          occupied: last.occupied,
          totalBeds: d.total_beds ?? 0,
        };
      })
      .sort((a, b) => b.ratePct - a.ratePct)
      .slice(0, limit);
  }

  private buildDepartmentForecastDeep(): void {
    const el = this.deptForecastCanvas?.nativeElement;
    const fcPack = this.deptForecastPack;
    if (!el || !fcPack?.departments?.length) return;

    const series = fcPack.departments.filter((d) => d.points?.length > 0);
    if (!series.length) return;

    const d = series.find((x) => x.department === this.deptForecastView);
    if (!d) return;

    const pack = this.chartPack;
    const tb = Math.max(1, d.total_beds ?? 1);
    const mapePct = (d.mape ?? 0) <= 1 ? (d.mape ?? 0) * 100 : (d.mape ?? 0);

    const histRaw = pack?.department_series?.[d.department];
    let histDates = [...(histRaw?.dates ?? [])];
    let histOcc = [...(histRaw?.occupied ?? [])];
    const maxHistPts = 110;
    if (histDates.length > maxHistPts) {
      const step = Math.ceil(histDates.length / maxHistPts);
      histDates = histDates.filter((_, i) => i % step === 0);
      histOcc = histOcc.filter((_, i) => i % step === 0);
    }
    const histMap = new Map<string, number>();
    histDates.forEach((dt, i) => histMap.set(dt, histOcc[i] ?? 0));

    const fcPointByDate = new Map(d.points.map((p) => [p.date, p]));
    const fcDates = d.points.map((p) => p.date);
    const labels = [...new Set([...histDates, ...fcDates])].sort();

    const lastHistDate = histDates.length > 0 ? histDates[histDates.length - 1] : null;
    const lastHistOcc = lastHistDate ? histMap.get(lastHistDate) : null;

    const bedLower = (p: (typeof d.points)[0]) =>
      p.lower_beds ?? Math.round((tb * p.lower_pct) / 100);
    const bedUpper = (p: (typeof d.points)[0]) =>
      p.upper_beds ?? Math.round((tb * p.upper_pct) / 100);

    const histActual = labels.map((date) => (histMap.has(date) ? histMap.get(date)! : null));
    const fcOccupied = labels.map((date) => {
      if (date === lastHistDate && lastHistOcc !== undefined) return lastHistOcc;
      const p = fcPointByDate.get(date);
      return p ? p.occupied : null;
    });
    const fcLower = labels.map((date) => {
      if (date === lastHistDate && lastHistOcc !== undefined) return lastHistOcc;
      const p = fcPointByDate.get(date);
      return p ? bedLower(p) : null;
    });
    const fcUpper = labels.map((date) => {
      if (date === lastHistDate && lastHistOcc !== undefined) return lastHistOcc;
      const p = fcPointByDate.get(date);
      return p ? bedUpper(p) : null;
    });

    let peak = tb;
    for (const date of labels) {
      const h = histMap.get(date);
      if (h != null) peak = Math.max(peak, h);
      const p = fcPointByDate.get(date);
      if (p) peak = Math.max(peak, p.occupied, bedLower(p), bedUpper(p));
    }
    const yMax = Math.max(tb, Math.ceil(peak * 1.06));

    const c = new Chart(el, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Confidence Range Lower (beds)',
            data: fcLower,
            borderColor: 'rgba(118, 75, 162, 0.45)',
            borderDash: [5, 4],
            pointRadius: 0,
            tension: 0.3,
            fill: false,
            borderWidth: 1.5,
            spanGaps: false,
          },
          {
            label: 'Confidence Range Upper (beds)',
            data: fcUpper,
            borderColor: 'rgba(118, 75, 162, 0.45)',
            borderDash: [5, 4],
            pointRadius: 0,
            tension: 0.3,
            fill: '-1',
            backgroundColor: 'rgba(118, 75, 162, 0.12)',
            borderWidth: 1.5,
            spanGaps: false,
          },
          {
            label: 'Actual Occupied (beds)',
            data: histActual,
            borderColor: PAL.primary,
            backgroundColor: 'transparent',
            tension: 0.28,
            pointRadius: 0,
            borderWidth: 3,
            spanGaps: false,
          },
          {
            label: 'Forecasted Occupied (beds)',
            data: fcOccupied,
            borderColor: PAL.coral,
            borderDash: [6, 4],
            tension: 0.28,
            pointRadius: 3,
            borderWidth: 3,
            spanGaps: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          title: {
            display: true,
            text: `${d.department} · ${fcPack.forecast_days}-Day Forecast · Accuracy ${mapePct.toFixed(1)}%`,
            font: {
              size: 16,
              weight: 'bold'
            }
          },
          legend: { position: 'top' },
          tooltip: {
            callbacks: {
              title: (items) => {
                const lbl = (items[0]?.label as string) ?? '';
                if (!lbl) return lbl;
                const d = new Date(lbl + 'T00:00:00');
                const day = d.toLocaleDateString('en-US', { weekday: 'long' });
                return `${day} · ${lbl}`;
              },
              label: (ctx) => {
                const date = labels[ctx.dataIndex];
                const p = fcPointByDate.get(date);
                const raw = ctx.parsed.y;
                if (raw == null || Number.isNaN(raw)) return '';
                const lab = String(ctx.dataset.label ?? '');
                if (lab.startsWith('Actual')) {
                  return `${lab}: ${raw} beds`;
                }
                if (p && lab.startsWith('Confidence Range Lower')) {
                  return `${lab}: ${raw} beds (${p.lower_pct}% occ)`;
                }
                if (p && lab.startsWith('Confidence Range Upper')) {
                  return `${lab}: ${raw} beds (${p.upper_pct}% occ)`;
                }
                if (p && lab.startsWith('Forecasted')) {
                  return `${lab}: ${raw} beds (${p.rate_pct}% occ)`;
                }
                return `${lab}: ${raw}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
            grid: { color: PAL.grid },
          },
          y: {
            min: 0,
            max: yMax,
            title: { display: true, text: 'Occupied beds' },
            grid: { color: PAL.grid },
          },
        },
      },
    });
    this.pushChart(c);
  }
}
