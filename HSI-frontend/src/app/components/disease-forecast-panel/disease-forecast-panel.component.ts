import {
  AfterViewInit,
  ChangeDetectorRef,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  PLATFORM_ID,
  SimpleChanges,
  ViewChild,
  inject,
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Chart, registerables, Chart as ChartType } from 'chart.js';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { ApiService } from '../../services/api.service';
import {
  DEFAULT_FORECAST_DAYS,
  GenericForecastResponse,
} from '../../models/dashboard.models';

Chart.register(...registerables);

type ForecastScope = 'category' | 'disease';

const EMPTY_FC: GenericForecastResponse = {
  forecast_data: [],
  confidence_interval: { lower: [], upper: [] },
  model_metrics: { mape: 0, rmse: 0, trend: 0, backtest_days: 0, engine: '' },
  forecast_model: { name: '', summary: '', confidence_intervals: '', accuracy_note: '', insights: [] },
};

@Component({
  selector: 'app-disease-forecast-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './disease-forecast-panel.component.html',
  styleUrl: './disease-forecast-panel.component.scss',
})
export class DiseaseForecastPanelComponent implements OnInit, OnChanges, AfterViewInit, OnDestroy {
  private readonly platformId = inject(PLATFORM_ID);
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  @Input() forecastDays = DEFAULT_FORECAST_DAYS;
  @Input() selectedModel: string | null = null;
  @Input() selectedDisease = '';
  @Input() asOfDate: string | null = null;

  @ViewChild('admissionsCanvas') admissionsCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('dischargesCanvas') dischargesCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('losCanvas') losCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('edWaitCanvas') edWaitCanvas?: ElementRef<HTMLCanvasElement>;

  categories: string[] = [
    'Trauma',  
    'Respiratory',
    'Cardiovascular',
    'Cancer',
    'Neurological',
    'Musculoskeletal',
    'General',
  ];
  diseases: string[] = [];
  scope: ForecastScope = 'category';
  selectedCategory = 'Trauma';  
  loading = false;
  error: string | null = null;

  admissionsForecast: GenericForecastResponse = EMPTY_FC;
  dischargesForecast: GenericForecastResponse = EMPTY_FC;
  losForecast: GenericForecastResponse = EMPTY_FC;
  edWaitForecast: GenericForecastResponse = EMPTY_FC;

  readonly modelOptions = [
    { value: 'prophet', label: 'Prophet' },
    { value: 'ridge', label: 'Ridge (Best for LOS)' },
    { value: 'holt_winters', label: 'Holt-Winters' },
    { value: 'auto_arima', label: 'Auto-ARIMA' },
    { value: 'xgboost', label: 'XGBoost' },
    { value: 'ensemble', label: 'Ensemble (Best Accuracy)' },
  ];

  expandedCards: Record<string, boolean> = {};

  toggleCardExpanded(key: string): void {
    this.expandedCards[key] = !this.expandedCards[key];
  }

  isExpanded(key: string): boolean {
    return !!this.expandedCards[key];
  }

  private charts: ChartType[] = [];
  private pendingRebuild = false;

