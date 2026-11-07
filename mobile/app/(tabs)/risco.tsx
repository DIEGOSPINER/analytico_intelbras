import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { carregarDados } from "../../src/api/cliente";
import { Cartao, Linha, Tela } from "../../src/components/Tela";

export default function Risco() {
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

  useFocusEffect(useCallback(() => { carregar(); }, [carregar]));

  const ocorrencias = (dados?.ocorrencias || dados?.risco || []) as Array<Record<string, unknown>>;
  const lista = Array.isArray(ocorrencias) ? ocorrencias.slice(0, 40) : [];

  return (
    <Tela titulo="Detector de risco" carregando={carregando} erro={erro} onRefresh={carregar}>
      <Cartao titulo="Itens no resumo" valor={String(dados?.itens ?? lista.length)} destaque />
      {lista.map((item, i) => (
        <Linha
          key={i}
          esquerda={`${item.categoria || item.classe || item.tipo || "evento"} · ${item.camera || ""}`}
          direita={String(item.quando || item.risco || "")}
          risco={Boolean(item.risco) || Number(item.nivel_risco || 0) >= 2}
        />
      ))}
      {!lista.length && !carregando ? (
        <Linha esquerda="Sem eventos de risco na memória atual — puxe para atualizar." />
      ) : null}
    </Tela>
  );
}
