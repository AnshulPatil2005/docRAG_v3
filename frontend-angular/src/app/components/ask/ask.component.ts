import { Component, inject, signal, computed, input, effect, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { ChatResponse, GraphQueryResponse } from '../../models/api.models';

type AskMode = 'smart' | 'quick';

/**
 * Single question box that can hit either backend query path:
 * - "smart" -> /graph-query (Neo4j + vector hybrid retrieval, understands
 *   citations/relationships, shows its reasoning). Default, and the better
 *   result whenever it's available.
 * - "quick" -> /chat (vector search only). Simpler and still useful when
 *   the graph store is unavailable, or to scope a search to one document.
 *
 * Replaces the old separate "Chat" and "Ask a Graph Question" cards, which
 * gave no indication of why there were two near-identical query boxes.
 */
@Component({
  selector: 'app-ask',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="card">
      <h2>Ask a question</h2>
      <p class="hint">
        Smart Q&amp;A understands citations and relationships between papers and is
        recommended. Quick Search is a simpler fallback -- useful if Smart Q&amp;A is
        unavailable, or to search inside just one document.
      </p>

      <div class="mode-toggle">
        <button type="button" [class.active]="mode() === 'smart'" (click)="mode.set('smart')">
          Smart Q&amp;A
        </button>
        <button type="button" [class.active]="mode() === 'quick'" (click)="mode.set('quick')">
          Quick Search
        </button>
      </div>

      <div class="form-group">
        <textarea
          [(ngModel)]="query"
          rows="3"
          placeholder="e.g. Which methods improved upon the Transformer?"
          class="textarea"
        ></textarea>
      </div>

      @if (mode() === 'quick') {
        <div class="form-group">
          <label class="select-label" for="searchIn">Search in</label>
          <select id="searchIn" [(ngModel)]="docId" class="select">
            <option value="">All documents</option>
            @for (doc of documentOptions(); track doc.doc_id) {
              <option [value]="doc.doc_id">{{ doc.filename }}</option>
            }
          </select>
        </div>
      }

      <button
        class="btn btn-primary"
        (click)="ask()"
        [disabled]="!query || isLoading()"
      >
        {{ isLoading() ? 'Thinking...' : 'Ask' }}
      </button>

      @if (smartResult(); as result) {
        <div class="result success">
          <div class="answer-section">
            <div class="section-header">
              <h3>Answer</h3>
              <span class="query-type-badge">{{ result.retrieval_trace.query_type }}</span>
            </div>
            <div class="answer-text">{{ result.answer }}</div>
          </div>

          @if (result.retrieval_trace.confidence_notes.length > 0) {
            <div class="notes-section">
              @for (note of result.retrieval_trace.confidence_notes; track $index) {
                <div class="confidence-note">&#9888; {{ note }}</div>
              }
            </div>
          }

          @if (result.sources.length > 0) {
            <div class="subsection">
              <h3>Source Papers</h3>
              <p class="subsection-hint">Click one to see its graph below.</p>
              @for (source of result.sources; track source.paper_id) {
                <div class="chip" (click)="viewGraph(source.paper_id)">
                  {{ source.title || source.paper_id }}
                </div>
              }
            </div>
          }

          @if (result.retrieval_trace.graph_facts.length > 0) {
            <div class="subsection">
              <h3>Graph Facts Used</h3>
              @for (fact of result.retrieval_trace.graph_facts; track $index) {
                <div class="fact">
                  <div class="fact-triple">
                    <span class="entity">{{ fact.subject.name }}</span>
                    <span class="relation">{{ fact.relation }}</span>
                    <span class="entity">{{ fact.object.name }}</span>
                  </div>
                  @if (fact.evidence) {
                    <div class="fact-evidence">"{{ fact.evidence }}"</div>
                  }
                </div>
              }
            </div>
          }

          @if (result.retrieval_trace.citation_paths.length > 0) {
            <div class="subsection">
              <h3>Citation Path</h3>
              @for (cp of result.retrieval_trace.citation_paths; track $index) {
                <div class="citation-path">
                  {{ cp.path.join(' → ') }}
                  <span class="path-meta">(depth {{ cp.depth }}, {{ cp.direction }})</span>
                </div>
              }
            </div>
          }
        </div>
      }

      @if (quickResult(); as result) {
        <div class="result success">
          <div class="answer-section">
            <h3>Answer</h3>
            <div class="answer-text">{{ result.answer }}</div>
          </div>

          @if (result.citations && result.citations.length > 0) {
            <div class="subsection">
              <h3>Citations</h3>
              @for (citation of result.citations; track $index) {
                <div class="citation">
                  <div class="citation-header">
                    <span class="source-label">Source {{ $index + 1 }}:</span>
                    <span class="source-name">{{ citation.filename || 'Unknown' }}</span>
                    @if (citation.page) {
                      <span class="page-number">(Page {{ citation.page }})</span>
                    }
                  </div>
                  <div class="citation-text">"{{ citation.text_snippet }}"</div>
                </div>
              }
            </div>
          }
        </div>
      }

      @if (error()) {
        <div class="result error">
          <p>{{ error() }}</p>
        </div>
      }
    </div>
  `,
  styles: [`
    .card {
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      padding: 1.5rem;
    }

    h2 {
      margin: 0 0 0.5rem;
      font-size: 1.125rem;
      font-weight: 600;
      color: #1a1a1a;
    }

    h3 {
      margin: 0 0 0.75rem;
      font-size: 0.9375rem;
      font-weight: 600;
      color: #333;
    }

    .hint {
      margin: 0 0 1rem;
      color: #666;
      font-size: 0.8125rem;
    }

    .mode-toggle {
      display: inline-flex;
      border: 1px solid #ddd;
      border-radius: 6px;
      overflow: hidden;
      margin-bottom: 1rem;
    }

    .mode-toggle button {
      padding: 0.5rem 1rem;
      border: none;
      background: #f5f5f5;
      color: #444;
      font-size: 0.875rem;
      font-weight: 500;
      cursor: pointer;
      transition: background-color 0.2s, color 0.2s;
    }

    .mode-toggle button + button {
      border-left: 1px solid #ddd;
    }

    .mode-toggle button.active {
      background: #1a1a1a;
      color: #fff;
    }

    .mode-toggle button:not(.active):hover {
      background: #e8e8e8;
    }

    .form-group {
      margin-bottom: 1rem;
    }

    .select-label {
      display: block;
      font-size: 0.8125rem;
      font-weight: 500;
      color: #444;
      margin-bottom: 0.375rem;
    }

    .textarea, .select {
      width: 100%;
      padding: 0.625rem 0.875rem;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 0.9375rem;
      font-family: inherit;
      background: #fff;
      transition: border-color 0.2s;
      box-sizing: border-box;
    }

    .textarea {
      resize: vertical;
      min-height: 80px;
    }

    .textarea:focus, .select:focus {
      outline: none;
      border-color: #333;
    }

    .btn {
      padding: 0.625rem 1.25rem;
      border: none;
      border-radius: 4px;
      font-size: 0.9375rem;
      font-weight: 500;
      cursor: pointer;
      transition: background-color 0.2s;
    }

    .btn:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }

    .btn-primary {
      background: #1a1a1a;
      color: #fff;
    }

    .btn-primary:hover:not(:disabled) {
      background: #333;
    }

    .result {
      margin-top: 1rem;
      padding: 1rem;
      border-radius: 4px;
      font-size: 0.9375rem;
    }

    .result.success {
      background: #f8f9fa;
      border: 1px solid #e0e0e0;
    }

    .result.error {
      background: #f8d7da;
      border: 1px solid #f5c6cb;
      color: #721c24;
    }

    .answer-section {
      margin-bottom: 1rem;
    }

    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
    }

    .query-type-badge {
      background: #e7f3ff;
      color: #004085;
      border-radius: 12px;
      padding: 0.15rem 0.625rem;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.02em;
    }

    .answer-text {
      line-height: 1.6;
      color: #1a1a1a;
      white-space: pre-wrap;
    }

    .notes-section {
      margin-bottom: 1rem;
    }

    .confidence-note {
      background: #fff3cd;
      border: 1px solid #ffe69c;
      border-radius: 4px;
      padding: 0.5rem 0.75rem;
      font-size: 0.8125rem;
      color: #664d03;
      margin-bottom: 0.5rem;
    }

    .subsection {
      border-top: 1px solid #e0e0e0;
      padding-top: 1rem;
      margin-top: 1rem;
    }

    .subsection-hint {
      margin: 0 0 0.5rem;
      color: #888;
      font-size: 0.75rem;
    }

    .chip {
      display: inline-block;
      background: #fff;
      border: 1px solid #ccc;
      border-radius: 16px;
      padding: 0.25rem 0.75rem;
      font-size: 0.8125rem;
      margin: 0 0.5rem 0.5rem 0;
      cursor: pointer;
    }

    .chip:hover {
      border-color: #1a1a1a;
      background: #f5f5f5;
    }

    .fact {
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      padding: 0.75rem;
      margin-bottom: 0.5rem;
    }

    .fact:last-child {
      margin-bottom: 0;
    }

    .fact-triple {
      font-size: 0.875rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      flex-wrap: wrap;
    }

    .entity {
      font-weight: 600;
      color: #1a1a1a;
    }

    .relation {
      color: #666;
      font-family: monospace;
      font-size: 0.75rem;
      background: #f0f0f0;
      border-radius: 3px;
      padding: 0.1rem 0.4rem;
    }

    .fact-evidence {
      margin-top: 0.375rem;
      font-style: italic;
      color: #555;
      font-size: 0.8125rem;
      padding-left: 0.75rem;
      border-left: 3px solid #ddd;
    }

    .citation-path {
      font-size: 0.875rem;
      color: #1a1a1a;
      margin-bottom: 0.375rem;
      font-family: monospace;
    }

    .path-meta {
      color: #888;
      font-family: inherit;
      font-size: 0.75rem;
      margin-left: 0.375rem;
    }

    .citation {
      background: #fff;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      padding: 0.875rem;
      margin-bottom: 0.75rem;
    }

    .citation:last-child {
      margin-bottom: 0;
    }

    .citation-header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 0.5rem;
    }

    .source-label {
      font-weight: 600;
      color: #444;
    }

    .source-name {
      color: #1a1a1a;
    }

    .page-number {
      color: #666;
      font-size: 0.875rem;
    }

    .citation-text {
      font-style: italic;
      color: #555;
      line-height: 1.5;
      padding-left: 0.75rem;
      border-left: 3px solid #ddd;
    }
  `]
})
export class AskComponent {
  private apiService = inject(ApiService);

  initialDocId = input<string>('');
  viewPaperGraph = output<string>();

  mode = signal<AskMode>('smart');
  query = '';
  docId = '';
  isLoading = signal(false);
  smartResult = signal<GraphQueryResponse | null>(null);
  quickResult = signal<ChatResponse | null>(null);
  error = signal<string | null>(null);

  documentOptions = computed(() => {
    const seen = new Set<string>();
    const options: { doc_id: string; filename: string }[] = [];
    for (const task of this.apiService.recentTasks()) {
      if (task.doc_id && !seen.has(task.doc_id)) {
        seen.add(task.doc_id);
        options.push({ doc_id: task.doc_id, filename: task.filename || task.doc_id });
      }
    }
    return options;
  });

  constructor() {
    effect(() => {
      const id = this.initialDocId();
      if (id) {
        this.setDocId(id);
      }
    });
  }

  setDocId(id: string): void {
    this.docId = id;
    this.mode.set('quick');
  }

  ask(): void {
    if (!this.query) return;

    this.isLoading.set(true);
    this.smartResult.set(null);
    this.quickResult.set(null);
    this.error.set(null);

    if (this.mode() === 'smart') {
      this.apiService.graphQuery({ query: this.query, top_k: 10 }).subscribe({
        next: (response) => {
          this.isLoading.set(false);
          this.smartResult.set(response);
        },
        error: (err) => {
          this.isLoading.set(false);
          this.error.set(`Error: ${err.message}`);
        }
      });
    } else {
      const request = {
        query: this.query,
        ...(this.docId && { doc_id: this.docId })
      };

      this.apiService.chat(request).subscribe({
        next: (response) => {
          this.isLoading.set(false);
          this.quickResult.set(response);
        },
        error: (err) => {
          this.isLoading.set(false);
          this.error.set(`Error: ${err.message}`);
        }
      });
    }
  }

  viewGraph(paperId: string): void {
    this.viewPaperGraph.emit(paperId);
  }
}
