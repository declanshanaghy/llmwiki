import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabaseUrl = process.env.SUPABASE_INTERNAL_URL || process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const supabase = createServerClient(
    supabaseUrl,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      // When using an internal URL, the cookie name must match the browser
      // client (which uses NEXT_PUBLIC_SUPABASE_URL). Derive from public URL.
      ...(process.env.SUPABASE_INTERNAL_URL && process.env.NEXT_PUBLIC_SUPABASE_URL
        ? { cookieOptions: { name: `sb-${new URL(process.env.NEXT_PUBLIC_SUPABASE_URL).hostname}-auth-token` } }
        : {}),
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: Record<string, unknown> }[]) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  const { data: { user } } = await supabase.auth.getUser();
  const path = request.nextUrl.pathname;

  const isPublic = path === "/" || path.startsWith("/login") || path.startsWith("/signup") || path.startsWith("/callback") || path.startsWith("/oauth");

  if (user && (path === "/" || path === "/login" || path === "/signup")) {
    const url = request.nextUrl.clone();
    url.pathname = "/wikis";  // AuthProvider will redirect to /onboarding if needed
    return NextResponse.redirect(url);
  }

  if (!user && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
