import { createClient } from "@supabase/supabase-js";

// Cloud sync is optional: without these two settings the app runs exactly as
// before, saving only on this device. Only the project URL and the
// publishable (anon) key belong in the browser; Row Level Security in the
// database decides what each signed-in user can read and write.
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

export const supabase = url && key
  ? createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true, storageKey: "pm2_auth" } })
  : null;
