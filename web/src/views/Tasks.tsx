import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { postJson } from "../api/client";
import { ApiState, useApi } from "../components/ApiState";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Run, TaskRow } from "../api/types";

const RISK_STYLE: Record<string, string> = {
  low: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  medium: "bg-amber-500/15 text-amber-600 dark:text-emerald-400",
  high: "bg-red-500/15 text-red-600 dark:text-red-400",
};

function NewTaskDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [risk, setRisk] = useState("low");
  const [allow, setAllow] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      await postJson("/tasks", {
        name,
        goal,
        risk,
        allow: allow.split(/[\s,]+/).filter(Boolean),
      });
      toast.success(`Contract ${name} created`);
      setOpen(false);
      setName("");
      setGoal("");
      setAllow("");
      onCreated();
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e).slice(0, 300));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Button data-testid="new-task-button" onClick={() => setOpen(true)}>+ New task</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="new-task-dialog">
          <DialogHeader>
            <DialogTitle>Start a task contract</DialogTitle>
            <DialogDescription>Creates the worktree, branch and gates via `harness task start`.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="task-name">Name</Label>
              <Input id="task-name" data-testid="task-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="invites" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="task-goal">Goal</Label>
              <Input id="task-goal" data-testid="task-goal" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="what does done look like?" />
            </div>
            <div className="grid gap-1.5">
              <Label>Risk</Label>
              <Select value={risk} onValueChange={setRisk}>
                <SelectTrigger data-testid="task-risk"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">low</SelectItem>
                  <SelectItem value="medium">medium</SelectItem>
                  <SelectItem value="high">high</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="task-allow">Allowed paths <span className="text-zinc-500">(comma or space separated)</span></Label>
              <Input id="task-allow" data-testid="task-allow" value={allow} onChange={(e) => setAllow(e.target.value)} placeholder="src/**, tests/**" />
            </div>
            {err && <p data-testid="task-error" className="rounded-md bg-red-500/10 p-2 text-sm text-red-600 dark:text-red-400">{err}</p>}
          </div>
          <DialogFooter>
            <Button data-testid="task-submit" onClick={() => void submit()} disabled={busy || !name || !goal}>
              {busy ? "creating…" : "Create contract"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export default function Tasks() {
  const qc = useQueryClient();
  const q = useApi<TaskRow[]>(["tasks"], "/tasks");
  const nav = useNavigate();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function verify(name: string) {
    setBusy(name);
    setErr(null);
    try {
      const r = await postJson<Run>(`/tasks/${name}/verify`, {});
      nav(`/runs/${r.id}`);
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e).slice(0, 200));
      setBusy(null);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Tasks</h1>
        <NewTaskDialog onCreated={() => void qc.invalidateQueries({ queryKey: ["tasks"] })} />
      </div>
      {err && <p data-testid="verify-error" className="mb-3 rounded-md bg-red-500/10 p-2 text-sm text-red-600 dark:text-red-400">{err}</p>}
      <ApiState
        q={q}
        render={(rows) => (
          <div className="grid gap-3 sm:grid-cols-2">
            {rows.map((t) => (
              <div key={t.name} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
                <div className="flex items-center justify-between">
                  <p className="font-semibold">{t.name}</p>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${RISK_STYLE[t.risk] ?? ""}`}>{t.risk}</span>
                </div>
                <p className="mt-1 font-mono text-xs text-zinc-500">{t.branch}</p>
                <p className="mt-2 text-sm">
                  {t.verdict === "PASS" ? (
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">PASS</span>
                  ) : t.verdict === "FAIL" ? (
                    <span className="font-semibold text-red-600 dark:text-red-400">FAIL</span>
                  ) : (
                    <span className="text-zinc-500">{t.verdict}</span>
                  )}
                </p>
                <Button
                  data-testid={`verify-${t.name}`}
                  disabled={busy === t.name}
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => void verify(t.name)}
                >
                  {busy === t.name ? "starting…" : "Verify ▶"}
                </Button>
              </div>
            ))}
            {rows.length === 0 && <p className="text-sm text-zinc-500">No contracts yet — start one with the button above.</p>}
          </div>
        )}
      />
    </div>
  );
}
