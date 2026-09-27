"use client";

/**
 * Auth context provider.
 * Tracks the Supabase user session for the client app.
 */

import {
  createContext,
  Suspense,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured, safeNextPath } from "@/lib/auth";
import LoginPrompt from "@/components/LoginPrompt";
import { markConsentGiven, persistResearchConsent } from "@/lib/consent";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  configured: boolean;
  /** From public.profiles.role — admins can refine rating stimuli; participants cannot. */
  isAdmin: boolean;
  requestLogin: (next?: string) => void;
  signInWithGoogle: (next?: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}

export default function AuthProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const configured = isSupabaseConfigured();

  // Session and login modal state
  const [user, setUser] = useState<User | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(configured);
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginNext, setLoginNext] = useState("/");
  const [authError, setAuthError] = useState<string | null>(null);

  // Read admin role from the profiles table
  const refreshProfileRole = useCallback(async (nextUser: User | null) => {
    if (!nextUser) {
      setIsAdmin(false);
      return;
    }
    const supabase = createClient();
    if (!supabase) {
      setIsAdmin(false);
      return;
    }
    const { data } = await supabase
      .from("profiles")
      .select("role")
      .eq("id", nextUser.id)
      .maybeSingle();
    setIsAdmin(data?.role === "admin");
  }, []);

  // Subscribe to Supabase auth session changes
  // Reference: https://supabase.com/docs/reference/javascript/auth-onauthstatechange
  useEffect(() => {
    const supabase = createClient();
    if (!supabase) {
      return;
    }

    let cancelled = false;

    supabase.auth
      .getSession()
      .then(async ({ data }) => {
        if (cancelled) return;
        const nextUser = data.session?.user ?? null;
        setUser(nextUser);
        await refreshProfileRole(nextUser);
        if (nextUser) void persistResearchConsent(nextUser.id);
        if (!cancelled) setLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setUser(null);
        setIsAdmin(false);
        setLoading(false);
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (cancelled) return;
      const nextUser = session?.user ?? null;
      setUser(nextUser);
      void refreshProfileRole(nextUser);
      if (nextUser) void persistResearchConsent(nextUser.id);
      setLoading(false);
    });

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, [refreshProfileRole]);

  // Open the login modal for a destination path
  const requestLogin = useCallback((next = "/") => {
    setAuthError(
      configured
        ? null
        : "Google sign-in is not configured yet. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to frontend/.env.local."
    );
    setLoginNext(safeNextPath(next));
    setLoginOpen(true);
  }, [configured]);

  const closeLogin = useCallback(() => {
    setLoginOpen(false);
    setAuthError(null);
  }, []);

  // Start Google OAuth and return to nextPath after callback
  // Reference: https://supabase.com/docs/reference/javascript/auth-signinwithoauth
  const signInWithGoogle = useCallback(async (next?: string) => {
    const destination = safeNextPath(next ?? loginNext);
    const supabase = createClient();
    if (!supabase) {
      setAuthError(
        "Google sign-in is not configured yet. Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to frontend/.env.local."
      );
      return;
    }

    setAuthError(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(destination)}`,
      },
    });

    if (error) {
      setAuthError(error.message);
    }
  }, [loginNext]);

  // Clear session and return home
  const signOut = useCallback(async () => {
    const supabase = createClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    try {
      localStorage.removeItem("bb_eval_experience");
    } catch {
      /* ignore */
    }
    setUser(null);
    closeLogin();
    router.push("/");
    router.refresh();
  }, [closeLogin, router]);

  const value = useMemo(
    () => ({
      user,
      loading,
      configured,
      isAdmin,
      requestLogin,
      signInWithGoogle,
      signOut,
    }),
    [user, loading, configured, isAdmin, requestLogin, signInWithGoogle, signOut]
  );

  return (
    <AuthContext.Provider value={value}>
      <Suspense fallback={null}>
        <LoginQueryReader />
      </Suspense>
      {children}
      <LoginPrompt
        open={loginOpen}
        nextPath={loginNext}
        error={authError}
        onClose={closeLogin}
        onContinue={() => {
          markConsentGiven();
          void signInWithGoogle(loginNext);
        }}
      />
    </AuthContext.Provider>
  );
}

function LoginQueryReader() {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, requestLogin } = useAuth();

  useEffect(() => {
    if (loading || user) return;
    if (params.get("login") !== "1") return;
    requestLogin(safeNextPath(params.get("next")));
    router.replace(pathname);
  }, [loading, params, pathname, requestLogin, router, user]);

  return null;
}
