import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";

import { postJson } from "../api/client";
import { useApi } from "../components/ApiState";
import { STATUS_STYLE } from "./Runs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { Run as RunT } from "../api/types";

type GateState = { state: "running" | "done"; ok?: boolean; secs?: number; cmd?: string };
type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export default function Run() {
  const { id = "" } = useParams();
  const [status, setStatus] = useState<RunStatus>("queued");
  const [task, setTask] = useState<string>("");
  const [gates, setGates] = useState<Record<string, GateState>>({});
  const [verdict, setVerdict] = useState<string | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const [lastLine, setLastLine] = useState(0);
  const scrollRef = useRef<HTMLPreElement>(null);
  const prevStatus = useRef<RunStatus | null>(null);
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

  useEffect(() => {
    const prev = prevStatus.current;
    prevStatus.current = status;
    if (prev === null || prev === status || !(prev === "queued" || prev === "running")) return;
    const label = task ? `Run for ${task}` : `Run ${id.slice(0, 8)}`;
    if (status === "running") toast.info(`${label} started`);
    else if (status === "succeeded") toast.success(`${label} succeeded`);
    else if (status === "failed") toast.error(`${label} failed`);
    else if (status === "cancelled") toast.error(`${label} cancelled`);
  }, [status, task, id]);

  return (
    <div data-testid="run-view">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Run <code className="text-base font-mono text-muted-foreground">{id}</code>
          </h1>
          {task && <p className="text-sm text-muted-foreground">task: {task}</p>}
        </div>
        <div className="flex items-center gap-3">
          <Badge data-testid="run-status" className={STATUS_STYLE[status] ?? ""}>{status}</Badge>
          {active ? (
            <Button
              data-testid="cancel-run"
              variant="destructive"
              onClick={() => void postJson(`/runs/${id}/cancel`, {})}
            >
              Cancel
            </Button>
          ) : (
            <Button asChild variant="outline">
              <Link to="/tasks">Back to tasks</Link>
            </Button>
          )}
        </div>
      </div>

      <div className="mb-4 grid gap-2 sm:grid-cols-2">
        {Object.entries(gates).map(([name, g]) => (
          <Card key={name} data-testid={`gate-${name}`} data-size="sm">
            <CardContent className="flex items-center justify-between">
              <span className="font-medium">{name}</span>
              <span className={g.state === "running" ? "animate-pulse text-amber-600 dark:text-amber-400" : g.ok ? "text-emerald-600 dark:text-emerald-400" : "text-destructive"}>
                {g.state === "running" ? "running…" : g.ok ? `PASS ${g.secs ?? ""}s` : "FAIL"}
              </span>
            </CardContent>
          </Card>
        ))}
        {verdict && (
          <Card data-testid="verdict" data-size="sm" className="col-span-full">
            <CardContent className="flex items-center justify-between">
              <span className="font-medium">Verdict</span>
              <Badge className={verdict === "PASS" ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400" : "bg-red-500/15 text-red-600 dark:text-red-400"}>
                {verdict}
              </Badge>
            </CardContent>
          </Card>
        )}
      </div>

      <pre
        ref={scrollRef}
        data-testid="run-output"
        className="max-h-96 overflow-auto rounded-lg bg-zinc-900 p-3 font-mono text-xs leading-5 text-zinc-100 ring-1 ring-foreground/10 dark:bg-black"
      >
        {lines.join("\n")}
      </pre>
    </div>
  );
}
