import type { Event } from "../types";

const AGENTS = ["Architect", "QA Engineer", "Developer"] as const;

type AgentName = (typeof AGENTS)[number];

interface AgentCardsProps {
  jobId: string | null;
  events: Event[];
}

interface AgentStats {
  state: "idle" | "active" | "done" | "error";
  totalSpawns: number;
  breakdown: { label: string; count: number }[];
}

function matchesAgent(event: Event, agent: AgentName): boolean {
  const msg = (event.message ?? "").toLowerCase();
  const type = (event.event_type ?? "").toLowerCase();
  if (agent === "Architect") {
    return msg.includes("architect") || type.includes("architect");
  }
  if (agent === "QA Engineer") {
    return (
      msg.includes("qa") ||
      msg.includes("evaluator") ||
      type.includes("qa") ||
      type.includes("evaluator")
    );
  }
  if (agent === "Developer") {
    return (
      msg.includes("developer") ||
      msg.includes("generator") ||
      type.includes("generator") ||
      type.includes("developer")
    );
  }
  return false;
}

function categorizeSpawn(msg: string, agent: AgentName): string {
  const lower = msg.toLowerCase();
  if (agent === "QA Engineer") {
    if (lower.includes("contract")) return "contracts";
    if (lower.includes("red") || lower.includes("test")) return "tests";
    if (lower.includes("review")) return "reviews";
    if (lower.includes("regression")) return "regression";
    // Bare "QA" message is the contracts phase
    if (lower === "qa" || lower === "qa engineer") return "contracts";
    return "review";
  }
  if (agent === "Developer") {
    if (lower.includes("scaffold")) return "scaffold";
    return "coding";
  }
  return "run";
}

function deriveAgentStats(agent: AgentName, events: Event[]): AgentStats {
  const agentEvents = events.filter((e) => matchesAgent(e, agent));
  const spawns = agentEvents.filter((e) => e.event_type === "agent_spawned");

  // Count by category
  const counts: Record<string, number> = {};
  for (const spawn of spawns) {
    const cat = categorizeSpawn(spawn.message ?? "", agent);
    counts[cat] = (counts[cat] ?? 0) + 1;
  }
  const breakdown = Object.entries(counts).map(([label, count]) => ({
    label,
    count,
  }));

  // Determine state
  let state: AgentStats["state"] = "idle";
  if (agentEvents.length > 0) {
    const last = agentEvents[agentEvents.length - 1];
    const lastTimestamp = last.timestamp;
    // If agent_spawned but newer events exist from other agents, it's done
    const hasNewerEvents = events.some(
      (e) =>
        e.timestamp > lastTimestamp &&
        (e.event_type === "agent_spawned" ||
          e.event_type === "task_completed" ||
          e.event_type === "round_result"),
    );
    if (last.event_type === "agent_spawned" && !hasNewerEvents) {
      state = "active";
    } else if (last.event_type === "agent_spawned" && hasNewerEvents) {
      state = "done";
    } else if (
      last.event_type === "task_completed" ||
      last.event_type === "agent_exited" ||
      last.status === "completed" ||
      last.status === "success"
    ) {
      state = "done";
    } else if (last.status === "failed" || last.status === "failure") {
      state = "error";
    } else {
      state = "active";
    }
  } else if (agent === "Architect") {
    // Architect is done if any task_started or later events exist
    // (meaning the pipeline moved past the Architect phase)
    const hasPostArchitectEvents = events.some(
      (e) =>
        e.event_type === "task_started" ||
        e.event_type === "task_completed" ||
        e.event_type === "round_result",
    );
    if (hasPostArchitectEvents) {
      state = "done";
    }
  }

  return { state, totalSpawns: spawns.length, breakdown };
}

const STATE_STYLES: Record<string, string> = {
  idle: "border-gray-600 bg-gray-900",
  active: "border-blue-500 bg-blue-900/50 animate-pulse",
  done: "border-green-500 bg-green-900/50",
  error: "border-red-500 bg-red-900/50",
};

const STATE_LABELS: Record<string, string> = {
  idle: "Idle",
  active: "Working...",
  done: "Done",
  error: "Error",
};

const STATE_DOT: Record<string, string> = {
  idle: "bg-gray-400",
  active: "bg-blue-400 animate-pulse",
  done: "bg-green-400",
  error: "bg-red-400",
};

export function AgentCards({
  jobId,
  events,
}: AgentCardsProps): React.ReactElement {
  void jobId;

  return (
    <div className="grid grid-cols-3 gap-4">
      {AGENTS.map((agent) => {
        const stats = deriveAgentStats(agent, events);

        return (
          <div
            key={agent}
            data-testid={`agent-card-${agent}`}
            className={`border-2 rounded-lg p-4 text-white ${STATE_STYLES[stats.state]}`}
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-bold text-lg">{agent}</h3>
              <div className="flex items-center gap-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${STATE_DOT[stats.state]}`}
                />
                <span className="text-sm text-gray-300">
                  {STATE_LABELS[stats.state]}
                </span>
              </div>
            </div>

            {stats.totalSpawns > 0 ? (
              <div className="mt-2">
                <p className="text-xs text-gray-400 mb-1">
                  {stats.totalSpawns} spawn{stats.totalSpawns !== 1 ? "s" : ""}
                </p>
                <div className="flex flex-wrap gap-2">
                  {stats.breakdown.map(({ label, count }) => (
                    <span
                      key={label}
                      className="text-xs bg-gray-800 px-2 py-0.5 rounded text-gray-300"
                    >
                      {count} {label}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-500 mt-2">No activity</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
