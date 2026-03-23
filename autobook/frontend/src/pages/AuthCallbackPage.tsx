import { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function AuthCallbackPage() {
  const location = useLocation();
  const { completeLogin, isAuthenticated } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        await completeLogin(location.search);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Login callback failed.");
      }
    })();
  }, [completeLogin, location.search]);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <main className="content">
      <section className="panel">
        <p className="eyebrow">Auth Callback</p>
        <h1>Completing sign-in</h1>
        {error ? <p role="alert">{error}</p> : <p>Exchanging your Cognito authorization code.</p>}
      </section>
    </main>
  );
}
