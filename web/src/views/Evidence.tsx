import { ApiState, useApi } from "../components/ApiState";
import type { TaskRow } from "../api/types";

export default function Evidence() {
  const q = useApi<TaskRow[]>(["tasks"], "/tasks");
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Evidence</h1>
      <p className="mb-4 text-sm text-zinc-500">
        Native report view is P3 work; meanwhile each task links to the CLI-generated HTML evidence
        (<code className="rounded bg-zinc-500/20 px-1">/api/evidence/&lt;task&gt;/html</code>, CSP-sandboxed).
      </p>
      <ApiState
        q={q}
        render={(rows) => (
          <ul className="space-y-2">
            {rows.map((t) => (
              <li key={t.name} className="flex items-center justify-between rounded-lg border border-zinc-200 px-4 py-2 text-sm dark:border-zinc-800">
                <span className="font-medium">{t.name}</span>
                <span className="flex items-center gap-3">
                  <span className={t.verdict === "PASS" ? "text-emerald-500" : t.verdict === "FAIL" ? "text-red-500" : "text-zinc-500"}>
                    {t.verdict}
                  </span>
                  <a className="text-zinc-400 underline-offset-2 hover:underline" href={`/api/evidence/${t.name}/html`}>
                    report
                  </a>
                </span>
              </li>
            ))}
            {rows.length === 0 && <li className="text-sm text-zinc-500">Nothing verified yet.</li>}
          </ul>
        )}
      />
    </div>
  );
}
