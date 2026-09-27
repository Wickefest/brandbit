"use client";

/**
 * Primary brand button.
 * Shared gold CTA styling for key actions.
 */

import type { ButtonHTMLAttributes } from "react";

export default function GoldButton({
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`rounded-full bg-gold-soft text-white font-bold text-2xl leading-none px-8 py-[15px] min-w-[279px] whitespace-nowrap transition-opacity disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-nav ${className}`}
    >
      {children}
    </button>
  );
}
