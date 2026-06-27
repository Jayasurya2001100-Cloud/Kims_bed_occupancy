import { Component, Input, OnInit, OnChanges, SimpleChanges, PLATFORM_ID, inject } from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

@Component({
  selector: 'app-bed-requirements-visual',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="bed-requirements-container">
      <div class="requirements-header">
        <h3>📊 Bed Requirements Forecast</h3>
        <p class="requirements-subtitle">Upcoming days bed demand prediction</p>
      </div>
      
      <!-- Key Insight Banner -->
      <div class="insight-banner" [class.warning]="peakOccupancy > 90" [class.critical]="peakOccupancy > 95">
        <div class="insight-icon">{{ peakOccupancy > 95 ? '🚨' : peakOccupancy > 90 ? '⚠️' : 'ℹ️' }}</div>
        <div class="insight-content">
          <strong>Peak demand expected: {{ peakDate }}</strong>
          <p>{{ peakBeds }} beds needed ({{ peakOccupancy }}% occupancy)</p>
          <p class="insight-action" *ngIf="peakOccupancy > 90">Action required: Prepare additional capacity</p>
        </div>
      </div>

      <!-- Main Chart -->
      <div class="chart-wrapper">
        <canvas #chartCanvas id="bedRequirementsChart"></canvas>
      </div>

      <!-- Daily Breakdown -->
      <div class="daily-breakdown">
        <h4>Next 7 Days Breakdown</h4>
        <div class="breakdown-grid">
          <div class="breakdown-day" *ngFor="let day of next7Days; let i = index" 
               [class.high-demand]="day.occupancy > 85"
               [class.critical]="day.occupancy > 90">
            <div class="day-date-main">{{ day.dateFormatted }}</div>
            <div class="day-weekday">{{ day.weekday }}</div>
            <div class="day-beds">{{ day.beds }} / {{ totalBeds }} beds</div>
            <div class="day-occupancy" [style.color]="getOccupancyColor(day.occupancy)">
              {{ day.occupancy }}% occupancy
            </div>
            <div class="day-indicator">
              {{ day.occupancy > 90 ? '🔴' : day.occupancy > 85 ? '🟡' : '🟢' }}
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .bed-requirements-container {
      background: white;
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      margin: 20px 0;
    }

    .requirements-header {
      margin-bottom: 20px;
      border-bottom: 2px solid #007DB0;
      padding-bottom: 12px;
    }

    .requirements-header h3 {
      margin: 0;
      color: #007DB0;
      font-size: 1.5rem;
    }

    .requirements-subtitle {
      margin: 4px 0 0 0;
      color: #6C6E71;
      font-size: 0.9rem;
    }

    .insight-banner {
      display: flex;
      gap: 16px;
      padding: 16px;
      background: #E3F2FD;
      border-left: 4px solid #007DB0;
      border-radius: 8px;
      margin-bottom: 24px;
    }

    .insight-banner.warning {
      background: #FFF3E0;
      border-left-color: #e67e22;
    }

    .insight-banner.critical {
      background: #FFEBEE;
      border-left-color: #FF0000;
    }

    .insight-icon {
      font-size: 2rem;
      line-height: 1;
    }

    .insight-content {
      flex: 1;
    }

    .insight-content strong {
      display: block;
      color: #2c3e50;
      font-size: 1.1rem;
      margin-bottom: 4px;
    }

    .insight-content p {
      margin: 2px 0;
      color: #6C6E71;
    }

    .insight-action {
      margin-top: 8px;
      padding: 6px 12px;
      background: rgba(255,0,0,0.1);
      border-radius: 4px;
      color: #FF0000;
      font-weight: 600;
    }

    .chart-wrapper {
      height: 400px;
      margin: 24px 0;
      position: relative;
    }

    .daily-breakdown {
      margin-top: 32px;
    }

    .daily-breakdown h4 {
      color: #2c3e50;
      margin-bottom: 16px;
      font-size: 1.1rem;
    }

    .breakdown-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
    }

    .breakdown-day {
      background: #f8f9fa;
      border-radius: 8px;
      padding: 12px;
      text-align: center;
      border: 2px solid transparent;
      transition: all 0.3s ease;
    }

    .breakdown-day:hover {
      transform: translateY(-2px);
      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }

    .breakdown-day.high-demand {
      background: #FFF3E0;
      border-color: #e67e22;
    }

    .breakdown-day.critical {
      background: #FFEBEE;
      border-color: #FF0000;
    }

    .day-date-main {
      font-size: 1rem;
      color: #2c3e50;
      font-weight: 700;
      margin: 4px 0;
    }

    .day-weekday {
      font-size: 0.75rem;
      color: #6C6E71;
      font-weight: 600;
      text-transform: uppercase;
      margin-bottom: 8px;
    }

    .day-beds {
      font-size: 1.3rem;
      font-weight: bold;
      color: #007DB0;
      margin: 8px 0;
    }

    .day-occupancy {
      font-size: 1.1rem;
      font-weight: 600;
      margin: 4px 0;
    }

    .day-indicator {
      font-size: 1.5rem;
      margin-top: 4px;
    }
  `]
})
export class BedRequirementsVisualComponent implements OnInit, OnChanges {
  private readonly platformId = inject(PLATFORM_ID);

  @Input() forecastData: any[] = [];
  @Input() currentBeds: number = 0;
  @Input() totalBeds: number = 0;

  chart: Chart | null = null;
  next7Days: any[] = [];
  peakDay: number = 0;
  peakDate: string = '';
  peakBeds: number = 0;
  peakOccupancy: number = 0;

  ngOnInit(): void {
    this.processData();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['forecastData'] || changes['currentBeds'] || changes['totalBeds']) {
      this.processData();
      if (isPlatformBrowser(this.platformId)) {
        requestAnimationFrame(() => this.renderChart());
      }
    }
  }

  processData(): void {
    if (!this.forecastData || this.forecastData.length === 0) {
      return;
    }

    // Process next 7 days with actual dates including year
    this.next7Days = this.forecastData.slice(0, 7).map((point, index) => {
      const beds = Math.round(point.predicted_occupied_beds || 0);
      const occupancy = Math.round((beds / this.totalBeds) * 100);
      const date = new Date(point.date + 'T00:00:00');
      const dateFormatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      const weekday = date.toLocaleDateString('en-US', { weekday: 'short' });
      return {
        date: point.date,
        dateFormatted,
        weekday,
        beds,
        occupancy
      };
    });

    // Find peak day
    let maxBeds = 0;
    let maxDay = 0;
    let maxDate = '';
    this.forecastData.forEach((point, index) => {
      const beds = Math.round(point.predicted_occupied_beds || 0);
      if (beds > maxBeds) {
        maxBeds = beds;
        maxDay = index + 1;
        maxDate = point.date;
      }
    });

    this.peakDay = maxDay;
    const peakDateObj = new Date(maxDate + 'T00:00:00');
    this.peakDate = peakDateObj.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    this.peakBeds = maxBeds;
    this.peakOccupancy = Math.round((maxBeds / this.totalBeds) * 100);
  }

  renderChart(): void {
    const canvas = document.getElementById('bedRequirementsChart') as HTMLCanvasElement;
    if (!canvas) return;

    if (this.chart) {
      this.chart.destroy();
    }

    const labels = this.forecastData.map(p => {
      const d = new Date(p.date + 'T00:00:00');
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' });
    });
    const forecastBeds = this.forecastData.map(p => Math.round(p.predicted_occupied_beds || 0));
    const actualBeds = new Array(this.forecastData.length).fill(this.currentBeds);
    const capacityLine = new Array(this.forecastData.length).fill(this.totalBeds);
    const warningLine = new Array(this.forecastData.length).fill(this.totalBeds * 0.9);

    // Calculate better y-axis range based on data
    const allValues = [...forecastBeds, this.currentBeds];
    const minBeds = Math.min(...allValues);
    const maxBeds = Math.max(...allValues);
    const yMin = Math.max(0, Math.floor(minBeds * 0.9));
    const yMax = Math.min(this.totalBeds, Math.ceil(maxBeds * 1.1));

    this.chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Current Occupancy',
            data: actualBeds,
            borderColor: '#6C6E71',
            backgroundColor: 'rgba(108, 110, 113, 0.1)',
            borderWidth: 2,
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false
          },
          {
            label: 'Forecasted Beds Required',
            data: forecastBeds,
            borderColor: '#007DB0',
            backgroundColor: 'rgba(0, 125, 176, 0.1)',
            borderWidth: 3,
            tension: 0.4,
            fill: true,
            pointRadius: 4,
            pointBackgroundColor: '#007DB0',
            pointBorderColor: '#fff',
            pointBorderWidth: 2
          },
          {
            label: 'Total Capacity',
            data: capacityLine,
            borderColor: '#27ae60',
            borderWidth: 2,
            borderDash: [10, 5],
            pointRadius: 0,
            fill: false
          },
          {
            label: 'Warning Threshold (90%)',
            data: warningLine,
            borderColor: '#e67e22',
            borderWidth: 2,
            borderDash: [3, 3],
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: 'index'
        },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: {
              usePointStyle: true,
              padding: 15,
              font: {
                size: 12
              }
            }
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            padding: 12,
            titleFont: {
              size: 14
            },
            bodyFont: {
              size: 13
            },
            callbacks: {
              label: (context) => {
                const label = context.dataset.label || '';
                const value = context.parsed.y;
                return `${label}: ${value} beds`;
              }
            }
          }
        },
        scales: {
          y: {
            min: yMin,
            max: yMax,
            title: {
              display: true,
              text: 'Number of Beds',
              font: {
                size: 14,
                weight: 'bold'
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.05)'
            },
            ticks: {
              stepSize: Math.ceil((yMax - yMin) / 8)
            }
          },
          x: {
            title: {
              display: true,
              text: 'Forecast Horizon',
              font: {
                size: 14,
                weight: 'bold'
              }
            },
            grid: {
              display: false
            }
          }
        }
      }
    });
  }

  getOccupancyColor(occupancy: number): string {
    if (occupancy >= 95) return '#FF0000';
    if (occupancy >= 90) return '#e67e22';
    if (occupancy >= 80) return '#f39c12';
    return '#27ae60';
  }
}
