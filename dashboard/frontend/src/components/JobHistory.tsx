import { usePolling } from "../hooks/usePolling";
import type { JobHistoryEntry } from "../types";

interface JobHistoryProps {
  onSelectJob: (jobId: string) => void;
  selectedJobId: string | null;
}

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-gray-500 text-white",
  in_progress: "bg-blue-500 text-white",
  completed: "bg-green-500 text-white",
  failed: "bg-red-500 text-white",
};

export function JobHistory({ onSelectJob, selectedJobId }: JobHistoryProps): React.ReactElement {
  const { data, loading } = usePolling<JobHistoryEntry[]>(
    async () => {
      const res = await fetch("/api/v1/jobs");
      return res.json();
    },
    { interval: 3000 }
  );

  const jobs = data ?? [];

  return (
    <div className="rounded-lg bg-gray-800 border border-gray-700 overflow-hidden">
      <table className="w-full text-sm text-left">
        <thead className="bg-gray-750 text-gray-400 uppercase text-xs">
          <tr>
            <th className="px-4 py-3">Repo</th>
            <th className="px-4 py-3">Issue</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Tasks</th>
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
                key={job.job_id}
                data-testid={`job-row-${job.job_id}`}
                className={`border-t border-gray-700 cursor-pointer hover:bg-gray-800 ${
                  selectedJobId === job.job_id ? "bg-blue-900" : ""
                }`}
                onClick={() => onSelectJob(job.job_id)}
              >
                <td className="px-4 py-3 text-white">{job.repo_name}</td>
                <td className="px-4 py-3 text-gray-300">#{job.issue_number}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${STATUS_BADGE[job.status] ?? STATUS_BADGE.pending}`}>
                    {job.status.replace("_", " ")}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-300">{job.completed_task_count}/{job.task_count}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
