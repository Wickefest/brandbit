/**
 * Research consent helpers.
 * Local and profile consent flags for study participation.
 */

import { createClient } from "@/lib/supabase/client";

export const CONSENT_FLAG_KEY = "bb_research_consent";
export const CONSENT_VERSION = "research-info-v1";

export function markConsentGiven() {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(CONSENT_FLAG_KEY, "1");
}

export async function persistResearchConsent(userId: string): Promise<void> {
  if (typeof window === "undefined") return;
  if (sessionStorage.getItem(CONSENT_FLAG_KEY) !== "1") return;

  const supabase = createClient();
  if (!supabase) return;

  const { data } = await supabase
    .from("profiles")
    .select("consented_at")
    .eq("id", userId)
    .maybeSingle();

  if (data?.consented_at) {
    sessionStorage.removeItem(CONSENT_FLAG_KEY);
    return;
  }

  const { error } = await supabase
    .from("profiles")
    .update({
      consented_at: new Date().toISOString(),
      consent_version: CONSENT_VERSION,
    })
    .eq("id", userId);

  if (!error) sessionStorage.removeItem(CONSENT_FLAG_KEY);
}
