import type { Event } from "../types";

const AGENTS = ["Architect", "QA Engineer", "Developer"] as const;

type AgentName = (typeof AGENTS)[number];

interface AgentCardsProps {
  jobId: string | null;
  events: Event[];
}

function deriveAgentState(
  agent: AgentName,
  events: Event[]
): "idle" | "active" | "done" | "error" {
  const agentEvents = events.filter((e) => e.agent === agent);
  if (agentEvents.length === 0) return "idle";
  const lastEvent = agentEvents[agentEvents.length - 1];
  if (lastEvent.event_type === "started" || lastEvent.event_type === "task_assigned") {
    return "active";
  }
  if (lastEvent.event_type === "completed") return "done";
  if (lastEvent.event_type === "error") return "error";
  return "idle";
}

const STATE_STYLES: Record<string, string> = {
  idle: "border-gray-400 bg-gray-900",
  active: "border-blue-500 bg-blue-900",
  done: "border-green-500 bg-green-900",
  error: "border-red-500 bg-red-900",
};

export function AgentCards({ jobId, events }: AgentCardsProps): React.ReactElement {
  void jobId;

  return (
    <div className="grid grid-cols-3 gap-4">
      {AGENTS.map((agent) => {
        const state = deriveAgentState(agent, events);
        const agentEvents = events.filter((e) => e.agent === agent);
        const lastEvent = agentEvents.length > 0 ? agentEvents[agentEvents.length - 1] : undefined;

        return (
          <div
            key={agent}
            data-testid={`agent-card-${agent}`}
            className={`border-2 rounded-lg p-4 text-white ${STATE_STYLES[state]}`}
          >
            <h3 className="font-bold text-lg">{agent}</h3>
            <p className="text-sm capitalize">{state}</p>
            {lastEvent && (
              <p className="text-xs text-gray-400 mt-1">{lastEvent.timestamp}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
