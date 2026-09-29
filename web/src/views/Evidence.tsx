import { ApiState, useApi } from "../components/ApiState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { TaskRow } from "../api/types";

export default function Evidence() {
  const q = useApi<TaskRow[]>(["tasks"], "/tasks");
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Evidence</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Native report view is P3 work; meanwhile each task links to the CLI-generated HTML evidence
        (<code className="rounded bg-zinc-500/20 px-1">/api/evidence/&lt;task&gt;/html</code>, CSP-sandboxed).
      </p>
      <ApiState
        q={q}
        render={(rows) =>
          rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing verified yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>task</TableHead>
                  <TableHead>verdict</TableHead>
                  <TableHead className="text-right">report</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((t) => (
                  <TableRow key={t.name}>
                    <TableCell className="font-medium">{t.name}</TableCell>
                    <TableCell>
                      <Badge
                        className={
                          t.verdict === "PASS"
                            ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                            : t.verdict === "FAIL"
                              ? "bg-red-500/15 text-red-600 dark:text-red-400"
                              : "bg-zinc-500/15 text-zinc-600 dark:text-zinc-400"
                        }
                      >
                        {t.verdict}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild variant="link" size="sm">
                        <a href={`/api/evidence/${t.name}/html`}>open</a>
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
