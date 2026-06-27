import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, ChangeDetectorRef, Component, Input, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

type ChatRole = 'assistant' | 'user';

interface CopilotMessage {
  role: ChatRole;
  content: string;
}

@Component({
  selector: 'app-dashboard-copilot',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './dashboard-copilot.component.html',
  styleUrl: './dashboard-copilot.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardCopilotComponent {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  @Input() asOfDate: string | null = null;
  @Input() selectedModel: string | null = null;
  @Input() forecastDays = 30;

  isOpen = false;
  loading = false;
  draft = '';
  messages: CopilotMessage[] = [
    {
      role: 'assistant',
      content:
        'I am Dashboard Copilot. Ask about occupancy outlook, department pressure, Emergency Department wait time, alerts, or what to expect from the current dashboard.',
    },
  ];

  readonly suggestedPrompts = [
    'What should operations expect over the next 30 days?',
    'Which departments are highest risk by day 30?',
    'Summarize the dashboard for an operations head.',
    'How is Emergency Department pressure affecting occupancy?',
  ];

  toggleOpen(): void {
    this.isOpen = !this.isOpen;
    this.cdr.markForCheck();
  }

  usePrompt(prompt: string): void {
    this.draft = prompt;
    this.sendMessage();
  }

  sendMessage(): void {
    const query = this.draft.trim();
    if (!query || this.loading) return;

    this.messages = [...this.messages, { role: 'user', content: query }];
    this.draft = '';
    this.loading = true;

    this.api
      .chatWithCopilot({
        query,
        as_of_date: this.asOfDate,
        model_preference: this.selectedModel,
        forecast_days: this.forecastDays,
      })
      .subscribe({
        next: (response) => {
          const suffix = response.as_of_date
            ? `\n\nContext date: ${response.as_of_date} · Horizon: ${response.forecast_days} days`
            : '';
          this.messages = [
            ...this.messages,
            { role: 'assistant', content: `${response.answer}${suffix}`.trim() },
          ];
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.messages = [
            ...this.messages,
            {
              role: 'assistant',
              content:
                'I could not answer that from the dashboard right now. Please retry after the data finishes loading.',
            },
          ];
          this.loading = false;
          this.cdr.markForCheck();
        },
      });
  }
}
