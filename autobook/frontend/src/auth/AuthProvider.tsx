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
  beginHostedSignUp,
  beginLogout,
  clearAuthSession,
  completeHostedLogin,
  fetchAuthMe,
  getAccessToken,
  refreshAuthSession,
} from "../api/auth";
import { isMockApiEnabled, isMockAuthEnabled } from "../config/env";
import type { AuthUser } from "../api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  isAuthenticated: boolean;
  login: (email?: string) => Promise<void>;
  signUp: (email?: string) => Promise<void>;
  logout: () => Promise<void>;
  completeLogin: (search: string) => Promise<void>;
  refreshUser: () => Promise<void>;
};

const MOCK_USER_STORAGE_KEY = "autobook_mock_user_email";

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
        setUser(buildMockUser(loadMockUserEmail()));
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
      login: async (email?: string) => {
        await beginHostedLogin(email);
        if (isMockApiEnabled()) {
          const resolvedUser = buildMockUser(email);
          persistMockUserEmail(resolvedUser.email);
          setUser(resolvedUser);
          setStatus("authenticated");
          return;
        }
        if (isMockAuthEnabled()) {
          persistMockUserEmail(email ?? "demo@autobook.local");
          const me = await fetchAuthMe();
          setUser(me);
          setStatus("authenticated");
        }
      },
      signUp: async (email?: string) => {
        await beginHostedSignUp(email);
        if (isMockApiEnabled()) {
          const resolvedUser = buildMockUser(email);
          persistMockUserEmail(resolvedUser.email);
          setUser(resolvedUser);
          setStatus("authenticated");
          return;
        }
        if (isMockAuthEnabled()) {
          persistMockUserEmail(email ?? "demo@autobook.local");
          const me = await fetchAuthMe();
          setUser(me);
          setStatus("authenticated");
        }
      },
      logout: async () => {
        await beginLogout();
        clearMockUserEmail();
        setUser(null);
        setStatus("anonymous");
      },
      completeLogin: async (search: string) => {
        if (isMockApiEnabled()) {
          const resolvedUser = buildMockUser(loadMockUserEmail());
          persistMockUserEmail(resolvedUser.email);
          setUser(resolvedUser);
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
            setUser(buildMockUser(loadMockUserEmail()));
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

function buildMockUser(email?: string): AuthUser {
  const normalizedEmail = (email ?? "demo@autobook.local").trim() || "demo@autobook.local";
  const normalizedId = normalizedEmail.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "mock-user";
  return {
    id: `mock-${normalizedId}`,
    cognito_sub: `mock-${normalizedId}`,
    email: normalizedEmail,
    role: "regular",
    role_source: "mock",
    token_use: "access",
  };
}

function loadMockUserEmail(): string | undefined {
  const storedEmail = localStorage.getItem(MOCK_USER_STORAGE_KEY);
  return storedEmail ?? undefined;
}

function persistMockUserEmail(email: string) {
  localStorage.setItem(MOCK_USER_STORAGE_KEY, email);
}

function clearMockUserEmail() {
  localStorage.removeItem(MOCK_USER_STORAGE_KEY);
}
