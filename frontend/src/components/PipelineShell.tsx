/**
 * Shared pipeline page shell.
 * Common title and layout for submit process and results.
 */

import type { ReactNode } from "react";

const TITLE_CLASS =
  "text-white text-5xl font-bold mt-[21px] mb-8 shrink-0";

const SHELL_CLASS =
  "flex-1 px-10 pb-8 max-w-[1466px] mx-auto w-full flex flex-col min-h-0";

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
