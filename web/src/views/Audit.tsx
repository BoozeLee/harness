import { ApiState, useApi } from "../components/ApiState";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { AuditEvent } from "../api/types";

const fmt = (t: number) => new Date(t * 1000).toLocaleTimeString();

const DECISION_STYLE: Record<string, string> = {
  allow: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  deny: "bg-red-500/15 text-red-600 dark:text-red-400",
  ask: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
};

export default function Audit() {
  const q = useApi<AuditEvent[]>(["audit"], "/audit");
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Audit log</h1>
      <p className="mb-4 text-sm text-muted-foreground">Live follow via SSE (/api/audit?follow=1) lands in P2.</p>
      <ApiState
        q={q}
        render={(events) => (
          <Table className="text-xs">
            <TableHeader>
              <TableRow>
                <TableHead className="pr-3">time</TableHead>
                <TableHead className="pr-3">decision</TableHead>
                <TableHead className="pr-3">tool</TableHead>
                <TableHead className="pr-3">target</TableHead>
                <TableHead>why</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.slice(-200).reverse().map((e, i) => (
                <TableRow key={i} className={e.blocked ? "bg-destructive/10" : ""}>
                  <TableCell className="py-1 pr-3 font-mono">{fmt(e.t)}</TableCell>
                  <TableCell className="py-1 pr-3">
                    <Badge className={DECISION_STYLE[e.decision] ?? ""}>{e.decision}</Badge>
                  </TableCell>
                  <TableCell className="py-1 pr-3">{e.tool}</TableCell>
                  <TableCell className="max-w-64 truncate py-1 pr-3 font-mono">{e.target}</TableCell>
                  <TableCell className="py-1 text-muted-foreground">{e.why}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      />
    </div>
  );
}
