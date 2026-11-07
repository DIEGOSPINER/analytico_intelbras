/**
 * Stub para quando a leitura migrar 100% para a nuvem (Lightsail/ECS).
 * Hoje o app usa EXPO_PUBLIC_API_URL → portal da borda (8787).
 * Depois: EXPO_PUBLIC_NUVEM_API_URL + mesmo Bearer ou INGEST/JWT futuro.
 */

import Constants from "expo-constants";

export function nuvemUrl(): string {
  const extra = (Constants.expoConfig?.extra || {}) as { nuvemApiUrl?: string };
  return (
    process.env.EXPO_PUBLIC_NUVEM_API_URL ||
    extra.nuvemApiUrl ||
    ""
  ).replace(/\/$/, "");
}

export function usandoNuvem(): boolean {
  return Boolean(nuvemUrl());
}

export async function saudeNuvem(): Promise<{ ok: boolean } | null> {
  const base = nuvemUrl();
  if (!base) return null;
  const resp = await fetch(`${base}/saude`);
  if (!resp.ok) return { ok: false };
  return resp.json();
}
