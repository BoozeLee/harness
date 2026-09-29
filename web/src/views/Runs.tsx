import { Link } from "react-router-dom";

import { ApiState, useApi } from "../components/ApiState";
import type { Run } from "../api/types";

const STYLE: Record<string, string> = {
  queued: "text-zinc-500",
  running: "text-amber-600 dark:text-amber-400",
  succeeded: "text-emerald-600 dark:text-emerald-400",
  failed: "text-red-600 dark:text-red-400",
  cancelled: "text-red-600 dark:text-red-400",
};

export default function Runs() {
  const q = useApi<Run[]>(["runs"], "/runs");
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Runs</h1>
      <ApiState
        q={q}
        render={(rows) => (
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-zinc-500">
              <tr><th className="py-1">task</th><th>kind</th><th>status</th><th>argv</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-1.5 font-medium">{r.task}</td>
                  <td>{r.kind}</td>
                  <td className={STYLE[r.status]}>{r.status}</td>
                  <td className="max-w-64 truncate font-mono text-xs text-zinc-500">{r.argv}</td>
                  <td className="text-right"><Link to={`/runs/${r.id}`} className="text-sm text-sky-600 dark:text-sky-400">stream →</Link></td>
                </tr>
              ))}
              {rows.length === 0 && <p className="text-sm text-zinc-500">No runs yet — press Verify on a task card.</p>}
            </tbody>
          </table>
        )}
      />
    </div>
  );
}
