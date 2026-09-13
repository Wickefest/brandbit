-- Brandbit Supabase setup
-- Prisma owns tables/enums. This file owns auth linkage, CHECKs, triggers, RLS, storage, library.

-- Enable pgcrypto for gen_random_uuid() where needed.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Link profiles.id to Supabase Auth users (cascade delete).
ALTER TABLE public.profiles
  DROP CONSTRAINT IF EXISTS profiles_id_fkey;
ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_id_fkey
  FOREIGN KEY (id) REFERENCES auth.users (id) ON DELETE CASCADE;

-- Allow evaluation item display_order values from 1 through 10.
ALTER TABLE public.evaluation_items
  DROP CONSTRAINT IF EXISTS evaluation_items_display_order_check;
ALTER TABLE public.evaluation_items
  ADD CONSTRAINT evaluation_items_display_order_check
  CHECK (display_order >= 1 AND display_order <= 10);

-- Enforce Likert score columns on evaluation_responses must be between 1 and 5.
DO $$
DECLARE
  col text;
BEGIN
  FOREACH col IN ARRAY ARRAY[
    'descriptor_accuracy',
    'brand_coherence',
    'fragrance_alignment',
    'music_alignment',
    'cross_modal_congruence',
    'creativity',
    'ideation_usefulness',
    'overall_quality'
  ]
  LOOP
    EXECUTE format(
      'ALTER TABLE public.evaluation_responses DROP CONSTRAINT IF EXISTS evaluation_responses_%s_check',
      col
    );
    EXECUTE format(
      'ALTER TABLE public.evaluation_responses ADD CONSTRAINT evaluation_responses_%s_check CHECK (%I BETWEEN 1 AND 5)',
      col, col
    );
  END LOOP;
END $$;

-- Add prior-experience and research-consent columns on profiles.
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS experience_perfumery boolean,
  ADD COLUMN IF NOT EXISTS experience_music boolean,
  ADD COLUMN IF NOT EXISTS experience_design boolean,
  ADD COLUMN IF NOT EXISTS consented_at timestamptz,
  ADD COLUMN IF NOT EXISTS consent_version text,
  ADD COLUMN IF NOT EXISTS generation_count integer NOT NULL DEFAULT 0;

-- Create participant profile automatically on Google sign-in.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, role)
  VALUES (NEW.id, 'participant')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

-- Remove old auth signup trigger if present before recreating.
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Fire handle_new_user after each new auth.users row.
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- Backfill profiles for any auth users that already exist.
INSERT INTO public.profiles (id, role)
SELECT id, 'participant'
FROM auth.users
ON CONFLICT (id) DO NOTHING;

-- Block clients from escalating their own profiles.role.
CREATE OR REPLACE FUNCTION public.protect_profile_role()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF NEW.role IS DISTINCT FROM OLD.role AND auth.uid() IS NOT NULL THEN
    RAISE EXCEPTION 'profiles.role can only be changed by a trusted operator'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;

-- Remove old role-protection trigger if present before recreating.
DROP TRIGGER IF EXISTS trg_protect_profile_role ON public.profiles;

-- Prevent role changes on profiles unless done by a trusted operator.
CREATE TRIGGER trg_protect_profile_role
  BEFORE UPDATE OF role ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.protect_profile_role();

-- Cap participant generation_count at 5 (admins uncapped).
CREATE OR REPLACE FUNCTION public.enforce_generation_cap()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF NEW.role IS DISTINCT FROM 'admin' AND NEW.generation_count > 5 THEN
    RAISE EXCEPTION 'accounts may run at most 5 generations' USING ERRCODE = '23514';
  END IF;
  IF NEW.generation_count < 0 THEN
    NEW.generation_count := 0;
  END IF;
  RETURN NEW;
END;
$$;

-- Remove old generation-cap trigger if present before recreating.
DROP TRIGGER IF EXISTS trg_profiles_generation_cap ON public.profiles;

-- Enforce generation_count cap on profiles insert/update.
CREATE TRIGGER trg_profiles_generation_cap
  BEFORE INSERT OR UPDATE OF generation_count, role ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_generation_cap();

