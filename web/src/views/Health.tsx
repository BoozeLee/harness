import { ApiState, useApi } from "../components/ApiState";
import type { Health as HealthT } from "../api/types";

export default function Health() {
  const q = useApi<HealthT>(["health"], "/health");
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Health</h1>
      <p className="mb-4 text-sm text-zinc-500">
        Probe of agent/CLI dependencies (plan §4.2). Missing tools are fixed on this box with
        <code className="ml-1 rounded bg-zinc-500/20 px-1">omarchy pkg add &lt;pkg&gt;</code>.
      </p>
      <ApiState
        q={q}
        render={(h) => (
          <table className="w-full text-left text-sm">
            <tbody>
              {Object.entries(h.tools).map(([name, version]) => (
                <tr key={name} className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="w-40 py-1.5 font-medium">{name}</td>
                  <td className={`py-1.5 font-mono text-xs ${version ? "" : "text-red-500"}`}>
                    {version ?? "MISSING"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      />
    </div>
  );
}
