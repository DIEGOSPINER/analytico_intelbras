import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { login as apiLogin, logout as apiLogout, tokenSalvo, usuarioSalvo, Usuario } from "./api/cliente";

type AuthCtx = {
  usuario: Usuario | null;
  pronto: boolean;
  entrar: (email: string, senha: string) => Promise<void>;
  sair: () => Promise<void>;
};

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [pronto, setPronto] = useState(false);

  useEffect(() => {
    (async () => {
      const token = await tokenSalvo();
      const user = await usuarioSalvo();
      if (token && user) setUsuario(user);
      setPronto(true);
    })();
  }, []);

  const valor = useMemo<AuthCtx>(
    () => ({
      usuario,
      pronto,
      entrar: async (email, senha) => {
        const dados = await apiLogin(email, senha);
        setUsuario(dados.usuario);
      },
      sair: async () => {
        await apiLogout();
        setUsuario(null);
      },
    }),
    [usuario, pronto]
  );

  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