-- Limit each evaluation to at most 10 evaluation_items.
CREATE OR REPLACE FUNCTION public.enforce_max_evaluation_items()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF (
    SELECT count(*)::integer
    FROM public.evaluation_items
    WHERE evaluation_id = NEW.evaluation_id
      AND id IS DISTINCT FROM NEW.id
  ) >= 10 THEN
    RAISE EXCEPTION 'an evaluation may contain at most 10 evaluation_items'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

-- Remove legacy max-five and current max-item triggers before recreating.
DROP TRIGGER IF EXISTS trg_evaluation_items_max_five ON public.evaluation_items;
DROP TRIGGER IF EXISTS trg_evaluation_items_max ON public.evaluation_items;

-- Enforce the 10-item cap when items are inserted or moved.
CREATE TRIGGER trg_evaluation_items_max
  BEFORE INSERT OR UPDATE OF evaluation_id ON public.evaluation_items
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_max_evaluation_items();

-- Drop obsolete five-item helper if an older deploy left it behind.
DROP FUNCTION IF EXISTS public.enforce_max_five_evaluation_items();

-- Freeze evaluation_items unless the parent evaluation is still draft.
CREATE OR REPLACE FUNCTION public.evaluation_items_draft_only()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  new_status text;
  old_status text;
BEGIN
  IF TG_OP = 'DELETE' THEN
    SELECT status::text INTO old_status FROM public.evaluations WHERE id = OLD.evaluation_id;
    IF old_status IS DISTINCT FROM 'draft' THEN
      RAISE EXCEPTION 'evaluation_items can only be removed while draft' USING ERRCODE = '23514';
    END IF;
    RETURN OLD;
  END IF;

  SELECT status::text INTO new_status FROM public.evaluations WHERE id = NEW.evaluation_id;
  IF new_status IS DISTINCT FROM 'draft' THEN
    RAISE EXCEPTION 'evaluation_items can only be changed while draft' USING ERRCODE = '23514';
  END IF;

  IF TG_OP = 'UPDATE' AND NEW.evaluation_id IS DISTINCT FROM OLD.evaluation_id THEN
    SELECT status::text INTO old_status FROM public.evaluations WHERE id = OLD.evaluation_id;
    IF old_status IS DISTINCT FROM 'draft' THEN
      RAISE EXCEPTION 'evaluation_items can only be moved while draft' USING ERRCODE = '23514';
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

-- Remove old draft-only items trigger if present before recreating.
DROP TRIGGER IF EXISTS trg_evaluation_items_draft_only ON public.evaluation_items;

-- Block item changes when the evaluation is not draft.
CREATE TRIGGER trg_evaluation_items_draft_only
  BEFORE INSERT OR UPDATE OR DELETE ON public.evaluation_items
  FOR EACH ROW
  EXECUTE FUNCTION public.evaluation_items_draft_only();

-- Helper: true when the current auth user has role admin.
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.profiles
    WHERE id = auth.uid() AND role = 'admin'
  );
$$;

-- Lock down is_admin execute grants to authenticated/service only.
REVOKE ALL ON FUNCTION public.is_admin() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_admin() TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_admin() TO service_role;

-- Turn on RLS for core evaluation tables.
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evaluation_responses ENABLE ROW LEVEL SECURITY;

-- Drop old profiles select policy before recreating.
DROP POLICY IF EXISTS profiles_select_own_or_admin ON public.profiles;

-- Let users read their own profile (admins can read all).
CREATE POLICY profiles_select_own_or_admin ON public.profiles
  FOR SELECT TO authenticated
  USING (id = auth.uid() OR public.is_admin());

-- Drop old profiles update policy before recreating.
DROP POLICY IF EXISTS profiles_update_own ON public.profiles;

-- Let users update their own profile row only.
CREATE POLICY profiles_update_own ON public.profiles
  FOR UPDATE TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- Drop old evaluations select policy before recreating.
DROP POLICY IF EXISTS evaluations_select_active_or_admin ON public.evaluations;

