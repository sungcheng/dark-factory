import { Header } from "./Header";
import { AgentCards } from "./AgentCards";
import { TaskProgress } from "./TaskProgress";
import { LiveLog } from "./LiveLog";
import { JobHistory } from "./JobHistory";

export function App(): JSX.Element {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        <AgentCards />
        <TaskProgress />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <LiveLog />
          <JobHistory />
        </div>
      </main>
    </div>
  );
}
