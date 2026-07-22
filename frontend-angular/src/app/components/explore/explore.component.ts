import { Component, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CitationExplorerComponent } from '../citation-explorer/citation-explorer.component';
import { PaperGraphComponent } from '../paper-graph/paper-graph.component';

type ExploreTab = 'all' | 'one';

/**
 * Groups the two graph views (all-papers citation graph, one paper's
 * internal graph) under a single card with a tab switcher, instead of two
 * separate top-level cards -- picking a paper in "All papers" jumps
 * straight to its graph in "One paper".
 */
@Component({
  selector: 'app-explore',
  standalone: true,
  imports: [CommonModule, CitationExplorerComponent, PaperGraphComponent],
  template: `
    <div class="card">
      <h2>Explore the graph</h2>

      <div class="mode-toggle">
        <button
          type="button"
          [class.active]="tab === 'all'"
          (click)="tab = 'all'"
        >All papers</button>
        <button
          type="button"
          [class.active]="tab === 'one'"
          (click)="tab = 'one'"
        >One paper</button>
      </div>

      <div [hidden]="tab !== 'all'">
        <app-citation-explorer (viewPaperGraph)="onViewOnePaper($event)" />
      </div>
      <div [hidden]="tab !== 'one'">
        <app-paper-graph #paperGraph />
      </div>
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
      margin: 0 0 1rem;
      font-size: 1.125rem;
      font-weight: 600;
      color: #1a1a1a;
    }

    .mode-toggle {
      display: inline-flex;
      border: 1px solid #ddd;
      border-radius: 6px;
      overflow: hidden;
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
  `]
})
export class ExploreComponent {
  @ViewChild('paperGraph') paperGraphComponent!: PaperGraphComponent;

  tab: ExploreTab = 'all';

  onViewOnePaper(paperId: string): void {
    this.tab = 'one';
    this.paperGraphComponent.setPaperId(paperId);
  }

  setPaperId(paperId: string): void {
    this.tab = 'one';
    this.paperGraphComponent.setPaperId(paperId);
  }
}
