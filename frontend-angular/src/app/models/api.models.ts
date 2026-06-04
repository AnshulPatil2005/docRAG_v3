export interface UploadResponse {
  message: string;
  task_id?: string;
  doc_id?: string;
  detail?: string;
}

export interface TaskStatus {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE';
  result?: unknown;
  error?: string;
}

export interface Citation {
  filename?: string;
  page?: number;
  doc_id?: string;
  text_snippet: string;
}

export interface ChatRequest {
  query: string;
  doc_id?: string;
}

export interface ChatResponse {
  answer: string;
  citations?: Citation[];
}

export interface RecentTask {
  task_id: string;
  doc_id?: string;
  filename: string;
  timestamp: string;
  status: string;
}

export interface HealthStatus {
  online: boolean;
  message?: string;
}
