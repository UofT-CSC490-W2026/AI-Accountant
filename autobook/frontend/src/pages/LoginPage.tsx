import { useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { isAuthOnlyMockEnabled, isMockApiEnabled } from "../config/env";

export function LoginPage() {
  const { isAuthenticated, login, signUp } = useAuth();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("demo@autobook.local");
  const [password, setPassword] = useState("demo-password");
  const isFullMockMode = isMockApiEnabled();
  const isMockAuthMode = isAuthOnlyMockEnabled() || isFullMockMode;

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleLogin() {
    setError(null);
    try {
      await login(email);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to start sign-in.");
    }
  }

  async function handleSignUp() {
    setError(null);
    try {
      await signUp(email);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to start sign-up.");
    }
  }

  const authNotice = getAuthNotice(searchParams.get("auth"));

  return (
    <main className="content">
      <section className="panel">
        <p className="eyebrow">Secure Access</p>
        <h1>Sign in</h1>
        <p>
          {isMockAuthMode
            ? "Demo auth mode is enabled. Enter any email and password to continue as that user."
            : "Use the Cognito hosted flow to create an account, verify your email, and then sign in."}
        </p>
        {authNotice ? <p role="status" className="warning-copy">{authNotice}</p> : null}
        {isMockAuthMode ? (
          <div className="auth-form-fields">
            <label className="field-label" htmlFor="login-email">
              Email
            </label>
            <input
              id="login-email"
              className="text-input"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="demo@autobook.local"
              autoComplete="email"
            />
            <label className="field-label" htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              className="text-input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Any password works in demo mode"
              autoComplete="current-password"
            />
          </div>
        ) : null}
        <div className="panel-actions">
          <button type="button" className="primary-button" onClick={handleLogin}>
            {isMockAuthMode ? "Demo sign in" : "Continue with Cognito"}
          </button>
          <button type="button" className="secondary-button" onClick={handleSignUp}>
            {isMockAuthMode ? "Demo register" : "Create account"}
          </button>
        </div>
        <p className="body-copy">
          {isMockAuthMode
            ? isFullMockMode
              ? "This mode is local-only and skips Cognito so the demo can proceed without external auth dependencies."
              : "This mode skips Cognito only. The rest of the app still talks to the real backend APIs."
            : "Demo path: create account, confirm the verification email, then return here and sign in."}
        </p>
        {error ? <p role="alert">{error}</p> : null}
      </section>
    </main>
  );
}

function getAuthNotice(authState: string | null): string | null {
  if (authState === "verified") {
    return "Account verified. Sign in to continue.";
  }
  if (authState === "restart") {
    return "Your sign-in session expired. Start again from this page.";
  }
  return null;
}
