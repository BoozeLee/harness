// Mirrors harness core schemas (harness/policy.py SCHEMA = 1). Keep in sync;
// P1 replaces this with generated types from the FastAPI OpenAPI document.

export type Risk = "low" | "medium" | "high";

export interface Scan {
  root: string;
  stacks: string[];
  gates: Record<string, string>;
  protected: string[];
  ci: string[];
  notes: string[];
  readiness: number;
  schema_version: number;
}

export interface Gate {
  cmd: string;
  min_risk: Risk;
  type?: "e2e";
}

export interface Verification {
  gates: Record<string, Gate>;
  review: boolean;
  schema_version: number;
}

export interface Policy {
  always_allow: string[];
  ask: string[];
  protected: string[];
  never_read: string[];
  never_commands: string[];
  schema_version: number;
}

export interface TaskContract {
  name: string;
  goal: string;
  accept: string[];
  risk: Risk;
  branch: string;
  worktree: string;
  base: string;
  allowed: string[];
  protected: string[];
  gates: Record<string, Gate>;
  review: boolean;
  created: number;
  schema_version: number;
}

export interface GateResult {
  name: string;
  cmd: string;
  ok: boolean;
  secs: number;
  tail: string;
  required: boolean;
  skipped?: boolean;
}

export interface Evidence {
  task: string;
  goal: string;
  accept: string[];
  results: GateResult[];
  files: string[];
  stat: string;
  verdict: "PASS" | "FAIL";
  time: number;
  schema_version: number;
}

export interface AuditEvent {
  t: number;
  tool: string;
  target: string | null;
  decision: "allow" | "deny" | "ask";
  blocked: boolean;
  why: string | null;
}

export interface Health {
  harness: string;
  repo: string;
  tools: Record<string, string | null>;
}

export interface TaskRow {
  name: string;
  risk: Risk;
  branch: string;
  verdict: string;
}

export interface ProjectTasks {
  total: number;
  pass: number;
  fail: number;
  unverified: number;
}

export interface Project {
  name: string;
  root: string;
  initialized: boolean;
  stacks: string[];
  gates: string[];
  protected: string[];
  ci: string[];
  readiness: number;
  tasks: ProjectTasks;
}

export interface ProjectList {
  schema_version: number;
  projects: Project[];
}

export interface Run {
  id: string;
  task: string;
  kind: "verify" | "agent";
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  argv: string;
  worktree: string;
  created: number;
  started: number | null;
  ended: number | null;
  exit_code: number | null;
}
