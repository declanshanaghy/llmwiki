import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  const supabaseUrl = process.env.SUPABASE_INTERNAL_URL || process.env.NEXT_PUBLIC_SUPABASE_URL!;
  return createServerClient(
    supabaseUrl,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      ...(process.env.SUPABASE_INTERNAL_URL && process.env.NEXT_PUBLIC_SUPABASE_URL
        ? { cookieOptions: { name: `sb-${new URL(process.env.NEXT_PUBLIC_SUPABASE_URL).hostname}-auth-token` } }
        : {}),
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: Record<string, unknown> }[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Server Component — ignore
          }
        },
      },
    },
  );
}
