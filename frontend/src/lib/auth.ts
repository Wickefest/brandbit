/**
 * Auth path helpers.
 * Protected prefixes and safe redirect path checks.
 */

export const PROTECTED_PREFIXES = [
  "/submit",
  "/library",
  "/process",
  "/results",
] as const;

export function isProtectedPath(pathname: string): boolean {
  return PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  );
}

export function isSupabaseConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();
  return Boolean(url && key);
}

/** Only allow in-app relative paths. */
export function safeNextPath(raw: string | null | undefined): string {
  if (!raw) return "/";
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.includes("://")) {
    return "/";
  }
  return raw;
}

export function avatarUrlFromUser(user: {
  user_metadata?: Record<string, unknown>;
} | null): string | null {
  const meta = user?.user_metadata;
  if (!meta) return null;
  const url = meta.avatar_url || meta.picture;
  return typeof url === "string" && url.length > 0 ? url : null;
}
