import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  PLATFORM_ID,
  SimpleChanges,
  ViewChild,
  inject,
  isDevMode,
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Chart, registerables, Chart as ChartType } from 'chart.js';
import { ForecastResponse } from '../../models/dashboard.models';

Chart.register(...registerables);

// use brand palette from backend/UI spec
const PAL = {
  primary: '#007DB0',
  coral: '#007DB0',
  band: 'rgba(0,125,176,0.12)',
  borderBand: 'rgba(0,125,176,0.35)',
  grid: 'rgba(0,0,0,0.06)',
};

@Component({
  selector: 'app-dashboard-forecast-mini',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard-forecast-mini.component.html',
  styleUrls: ['./dashboard-forecast-mini.component.scss'],
})
export class DashboardForecastMiniComponent implements OnChanges, AfterViewInit, OnDestroy {
  private readonly platformId = inject(PLATFORM_ID);

  @Input() forecast: ForecastResponse | null = null;
  @Input() totalBeds = 1;

  @ViewChild('lineCanvas') lineCanvas?: ElementRef<HTMLCanvasElement>;
  @ViewChild('barCanvas') barCanvas?: ElementRef<HTMLCanvasElement>;

  private charts: ChartType[] = [];

  ngOnChanges(changes: SimpleChanges): void {
    if (!changes['forecast'] || !isPlatformBrowser(this.platformId)) return;
    requestAnimationFrame(() => requestAnimationFrame(() => this.rebuild()));
  }

  ngAfterViewInit(): void {
    if (isPlatformBrowser(this.platformId)) {
      requestAnimationFrame(() => requestAnimationFrame(() => this.rebuild()));
    }
  }

  ngOnDestroy(): void {
    this.destroyCharts();
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

  private rebuild(): void {
    this.destroyCharts();
    const rows = this.forecast?.forecast_data ?? [];
    if (!rows.length) return;

    const labels = rows.map((r) => r.date);
    const tb = Math.max(1, this.totalBeds);
    const mid = rows.map((r) => Math.round(r.predicted_occupancy_rate * 1000) / 10);
    const lo = rows.map((r) => Math.round(r.lower_bound * 1000) / 10);
    const hi = rows.map((r) => Math.round(r.upper_bound * 1000) / 10);
    const beds = rows.map((r) => r.predicted_occupied_beds);

    const el1 = this.lineCanvas?.nativeElement;
    if (el1) {
      const c1 = new Chart(el1, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Lower %',
              data: lo,
              borderColor: PAL.borderBand,
              borderDash: [4, 3],
              pointRadius: 0,
              tension: 0.25,
              fill: false,
            },
            {
              label: 'Upper %',
              data: hi,
              borderColor: PAL.borderBand,
              borderDash: [4, 3],
              pointRadius: 0,
              tension: 0.25,
              fill: '-1',
              backgroundColor: PAL.band,
            },
            {
              label: 'Predicted %',
              data: mid,
              borderColor: PAL.coral,
              backgroundColor: 'transparent',
              borderWidth: 2.5,
              tension: 0.25,
              pointRadius: 3,
              fill: false,
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
              text: `Hospital-wide forecast — ${labels.length} days (rate % + model band)`,
            },
            legend: { position: 'top' },
          },
          scales: {
            x: {
              ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
              grid: { color: PAL.grid },
            },
            y: {
              min: 0,
              max: 100,
              title: { display: true, text: 'Occupancy %' },
              grid: { color: PAL.grid },
            },
          },
        },
      });
      this.charts.push(c1);
    }

    const el2 = this.barCanvas?.nativeElement;
    if (el2) {
      const c2 = new Chart(el2, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: 'Predicted occupied beds',
              data: beds,
              backgroundColor: labels.map((_, i) =>
                i === labels.length - 1 ? 'rgba(253, 126, 20, 0.85)' : 'rgba(102, 126, 234, 0.55)',
              ),
              borderRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            title: {
              display: true,
              text: `Predicted census (beds) · capacity ${tb}`,
            },
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = ctx.parsed.y;
                  const pct = rows[ctx.dataIndex]?.predicted_occupancy_rate;
                  const p = pct != null ? `${(pct * 100).toFixed(1)}%` : '';
                  return `${v} beds (${p})`;
                },
              },
            },
          },
          scales: {
            x: {
              ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 14 },
              grid: { display: false },
            },
            y: {
              beginAtZero: true,
              title: { display: true, text: 'Beds' },
              suggestedMax: tb,
              grid: { color: PAL.grid },
            },
          },
        },
      });
      this.charts.push(c2);
    }

    if (isDevMode() && !el1 && !el2) {
      console.warn('[dashboard-forecast-mini] canvases not ready');
    }
  }
}
