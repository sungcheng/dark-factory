import type { Job, Event, Task } from "../types";

interface TaskProgressProps {
  job: Job | null;
  events: Event[];
  tasks: Task[];
}

export function TaskProgress({ job, events, tasks }: TaskProgressProps): React.ReactElement {
  void job;
  void events;

  if (tasks.length === 0) {
    return (
      <div className="text-gray-500">No tasks</div>
    );
  }

  const rounds = Array.from(new Set(tasks.map((t) => t.round))).sort((a, b) => a - b);

  return (
    <ul>
      {tasks.map((task) => (
        <li
          key={task.id}
          data-testid={`task-item-${task.id}`}
          className="flex items-center gap-2 py-2"
        >
          <span className="text-sm text-white">{task.description}</span>
          {rounds
            .filter((r) => r === task.round)
            .map((round) => {
              const roundTasks = tasks.filter((t) => t.round === round);
              const failed = roundTasks.some((t) => t.status === "failed");
              const allCompleted = roundTasks.every((t) => t.status === "completed");
              let dotClass = "text-gray-500 text-xl";
              if (failed) dotClass = "text-red-500 text-xl";
              else if (allCompleted) dotClass = "text-green-500 text-xl";

              return (
                <span key={round} className={dotClass}>
                  ● <span className="text-xs text-gray-400">R{round}</span>
                </span>
              );
            })}
        </li>
      ))}
    </ul>
  );
}