-- Participants see active evaluations; admins see all.
CREATE POLICY evaluations_select_active_or_admin ON public.evaluations
  FOR SELECT TO authenticated
  USING (status = 'active' OR public.is_admin());

-- Drop old evaluations insert policy before recreating.
DROP POLICY IF EXISTS evaluations_insert_admin ON public.evaluations;

-- Only admins may create evaluations (as themselves).
CREATE POLICY evaluations_insert_admin ON public.evaluations
  FOR INSERT TO authenticated
  WITH CHECK (public.is_admin() AND created_by = auth.uid());

-- Drop old evaluations update policy before recreating.
DROP POLICY IF EXISTS evaluations_update_admin ON public.evaluations;

-- Only admins may update evaluations.
CREATE POLICY evaluations_update_admin ON public.evaluations
  FOR UPDATE TO authenticated
  USING (public.is_admin()) WITH CHECK (public.is_admin());

-- Drop old evaluations delete policy before recreating.
DROP POLICY IF EXISTS evaluations_delete_admin ON public.evaluations;

-- Only admins may delete evaluations.
CREATE POLICY evaluations_delete_admin ON public.evaluations
  FOR DELETE TO authenticated
  USING (public.is_admin());

-- Drop old evaluation_items select policy before recreating.
DROP POLICY IF EXISTS evaluation_items_select_active_or_admin ON public.evaluation_items;

-- Items readable when parent evaluation is active (or caller is admin).
CREATE POLICY evaluation_items_select_active_or_admin ON public.evaluation_items
  FOR SELECT TO authenticated
  USING (
    public.is_admin()
    OR EXISTS (
      SELECT 1 FROM public.evaluations e
      WHERE e.id = evaluation_id AND e.status = 'active'
    )
  );

-- Drop old evaluation_items insert policy before recreating.
DROP POLICY IF EXISTS evaluation_items_insert_admin_draft ON public.evaluation_items;

-- Admins may insert items only while the evaluation is draft.
CREATE POLICY evaluation_items_insert_admin_draft ON public.evaluation_items
  FOR INSERT TO authenticated
  WITH CHECK (
    public.is_admin()
    AND EXISTS (
      SELECT 1 FROM public.evaluations e
      WHERE e.id = evaluation_id AND e.status = 'draft'
    )
  );

-- Drop old evaluation_items update policy before recreating.
DROP POLICY IF EXISTS evaluation_items_update_admin_draft ON public.evaluation_items;

-- Admins may update items only while the evaluation is draft.
CREATE POLICY evaluation_items_update_admin_draft ON public.evaluation_items
  FOR UPDATE TO authenticated
  USING (
    public.is_admin()
    AND EXISTS (
      SELECT 1 FROM public.evaluations e
      WHERE e.id = evaluation_id AND e.status = 'draft'
    )
  )
  WITH CHECK (
    public.is_admin()
    AND EXISTS (
      SELECT 1 FROM public.evaluations e
      WHERE e.id = evaluation_id AND e.status = 'draft'
    )
  );

-- Drop old evaluation_items delete policy before recreating.
DROP POLICY IF EXISTS evaluation_items_delete_admin_draft ON public.evaluation_items;

-- Admins may delete items only while the evaluation is draft.
CREATE POLICY evaluation_items_delete_admin_draft ON public.evaluation_items
  FOR DELETE TO authenticated
  USING (
    public.is_admin()
    AND EXISTS (
      SELECT 1 FROM public.evaluations e
      WHERE e.id = evaluation_id AND e.status = 'draft'
    )
  );

-- Drop old evaluation_responses select policy before recreating.
DROP POLICY IF EXISTS evaluation_responses_select_own_or_admin ON public.evaluation_responses;

-- Participants read own responses; admins read all.
CREATE POLICY evaluation_responses_select_own_or_admin ON public.evaluation_responses
  FOR SELECT TO authenticated
  USING (participant_id = auth.uid() OR public.is_admin());

-- Drop old evaluation_responses insert policy before recreating.
DROP POLICY IF EXISTS evaluation_responses_insert_own_active ON public.evaluation_responses;

