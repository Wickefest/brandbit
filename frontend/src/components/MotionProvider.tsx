"use client";

/**
 * Motion config provider.
 * Wraps the app with shared animation settings.
 */

// Reference: https://motion.dev/docs/react-motion-config
import { LayoutGroup, MotionConfig } from "motion/react";
import type { ReactNode } from "react";

export default function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <LayoutGroup id="brandbit">{children}</LayoutGroup>
    </MotionConfig>
  );
}
