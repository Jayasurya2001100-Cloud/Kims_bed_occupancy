import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { RegistrationComponent } from './components/registration/registration.component';
import { PayerIntelligenceComponent } from './components/payer-intelligence/payer-intelligence.component';
import { OccupancyAlertsComponent } from './components/occupancy-alerts/occupancy-alerts.component';
import { BedAllocationMonitorComponent } from './components/bed-allocation-monitor/bed-allocation-monitor.component';

export const routes: Routes = [
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: DashboardComponent },
  { path: 'registration', component: RegistrationComponent },
  { path: 'payer-intelligence', component: PayerIntelligenceComponent },
  { path: 'occupancy-alerts', component: OccupancyAlertsComponent },
  { path: 'bed-allocation-monitor', component: BedAllocationMonitorComponent },
];
