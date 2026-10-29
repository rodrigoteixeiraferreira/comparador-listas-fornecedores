"use server";

import { redirect } from "next/navigation";
import { isLocale } from "@/lib/i18n/locales";
import { createClient } from "@/lib/supabase/server";

export async function signIn(lang: string, _state: { failed: boolean }, form: FormData) {
  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({
    email: String(form.get("email") ?? ""),
    password: String(form.get("password") ?? ""),
  });
  if (error) return { failed: true };
  redirect(`/${isLocale(lang) ? lang : "pt"}`);
}
