import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { carregarDados } from "../../src/api/cliente";
import { Cartao, Tela } from "../../src/components/Tela";
import { useAuth } from "../../src/auth";

export default function Inicio() {
  const { usuario } = useAuth();
  const [dados, setDados] = useState<Record<string, unknown> | null>(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      setDados(await carregarDados());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro");
    } finally {
      setCarregando(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      carregar();
    }, [carregar])
  );

  const match = (dados?.match || {}) as Record<string, unknown>;

  return (
    <Tela titulo={`Olá, ${usuario?.nome || "operador"}`} carregando={carregando} erro={erro} onRefresh={carregar}>
      <Cartao titulo="Fonte" valor={String(dados?.fonte_dados || "—")} />
      <Cartao titulo="Câmeras" valor={String(dados?.cameras ?? "—")} />
      <Cartao titulo="Faces / passagens" valor={String(dados?.faces ?? "—")} />
      <Cartao
        titulo="Último match"
        valor={
          match?.id
            ? `${match.nome || match.id} · ${match.camera || ""}`
            : "Nenhum reconhecimento recente"
        }
        destaque={Boolean(match?.id)}
      />
    </Tela>
  );
}
