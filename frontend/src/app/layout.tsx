/**
 * Root app layout.
 * Loads fonts providers navbar shell and global styles.
 */

import type { Metadata } from "next";
// Reference: https://nextjs.org/docs/app/building-your-application/optimizing/fonts
import { Inria_Serif } from "next/font/google";
import MotionProvider from "@/components/MotionProvider";
import AuthProvider from "@/components/AuthProvider";
import "./globals.css";

const inriaSerif = Inria_Serif({
  weight: ["300", "400", "700"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-inria-serif",
});

export const metadata: Metadata = {
  title: "Brandbit",
  description: "Speed-up Brand Ideation bit-by-bit.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inriaSerif.variable}>
      <body className={`${inriaSerif.className} bg-ink min-h-screen text-nav font-serif`}>
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <MotionProvider>
          <AuthProvider>{children}</AuthProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
