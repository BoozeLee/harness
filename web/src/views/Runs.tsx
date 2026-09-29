import { Link } from "react-router-dom";

import { ApiState, useApi } from "../components/ApiState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { Run } from "../api/types";

export const STATUS_STYLE: Record<string, string> = {
  queued: "bg-zinc-500/15 text-zinc-600 dark:text-zinc-400",
  running: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  succeeded: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  failed: "bg-red-500/15 text-red-600 dark:text-red-400",
  cancelled: "bg-red-500/15 text-red-600 dark:text-red-400",
};

export default function Runs() {
  const q = useApi<Run[]>(["runs"], "/runs");
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Runs</h1>
      <ApiState
        q={q}
        render={(rows) =>
          rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No runs yet — press Verify on a task card.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>task</TableHead>
                  <TableHead>kind</TableHead>
                  <TableHead>status</TableHead>
                  <TableHead>argv</TableHead>
                  <TableHead className="text-right" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.task}</TableCell>
                    <TableCell>{r.kind}</TableCell>
                    <TableCell>
                      <Badge className={STATUS_STYLE[r.status] ?? ""}>{r.status}</Badge>
                    </TableCell>
                    <TableCell className="max-w-64 truncate font-mono text-xs text-muted-foreground">{r.argv}</TableCell>
                    <TableCell className="text-right">
                      <Button asChild variant="link" size="sm">
                        <Link to={`/runs/${r.id}`}>stream →</Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )
        }
      />
    </div>
  );
}
