/**
 * OAuth callback route.
 * Exchanges the auth code for a session then redirects safely.
 */

import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { safeNextPath } from "@/lib/auth";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = safeNextPath(searchParams.get("next"));

  // Exchange the OAuth code for a session cookie
  // Reference: https://supabase.com/docs/reference/javascript/auth-exchangecodeforsession
  if (code) {
    const supabase = await createClient();
    if (supabase) {
      const { error } = await supabase.auth.exchangeCodeForSession(code);
      if (!error) {
        return NextResponse.redirect(`${origin}${next}`);
      }
    }
  }

  const fail = new URL("/", origin);
  fail.searchParams.set("login", "1");
  fail.searchParams.set("next", next);
  return NextResponse.redirect(fail);
}
