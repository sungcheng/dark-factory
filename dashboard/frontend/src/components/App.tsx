import { useState, useEffect, useCallback } from "react";
import { Header } from "./Header";
import { AgentCards } from "./AgentCards";
import { TaskProgress } from "./TaskProgress";
import { LiveLog } from "./LiveLog";
import { TimeEstimate } from "./TimeEstimate";
import type { Event, Task } from "../types";

interface JobSummary {
  job_id: string;
  repo_name: string;
  issue_number: number;
  status: string;
  task_count: number;
  completed_task_count: number;
}

interface JobDetailResponse {
  job_id: string;
  repo_name: string;
  issue_number: number;
  status: string;
  tasks: Task[];
}

/** Aggregate view: one entry per repo with all issues rolled up. */
interface RepoGroup {
  repo_name: string;
  jobs: JobSummary[];
  status: string;
  task_count: number;
  completed_task_count: number;
}

function groupByRepo(jobs: JobSummary[]): RepoGroup[] {
  const map = new Map<string, JobSummary[]>();
  for (const j of jobs) {
    const list = map.get(j.repo_name) ?? [];
    list.push(j);
    map.set(j.repo_name, list);
  }

  const groups: RepoGroup[] = [];
  for (const [repo_name, repoJobs] of map) {
    const task_count = repoJobs.reduce((s, j) => s + j.task_count, 0);
    const completed_task_count = repoJobs.reduce(
      (s, j) => s + j.completed_task_count,
      0,
    );
    // Derive aggregate status: in_progress > failed > completed > pending
    let status = "completed";
    if (repoJobs.some((j) => j.status === "in_progress")) {
      status = "in_progress";
    } else if (repoJobs.some((j) => j.status === "failed")) {
      status = "failed";
    } else if (repoJobs.every((j) => j.status === "completed")) {
      status = "completed";
    } else {
      status = "pending";
    }
    groups.push({ repo_name, jobs: repoJobs, status, task_count, completed_task_count });
  }
  return groups;
}

const STATUS_DOT: Record<string, string> = {
  pending: "bg-gray-400",
  in_progress: "bg-blue-400 animate-pulse",
  completed: "bg-green-400",
  failed: "bg-red-400",
};

export function App(): React.ReactElement {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);
  const [allTasks, setAllTasks] = useState<Task[]>([]);
  const [allEvents, setAllEvents] = useState<Event[]>([]);

  // Fetch job list and auto-select repo with in-progress work
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch("/api/v1/jobs");
        if (!res.ok) return;
        const data: JobSummary[] = await res.json();
        setJobs(data);

        // Auto-select repo with in-progress job on initial load
        if (!selectedRepo && data.length > 0) {
          const active = data.find((j) => j.status === "in_progress");
          setSelectedRepo((active ?? data[0]).repo_name);
        }
      } catch {
        // retry next interval
      }
    };

    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [selectedRepo]);

  // Fetch detail + events for ALL issues in the selected repo
  const fetchRepoData = useCallback(async () => {
    if (!selectedRepo) {
      setAllTasks([]);
      setAllEvents([]);
      return;
    }

    const repoJobs = jobs.filter((j) => j.repo_name === selectedRepo);
    if (repoJobs.length === 0) return;

    const taskResults: Task[] = [];
    const eventResults: Event[] = [];

    await Promise.all(
      repoJobs.map(async (j) => {
        const encoded = encodeURIComponent(j.job_id);
        try {
          const [detailRes, logRes] = await Promise.all([
            fetch(`/api/v1/jobs/${encoded}`),
            fetch(`/api/v1/jobs/${encoded}/log`),
          ]);
          if (detailRes.ok) {
            const detail: JobDetailResponse = await detailRes.json();
            taskResults.push(...detail.tasks);
          }
          if (logRes.ok) {
            const log = await logRes.json();
            if (Array.isArray(log)) eventResults.push(...log);
          }
        } catch {
          // skip failed fetches
        }
      }),
    );

    setAllTasks(taskResults);
    setAllEvents(eventResults);
  }, [selectedRepo, jobs]);

  useEffect(() => {
    fetchRepoData();
    const interval = setInterval(fetchRepoData, 3000);
    return () => clearInterval(interval);
  }, [fetchRepoData]);

  const repoGroups = groupByRepo(jobs);
  const currentGroup = repoGroups.find((g) => g.repo_name === selectedRepo);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />
      <div className="flex flex-col gap-6 p-6">

        {/* Repo selector + status bar */}
        <section className="flex items-center gap-4">
          <select
            value={selectedRepo ?? ""}
            onChange={(e) => setSelectedRepo(e.target.value || null)}
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {repoGroups.length === 0 && <option value="">No jobs</option>}
            {repoGroups.map((g) => (
              <option key={g.repo_name} value={g.repo_name}>
                {g.repo_name} — {g.status.replace("_", " ")} ({g.jobs.length} issue{g.jobs.length !== 1 ? "s" : ""})
              </option>
            ))}
          </select>

          {currentGroup && (
            <div className="flex items-center gap-3 text-sm">
              <span className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[currentGroup.status] ?? STATUS_DOT.pending}`} />
              <span className="text-gray-300">
                {currentGroup.status.replace("_", " ")}
              </span>
              <span className="text-gray-500">|</span>
              <span className="text-gray-300">
                {currentGroup.completed_task_count}/{currentGroup.task_count} tasks
              </span>
              <span className="text-gray-500">|</span>
              <TimeEstimate
                events={allEvents}
                tasks={allTasks}
                jobStatus={currentGroup.status}
              />
            </div>
          )}
        </section>

        {/* Agent status cards */}
        <section>
          <h2 className="text-lg font-semibold mb-3 text-gray-400">Agents</h2>
          <AgentCards jobId={selectedRepo} events={allEvents} />
        </section>

        {/* Task progress + Live log side by side */}
        <section className="grid grid-cols-2 gap-6">
          <div>
            <h2 className="text-lg font-semibold mb-3 text-gray-400">Tasks</h2>
            <TaskProgress job={null} events={allEvents} tasks={allTasks} />
          </div>
          <div>
            <h2 className="text-lg font-semibold mb-3 text-gray-400">Live Log</h2>
            <LiveLog jobId={selectedRepo} events={allEvents} />
          </div>
        </section>
      </div>
    </div>
  );
}
