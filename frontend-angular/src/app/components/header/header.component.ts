import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <header class="header">
      <div class="header-content">
        <h1>DocRAG</h1>
        <p class="subtitle">Document Retrieval-Augmented Generation</p>
      </div>
      <div class="header-controls">
        <div class="api-url-input">
          <label for="apiUrl">API URL:</label>
          <input
            type="text"
            id="apiUrl"
            [ngModel]="apiService.apiUrl()"
            (ngModelChange)="onApiUrlChange($event)"
            placeholder="https://docrag-2gvg.onrender.com"
          />
        </div>
        <div class="api-url-input llm-key-input" [class.required]="!apiService.llmStatus().server_key_configured">
          <label for="llmApiKey">
            OpenRouter Key{{ apiService.llmStatus().server_key_configured ? ' (optional):' : ' (required):' }}
          </label>
          <input
            type="password"
            id="llmApiKey"
            [ngModel]="apiService.llmApiKey()"
            (ngModelChange)="onLlmApiKeyChange($event)"
            placeholder="sk-or-v1-..."
          />
        </div>
        <div class="status-indicator" [class.online]="apiService.healthStatus().online">
          <span class="dot"></span>
          <span class="text">{{ apiService.healthStatus().online ? 'Online' : 'Offline' }}</span>
        </div>
      </div>
    </header>
    @if (!apiService.llmStatus().server_key_configured && !apiService.llmApiKey()) {
      <div class="llm-key-banner">
        No server-side OpenRouter API key is configured. Enter your own key above to ask questions
        (get one free at <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">openrouter.ai/keys</a>).
      </div>
    }
  `,
  styles: [`
    .header {
      background: #fff;
      border-bottom: 1px solid #e0e0e0;
      padding: 1.5rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }

    .header-content h1 {
      margin: 0;
      font-size: 1.75rem;
      font-weight: 600;
      color: #1a1a1a;
    }

    .subtitle {
      margin: 0.25rem 0 0;
      font-size: 0.875rem;
      color: #666;
    }

    .header-controls {
      display: flex;
      align-items: center;
      gap: 1.5rem;
      flex-wrap: wrap;
    }

    .api-url-input {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .api-url-input label {
      font-size: 0.875rem;
      color: #444;
      font-weight: 500;
    }

    .api-url-input input {
      padding: 0.5rem 0.75rem;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 0.875rem;
      width: 280px;
      transition: border-color 0.2s;
    }

    .api-url-input input:focus {
      outline: none;
      border-color: #333;
    }

    .llm-key-input.required label {
      color: #b02a37;
    }

    .llm-key-input.required input {
      border-color: #dc3545;
    }

    .llm-key-banner {
      width: 100%;
      padding: 0.5rem 2rem 1rem;
      font-size: 0.8125rem;
      color: #b02a37;
      background: #fff;
    }

    .llm-key-banner a {
      color: inherit;
      text-decoration: underline;
    }

    .status-indicator {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 1rem;
      background: #f5f5f5;
      border-radius: 20px;
      font-size: 0.875rem;
    }

    .status-indicator .dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #dc3545;
    }

    .status-indicator.online .dot {
      background: #28a745;
    }

    .status-indicator .text {
      color: #444;
      font-weight: 500;
    }

    @media (max-width: 768px) {
      .header {
        padding: 1rem;
      }

      .api-url-input input {
        width: 200px;
      }
    }
  `]
})
export class HeaderComponent {
  apiService = inject(ApiService);

  onApiUrlChange(url: string): void {
    this.apiService.setApiUrl(url);
  }

  onLlmApiKeyChange(key: string): void {
    this.apiService.setLlmApiKey(key);
  }
}
