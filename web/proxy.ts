import { NextResponse, type NextRequest } from "next/server";
import { isLocale, pickLocale } from "@/lib/i18n/locales";
import { updateSession } from "@/lib/supabase/proxy";

// Toda rota começa pelo idioma (/pt, /es, /en). Sem sessão, só a tela de login abre. É a checagem otimista: as
// páginas conferem a sessão de novo, e o banco só entrega dado a quem fez login.
export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const lang = pathname.split("/")[1];
  if (!isLocale(lang)) {
    const url = request.nextUrl.clone();
    url.pathname = `/${pickLocale(request.headers.get("accept-language"))}${pathname === "/" ? "" : pathname}`;
    return NextResponse.redirect(url);
  }
  const { response, loggedIn } = await updateSession(request);
  const atLogin = pathname === `/${lang}/login`;
  if (loggedIn === atLogin) {
    const url = request.nextUrl.clone();
    url.pathname = atLogin ? `/${lang}` : `/${lang}/login`;
    url.search = "";
    const redirect = NextResponse.redirect(url);
    response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
    return redirect;
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/|favicon.ico|icon.svg|.*\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
