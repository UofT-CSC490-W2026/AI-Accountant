import { type ReactNode, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { RealtimeClock } from "../components/RealtimeClock";
import { ensureSocketConnection } from "../api/realtime";

type AppLayoutProps = {
  children: ReactNode;
};

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/transactions", label: "Transaction" },
  { to: "/clarifications", label: "Clarifications" },
  { to: "/ledger", label: "Ledger" },
  { to: "/statements", label: "Statements" },
];

export function AppLayout({ children }: AppLayoutProps) {
  useEffect(() => {
    ensureSocketConnection();
  }, []);
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Startup Demo</p>
          <h1>{import.meta.env.VITE_APP_NAME ?? "AI Accountant"}</h1>
        </div>
        <p className="topbar-copy">
          Natural language bookkeeping with confidence-gated review.
        </p>
        <div className="topbar-clock">
          <RealtimeClock variant="surface" />
        </div>
      </header>

      <nav className="nav">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              isActive ? "nav-link nav-link-active" : "nav-link"
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <main className="content">{children}</main>
    </div>
  );
}
