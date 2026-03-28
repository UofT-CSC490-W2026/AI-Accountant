import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { AuthCallbackError } from "../api/auth";
import { useAuth } from "../auth/AuthProvider";

const startedCallbackSearches = new Set<string>();

export function AuthCallbackPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { completeLogin, isAuthenticated } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const callbackSearch = location.search;
    if (startedCallbackSearches.has(callbackSearch)) {
      return;
    }
    startedCallbackSearches.add(callbackSearch);

    void (async () => {
      try {
        await completeLogin(callbackSearch);
      } catch (nextError) {
        if (nextError instanceof AuthCallbackError) {
          if (nextError.code === "needs_sign_in") {
            navigate("/login?auth=verified", { replace: true });
            return;
          }
          if (nextError.code === "restart_sign_in") {
            navigate("/login?auth=restart", { replace: true });
            return;
          }
        }
        setError(nextError instanceof Error ? nextError.message : "Login callback failed.");
      }
    })();
  }, [completeLogin, location.search, navigate]);

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
