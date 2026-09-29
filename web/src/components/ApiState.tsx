import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { getJson } from "../api/client";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";

export function useApi<T>(key: string[], path: string): UseQueryResult<T> {
  return useQuery<T>({
    queryKey: key,
    queryFn: () => getJson<T>(path),
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

interface Props<T> {
  q: UseQueryResult<T>;
  render: (data: T) => ReactNode;
}

export function ApiState<T>({ q, render }: Props<T>) {
  if (q.isPending) return <Skeleton className="h-5 w-40" />;
  if (q.isError)
    return (
      <Alert className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400">
        <AlertTitle>API offline</AlertTitle>
        <AlertDescription>
          The dashboard expects the local server on 127.0.0.1:8766 (plan §4.2, phase P1).
          The CLI stays fully usable without it: <code className="rounded bg-zinc-500/20 px-1">harness --help</code>
        </AlertDescription>
        <p className="mt-2 text-xs opacity-70">{String(q.error.message).slice(0, 200)}</p>
      </Alert>
    );
  return <>{render(q.data)}</>;
}
