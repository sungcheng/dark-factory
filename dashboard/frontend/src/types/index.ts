export enum EventType {
  AGENT_STARTED = "agent_started",
  AGENT_COMPLETED = "agent_completed",
  TASK_CREATED = "task_created",
  TASK_COMPLETED = "task_completed",
  TEST_PASSED = "test_passed",
  TEST_FAILED = "test_failed",
  LOG_OUTPUT = "log_output",
  ERROR = "error",
}

export interface Event {
  id: string;
  timestamp: string;
  type: EventType;
  job_id: string;
  agent_name?: string;
  message: string;
  data?: Record<string, unknown>;
}

export interface JobSummary {
  id: string;
  issue_number: number;
  task_number: number;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  started_at?: string;
  completed_at?: string;
  agent_name?: string;
  progress_percent: number;
}

export interface JobDetail extends JobSummary {
  description: string;
  events: Event[];
  error_message?: string;
  approver_feedback?: string;
}
