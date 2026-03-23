import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
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

  return (
    <main className="content">
      <section className="panel">
        <p className="eyebrow">Secure Access</p>
        <h1>Sign in</h1>
        <p>Use the Cognito hosted login flow to access the protected bookkeeping workspace.</p>
        <button type="button" className="primary-button" onClick={handleLogin}>
          Continue with Cognito
        </button>
        {error ? <p role="alert">{error}</p> : null}
      </section>
    </main>
  );
}
