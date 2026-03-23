import {
  createContext,
  type ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  beginHostedLogin,
  beginLogout,
  clearAuthSession,
  completeHostedLogin,
  fetchAuthMe,
  getAccessToken,
  refreshAuthSession,
} from "../api/auth";
import type { AuthUser } from "../api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  completeLogin: (search: string) => Promise<void>;
  refreshUser: () => Promise<void>;
};

const MOCK_USER: AuthUser = {
  id: "mock-user",
  cognito_sub: "mock-user",
  email: "demo@autobook.local",
  role: "regular",
  role_source: "mock",
  token_use: "access",
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    void bootstrapAuth();
  }, []);

  async function bootstrapAuth() {
    if (isMockApiEnabled()) {
      if (getAccessToken()) {
        setUser(MOCK_USER);
        setStatus("authenticated");
      } else {
        setUser(null);
        setStatus("anonymous");
      }
      return;
    }

    if (!getAccessToken()) {
      setUser(null);
      setStatus("anonymous");
      return;
    }

    try {
      const me = await fetchAuthMe();
      setUser(me);
      setStatus("authenticated");
      return;
    } catch {
      try {
        const me = await refreshAuthSession();
        setUser(me);
        setStatus("authenticated");
        return;
      } catch {
        clearAuthSession();
      }
    }

    setUser(null);
    setStatus("anonymous");
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      isAuthenticated: status === "authenticated",
      login: async () => {
        await beginHostedLogin();
        if (isMockApiEnabled()) {
          setUser(MOCK_USER);
          setStatus("authenticated");
        }
      },
      logout: async () => {
        await beginLogout();
        setUser(null);
        setStatus("anonymous");
      },
      completeLogin: async (search: string) => {
        if (isMockApiEnabled()) {
          setUser(MOCK_USER);
          setStatus("authenticated");
          return;
        }
        setStatus("loading");
        const me = await completeHostedLogin(search);
        setUser(me);
        setStatus("authenticated");
      },
      refreshUser: async () => {
        if (isMockApiEnabled()) {
          if (getAccessToken()) {
            setUser(MOCK_USER);
            setStatus("authenticated");
          } else {
            setUser(null);
            setStatus("anonymous");
          }
          return;
        }
        setStatus("loading");
        const me = await fetchAuthMe();
        setUser(me);
        setStatus("authenticated");
      },
    }),
    [status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

function isMockApiEnabled() {
  return import.meta.env.VITE_USE_MOCK_API !== "false";
}
