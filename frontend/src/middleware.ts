/**
 * Next.js edge middleware entry.
 * Refreshes the Supabase session and gates protected routes.
 */

// Reference: https://nextjs.org/docs/app/building-your-application/routing/middleware
import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|assets|.*\\.(?:svg|png|jpg|jpeg|gif|webp|mp4)$).*)",
  ],
};
