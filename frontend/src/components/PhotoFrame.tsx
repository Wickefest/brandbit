/**
 * Photo frame layout helper.
 * Consistent framing around brand images.
 */

import type { ReactNode } from "react";

export default function PhotoFrame({
  children,
  className = "",
  innerClassName = "",
}: {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
}) {
  return (
    <div className={`bg-gold rounded-[10px] p-3 ${className}`}>
      <div
        className={`bg-white rounded-[10px] overflow-hidden h-full ${innerClassName}`}
      >
        {children}
      </div>
    </div>
  );
}
