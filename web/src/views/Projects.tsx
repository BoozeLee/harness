import { ApiState, useApi } from "../components/ApiState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { ProjectList } from "../api/types";

export default function Projects() {
  const q = useApi<ProjectList>(["projects"], "/v1/projects");
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold">Projects</h1>
      <ApiState
        q={q}
        render={(list) => (
          <div className="grid gap-3">
            {list.projects.map((p) => (
              <Card key={p.root} data-testid="project-row">
                <CardContent className="space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold" data-testid="project-name">{p.name}</p>
                    <p className="text-sm text-zinc-500" data-testid="project-readiness">
                      readiness {p.readiness}/100
                    </p>
                  </div>
                  <p className="font-mono text-xs text-zinc-500">{p.root}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {!p.initialized && (
                      <Badge variant="secondary" className="bg-amber-500/15 text-amber-700 dark:text-amber-400">
                        not initialized
                      </Badge>
                    )}
                    {p.stacks.map((st) => (
                      <Badge key={st} variant="secondary">{st}</Badge>
                    ))}
                    {p.gates.map((g) => (
                      <Badge key={g} variant="outline">{g}</Badge>
                    ))}
                  </div>
                  <p className="text-sm">
                    <span>{p.tasks.total} tasks</span>
                    {" · "}
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">{p.tasks.pass} PASS</span>
                    {" · "}
                    <span className="font-semibold text-red-600 dark:text-red-400">{p.tasks.fail} FAIL</span>
                    {" · "}
                    <span className="text-zinc-500">{p.tasks.unverified} unverified</span>
                  </p>
                </CardContent>
              </Card>
            ))}
            {list.projects.length === 0 && <p className="text-sm text-zinc-500">No projects bound to this server.</p>}
          </div>
        )}
      />
    </div>
  );
}
