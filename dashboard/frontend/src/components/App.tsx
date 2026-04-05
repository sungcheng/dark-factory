import { useState } from "react";
import { Header } from "./Header";
import { AgentCards } from "./AgentCards";
import { TaskProgress } from "./TaskProgress";
import { LiveLog } from "./LiveLog";
import { JobHistory } from "./JobHistory";
import { usePolling } from "../hooks/usePolling";
import type { Job, Event, Task } from "../types";

export function App(): React.ReactElement {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const { data: currentJob } = usePolling<Job | null>(
    async () => {
      if (!selectedJobId) return null;
      const res = await fetch(`/api/v1/jobs/${selectedJobId}`);
      return res.json();
    },
    { enabled: !!selectedJobId, interval: 3000 }
  );

  const { data: events } = usePolling<Event[]>(
    async () => {
      if (!selectedJobId) return [];
      const res = await fetch(`/api/v1/jobs/${selectedJobId}/events`);
      return res.json();
    },
    { enabled: !!selectedJobId, interval: 3000 }
  );

  const { data: tasks } = usePolling<Task[]>(
    async () => {
      if (!selectedJobId) return [];
      const res = await fetch(`/api/v1/jobs/${selectedJobId}/tasks`);
      return res.json();
    },
    { enabled: !!selectedJobId, interval: 3000 }
  );

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />
      <div className="flex flex-col gap-6 p-6 bg-gray-950 min-h-screen text-white">
        <section>
          <h2 className="text-xl font-bold mb-4">Agent Status</h2>
          <AgentCards
            jobId={selectedJobId}
            events={events ?? []}
          />
        </section>

        <section className="grid grid-cols-2 gap-6">
          <div>
            <h2 className="text-xl font-bold mb-4">Task Progress</h2>
            <TaskProgress
              job={currentJob ?? null}
              events={events ?? []}
              tasks={tasks ?? []}
            />
          </div>
          <div>
            <h2 className="text-xl font-bold mb-4">Live Log</h2>
            <LiveLog jobId={selectedJobId} />
          </div>
        </section>

        <section>
          <h2 className="text-xl font-bold mb-4">Job History</h2>
          <JobHistory
            onSelectJob={setSelectedJobId}
            selectedJobId={selectedJobId}
          />
        </section>
      </div>
    </div>
  );
}
