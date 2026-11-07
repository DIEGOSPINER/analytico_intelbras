import Constants from "expo-constants";
import AsyncStorage from "@react-native-async-storage/async-storage";

const CHAVE_TOKEN = "c4istar.token";
const CHAVE_USER = "c4istar.usuario";

function baseUrl(): string {
  const extra = (Constants.expoConfig?.extra || {}) as { apiUrl?: string };
  return (
    process.env.EXPO_PUBLIC_API_URL ||
    extra.apiUrl ||
    "http://127.0.0.1:8787"
  ).replace(/\/$/, "");
}

async function headers(json = true): Promise<Record<string, string>> {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const token = await AsyncStorage.getItem(CHAVE_TOKEN);
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function pedir<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${baseUrl()}${path}`, init);
  const dados = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error((dados as { erro?: string }).erro || `HTTP ${resp.status}`);
  }
  return dados as T;
}

export type Usuario = {
  email: string;
  nome: string;
  documento: string;
  perfil: string;
  trocar_no_acesso?: boolean;
};

export async function saude() {
  return pedir<{ ok: boolean; postgres?: boolean; modelo?: string }>("/api/mobile/saude");
}

export async function login(email: string, senha: string) {
  const dados = await pedir<{
    ok: boolean;
    token: string;
    usuario: Usuario;
  }>("/api/mobile/login", {
    method: "POST",
    headers: await headers(),
    body: JSON.stringify({ email, senha }),
  });
  await AsyncStorage.setItem(CHAVE_TOKEN, dados.token);
  await AsyncStorage.setItem(CHAVE_USER, JSON.stringify(dados.usuario));
  return dados;
}

export async function logout() {
  await AsyncStorage.multiRemove([CHAVE_TOKEN, CHAVE_USER]);
}

export async function usuarioSalvo(): Promise<Usuario | null> {
  const bruto = await AsyncStorage.getItem(CHAVE_USER);
  if (!bruto) return null;
  try {
    return JSON.parse(bruto) as Usuario;
  } catch {
    return null;
  }
}

export async function tokenSalvo(): Promise<string | null> {
  return AsyncStorage.getItem(CHAVE_TOKEN);
}

export async function carregarDados() {
  return pedir<Record<string, unknown>>("/api/mobile/dados", {
    headers: await headers(false),
  });
}

export async function falarStive(pergunta: string) {
  return pedir<{ ok: boolean; fala: string; visual?: Record<string, unknown> }>(
    "/api/mobile/stive",
    {
      method: "POST",
      headers: await headers(),
      body: JSON.stringify({ pergunta }),
    }
  );
}

export async function carregarCustos() {
  return pedir<{
    ok: boolean;
    total_usd?: number;
    itens?: Array<{ canal: string; direcao: string; mensagens: number; usd: number }>;
    ano?: number;
    mes?: number;
  }>("/api/mobile/custos", { headers: await headers(false) });
}

export { baseUrl };
