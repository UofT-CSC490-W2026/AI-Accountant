import { useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function LoginPage() {
  const { isAuthenticated, login, signUp } = useAuth();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleLogin() {
    setError(null);
    try {
      await login();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to start sign-in.");
    }
  }

  async function handleSignUp() {
    setError(null);
    try {
      await signUp();
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
        <p>Use the Cognito hosted flow to create an account, verify your email, and then sign in.</p>
        {authNotice ? <p role="status" className="warning-copy">{authNotice}</p> : null}
        <div className="panel-actions">
          <button type="button" className="primary-button" onClick={handleLogin}>
            Continue with Cognito
          </button>
          <button type="button" className="secondary-button" onClick={handleSignUp}>
            Create account
          </button>
        </div>
        <p className="body-copy">Demo path: create account, confirm the verification email, then return here and sign in.</p>
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