  ngOnInit(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.api.getDiseaseCategories().subscribe({
      next: (r) => {
        this.categories = r.categories ?? [];
        if (!this.selectedCategory && this.categories.length) {
          this.selectedCategory = this.categories[0];
        }
      },
    });
    this.api.getDiseaseList().subscribe({
      next: (r) => (this.diseases = r.diseases ?? []),
    });
    this.loadForecasts();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['selectedDisease']?.currentValue) {
      this.scope = 'disease';
      this.loadForecasts();
    }
    if (changes['forecastDays'] || changes['selectedModel'] || changes['asOfDate']) {
      this.loadForecasts();
    }
  }

  ngAfterViewInit(): void {
    if (this.pendingRebuild) {
      this.scheduleChartBuild();
    }
  }

  ngOnDestroy(): void {
    this.destroyCharts();
  }

  onScopeChange(ev: Event): void {
    this.scope = (ev.target as HTMLSelectElement).value as ForecastScope;
    this.loadForecasts();
  }

  onCategoryChange(ev: Event): void {
    this.selectedCategory = (ev.target as HTMLSelectElement).value;
    this.loadForecasts();
  }

  onDiseaseChange(ev: Event): void {
    this.selectedDisease = (ev.target as HTMLSelectElement).value;
    this.loadForecasts();
  }

  onModelChange(ev: Event): void {
    const v = (ev.target as HTMLSelectElement).value;
    this.selectedModel = v || 'prophet';
    this.loadForecasts();
  }

  scopeLabel(): string {
    return this.scope === 'category' ? this.selectedCategory : this.selectedDisease;
  }

  hasScopeSelection(): boolean {
    return this.scope === 'category' ? !!this.selectedCategory : !!this.selectedDisease;
  }

  modelMeta(_fc: GenericForecastResponse): string {
    return '';
  }

  forecastExplanation(fc: GenericForecastResponse): string {
    return (fc.forecast_model?.explanation || fc.forecast_model?.summary || '').trim();
  }

  forecastInsights(fc: GenericForecastResponse): string[] {
    return (fc.forecast_model?.insights ?? []).filter((x) => !!x?.trim());
  }

  loadForecasts(): void {
    if (!isPlatformBrowser(this.platformId)) return;

    const req = {
      days: this.forecastDays,
      model_preference: this.selectedModel ?? 'prophet',
      as_of_date: this.asOfDate,
    };

    const ed$ = this.api.getEdWaitTimeForecast(req).pipe(catchError(() => of(EMPTY_FC)));

    if (!this.hasScopeSelection()) {
      this.admissionsForecast = EMPTY_FC;
      this.dischargesForecast = EMPTY_FC;
      this.losForecast = EMPTY_FC;
      ed$.subscribe({
        next: (ed) => {
          this.edWaitForecast = ed;
          this.scheduleChartBuild();
        },
      });
      return;
    }

    this.loading = true;
    this.error = null;

    const key = this.scope === 'category' ? this.selectedCategory : this.selectedDisease;
    const admissions$ =
      this.scope === 'category'
        ? this.api.getCategoryAdmissionsForecast(key, req)
        : this.api.getDiseaseAdmissionsForecast(key, req);
    const discharges$ =
      this.scope === 'category'
        ? this.api.getCategoryDischargesForecast(key, req)
        : this.api.getDiseaseDischargesForecast(key, req);
    const los$ =
      this.scope === 'category'
        ? this.api.getCategoryLosForecast(key, req)
        : this.api.getDiseaseLosForecast(key, req);

    forkJoin({
      admissions: admissions$.pipe(catchError(() => of(EMPTY_FC))),
      discharges: discharges$.pipe(catchError(() => of(EMPTY_FC))),
      los: los$.pipe(catchError(() => of(EMPTY_FC))),
      edWait: ed$,
    }).subscribe({
      next: ({ admissions, discharges, los, edWait }) => {
        this.admissionsForecast = admissions;
        this.dischargesForecast = discharges;
        this.losForecast = los;
        this.edWaitForecast = edWait;
        this.loading = false;
        this.scheduleChartBuild();
      },
      error: () => {
        this.loading = false;
        this.error = 'Failed to load disease forecasts. Confirm the API is running on port 8000.';
        this.cdr.markForCheck();
      },
    });
  }

  private scheduleChartBuild(): void {
    if (!isPlatformBrowser(this.platformId)) return;
    this.pendingRebuild = true;
    this.cdr.detectChanges();
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        this.pendingRebuild = false;
        this.buildCharts();
      });
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

  private buildCharts(): void {
    this.destroyCharts();
    this.buildGenericChart(
      this.admissionsCanvas,
      this.admissionsForecast,
      'Admissions forecast (patients/day)',
      'Patients',
      '#667eea',
    );
    this.buildGenericChart(
      this.dischargesCanvas,
      this.dischargesForecast,
      'Discharge forecast (patients/day)',
      'Discharges',
      '#20c997',
    );
    this.buildGenericChart(
      this.losCanvas,
      this.losForecast,
      'Length of stay forecast (7-day operational trend)',
      'Days',
      '#764ba2',
    );
    this.buildGenericChart(
      this.edWaitCanvas,
      this.edWaitForecast,
      'Emergency Department wait time forecast (minutes)',
      'Minutes',
      '#fd7e14',
    );
  }

  private buildGenericChart(
    canvasRef: ElementRef<HTMLCanvasElement> | undefined,
    fc: GenericForecastResponse,
    title: string,
    yLabel: string,
    color: string,
  ): void {
    const el = canvasRef?.nativeElement;
    const rows = fc.forecast_data ?? [];
    if (!el || !rows.length) return;

    const labels = rows.map((r) => r.date);
    const values = rows.map((r) => Math.round(r.predicted_value * 10) / 10);
    const lo = rows.map((r) =>
      r.lower_bound != null ? Math.round(r.lower_bound * 10) / 10 : null,
    );
    const hi = rows.map((r) =>
      r.upper_bound != null ? Math.round(r.upper_bound * 10) / 10 : null,
    );

    const c = new Chart(el, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Lower',
            data: lo,
            borderColor: color + '66',
            borderDash: [4, 3],
            pointRadius: 0,
            tension: 0.25,
            fill: false,
          },
          {
            label: 'Upper',
            data: hi,
            borderColor: color + '66',
            borderDash: [4, 3],
            pointRadius: 0,
            tension: 0.25,
            fill: '-1',
            backgroundColor: color + '22',
          },
          {
            label: 'Predicted',
            data: values,
            borderColor: color,
            backgroundColor: 'transparent',
            borderWidth: 2.5,
            tension: 0.25,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          title: { display: true, text: title },
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
            grid: { color: 'rgba(0,0,0,0.06)' },
          },
          y: {
            beginAtZero: false,
            title: { display: true, text: yLabel },
            grid: { color: 'rgba(0,0,0,0.06)' },
          },
        },
      },
    });
    this.charts.push(c);
  }
}
