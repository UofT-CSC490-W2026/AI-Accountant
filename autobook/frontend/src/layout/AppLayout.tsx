import { type ReactNode, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { RealtimeClock } from "../components/RealtimeClock";
import { ensureConnection } from "../api/realtime";
import { useAuth } from "../auth/AuthProvider";

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
  const { user, logout } = useAuth();

  useEffect(() => {
    ensureConnection();
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
        <div className="topbar-copy">
          <strong>{user?.email}</strong>
          <button type="button" className="nav-link" onClick={() => void logout()}>
            Logout
          </button>
        </div>
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
