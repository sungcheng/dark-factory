import { useRef, useEffect } from "react";
import type { Event } from "../types";

interface LiveLogProps {
  jobId: string | null;
  events: Event[];
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  job_started: "text-blue-400",
  agent_spawned: "text-yellow-400",
  task_started: "text-blue-300",
  task_completed: "text-green-400",
  task_failed: "text-red-400",
  round_result: "text-purple-400",
  agent_exited: "text-gray-400",
  job_completed: "text-green-500",
  job_failed: "text-red-500",
};

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toTimeString().slice(0, 8);
}

function formatEventType(type: string): string {
  return type.replace(/_/g, " ");
}

export function LiveLog({ jobId, events }: LiveLogProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [events]);

  if (!jobId) {
    return (
      <div data-testid="log-container" className="h-64 overflow-y-auto bg-gray-950 rounded-lg p-3 text-gray-500">
        Select a job to see logs
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div data-testid="log-container" className="h-64 overflow-y-auto bg-gray-950 rounded-lg p-3 text-gray-500">
        No events yet
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      data-testid="log-container"
      className="h-64 overflow-y-auto bg-gray-950 rounded-lg p-3 font-mono text-sm"
    >
      {events.map((entry) => {
        const colorClass = EVENT_TYPE_COLORS[entry.event_type] ?? "text-gray-300";
        return (
          <div key={entry.id} className="py-0.5">
            <span className="text-gray-500 text-sm">[{formatTime(entry.timestamp)}]</span>{" "}
            <span className={colorClass}>{formatEventType(entry.event_type)}</span>{" "}
            <span className="text-gray-400">| {entry.task_id} |</span>{" "}
            {entry.message && <span className="text-white">{entry.message}</span>}
            {!entry.message && <span className="text-gray-500">{entry.status}</span>}
          </div>
        );
      })}
    </div>
  );
}
