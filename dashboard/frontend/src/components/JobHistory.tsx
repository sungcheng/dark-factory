import { usePolling } from "../hooks/usePolling";
import type { JobHistoryEntry } from "../types";

interface JobHistoryProps {
  onSelectJob: (jobId: string) => void;
  selectedJobId: string | null;
}

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-gray-500 text-white",
  running: "bg-blue-500 text-white",
  completed: "bg-green-500 text-white",
  failed: "bg-red-500 text-white",
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

export function JobHistory({ onSelectJob, selectedJobId }: JobHistoryProps): React.ReactElement {
  const { data, loading } = usePolling<{ jobs: JobHistoryEntry[]; total: number }>(
    async () => {
      const res = await fetch("/api/v1/jobs?limit=10");
      return res.json();
    },
    { interval: 3000 }
  );

  const jobs = data?.jobs ?? [];

  return (
    <div className="rounded-lg bg-gray-800 border border-gray-700 overflow-hidden">
      <table className="w-full text-sm text-left">
        <thead className="bg-gray-750 text-gray-400 uppercase text-xs">
          <tr>
            <th className="px-4 py-3">Repo Name</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Duration</th>
            <th className="px-4 py-3">Created</th>
          </tr>
        </thead>
        <tbody>
          {loading && jobs.length === 0 ? (
            <>
              {[1, 2, 3].map((i) => (
                <tr key={i} className="border-t border-gray-700">
                  <td className="px-4 py-3" colSpan={4}>
                    <div className="h-4 bg-gray-700 rounded animate-pulse" />
                  </td>
                </tr>
              ))}
            </>
          ) : jobs.length === 0 ? (
            <tr>
              <td className="px-4 py-3 text-gray-500" colSpan={4}>
                No jobs
              </td>
            </tr>
          ) : (
            jobs.map((job) => (
              <tr
                key={job.id}
                data-testid={`job-row-${job.id}`}
                className={`border-t border-gray-700 cursor-pointer hover:bg-gray-800 ${
                  selectedJobId === job.id ? "bg-blue-900" : ""
                }`}
                onClick={() => onSelectJob(job.id)}
              >
                <td className="px-4 py-3 text-white">{job.repo_name}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_BADGE[job.status]}`}>
                    {job.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-300">{formatDuration(job.duration_seconds)}</td>
                <td className="px-4 py-3 text-gray-400">{job.created_at}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
