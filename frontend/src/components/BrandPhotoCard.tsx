"use client";

/**
 * Brand photo display card.
 * Shows the uploaded or library product image.
 */

import { motion } from "motion/react";
import type { ReactNode } from "react";
import PhotoFrame from "@/components/PhotoFrame";

export const PHOTO_CARD_LAYOUT_ID = "brandbit-photo-card";

const spring = {
  type: "spring" as const,
  stiffness: 320,
  damping: 34,
  mass: 0.85,
};

export default function BrandPhotoCard({
  children,
  className = "",
  innerClassName = "",
}: {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
}) {
  return (
    <motion.div
      layoutId={PHOTO_CARD_LAYOUT_ID}
      transition={spring}
      className={`w-full sm:w-[470px] h-[537px] shrink-0 ${className}`}
    >
      <PhotoFrame className="h-full" innerClassName={innerClassName}>
        {children}
      </PhotoFrame>
    </motion.div>
  );
}
