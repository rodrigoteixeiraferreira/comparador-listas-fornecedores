import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// renova a sessão a cada requisição e diz se há alguém logado
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll(toSet, headers) {
          toSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          toSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
          Object.entries(headers).forEach(([key, value]) => response.headers.set(key, value));
        },
      },
    },
  );
  // nada entre a criação do cliente e o getClaims: é ele que renova a sessão
  const { data } = await supabase.auth.getClaims();
  return { response, loggedIn: Boolean(data?.claims) };
}
