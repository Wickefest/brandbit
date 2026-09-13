"use client";

/**
 * Home landing page.
 * Brand hero and entry into the submission flow.
 */

import { useEffect, useRef } from "react";
// Reference: https://nextjs.org/docs/app/api-reference/functions/use-router
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import GoldButton from "@/components/GoldButton";
import { useAuth } from "@/components/AuthProvider";

export default function Home() {
  // Navigation and auth state for the start CTA
  const router = useRouter();
  const { user, loading, requestLogin } = useAuth();
  const videoRef = useRef<HTMLVideoElement>(null);

  // Autoplay muted hero video once the element is ready
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = true;
    video.volume = 0;
    video.play().catch(() => {});
  }, []);

  return (
    <main id="main-content" className="relative min-h-screen overflow-hidden flex flex-col">
      {/* Hero video background */}
      <div className="absolute inset-0">
        <video
          ref={videoRef}
          className="absolute inset-0 h-full w-full object-cover"
          src="/assets/images/hero-water.mp4"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-ink-overlay/60" />
      </div>

      <div className="relative z-10 flex flex-col min-h-screen">
        <Navbar />

        {/* Main content */}
        <div className="flex-1 flex flex-col items-center justify-center px-8 pb-16 text-center">
          <h1 className="text-[#FFECEC] text-[clamp(3rem,8vw,6rem)] font-bold leading-[1.05] max-w-[720px]">
            Speed-up Brand Ideation
            <br />
            bit-by-bit.
          </h1>
          <p className="text-nav text-base font-light leading-[25px] max-w-[775px] mt-8">
            Start by submitting a single image. This archive returns fragrance, a
            music starting point, and a report explaining how the three belong to
            one brand. New entries are filed under a number and a name.
          </p>
          <div className="mt-10 flex flex-col items-center gap-4">
            {/* Start process or ask for login first */}
            <GoldButton
              disabled={loading}
              onClick={() => {
                if (loading) return;
                if (!user) {
                  requestLogin("/submit");
                  return;
                }
                router.push("/submit");
              }}
            >
              START PROCESS
            </GoldButton>
          </div>
        </div>
      </div>
    </main>
  );
}
