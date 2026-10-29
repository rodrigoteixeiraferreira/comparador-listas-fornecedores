import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

// o cliente do servidor, com a sessão de quem está no painel: o banco só deixa ler quem entrou
export async function createClient() {
  const store = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => store.getAll(),
        setAll(toSet) {
          try {
            toSet.forEach(({ name, value, options }) => store.set(name, value, options));
          } catch {
            // num Server Component não se grava cookie; o proxy renova a sessão na próxima requisição
          }
        },
      },
    },
  );
}

// a checagem de verdade (o proxy só redireciona): sem sessão válida, volta ao login
export async function requireUser(lang: string) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (!data?.claims) redirect(`/${lang}/login`);
  return supabase;
}
