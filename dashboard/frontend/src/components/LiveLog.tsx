import { useRef, useEffect } from "react";
import { usePolling } from "../hooks/usePolling";
import type { LogEntry } from "../types";

interface LiveLogProps {
  jobId: string | null;
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  started: "text-blue-400",
  completed: "text-green-400",
  error: "text-red-400",
  task_assigned: "text-yellow-400",
  task_completed: "text-green-400",
};

function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toTimeString().slice(0, 8);
}

export function LiveLog({ jobId }: LiveLogProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);

  const { data, loading, error } = usePolling<{ logs: LogEntry[]; job_id: string }>(
    async () => {
      if (!jobId) return { logs: [], job_id: "" };
      const res = await fetch(`/api/v1/jobs/${jobId}/log`);
      return res.json();
    },
    { enabled: jobId !== null, interval: 3000 }
  );

  const logs = data?.logs ?? [];

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  if (!jobId) {
    return (
      <div data-testid="log-container" className="h-64 overflow-y-auto bg-gray-950 rounded-lg p-3 text-gray-500">
        No logs
      </div>
    );
  }

  if (loading && logs.length === 0) {
    return (
      <div data-testid="log-container" className="h-64 overflow-y-auto bg-gray-950 rounded-lg p-3 text-gray-500">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="log-container" className="h-64 overflow-y-auto bg-gray-950 rounded-lg p-3 text-red-400">
        Error: {error.message}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      data-testid="log-container"
      className="h-64 overflow-y-auto bg-gray-950 rounded-lg p-3 font-mono text-sm"
    >
      {logs.map((entry, i) => {
        const colorClass = EVENT_TYPE_COLORS[entry.event_type] ?? "text-gray-300";
        return (
          <div key={i} className="py-0.5">
            <span className="text-gray-500 text-sm">[{formatTime(entry.timestamp)}]</span>{" "}
            <span className={colorClass}>{entry.event_type}</span>{" "}
            <span className="text-gray-400">| {entry.agent} |</span>{" "}
            <span className="text-white">{entry.message}</span>
          </div>
        );
      })}
    </div>
  );
}
