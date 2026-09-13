"use client";

/**
 * Top navigation bar.
 * Links auth state and login prompt entry.
 */

import { useEffect, useRef, useState } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/components/link
import Link from "next/link";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-pathname
import { usePathname, useRouter } from "next/navigation";
import { User } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { avatarUrlFromUser } from "@/lib/auth";

const AUTH_LINKS = [
  { href: "/", label: "Home" },
  { href: "/submit", label: "New Submission" },
  { href: "/library", label: "Library" },
] as const;

function ProfileControl() {
  const { user, loading, isAdmin, requestLogin, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onPointer = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  if (loading) {
    return (
      <span
        className="h-10 w-10 rounded-full border border-black/15 bg-black/5"
        aria-hidden="true"
      />
    );
  }

  if (!user) {
    return (
      <button
        type="button"
        onClick={() => requestLogin(pathname || "/")}
        className="flex h-10 w-10 items-center justify-center rounded-full border border-black/20 text-black cursor-pointer transition-transform duration-200 hover:scale-[1.04] hover:border-black/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-black"
        aria-label="Sign in"
      >
        <User size={22} strokeWidth={1.7} aria-hidden="true" />
      </button>
    );
  }

  const avatar = avatarUrlFromUser(user);

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setMenuOpen((open) => !open)}
        className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-black/20 text-black cursor-pointer transition-transform duration-200 hover:scale-[1.04] hover:border-black/40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-black"
        aria-label="Account"
        aria-expanded={menuOpen}
        aria-haspopup="menu"
      >
        {avatar ? (
          // Google-hosted avatar; <img> avoids next/image remote config.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={avatar}
            alt=""
            referrerPolicy="no-referrer"
            className="h-full w-full object-cover"
          />
        ) : (
          <User size={22} strokeWidth={1.7} aria-hidden="true" />
        )}
      </button>
      {menuOpen ? (
        <div
          role="menu"
          className="absolute left-0 top-[calc(100%+8px)] z-50 w-max min-w-[9.5rem] rounded-2xl border border-black/10 bg-nav py-1.5 text-black shadow-[0_14px_32px_rgba(0,0,0,0.28)]"
        >
          {isAdmin ? (
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                router.push("/export");
              }}
              className="w-full whitespace-nowrap px-4 py-2.5 text-left text-sm font-bold cursor-pointer transition-colors duration-150 hover:bg-black/5"
            >
              Export study data
            </button>
          ) : null}
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setMenuOpen(false);
              void signOut();
            }}
            className="w-full whitespace-nowrap px-4 py-2.5 text-left text-sm font-bold cursor-pointer transition-colors duration-150 hover:bg-red-50 hover:text-red-600"
          >
            Log out
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const links = user
    ? AUTH_LINKS
    : AUTH_LINKS.filter((link) => link.href === "/");

  const handleNewSubmission = () => {
    sessionStorage.clear();
    router.push("/submit");
  };

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    if (href === "/submit")
      return pathname === "/submit" || pathname === "/process";
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  const linkClass = (active: boolean) =>
    `relative cursor-pointer transition-all duration-200 hover:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-black after:absolute after:left-0 after:-bottom-1 after:h-[2px] after:bg-black after:transition-all after:duration-250 ${
      active
        ? "font-bold opacity-100 after:w-full"
        : "font-light opacity-75 hover:opacity-100 after:w-0 hover:after:w-full"
    }`;

  return (
    <nav className="relative z-40 px-10 pt-8 pb-4" aria-label="Primary">
      <div className="nav-gloss mx-auto max-w-[1466px] w-full h-20 rounded-full flex items-center justify-between px-[50px]">
        <span className="text-black text-[32px] font-bold leading-none transition-transform duration-200 hover:scale-[1.02] select-none">
          Brandbit
        </span>
        <div className="relative z-10 flex items-center gap-10 text-base text-black">
          {links.map((link) =>
            link.href === "/submit" ? (
              <button
                key={link.href}
                type="button"
                onClick={handleNewSubmission}
                className={linkClass(isActive(link.href))}
                aria-current={isActive(link.href) ? "page" : undefined}
              >
                {link.label}
              </button>
            ) : (
              <Link
                key={link.href}
                href={link.href}
                className={linkClass(isActive(link.href))}
                aria-current={isActive(link.href) ? "page" : undefined}
              >
                {link.label}
              </Link>
            )
          )}
          <ProfileControl />
        </div>
      </div>
    </nav>
  );
}
