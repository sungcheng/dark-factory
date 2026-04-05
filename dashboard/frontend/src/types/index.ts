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
  job_id: string;
  agent: "Architect" | "QA Engineer" | "Developer";
  event_type: "started" | "completed" | "error" | "task_assigned" | "task_completed";
  message: string;
  timestamp: string;
  round: number;
}

export interface Job {
  id: string;
  repo_name: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  duration_seconds?: number;
}

export interface Task {
  id: string;
  job_id: string;
  round: number;
  description: string;
  status: "pending" | "completed" | "failed";
  created_at: string;
}

export interface RoundResult {
  round: number;
  status: "success" | "failure";
  timestamp: string;
}

export interface AgentStatus {
  agent: "Architect" | "QA Engineer" | "Developer";
  state: "idle" | "active" | "done";
  lastEvent?: Event;
  currentTask?: string;
}

export interface JobHistoryEntry {
  id: string;
  repo_name: string;
  status: "pending" | "running" | "completed" | "failed";
  duration_seconds: number;
  created_at: string;
}

export interface LogEntry {
  timestamp: string;
  event_type: string;
  agent: string;
  message: string;
  round: number;
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
