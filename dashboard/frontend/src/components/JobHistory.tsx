export function JobHistory(): JSX.Element {
  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-200 mb-3">Job History</h2>
      <div className="rounded-lg bg-gray-800 border border-gray-700 overflow-hidden">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-750 text-gray-400 uppercase text-xs">
            <tr>
              <th className="px-4 py-3">Issue #</th>
              <th className="px-4 py-3">Task</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Started</th>
              <th className="px-4 py-3">Duration</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="px-4 py-3 text-gray-500" colSpan={5}>
                No jobs yet
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
