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
  task_id: string;
  event_type: string;
  status: string;
  message: string | null;
  job_id: string;
  timestamp: string;
}

export interface Job {
  id: string;
  repo_name: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  duration_seconds?: number;
}

export interface SubTask {
  id: string;
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed" | "success" | "failed";
  acceptance_criteria: string[];
  depends_on: string[];
  failure_issue: number | null;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed" | "success" | "failed";
  issue_number: number | null;
  failure_issue: number | null;
  acceptance_criteria: string[];
  depends_on: string[];
  subtasks?: SubTask[];
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
  job_id: string;
  repo_name: string;
  issue_number: number;
  status: "pending" | "in_progress" | "completed" | "failed";
  task_count: number;
  completed_task_count: number;
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
