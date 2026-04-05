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

const STATUS_DOT: Record<string, string> = {
  pending: "bg-gray-400",
  in_progress: "bg-blue-400 animate-pulse",
  completed: "bg-green-400",
  failed: "bg-red-400",
};

export function App(): React.ReactElement {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetailResponse | null>(null);
  const [events, setEvents] = useState<Event[]>([]);

  // Fetch job list and auto-select in-progress job
  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const res = await fetch("/api/v1/jobs");
        if (!res.ok) return;
        const data: JobSummary[] = await res.json();
        setJobs(data);

        // Auto-select first in-progress job (or first job) on initial load
        if (!selectedJobId && data.length > 0) {
          const active = data.find((j) => j.status === "in_progress");
          setSelectedJobId((active ?? data[0]).job_id);
        }
      } catch {
        // retry next interval
      }
    };

    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [selectedJobId]);

  // Fetch detail + events for selected job
  const fetchJobData = useCallback(async () => {
    if (!selectedJobId) {
      setJobDetail(null);
      setEvents([]);
      return;
    }

    const encoded = encodeURIComponent(selectedJobId);

    try {
      const [detailRes, logRes] = await Promise.all([
        fetch(`/api/v1/jobs/${encoded}`),
        fetch(`/api/v1/jobs/${encoded}/log`),
      ]);

      if (detailRes.ok) {
        setJobDetail(await detailRes.json());
      }

      if (logRes.ok) {
        const log = await logRes.json();
        setEvents(Array.isArray(log) ? log : []);
      }
    } catch {
      // retry next interval
    }
  }, [selectedJobId]);

  useEffect(() => {
    fetchJobData();
    const interval = setInterval(fetchJobData, 3000);
    return () => clearInterval(interval);
  }, [fetchJobData]);

  const tasks = jobDetail?.tasks ?? [];
  const currentJob = jobs.find((j) => j.job_id === selectedJobId);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />
      <div className="flex flex-col gap-6 p-6">

        {/* Job selector + status bar */}
        <section className="flex items-center gap-4">
          <select
            value={selectedJobId ?? ""}
            onChange={(e) => setSelectedJobId(e.target.value || null)}
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
          >
            {jobs.length === 0 && <option value="">No jobs</option>}
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                {j.repo_name} #{j.issue_number} — {j.status.replace("_", " ")}
              </option>
            ))}
          </select>

          {currentJob && (
            <div className="flex items-center gap-3 text-sm">
              <span className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[currentJob.status] ?? STATUS_DOT.pending}`} />
              <span className="text-gray-300">
                {currentJob.status.replace("_", " ")}
              </span>
              <span className="text-gray-500">|</span>
              <span className="text-gray-300">
                {currentJob.completed_task_count}/{currentJob.task_count} tasks
              </span>
              <span className="text-gray-500">|</span>
              <TimeEstimate
                events={events}
                tasks={tasks}
                jobStatus={currentJob.status}
              />
            </div>
          )}
        </section>

        {/* Agent status cards */}
        <section>
          <h2 className="text-lg font-semibold mb-3 text-gray-400">Agents</h2>
          <AgentCards jobId={selectedJobId} events={events} />
        </section>

        {/* Task progress + Live log side by side */}
        <section className="grid grid-cols-2 gap-6">
          <div>
            <h2 className="text-lg font-semibold mb-3 text-gray-400">Tasks</h2>
            <TaskProgress job={null} events={events} tasks={tasks} />
          </div>
          <div>
            <h2 className="text-lg font-semibold mb-3 text-gray-400">Live Log</h2>
            <LiveLog jobId={selectedJobId} events={events} />
          </div>
        </section>
      </div>
    </div>
  );
}
