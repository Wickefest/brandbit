/**
 * Shared pipeline page shell.
 * Common title and layout for submit process and results.
 */

import type { ReactNode } from "react";

const TITLE_CLASS =
  "text-white text-3xl sm:text-4xl md:text-5xl font-bold mt-4 md:mt-[21px] mb-6 md:mb-8 shrink-0";

const SHELL_CLASS =
  "flex-1 px-4 sm:px-6 md:px-10 pb-8 max-w-[1466px] mx-auto w-full flex flex-col min-h-0 overflow-x-hidden";

export default function PipelineShell({
  title = "Orchestration Pipeline",
  children,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`${SHELL_CLASS} ${className}`}>
      <h1 className={TITLE_CLASS}>{title}</h1>
      {children}
    </div>
  );
}
