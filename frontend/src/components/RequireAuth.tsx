"use client";

/**
 * Auth gate wrapper.
 * Redirects unauthenticated users away from protected pages.
 */

import { useEffect } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import Navbar from "@/components/Navbar";

export default function RequireAuth({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  // Send guests to home with the login modal open
  useEffect(() => {
    if (loading || user) return;
    const next = encodeURIComponent(pathname);
    router.replace(`/?login=1&next=${next}`);
  }, [loading, pathname, router, user]);

  if (loading || !user) {
    return (
      <main id="main-content" className="min-h-screen bg-ink flex flex-col">
        <Navbar />
      </main>
    );
  }

  return children;
}
