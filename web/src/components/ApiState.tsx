import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { getJson } from "../api/client";

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

/** The API server is P1 work; offline is the expected state for this draft. */
export function ApiState<T>({ q, render }: Props<T>) {
  if (q.isPending) return <p className="text-sm text-zinc-500">loading…</p>;
  if (q.isError)
    return (
      <div className="rounded-lg border border-amber-300/40 bg-amber-500/10 p-4 text-sm">
        <p className="font-semibold text-amber-600 dark:text-amber-400">API offline</p>
        <p className="mt-1 text-zinc-600 dark:text-zinc-400">
          The dashboard expects the local server on 127.0.0.1:8766 (plan §4.2, phase P1).
          The CLI stays fully usable without it: <code className="rounded bg-zinc-500/20 px-1">harness --help</code>
        </p>
        <p className="mt-2 text-xs text-zinc-500">{String(q.error.message).slice(0, 200)}</p>
      </div>
    );
  return <>{render(q.data)}</>;
}