-- Participants may insert ratings only on active evaluation items.
CREATE POLICY evaluation_responses_insert_own_active ON public.evaluation_responses
  FOR INSERT TO authenticated
  WITH CHECK (
    participant_id = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.evaluation_items ei
      JOIN public.evaluations e ON e.id = ei.evaluation_id
      WHERE ei.id = evaluation_item_id AND e.status = 'active'
    )
  );

-- Drop old evaluation_responses update policy before recreating.
DROP POLICY IF EXISTS evaluation_responses_update_own_active ON public.evaluation_responses;

-- Participants may update their ratings only on active evaluation items.
CREATE POLICY evaluation_responses_update_own_active ON public.evaluation_responses
  FOR UPDATE TO authenticated
  USING (
    participant_id = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.evaluation_items ei
      JOIN public.evaluations e ON e.id = ei.evaluation_id
      WHERE ei.id = evaluation_item_id AND e.status = 'active'
    )
  )
  WITH CHECK (
    participant_id = auth.uid()
    AND EXISTS (
      SELECT 1
      FROM public.evaluation_items ei
      JOIN public.evaluations e ON e.id = ei.evaluation_id
      WHERE ei.id = evaluation_item_id AND e.status = 'active'
    )
  );

-- Deny anonymous access to evaluation tables.
REVOKE ALL ON TABLE public.profiles FROM anon;
REVOKE ALL ON TABLE public.evaluations FROM anon;
REVOKE ALL ON TABLE public.evaluation_items FROM anon;
REVOKE ALL ON TABLE public.evaluation_responses FROM anon;

-- Grant authenticated app roles on evaluation tables.
GRANT SELECT, UPDATE ON TABLE public.profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.evaluations TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.evaluation_items TO authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.evaluation_responses TO authenticated;

-- Grant service_role full access on evaluation tables.
GRANT ALL ON TABLE public.profiles TO service_role;
GRANT ALL ON TABLE public.evaluations TO service_role;
GRANT ALL ON TABLE public.evaluation_items TO service_role;
GRANT ALL ON TABLE public.evaluation_responses TO service_role;

-- Create/update public bucket for evaluation stimulus images.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'evaluation-images',
  'evaluation-images',
  true,
  10485760,
  ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO UPDATE
SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Drop old evaluation-images select policy before recreating.
DROP POLICY IF EXISTS evaluation_images_select_public ON storage.objects;

-- Anyone may read evaluation images.
CREATE POLICY evaluation_images_select_public ON storage.objects
  FOR SELECT TO public
  USING (bucket_id = 'evaluation-images');

-- Drop old evaluation-images insert policy before recreating.
DROP POLICY IF EXISTS evaluation_images_insert_admin ON storage.objects;

-- Only admins may upload evaluation images.
CREATE POLICY evaluation_images_insert_admin ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'evaluation-images' AND public.is_admin());

-- Drop old evaluation-images update policy before recreating.
DROP POLICY IF EXISTS evaluation_images_update_admin ON storage.objects;

-- Only admins may update evaluation images.
CREATE POLICY evaluation_images_update_admin ON storage.objects
  FOR UPDATE TO authenticated
  USING (bucket_id = 'evaluation-images' AND public.is_admin())
  WITH CHECK (bucket_id = 'evaluation-images' AND public.is_admin());

-- Drop old evaluation-images delete policy before recreating.
DROP POLICY IF EXISTS evaluation_images_delete_admin ON storage.objects;

-- Only admins may delete evaluation images.
CREATE POLICY evaluation_images_delete_admin ON storage.objects
  FOR DELETE TO authenticated
  USING (bucket_id = 'evaluation-images' AND public.is_admin());

-- Store personal/shared generation archives for the Library page.
CREATE TABLE IF NOT EXISTS public.library_entries (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES public.profiles (id) ON DELETE CASCADE,
  execution_id text NOT NULL,
  title text NOT NULL,
  summary text NOT NULL,
  mode text,
  image_url text,
  generated_output jsonb NOT NULL,
  saved_at timestamptz NOT NULL DEFAULT now(),
  viewed_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT library_entries_user_execution_unique UNIQUE (user_id, execution_id)
);

