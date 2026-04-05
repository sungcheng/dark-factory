import { useState, useEffect } from "react";
import type { Event, Task } from "../types";

interface TimeEstimateProps {
  events: Event[];
  tasks: Task[];
  jobStatus: string;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return `${hours}h ${remainMins}m`;
}

function getJobStartTime(events: Event[]): Date | null {
  // Use the EARLIEST job_started event — this is when the overall run began
  const starts = events
    .filter((e) => e.event_type === "job_started")
    .map((e) => new Date(e.timestamp).getTime())
    .sort((a, b) => a - b); // oldest first

  if (starts.length > 0) {
    return new Date(starts[0]);
  }
  // Fallback: earliest event timestamp
  if (events.length > 0) {
    const timestamps = events.map((e) => new Date(e.timestamp).getTime());
    return new Date(Math.min(...timestamps));
  }
  return null;
}

function getTaskDurations(events: Event[]): number[] {
  // Find pairs of task_started → task_completed for same task_id
  // Events must be sorted chronologically (App.tsx sorts them)
  const starts: Record<string, string> = {};
  const durations: number[] = [];

  const sorted = [...events].sort(
    (a, b) =>
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  );

  for (const e of sorted) {
    if (e.event_type === "task_started") {
      starts[e.task_id] = e.timestamp;
    }
    if (
      (e.event_type === "task_completed" || e.event_type === "task_failed") &&
      starts[e.task_id]
    ) {
      const startTime = new Date(starts[e.task_id]).getTime();
      const endTime = new Date(e.timestamp).getTime();
      const duration = (endTime - startTime) / 1000;
      if (duration > 0) {
        durations.push(duration);
      }
      delete starts[e.task_id];
    }
  }

  return durations;
}

export function TimeEstimate({
  events,
  tasks,
  jobStatus,
}: TimeEstimateProps): React.ReactElement {
  const [now, setNow] = useState(Date.now());

  // Update "now" every second for live elapsed time
  useEffect(() => {
    if (jobStatus !== "in_progress") return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [jobStatus]);

  const startTime = getJobStartTime(events);
  const completedDurations = getTaskDurations(events);

  const completedCount = tasks.filter(
    (t) => t.status === "completed" || t.status === "success",
  ).length;
  const pendingCount = tasks.filter(
    (t) => t.status === "pending" || t.status === "in_progress",
  ).length;
  const totalCount = tasks.length;

  // Elapsed time
  const elapsed = startTime ? (now - startTime.getTime()) / 1000 : 0;

  // Average time per completed task
  const avgTaskTime =
    completedDurations.length > 0
      ? completedDurations.reduce((a, b) => a + b, 0) /
        completedDurations.length
      : 0;

  // Estimated remaining
  const estimatedRemaining = avgTaskTime > 0 ? pendingCount * avgTaskTime : 0;

  if (events.length === 0 || !startTime) {
    return <div className="text-xs text-gray-500">Waiting for events...</div>;
  }

  return (
    <div className="flex items-center gap-4 text-sm">
      {/* Elapsed */}
      <div className="flex items-center gap-1.5">
        <span className="text-gray-500">Elapsed:</span>
        <span className="text-white font-mono">
          {formatDuration(elapsed)}
        </span>
      </div>

      {/* Estimated remaining */}
      {jobStatus === "in_progress" && totalCount > 0 && (
        <>
          <span className="text-gray-600">|</span>
          <div className="flex items-center gap-1.5">
            <span className="text-gray-500">Est. remaining:</span>
            <span className="text-yellow-300 font-mono">
              {avgTaskTime > 0
                ? formatDuration(estimatedRemaining)
                : `~${pendingCount * 5}–${pendingCount * 10}m`}
            </span>
          </div>
        </>
      )}

      {/* Avg per task (once we have data) */}
      {completedDurations.length > 0 && (
        <>
          <span className="text-gray-600">|</span>
          <div className="flex items-center gap-1.5">
            <span className="text-gray-500">Avg/task:</span>
            <span className="text-gray-300 font-mono">
              {formatDuration(avgTaskTime)}
            </span>
          </div>
        </>
      )}

      {/* Completed jobs show total time */}
      {jobStatus === "completed" && (
        <>
          <span className="text-gray-600">|</span>
          <span className="text-green-400">Completed</span>
        </>
      )}
      {jobStatus === "failed" && (
        <>
          <span className="text-gray-600">|</span>
          <span className="text-red-400">Failed</span>
        </>
      )}
    </div>
  );
}
