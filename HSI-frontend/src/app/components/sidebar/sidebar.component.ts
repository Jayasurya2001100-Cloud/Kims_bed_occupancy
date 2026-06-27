import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <nav class="sidebar">
      <div class="logo">KIMS Hospital</div>
      <ul class="nav-links">
        <li><a routerLink="/dashboard" routerLinkActive="active">📊 Dashboard</a></li>
        <li><a routerLink="/registration" routerLinkActive="active">➕ Registration</a></li>
        <li><a routerLink="/bed-allocation-monitor" routerLinkActive="active">🛏️ Bed Monitor</a></li>
        <li><a routerLink="/payer-intelligence" routerLinkActive="active">💳 Payer Intelligence</a></li>
        <li><a routerLink="/occupancy-alerts" routerLinkActive="active">⚠️ Alerts</a></li>
      </ul>
    </nav>
  `,
  styles: [`
    .sidebar {
      width: 240px;
      height: 100vh;
      background: var(--blue-dk);
      color: white;
      position: fixed;
      left: 0;
      top: 0;
      display: flex;
      flex-direction: column;
      padding: 1.5rem 0;
    }
    .logo {
      font-size: 1.25rem;
      font-weight: 700;
      padding: 0 1.5rem 2rem;
      border-bottom: 1px solid rgba(255,255,255,0.1);
    }
    .nav-links {
      list-style: none;
      padding: 1rem 0;
    }
    .nav-links a {
      display: block;
      padding: 0.75rem 1.5rem;
      color: rgba(255,255,255,0.8);
      text-decoration: none;
      transition: all 0.2s;
    }
    .nav-links a:hover {
      background: rgba(255,255,255,0.1);
      color: white;
    }
    .nav-links a.active {
      background: var(--blue);
      color: white;
      border-left: 4px solid white;
    }
  `]
})
export class SidebarComponent {}