-- Mark admin-shared library entries visible to other authenticated users.
ALTER TABLE public.library_entries
  ADD COLUMN IF NOT EXISTS is_shared boolean NOT NULL DEFAULT false;

-- Speed up library lists sorted by last viewed.
CREATE INDEX IF NOT EXISTS library_entries_user_viewed_idx
  ON public.library_entries (user_id, viewed_at DESC);

-- Speed up library lists sorted by saved time.
CREATE INDEX IF NOT EXISTS library_entries_user_saved_idx
  ON public.library_entries (user_id, saved_at DESC);

-- Speed up lookups of shared library entries.
CREATE INDEX IF NOT EXISTS library_entries_shared_idx
  ON public.library_entries (is_shared)
  WHERE is_shared = true;

-- Turn on RLS for library_entries.
ALTER TABLE public.library_entries ENABLE ROW LEVEL SECURITY;

-- Cap personal libraries at 5; only admins may create shared entries.
CREATE OR REPLACE FUNCTION public.enforce_library_caps()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
  personal_count integer;
BEGIN
  IF public.is_admin() THEN
    RETURN NEW;
  END IF;

  IF NEW.is_shared IS TRUE THEN
    RAISE EXCEPTION 'only admins can create shared library entries' USING ERRCODE = '42501';
  END IF;

  SELECT COUNT(*)::integer INTO personal_count
  FROM public.library_entries
  WHERE user_id = NEW.user_id
    AND is_shared = false
    AND id IS DISTINCT FROM NEW.id;

  IF TG_OP = 'INSERT' AND personal_count >= 5 THEN
    RAISE EXCEPTION 'personal library may contain at most 5 entries' USING ERRCODE = '23514';
  END IF;
  IF TG_OP = 'UPDATE'
    AND OLD.is_shared IS TRUE
    AND NEW.is_shared IS FALSE
    AND personal_count >= 5 THEN
    RAISE EXCEPTION 'personal library may contain at most 5 entries' USING ERRCODE = '23514';
  END IF;

  RETURN NEW;
END;
$$;

-- Remove old library-cap trigger if present before recreating.
DROP TRIGGER IF EXISTS trg_library_entries_caps ON public.library_entries;

-- Enforce personal/shared library caps on insert/update.
CREATE TRIGGER trg_library_entries_caps
  BEFORE INSERT OR UPDATE OF is_shared, user_id ON public.library_entries
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_library_caps();

-- Drop superseded own-only library select policies before recreating.
DROP POLICY IF EXISTS library_entries_select_own ON public.library_entries;
DROP POLICY IF EXISTS library_entries_select_own_or_shared ON public.library_entries;

-- Users can read their own entries plus any shared entries.
CREATE POLICY library_entries_select_own_or_shared ON public.library_entries
  FOR SELECT TO authenticated
  USING (user_id = auth.uid() OR is_shared = true);

-- Drop old library insert policy before recreating.
DROP POLICY IF EXISTS library_entries_insert_own ON public.library_entries;

-- Users insert their own entries; only admins may set is_shared.
CREATE POLICY library_entries_insert_own ON public.library_entries
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = auth.uid()
    AND (
      is_shared = false
      OR public.is_admin()
    )
  );

-- Drop superseded library update policies before recreating.
DROP POLICY IF EXISTS library_entries_update_own ON public.library_entries;
DROP POLICY IF EXISTS library_entries_update_own_or_admin_shared ON public.library_entries;

-- Owner or admin may update; shared flag still admin-only via WITH CHECK.
CREATE POLICY library_entries_update_own_or_admin_shared ON public.library_entries
  FOR UPDATE TO authenticated
  USING (user_id = auth.uid() OR public.is_admin())
  WITH CHECK (
    user_id = auth.uid()
    AND (
      is_shared = false
      OR public.is_admin()
    )
  );

-- Drop superseded library delete policies before recreating.
DROP POLICY IF EXISTS library_entries_delete_own ON public.library_entries;
DROP POLICY IF EXISTS library_entries_delete_own_or_admin_shared ON public.library_entries;

