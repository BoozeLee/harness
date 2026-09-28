const BASE = "/api";

function headers(): HeadersInit {
  const token = import.meta.env.VITE_HARNESS_TOKEN as string | undefined;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) throw new ApiError(r.status, await r.text());
  return (await r.json()) as T;
}

export function getJson<T>(path: string): Promise<T> {
  return fetch(`${BASE}${path}`, { headers: headers() }).then(handle<T>);
}

export function postJson<T>(path: string, body: unknown): Promise<T> {
  return fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers() },
    body: JSON.stringify(body),
  }).then(handle<T>);
}
