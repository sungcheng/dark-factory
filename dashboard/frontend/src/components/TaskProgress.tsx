import { useState, useEffect } from "react";
import type { Job, Event, SubTask } from "../types";
import type { TaskWithParent } from "./App";

interface TaskProgressProps {
  job: Job | null;
  events: Event[];
  tasks: TaskWithParent[];
}

const STATUS_DOT: Record<string, string> = {
  pending: "bg-gray-500",
  completed: "bg-green-500",
  success: "bg-green-500",
  failed: "bg-red-500",
  in_progress: "bg-blue-500 animate-pulse",
};

const STATUS_BADGE: Record<string, string> = {
  in_progress: "text-blue-400",
  completed: "text-green-400",
  success: "text-green-400",
  failed: "text-red-400",
  pending: "text-gray-400",
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return `${hours}h ${remainMins}m`;
}

interface TaskTiming {
  startedAt: Date | null;
  completedAt: Date | null;
  elapsed: number;
  isActive: boolean;
}

function getTaskTimings(
  tasks: TaskWithParent[],
  events: Event[],
): Record<string, TaskTiming> {
  const timings: Record<string, TaskTiming> = {};

  for (const task of tasks) {
    timings[task.id] = {
      startedAt: null,
      completedAt: null,
      elapsed: 0,
      isActive: false,
    };
    for (const sub of task.subtasks ?? []) {
      timings[sub.id] = {
        startedAt: null,
        completedAt: null,
        elapsed: 0,
        isActive: false,
      };
    }
  }

  for (const e of events) {
    const taskId = e.task_id;
    if (!timings[taskId]) continue;

    if (e.event_type === "task_started") {
      timings[taskId].startedAt = new Date(e.timestamp);
      timings[taskId].isActive = true;
    }
    if (
      e.event_type === "task_completed" ||
      e.event_type === "task_failed"
    ) {
      timings[taskId].completedAt = new Date(e.timestamp);
      timings[taskId].isActive = false;
      if (timings[taskId].startedAt) {
        timings[taskId].elapsed =
          (new Date(e.timestamp).getTime() -
            timings[taskId].startedAt!.getTime()) /
          1000;
      }
    }
  }

  return timings;
}

function getRoundsForTask(
  taskId: string,
  events: Event[],
): { round: number; passed: boolean }[] {
  return events
    .filter(
      (e) => e.task_id === taskId && e.event_type === "round_result",
    )
    .map((e) => ({
      round: parseInt(e.message?.replace("round ", "") ?? "0", 10),
      passed: e.status === "success",
    }));
}

interface IssueGroup {
  issueNumber: number;
  status: string;
  tasks: TaskWithParent[];
  completedCount: number;
}

function groupByIssue(tasks: TaskWithParent[]): IssueGroup[] {
  const map = new Map<number, TaskWithParent[]>();
  const statusMap = new Map<number, string>();

  for (const t of tasks) {
    const list = map.get(t.parentIssue) ?? [];
    list.push(t);
    map.set(t.parentIssue, list);
    statusMap.set(t.parentIssue, t.parentStatus);
  }

  const groups: IssueGroup[] = [];
  for (const [issueNumber, issueTasks] of map) {
    const completedCount = issueTasks.filter(
      (t) => t.status === "completed" || t.status === "success",
    ).length;
    groups.push({
      issueNumber,
      status: statusMap.get(issueNumber) ?? "pending",
      tasks: issueTasks,
      completedCount,
    });
  }

  // Sort: in_progress first, then failed, then pending, then completed
  const order: Record<string, number> = {
    in_progress: 0,
    failed: 1,
    pending: 2,
    completed: 3,
    success: 3,
  };
  groups.sort(
    (a, b) => (order[a.status] ?? 4) - (order[b.status] ?? 4),
  );

  return groups;
}

