import { NavLink, Navigate, Outlet, Route, Routes } from "react-router-dom";

import Audit from "./views/Audit";
import Evidence from "./views/Evidence";
import Health from "./views/Health";
import Policy from "./views/Policy";
import Readiness from "./views/Readiness";
import Run from "./views/Run";
import Runs from "./views/Runs";
import Tasks from "./views/Tasks";

const NAV = [
  { to: "readiness", label: "Readiness" },
  { to: "tasks", label: "Tasks" },
  { to: "runs", label: "Runs" },
  { to: "evidence", label: "Evidence" },
  { to: "policy", label: "Policy" },
  { to: "audit", label: "Audit" },
  { to: "health", label: "Health" },
];

function Shell() {
  return (
    <div className="flex min-h-screen bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <aside className="w-52 shrink-0 border-r border-zinc-200 p-4 dark:border-zinc-800">
        <p className="mb-6 text-lg font-bold tracking-tight">Harness</p>
        <nav className="flex flex-col gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `rounded-md px-3 py-1.5 text-sm font-medium ${
                  isActive ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "text-zinc-600 hover:bg-zinc-200/60 dark:text-zinc-400 dark:hover:bg-zinc-800"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="mx-auto w-full max-w-4xl p-6">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Navigate to="readiness" replace />} />
        <Route path="readiness" element={<Readiness />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="runs" element={<Runs />} />
        <Route path="runs/:id" element={<Run />} />
        <Route path="evidence" element={<Evidence />} />
        <Route path="policy" element={<Policy />} />
        <Route path="audit" element={<Audit />} />
        <Route path="health" element={<Health />} />
      </Route>
    </Routes>
  );
}
