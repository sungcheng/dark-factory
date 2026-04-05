export function TaskProgress(): JSX.Element {
  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-200 mb-3">Task Progress</h2>
      <div className="rounded-lg bg-gray-800 border border-gray-700 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">No active task</span>
          <span className="text-sm text-gray-500">0%</span>
        </div>
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div className="bg-blue-500 h-2 rounded-full" style={{ width: "0%" }} />
        </div>
      </div>
    </section>
  );
}
