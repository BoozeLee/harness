import { ApiState, useApi } from "../components/ApiState";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { Health as HealthT } from "../api/types";

export default function Health() {
  const q = useApi<HealthT>(["health"], "/health");
  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">Health</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Probe of agent/CLI dependencies (plan §4.2). Missing tools are fixed on this box with
        <code className="ml-1 rounded bg-zinc-500/20 px-1">omarchy pkg add &lt;pkg&gt;</code>.
      </p>
      <ApiState
        q={q}
        render={(h) => (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-40">tool</TableHead>
                <TableHead>version</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.entries(h.tools).map(([name, version]) => (
                <TableRow key={name}>
                  <TableCell className="font-medium">{name}</TableCell>
                  <TableCell>
                    {version ? (
                      <span className="font-mono text-xs">{version}</span>
                    ) : (
                      <Badge variant="destructive">MISSING</Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      />
    </div>
  );
}
