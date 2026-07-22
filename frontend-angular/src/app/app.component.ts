import { Component, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HeaderComponent } from './components/header/header.component';
import { UploadComponent } from './components/upload/upload.component';
import { StatusComponent } from './components/status/status.component';
import { RecentTasksComponent } from './components/recent-tasks/recent-tasks.component';
import { AskComponent } from './components/ask/ask.component';
import { ExploreComponent } from './components/explore/explore.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    HeaderComponent,
    UploadComponent,
    StatusComponent,
    RecentTasksComponent,
    AskComponent,
    ExploreComponent
  ],
  template: `
    <app-header />

    <main class="main-content">
      <div class="container">
        <app-upload (taskUploaded)="onTaskUploaded($event)" />
        <app-recent-tasks
          (checkStatus)="onCheckStatus($event)"
          (useInChat)="onUseInChat($event)"
        />
        <app-status #statusComponent />
        <app-ask #askComponent (viewPaperGraph)="onViewPaperGraph($event)" />
        <app-explore #exploreComponent />
      </div>
    </main>

    <footer class="footer">
      <p>DocRAG - Document Retrieval-Augmented Generation</p>
    </footer>
  `,
  styles: [`
    :host {
      display: flex;
      flex-direction: column;
      min-height: 100vh;
    }

    .main-content {
      flex: 1;
      background: #f5f5f5;
      padding: 2rem;
    }

    .container {
      max-width: 860px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }

    .footer {
      background: #fff;
      border-top: 1px solid #e0e0e0;
      padding: 1rem 2rem;
      text-align: center;
    }

    .footer p {
      margin: 0;
      color: #666;
      font-size: 0.875rem;
    }

    @media (max-width: 900px) {
      .main-content {
        padding: 1rem;
      }
    }
  `]
})
export class AppComponent {
  @ViewChild('statusComponent') statusComponent!: StatusComponent;
  @ViewChild('askComponent') askComponent!: AskComponent;
  @ViewChild('exploreComponent') exploreComponent!: ExploreComponent;

  onTaskUploaded(event: { taskId: string; docId?: string }): void {
    this.statusComponent.setTaskId(event.taskId);
    if (event.docId) {
      this.askComponent.setDocId(event.docId);
    }
  }

  onCheckStatus(taskId: string): void {
    this.statusComponent.setTaskId(taskId);
  }

  onUseInChat(docId: string): void {
    this.askComponent.setDocId(docId);
  }

  onViewPaperGraph(paperId: string): void {
    this.exploreComponent.setPaperId(paperId);
  }
}