export function TaskProgress({
  job,
  events,
  tasks,
}: TaskProgressProps): React.ReactElement {
  void job;
  const [now, setNow] = useState(Date.now());
  const [collapsedIssues, setCollapsedIssues] = useState<Set<number>>(
    new Set(),
  );

  useEffect(() => {
    const hasActive = tasks.some(
      (t) => t.status === "in_progress" || t.status === "pending",
    );
    if (!hasActive) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [tasks]);

  // Auto-collapse completed issues
  useEffect(() => {
    const groups = groupByIssue(tasks);
    const done = new Set<number>();
    for (const g of groups) {
      if (
        g.status === "completed" ||
        g.status === "success"
      ) {
        done.add(g.issueNumber);
      }
    }
    setCollapsedIssues(done);
  }, [tasks]);

  if (tasks.length === 0) {
    return (
      <div className="text-gray-500">Select a job to see tasks</div>
    );
  }

  const completedCount = tasks.filter(
    (t) => t.status === "completed" || t.status === "success",
  ).length;
  const total = tasks.length;
  const timings = getTaskTimings(tasks, events);
  const issueGroups = groupByIssue(tasks);

  const toggleCollapse = (issueNumber: number) => {
    setCollapsedIssues((prev) => {
      const next = new Set(prev);
      if (next.has(issueNumber)) {
        next.delete(issueNumber);
      } else {
        next.add(issueNumber);
      }
      return next;
    });
  };

  return (
    <div>
      {/* Overall progress bar */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex-1 bg-gray-700 rounded-full h-2">
          <div
            className="bg-green-500 h-2 rounded-full transition-all duration-500"
            style={{
              width: `${total > 0 ? (completedCount / total) * 100 : 0}%`,
            }}
          />
        </div>
        <span className="text-sm text-gray-400">
          <span className="text-green-400">{completedCount} done</span>
          {" · "}
          <span className="text-blue-400">
            {total - completedCount} remaining
          </span>
        </span>
      </div>

      {/* Issue groups */}
      <div className="space-y-3">
        {issueGroups.map((group) => {
          const isCollapsed = collapsedIssues.has(group.issueNumber);
          const statusClass =
            STATUS_BADGE[group.status] ?? STATUS_BADGE.pending;
          const dotClass =
            STATUS_DOT[group.status] ?? STATUS_DOT.pending;

          return (
            <div key={group.issueNumber} className="border border-gray-700 rounded-lg overflow-hidden">
              {/* Issue header — clickable to collapse/expand */}
              <button
                onClick={() => toggleCollapse(group.issueNumber)}
                className="w-full flex items-center gap-3 px-3 py-2 bg-gray-800/50 hover:bg-gray-800 transition-colors text-left"
              >
                <span
                  className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${dotClass}`}
                />
                <span className="text-sm font-medium text-white flex-1">
                  Issue #{group.issueNumber}
                </span>
                <span className="text-xs text-gray-400">
                  {group.completedCount}/{group.tasks.length} tasks
                </span>
                <span className={`text-xs capitalize ${statusClass}`}>
                  {group.status.replace("_", " ")}
                </span>
                <span className="text-xs text-gray-500">
                  {isCollapsed ? "▶" : "▼"}
                </span>
              </button>

              {/* Task list — collapsible */}
              {!isCollapsed && (
                <ul className="px-2 py-1 space-y-1">
                  {group.tasks.map((task) => {
                    const status = task.status ?? "pending";
                    const taskDot =
                      STATUS_DOT[status] ?? STATUS_DOT.pending;
                    const timing = timings[task.id];
                    const rounds = getRoundsForTask(task.id, events);

                    let elapsed = timing?.elapsed ?? 0;
                    if (timing?.isActive && timing.startedAt) {
                      elapsed =
                        (now - timing.startedAt.getTime()) / 1000;
                    }

                    const subtasks: SubTask[] = task.subtasks ?? [];
                    const hasSubtasks = subtasks.length > 0;
                    const subCompleted = subtasks.filter(
                      (s) =>
                        s.status === "completed" ||
                        s.status === "success",
                    ).length;

                    return (
                      <li
                        key={task.id}
                        data-testid={`task-item-${task.id}`}
                      >
                        <div className="flex items-start gap-3 py-2 px-3 rounded bg-gray-800">
                          <span
                            className={`mt-1.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${taskDot}`}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm text-white font-medium truncate">
                                {task.title ?? task.description}
                                {hasSubtasks && (
                                  <span className="text-xs text-gray-500 ml-2">
                                    ({subCompleted}/{subtasks.length}{" "}
                                    subtasks)
                                  </span>
                                )}
                              </p>
                              {elapsed > 0 && (
                                <span
                                  className={`text-xs font-mono flex-shrink-0 ${
                                    timing?.isActive
                                      ? "text-blue-400"
                                      : "text-gray-400"
                                  }`}
                                >
                                  {formatDuration(elapsed)}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-xs text-gray-400 capitalize">
                                {status.replace("_", " ")}
                              </span>
                              {rounds.length > 0 && (
                                <div className="flex items-center gap-1">
                                  {rounds.map((r) => (
                                    <span
                                      key={r.round}
                                      className={`w-1.5 h-1.5 rounded-full ${
                                        r.passed
                                          ? "bg-green-500"
                                          : "bg-red-500"
                                      }`}
                                      title={`Round ${r.round}: ${r.passed ? "pass" : "fail"}`}
                                    />
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                        {/* Subtasks */}
                        {hasSubtasks && (
                          <ul className="ml-6 mt-1 space-y-1">
                            {subtasks.map((sub) => {
                              const subStatus =
                                sub.status ?? "pending";
                              const subDot =
                                STATUS_DOT[subStatus] ??
                                STATUS_DOT.pending;
                              const subTiming = timings[sub.id];
                              const subRounds = getRoundsForTask(
                                sub.id,
                                events,
                              );
                              let subElapsed =
                                subTiming?.elapsed ?? 0;
                              if (
                                subTiming?.isActive &&
                                subTiming.startedAt
                              ) {
                                subElapsed =
                                  (now -
                                    subTiming.startedAt.getTime()) /
                                  1000;
                              }

                              return (
                                <li
                                  key={sub.id}
                                  className="flex items-start gap-2 py-1.5 px-2 rounded bg-gray-850 border-l-2 border-gray-700"
                                >
                                  <span
                                    className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${subDot}`}
                                  />
                                  <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between gap-2">
                                      <p className="text-xs text-gray-300 truncate">
                                        {sub.title}
                                      </p>
                                      {subElapsed > 0 && (
                                        <span
                                          className={`text-xs font-mono flex-shrink-0 ${
                                            subTiming?.isActive
                                              ? "text-blue-400"
                                              : "text-gray-500"
                                          }`}
                                        >
                                          {formatDuration(subElapsed)}
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex items-center gap-1 mt-0.5">
                                      <span className="text-xs text-gray-500 capitalize">
                                        {subStatus.replace("_", " ")}
                                      </span>
                                      {subRounds.map((r) => (
                                        <span
                                          key={r.round}
                                          className={`w-1 h-1 rounded-full ${
                                            r.passed
                                              ? "bg-green-500"
                                              : "bg-red-500"
                                          }`}
                                        />
                                      ))}
                                    </div>
                                  </div>
                                </li>
                              );
                            })}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
