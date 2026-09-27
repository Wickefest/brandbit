"use client";

/**
 * Home landing page.
 * Brand hero and entry into the submission flow.
 */

import { useEffect, useRef, useState } from "react";
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
  const [videoReady, setVideoReady] = useState(false);

  // Autoplay muted hero video; hide until playing so iOS cannot show a play glyph
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    video.setAttribute("playsinline", "true");
    video.setAttribute("webkit-playsinline", "true");
    video.defaultMuted = true;
    video.muted = true;
    video.volume = 0;

    const tryPlay = () => {
      video.defaultMuted = true;
      video.muted = true;
      video.volume = 0;
      const play = video.play();
      if (play && typeof play.then === "function") {
        play
          .then(() => setVideoReady(true))
          .catch(() => setVideoReady(false));
      }
    };

    const onPlaying = () => setVideoReady(true);

    tryPlay();
    video.addEventListener("loadeddata", tryPlay);
    video.addEventListener("canplay", tryPlay);
    video.addEventListener("playing", onPlaying);
    return () => {
      video.removeEventListener("loadeddata", tryPlay);
      video.removeEventListener("canplay", tryPlay);
      video.removeEventListener("playing", onPlaying);
    };
  }, []);

  return (
    <main id="main-content" className="relative min-h-screen overflow-hidden flex flex-col">
      {/* Ink fallback hides native play chrome if autoplay fails */}
      <div className="absolute inset-0 bg-ink">
        <video
          ref={videoRef}
          className={`hero-video absolute inset-0 h-full w-full object-cover pointer-events-none transition-opacity duration-500 ${
            videoReady ? "opacity-100" : "opacity-0"
          }`}
          src="/assets/images/hero-water.mp4"
          autoPlay
          loop
          muted
          playsInline
          preload="metadata"
          controls={false}
          disablePictureInPicture
          disableRemotePlayback
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-ink-overlay/60 pointer-events-none" />
      </div>

      <div className="relative z-10 flex flex-col min-h-screen">
        <Navbar />

        {/* Main content */}
        <div className="flex-1 flex flex-col items-center justify-center px-8 pb-16 text-center">
          <h1 className="text-[#FFECEC] text-[clamp(2.4rem,8vw,6rem)] font-bold leading-[1.05] max-w-[720px]">
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