-- Owners delete personal entries; admins delete shared (or their own).
CREATE POLICY library_entries_delete_own_or_admin_shared ON public.library_entries
  FOR DELETE TO authenticated
  USING (
    (user_id = auth.uid() AND is_shared = false)
    OR (public.is_admin() AND is_shared = true)
    OR (user_id = auth.uid() AND public.is_admin())
  );

-- Deny anonymous access to library_entries.
REVOKE ALL ON TABLE public.library_entries FROM anon;

-- Grant authenticated CRUD on library_entries.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.library_entries TO authenticated;

-- Grant service_role full access on library_entries.
GRANT ALL ON TABLE public.library_entries TO service_role;

-- Store peer ratings against shared library entries.
CREATE TABLE IF NOT EXISTS public.library_ratings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  library_entry_id uuid NOT NULL REFERENCES public.library_entries (id) ON DELETE CASCADE,
  participant_id uuid NOT NULL REFERENCES public.profiles (id) ON DELETE CASCADE,
  descriptor_accuracy smallint NOT NULL,
  brand_coherence smallint NOT NULL,
  fragrance_alignment smallint NOT NULL,
  music_alignment smallint NOT NULL,
  cross_modal_congruence smallint NOT NULL,
  creativity smallint NOT NULL,
  ideation_usefulness smallint NOT NULL,
  overall_quality smallint NOT NULL,
  comments text,
  submitted_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT library_ratings_participant_entry_unique UNIQUE (participant_id, library_entry_id)
);

-- Enforce Likert score columns on library_ratings must be between 1 and 5.
DO $$
DECLARE
  col text;
BEGIN
  FOREACH col IN ARRAY ARRAY[
    'descriptor_accuracy',
    'brand_coherence',
    'fragrance_alignment',
    'music_alignment',
    'cross_modal_congruence',
    'creativity',
    'ideation_usefulness',
    'overall_quality'
  ]
  LOOP
    EXECUTE format(
      'ALTER TABLE public.library_ratings DROP CONSTRAINT IF EXISTS library_ratings_%s_check',
      col
    );
    EXECUTE format(
      'ALTER TABLE public.library_ratings ADD CONSTRAINT library_ratings_%s_check CHECK (%I BETWEEN 1 AND 5)',
      col, col
    );
  END LOOP;
END $$;

-- Speed up ratings lookup by library entry.
CREATE INDEX IF NOT EXISTS library_ratings_entry_idx
  ON public.library_ratings (library_entry_id);

-- Speed up ratings lookup by participant.
CREATE INDEX IF NOT EXISTS library_ratings_participant_idx
  ON public.library_ratings (participant_id);

-- Turn on RLS for library_ratings.
ALTER TABLE public.library_ratings ENABLE ROW LEVEL SECURITY;

-- Only allow ratings on entries marked is_shared.
CREATE OR REPLACE FUNCTION public.enforce_library_rating_shared()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.library_entries e
    WHERE e.id = NEW.library_entry_id AND e.is_shared = true
  ) THEN
    RAISE EXCEPTION 'ratings are only allowed on shared library entries' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END;
$$;

-- Remove old shared-rating trigger if present before recreating.
DROP TRIGGER IF EXISTS trg_library_ratings_shared ON public.library_ratings;

-- Enforce shared-only ratings on insert/update of library_entry_id.
CREATE TRIGGER trg_library_ratings_shared
  BEFORE INSERT OR UPDATE OF library_entry_id ON public.library_ratings
  FOR EACH ROW
  EXECUTE FUNCTION public.enforce_library_rating_shared();

-- Drop old library_ratings select policy before recreating.
DROP POLICY IF EXISTS library_ratings_select_own_or_admin ON public.library_ratings;

-- Participants read own ratings; admins read all.
CREATE POLICY library_ratings_select_own_or_admin ON public.library_ratings
  FOR SELECT TO authenticated
  USING (participant_id = auth.uid() OR public.is_admin());

