export function LiveLog(): JSX.Element {
  return (
    <section>
      <h2 className="text-lg font-semibold text-gray-200 mb-3">Live Log</h2>
      <div className="rounded-lg bg-gray-800 border border-gray-700 p-4 h-64 overflow-y-auto font-mono text-sm">
        <p className="text-gray-500">Waiting for events...</p>
      </div>
    </section>
  );
}
