import { ApiState, useApi } from "../components/ApiState";
import type { Scan } from "../api/types";

export default function Readiness() {
  const q = useApi<Scan>(["scan"], "/scan");
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Agent-readiness</h1>
      <ApiState
        q={q}
        render={(s) => (
          <div className="space-y-4">
            <p className="text-4xl font-bold">
              {s.readiness}
              <span className="text-lg text-zinc-500">/100</span>
            </p>
            <p className="text-sm">
              {s.stacks.map((st) => (
                <span key={st} className="mr-2 rounded-full bg-zinc-200 px-2.5 py-0.5 text-xs font-medium dark:bg-zinc-800">
                  {st}
                </span>
              ))}
            </p>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800">
                <tr>
                  <th className="py-1 pr-4">Gate</th>
                  <th className="py-1">Command</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.gates).map(([k, cmd]) => (
                  <tr key={k} className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1.5 pr-4 font-medium">{k}</td>
                    <td className="py-1.5 font-mono text-xs">{cmd}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {s.notes.map((n) => (
              <p key={n} className="text-sm text-amber-600 dark:text-amber-400">! {n}</p>
            ))}
          </div>
        )}
      />
    </div>
  );
}