-- Drop old library_ratings insert policy before recreating.
DROP POLICY IF EXISTS library_ratings_insert_own ON public.library_ratings;

-- Participants may rate shared library entries once (unique constraint).
CREATE POLICY library_ratings_insert_own ON public.library_ratings
  FOR INSERT TO authenticated
  WITH CHECK (
    participant_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.library_entries e
      WHERE e.id = library_entry_id AND e.is_shared = true
    )
  );

-- Ratings are one-shot: remove any participant update policy if present.
DROP POLICY IF EXISTS library_ratings_update_own ON public.library_ratings;

-- Grant authenticated select/insert on library_ratings.
GRANT SELECT, INSERT ON TABLE public.library_ratings TO authenticated;

-- Grant service_role full access on library_ratings.
GRANT ALL ON TABLE public.library_ratings TO service_role;

-- Create/update public bucket for library thumbnail images.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'library-images',
  'library-images',
  true,
  5242880,
  ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO UPDATE
SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Drop old library-images select policy before recreating.
DROP POLICY IF EXISTS library_images_select_public ON storage.objects;

-- Anyone may read library images.
CREATE POLICY library_images_select_public ON storage.objects
  FOR SELECT TO public
  USING (bucket_id = 'library-images');

-- Drop old library-images insert policy before recreating.
DROP POLICY IF EXISTS library_images_insert_own ON storage.objects;

-- Users may upload only under their own user_id folder.
CREATE POLICY library_images_insert_own ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'library-images'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Drop old library-images update policy before recreating.
DROP POLICY IF EXISTS library_images_update_own ON storage.objects;

-- Users may update only objects under their own user_id folder.
CREATE POLICY library_images_update_own ON storage.objects
  FOR UPDATE TO authenticated
  USING (
    bucket_id = 'library-images'
    AND (storage.foldername(name))[1] = auth.uid()::text
  )
  WITH CHECK (
    bucket_id = 'library-images'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Drop old library-images delete policy before recreating.
DROP POLICY IF EXISTS library_images_delete_own ON storage.objects;

-- Users may delete only objects under their own user_id folder.
CREATE POLICY library_images_delete_own ON storage.objects
  FOR DELETE TO authenticated
  USING (
    bucket_id = 'library-images'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Create/update public bucket for library MusicGen audio.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'library-audio',
  'library-audio',
  true,
  20971520,
  ARRAY['audio/wav', 'audio/x-wav', 'audio/wave', 'audio/mpeg', 'audio/mp3']
)
ON CONFLICT (id) DO UPDATE
SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

-- Drop old library-audio select policy before recreating.
DROP POLICY IF EXISTS library_audio_select_public ON storage.objects;

-- Anyone may read library audio.
CREATE POLICY library_audio_select_public ON storage.objects
  FOR SELECT TO public
  USING (bucket_id = 'library-audio');

-- Drop old library-audio insert policy before recreating.
DROP POLICY IF EXISTS library_audio_insert_own ON storage.objects;

-- Users may upload audio only under their own user_id folder.
CREATE POLICY library_audio_insert_own ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (
    bucket_id = 'library-audio'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Drop old library-audio update policy before recreating.
DROP POLICY IF EXISTS library_audio_update_own ON storage.objects;

-- Users may update audio only under their own user_id folder.
CREATE POLICY library_audio_update_own ON storage.objects
  FOR UPDATE TO authenticated
  USING (
    bucket_id = 'library-audio'
    AND (storage.foldername(name))[1] = auth.uid()::text
  )
  WITH CHECK (
    bucket_id = 'library-audio'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Drop old library-audio delete policy before recreating.
DROP POLICY IF EXISTS library_audio_delete_own ON storage.objects;

-- Users may delete audio only under their own user_id folder.
CREATE POLICY library_audio_delete_own ON storage.objects
  FOR DELETE TO authenticated
  USING (
    bucket_id = 'library-audio'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

-- Optional: promote yourself after first Google login
-- UPDATE public.profiles AS p SET role = 'admin'
-- FROM auth.users AS u WHERE p.id = u.id AND u.email = 'you@gmail.com';
