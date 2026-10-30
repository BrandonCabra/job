export type Job = {
  id: string;
  title: string;
  company: string;
  description: string;
  url: string;
  location: string;
  source: string;
  published_at: string;
  status: string;
};

export type Application = {
  id: number;
  created_at: string;
  job_id: string;
  company: string;
  title: string;
  url: string;
  score: number;
  status: string;
  step: string;
  cv_path: string;
  cover_letter_path: string;
  details: Record<string, unknown>;
};

export type Task = {
  id: string;
  task_type: string;
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result: Record<string, unknown>;
  error: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers }
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `La API respondió ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  jobs: () => request<Job[]>("/api/v1/jobs?limit=50"),
  applications: () => request<Application[]>("/api/v1/applications?limit=100"),
  enqueue: (jobId: string, type: "evaluate-task" | "documents-task") =>
    request<Task>(`/api/v1/jobs/${encodeURIComponent(jobId)}/${type}`, { method: "POST" }),
  task: (taskId: string) => request<Task>(`/api/v1/tasks/${encodeURIComponent(taskId)}`),
  updateApplication: (id: number, status: string, step?: string) =>
    request<Application>(`/api/v1/applications/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status, step })
    }),
  documentUrl: (path: string) => {
    const filename = path.split("/").pop() ?? "";
    return `/api/v1/documents/${encodeURIComponent(filename)}`;
  }
};
