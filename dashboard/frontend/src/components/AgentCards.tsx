const AGENTS = ["generator", "tester", "reviewer", "integrator", "evaluator"] as const;

export function AgentCards(): JSX.Element {
  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-200 mb-3">Agents</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {AGENTS.map((agent) => (
          <div
            key={agent}
            className="rounded-lg bg-gray-800 border border-gray-700 p-4"
          >
            <p className="text-sm font-medium text-gray-300 capitalize">{agent}</p>
            <p className="text-xs text-gray-500 mt-1">Idle</p>
          </div>
        ))}
      </div>
    </section>
  );
}
