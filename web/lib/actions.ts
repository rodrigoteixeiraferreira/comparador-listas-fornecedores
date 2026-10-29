"use server";

import { redirect } from "next/navigation";
import { isLocale } from "./i18n/locales";
import { createClient } from "./supabase/server";

export async function signOut(lang: string) {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect(`/${isLocale(lang) ? lang : "pt"}/login`);
}
