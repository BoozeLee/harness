import { ApiState, useApi } from "../components/ApiState";
import type { Policy as PolicyT } from "../api/types";

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <p className="mb-2 text-sm font-semibold">{title}</p>
      <ul className="space-y-1 font-mono text-xs text-zinc-600 dark:text-zinc-400">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  );
}

export default function Policy() {
  const q = useApi<PolicyT>(["policy"], "/policy");
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Policy</h1>
      <p className="mb-4 text-sm text-zinc-500">Read-only draft; the editor with settings.json preview lands in P3.</p>
      <ApiState
        q={q}
        render={(p) => (
          <div className="grid gap-3 sm:grid-cols-2">
            <List title="protected (write denied)" items={p.protected} />
            <List title="never_read (secrets)" items={p.never_read} />
            <List title="never_commands" items={p.never_commands} />
            <List title="ask (human approval)" items={p.ask} />
          </div>
        )}
      />
    </div>
  );
}
