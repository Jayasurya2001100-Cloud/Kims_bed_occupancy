import { Injectable, inject, PLATFORM_ID } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { isPlatformBrowser } from '@angular/common';
import { Observable, of } from 'rxjs';
import { map } from 'rxjs/operators';
import {
  CopilotChatRequest,
  CopilotChatResponse,
  DashboardMetrics,
  DEFAULT_FORECAST_DAYS,
  ForecastRequest,
  ForecastResponse,
  GenericForecastResponse,
  OccupancyData,
} from '../models/dashboard.models';
import { ChartPack, DepartmentForecastsPack } from '../models/chart-pack.models';
import {
  PayerChannel,
  BusinessRule,
  BedType,
  PatientRegistration,
  BedRecommendationResponse,
  AdmissionResponse,
  PayerForecast,
  OccupancyAlert,
  BedStatus,
  ModelMetadata,
} from '../models/registration.models';

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly platformId = inject(PLATFORM_ID);

  /** Browser: same-origin `/api` (dev proxy). Server SSR: call backend directly. */
  private get apiRoot(): string {
    if (isPlatformBrowser(this.platformId)) {
      return `${window.location.origin}/api`;
    }
    return 'http://127.0.0.1:8000/api';
  }

  private departmentForecastsCache = new Map<string, DepartmentForecastsPack>();

  private getHeaders(): HttpHeaders {
    return new HttpHeaders({
      'Content-Type': 'application/json',
    });
  }

  private departmentForecastsCacheKey(
    days: number,
    modelPreference: string | null,
    asOfDate: string | null,
  ): string {
    return `${days}:${modelPreference ?? 'default'}:${asOfDate ?? 'latest'}`;
  }

  getDashboardAvailableDates(limit: number = 30): Observable<{ dates: string[] }> {
    return this.http.get<{ dates: string[] }>(`${this.apiRoot}/dashboard/available-dates?limit=${limit}`, {
      headers: this.getHeaders(),
    });
  }

  getDashboardMetrics(asOfDate: string | null = null): Observable<DashboardMetrics> {
    let params = new HttpParams();
    if (asOfDate) {
      params = params.set('as_of_date', asOfDate);
    }
    return this.http.get<DashboardMetrics>(`${this.apiRoot}/dashboard/metrics`, {
      headers: this.getHeaders(),
      params,
    });
  }

  generateForecast(request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS }): Observable<ForecastResponse> {
    return this.http.post<ForecastResponse>(`${this.apiRoot}/forecast`, request, {
      headers: this.getHeaders(),
    });
  }

  getHistoricalRollingForecast(
    days: number = DEFAULT_FORECAST_DAYS,
    blockDays: number = 21,
    trainDays: number = 90,
    modelPreference: string | null = null,
    asOfDate: string | null = null,
  ): Observable<ForecastResponse> {
    let params = new HttpParams().set('days', String(days)).set('block_days', String(blockDays)).set('train_days', String(trainDays));
    if (modelPreference) {
      params = params.set('model_preference', modelPreference);
    }
    if (asOfDate) {
      params = params.set('as_of_date', asOfDate);
    }
    return this.http.get<ForecastResponse>(`${this.apiRoot}/analytics/historical-rolling-forecast`, {
      headers: this.getHeaders(),
      params,
    });
  }

  getHistoricalData(days: number = 30, asOfDate: string | null = null): Observable<OccupancyData[]> {
    let params = new HttpParams().set('days', String(days));
    if (asOfDate) {
      params = params.set('as_of_date', asOfDate);
    }
    return this.http.get<OccupancyData[]>(`${this.apiRoot}/historical-data`, {
      headers: this.getHeaders(),
      params,
    });
  }

  getChartPack(days: number = DEFAULT_FORECAST_DAYS, asOfDate: string | null = null): Observable<ChartPack> {
    let params = new HttpParams().set('days', String(days));
    if (asOfDate) {
      params = params.set('as_of_date', asOfDate);
    }
    return this.http.get<ChartPack>(`${this.apiRoot}/analytics/chart-pack`, {
      headers: this.getHeaders(),
      params,
    });
  }

  /** Prophet / Auto-ARIMA / XGBoost (or naive) — one series per department. */
  getDepartmentForecasts(
    days: number = DEFAULT_FORECAST_DAYS,
    modelPreference: string | null = null,
    asOfDate: string | null = null,
  ): Observable<DepartmentForecastsPack> {
    const cacheKey = this.departmentForecastsCacheKey(days, modelPreference, asOfDate);
    const cached = this.departmentForecastsCache.get(cacheKey);
    if (cached) {
      return of(cached);
    }

    let params = new HttpParams().set('days', String(days));
    if (modelPreference) {
      params = params.set('model_preference', modelPreference);
    }
    if (asOfDate) {
      params = params.set('as_of_date', asOfDate);
    }
    return this.http.get<DepartmentForecastsPack>(`${this.apiRoot}/analytics/department-forecasts`, {
      headers: this.getHeaders(),
      params,
    }).pipe(
      map((deptFc) => {
        this.departmentForecastsCache.set(cacheKey, deptFc);
        return deptFc;
      }),
    );
  }

  getPatientCountForecast(
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/patient-count/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getLabourStaffingForecast(
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/labour-staffing/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getHistoricalStaffingForecast(
    days: number = 90,
    blockDays: number = 21,
    trainDays: number = 90,
    modelPreference: string | null = null,
    asOfDate: string | null = null,
  ): Observable<GenericForecastResponse> {
    let params = new HttpParams()
      .set('days', String(days))
      .set('block_days', String(blockDays))
      .set('train_days', String(trainDays));
    if (modelPreference) params = params.set('model_preference', modelPreference);
    if (asOfDate) params = params.set('as_of_date', asOfDate);
    return this.http.get<GenericForecastResponse>(
      `${this.apiRoot}/analytics/historical-staffing-forecast`,
      { headers: this.getHeaders(), params },
    );
  }

  getExpandingWindowStaffingForecast(
    modelPreference: string | null = null,
    asOfDate: string | null = null,
  ): Observable<GenericForecastResponse> {
    let params = new HttpParams();
    if (modelPreference) params = params.set('model_preference', modelPreference);
    if (asOfDate) params = params.set('as_of_date', asOfDate);
    return this.http.get<GenericForecastResponse>(
      `${this.apiRoot}/analytics/expanding-window-staffing-forecast`,
      { headers: this.getHeaders(), params },
    );
  }

  getDepartments(): Observable<string[]> {
    return this.http
      .get<{ departments: string[] }>(`${this.apiRoot}/departments`, {
        headers: this.getHeaders(),
      })
      .pipe(map((response) => response.departments));
  }

  getDiseaseList(): Observable<{ diseases: string[] }> {
    return this.http.get<{ diseases: string[] }>(`${this.apiRoot}/disease/list`, {
      headers: this.getHeaders(),
    });
  }

  getDiseaseCategories(): Observable<{ categories: string[] }> {
    return this.http.get<{ categories: string[] }>(`${this.apiRoot}/disease/categories`, {
      headers: this.getHeaders(),
    });
  }

  getTopDiseases(): Observable<{ top_diseases: { [key: string]: number } }> {
    return this.http.get<{ top_diseases: { [key: string]: number } }>(
      `${this.apiRoot}/disease/top-diseases`,
      { headers: this.getHeaders() },
    );
  }

  getMonthlyPatterns(): Observable<{ monthly_patterns: { [key: string]: any } }> {
    return this.http.get<{ monthly_patterns: { [key: string]: any } }>(
      `${this.apiRoot}/disease/monthly-patterns`,
      { headers: this.getHeaders() },
    );
  }

  getCurrentMonthAnalysis(): Observable<any> {
    return this.http.get<any>(`${this.apiRoot}/disease/current-month-analysis`, {
      headers: this.getHeaders(),
    });
  }

  getDiseaseInsights(disease: string): Observable<any> {
    return this.http.get<any>(
      `${this.apiRoot}/disease/insights/${encodeURIComponent(disease)}`,
      { headers: this.getHeaders() },
    );
  }

  getDiseaseAdmissionsForecast(
    disease: string,
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/disease/${encodeURIComponent(disease)}/admissions/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getDiseaseDischargesForecast(
    disease: string,
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/disease/${encodeURIComponent(disease)}/discharges/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getDiseaseLosForecast(
    disease: string,
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/disease/${encodeURIComponent(disease)}/los/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getCategoryAdmissionsForecast(
    category: string,
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/disease-category/${encodeURIComponent(category)}/admissions/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getCategoryDischargesForecast(
    category: string,
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/disease-category/${encodeURIComponent(category)}/discharges/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getCategoryLosForecast(
    category: string,
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(
      `${this.apiRoot}/disease-category/${encodeURIComponent(category)}/los/forecast`,
      request,
      { headers: this.getHeaders() },
    );
  }

  getEdWaitTimeForecast(
    request: ForecastRequest = { days: DEFAULT_FORECAST_DAYS },
  ): Observable<GenericForecastResponse> {
    return this.http.post<GenericForecastResponse>(`${this.apiRoot}/ed/wait-time/forecast`, request, {
      headers: this.getHeaders(),
    });
  }

  chatWithCopilot(request: CopilotChatRequest): Observable<CopilotChatResponse> {
    return this.http.post<CopilotChatResponse>(`${this.apiRoot}/copilot/chat`, request, {
      headers: this.getHeaders(),
    });
  }

  // Registration & Bed Allocation APIs

  getPayerChannels(): Observable<{ payer_channels: PayerChannel[] }> {
    return this.http.get<{ payer_channels: PayerChannel[] }>(
      `${this.apiRoot}/config/payer-channels`,
      { headers: this.getHeaders() }
    );
  }

  getBusinessRules(): Observable<{ business_rules: Record<string, BusinessRule> }> {
    return this.http.get<{ business_rules: Record<string, BusinessRule> }>(
      `${this.apiRoot}/config/business-rules`,
      { headers: this.getHeaders() }
    );
  }

  getOccupancyThresholds(): Observable<{ thresholds: Record<string, number> }> {
    return this.http.get<{ thresholds: Record<string, number> }>(
      `${this.apiRoot}/config/occupancy-thresholds`,
      { headers: this.getHeaders() }
    );
  }

  getBedTypes(): Observable<{ bed_types: BedType[] }> {
    return this.http.get<{ bed_types: BedType[] }>(
      `${this.apiRoot}/config/bed-types`,
      { headers: this.getHeaders() }
    );
  }

  getSpecialties(): Observable<{ specialties: string[] }> {
    return this.http.get<{ specialties: string[] }>(
      `${this.apiRoot}/config/specialties`,
      { headers: this.getHeaders() }
    );
  }

  getModelMetadata(): Observable<ModelMetadata> {
    return this.http.get<ModelMetadata>(
      `${this.apiRoot}/model-metadata`,
      { headers: this.getHeaders() }
    );
  }

  recommendBeds(patientData: any, includeForecast: boolean = true): Observable<BedRecommendationResponse> {
    return this.http.post<BedRecommendationResponse>(
      `${this.apiRoot}/bed/recommend`,
      { patient_data: patientData, include_forecast: includeForecast },
      { headers: this.getHeaders() }
    );
  }

  registerAdmission(patient: PatientRegistration, bedId?: string): Observable<AdmissionResponse> {
    return this.http.post<AdmissionResponse>(
      `${this.apiRoot}/admissions/register`,
      { patient, bed_id: bedId },
      { headers: this.getHeaders() }
    );
  }

  getPayerForecast(days: number = 30, payerChannel?: string): Observable<{ forecast_days: number; payer_forecasts: PayerForecast[]; timestamp: string }> {
    let params = new HttpParams().set('days', String(days));
    if (payerChannel) {
      params = params.set('payer_channel', payerChannel);
    }
    return this.http.get<{ forecast_days: number; payer_forecasts: PayerForecast[]; timestamp: string }>(
      `${this.apiRoot}/payer/forecast`,
      { headers: this.getHeaders(), params }
    );
  }

  getAlerts(severity?: string): Observable<{ alerts: OccupancyAlert[]; count: number; timestamp: string }> {
    let params = new HttpParams();
    if (severity) {
      params = params.set('severity', severity);
    }
    return this.http.get<{ alerts: OccupancyAlert[]; count: number; timestamp: string }>(
      `${this.apiRoot}/alerts`,
      { headers: this.getHeaders(), params }
    );
  }

  getBedStatus(department?: string): Observable<{ departments: BedStatus[]; timestamp: string }> {
    let params = new HttpParams();
    if (department) {
      params = params.set('department', department);
    }
    return this.http.get<{ departments: BedStatus[]; timestamp: string }>(
      `${this.apiRoot}/bed-status`,
      { headers: this.getHeaders(), params }
    );
  }
}
