import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { postJson } from "../api/client";
import { useApi } from "../components/ApiState";
import type { Run as RunT } from "../api/types";

type GateState = { state: "running" | "done"; ok?: boolean; secs?: number; cmd?: string };
type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

const STATUS_STYLE: Record<string, string> = {
  queued: "text-zinc-500",
  running: "text-amber-600 dark:text-amber-400",
  succeeded: "text-emerald-600 dark:text-emerald-400",
  failed: "text-red-600 dark:text-red-400",
  cancelled: "text-red-600 dark:text-red-400",
};

export default function Run() {
  const { id = "" } = useParams();
  const [status, setStatus] = useState<RunStatus>("queued");
  const [task, setTask] = useState<string>("");
  const [gates, setGates] = useState<Record<string, GateState>>({});
  const [verdict, setVerdict] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [lastLine, setLastLine] = useState(0);
  const scrollRef = useRef<HTMLPreElement>(null);
  const active = status === "queued" || status === "running";
  const run = useApi<RunT>(["runs", id], `/runs/${id}`);
  useEffect(() => {
    if (run.data) setTask(run.data.task);
  }, [run.data]);

  useEffect(() => {
    const es = new EventSource(`/api/runs/${id}/events`);
    const on = <T,>(ev: string, fn: (d: T) => void) =>
      es.addEventListener(ev, (e: MessageEvent) => fn(JSON.parse(e.data) as T));
    on<{ status: RunStatus }>("status", (d) => setStatus(d.status));
    on<{ name: string; state: string; ok?: boolean; secs?: number; cmd?: string }>("gate", (d) =>
      setGates((g) => ({ ...g, [d.name]: { state: d.state === "running" ? "running" : "done", ok: d.ok, secs: d.secs, cmd: d.cmd } })));
    on<{ verdict: string }>("verdict", (d) => setVerdict(d.verdict));
    on<{ line: string }>("out", (d) => {
      setLines((l) => [...l.slice(-499), d.line]);
      setLastLine((n) => n + 1);
    });
    on("end", () => es.close());
    return () => es.close();
  }, [id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [lastLine]);

  return (
    <div data-testid="run-view">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Run <code className="text-base font-mono text-zinc-500">{id}</code>
          </h1>
          {task && <p className="text-sm text-zinc-500">task: {task}</p>}
        </div>
        <div className="flex items-center gap-3">
          <span data-testid="run-status" className={`font-semibold ${STATUS_STYLE[status]}`}>{status}</span>
          {active ? (
            <button
              data-testid="cancel-run"
              className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white"
              onClick={() => void postJson(`/runs/${id}/cancel`, {})}
            >
              Cancel
            </button>
          ) : (
            <Link to="/tasks" className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700">Back to tasks</Link>
          )}
        </div>
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        {Object.entries(gates).map(([name, g]) => (
          <div key={name} data-testid={`gate-${name}`} className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
            <span className="font-medium">{name}</span>
            <span className={g.state === "running" ? "animate-pulse text-amber-600 dark:text-amber-400" : g.ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}>
              {g.state === "running" ? "running…" : g.ok ? `PASS ${g.secs ?? ""}s` : "FAIL"}
            </span>
          </div>
        ))}
        {verdict && (
          <div data-testid="verdict" className="col-span-full rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
            Verdict: <span className={verdict === "PASS" ? "font-bold text-emerald-600 dark:text-emerald-400" : "font-bold text-red-600 dark:text-red-400"}>{verdict}</span>
          </div>
        )}
      </div>

      <pre
        ref={scrollRef}
        data-testid="run-output"
        className="max-h-96 overflow-auto rounded-lg bg-zinc-900 p-3 font-mono text-xs leading-5 text-zinc-100 dark:bg-black"
      >
        {lines.join("\n")}
      </pre>
    </div>
  );
}
