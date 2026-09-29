import { ApiState, useApi } from "../components/ApiState";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { Scan } from "../api/types";

export default function Readiness() {
  const q = useApi<Scan>(["scan"], "/scan");
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Agent-readiness</h1>
      <ApiState
        q={q}
        render={(s) => (
          <div className="space-y-4">
            <Card>
              <CardContent className="flex flex-wrap items-center gap-3">
                <p className="text-4xl font-bold">
                  {s.readiness}
                  <span className="text-lg text-muted-foreground">/100</span>
                </p>
                <p>
                  {s.stacks.map((st) => (
                    <Badge key={st} variant="secondary" className="mr-2">{st}</Badge>
                  ))}
                </p>
              </CardContent>
            </Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pr-4">Gate</TableHead>
                  <TableHead>Command</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(s.gates).map(([k, cmd]) => (
                  <TableRow key={k}>
                    <TableCell className="py-1.5 pr-4 font-medium">{k}</TableCell>
                    <TableCell className="py-1.5 font-mono text-xs">{cmd}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {s.notes.map((n) => (
              <Alert key={n} className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400">
                <AlertDescription>! {n}</AlertDescription>
              </Alert>
            ))}
          </div>
        )}
      />
    </div>
  );
}
