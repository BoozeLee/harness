import { ApiState, useApi } from "../components/ApiState";
import type { AuditEvent } from "../api/types";

const fmt = (t: number) => new Date(t * 1000).toLocaleTimeString();

export default function Audit() {
  const q = useApi<AuditEvent[]>(["audit"], "/audit");
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Audit log</h1>
      <p className="mb-4 text-sm text-zinc-500">Live follow via SSE (/api/audit?follow=1) lands in P2.</p>
      <ApiState
        q={q}
        render={(events) => (
          <table className="w-full text-left text-xs">
            <thead className="border-b border-zinc-200 text-zinc-500 dark:border-zinc-800">
              <tr>
                <th className="py-1 pr-3">time</th>
                <th className="py-1 pr-3">decision</th>
                <th className="py-1 pr-3">tool</th>
                <th className="py-1 pr-3">target</th>
                <th className="py-1">why</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(-200).reverse().map((e, i) => (
                <tr key={i} className={e.blocked ? "bg-red-500/10" : ""}>
                  <td className="py-1 pr-3 font-mono">{fmt(e.t)}</td>
                  <td className="py-1 pr-3 font-semibold uppercase">{e.decision}</td>
                  <td className="py-1 pr-3">{e.tool}</td>
                  <td className="max-w-64 truncate py-1 pr-3 font-mono">{e.target}</td>
                  <td className="py-1 text-zinc-500">{e.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      />
    </div>
  );
}
