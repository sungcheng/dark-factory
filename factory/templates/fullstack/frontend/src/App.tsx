import { useEffect, useState } from "react";

function App() {
  const [status, setStatus] = useState<string>("loading...");

  useEffect(() => {
    fetch("/api/v1/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-950 text-white">
      <h1 className="text-4xl font-bold mb-4">{"{{PROJECT_NAME}}"}</h1>
      <p className="text-lg text-gray-400">
        API status: <span className="font-mono text-green-400">{status}</span>
      </p>
    </div>
  );
}

export default App;
