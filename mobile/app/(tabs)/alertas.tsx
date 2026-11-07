import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { carregarDados } from "../../src/api/cliente";
import { Linha, Tela } from "../../src/components/Tela";

export default function Alertas() {
  const [itens, setItens] = useState<Array<Record<string, unknown>>>([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const dados = await carregarDados();
      setItens((dados.historico as Array<Record<string, unknown>>) || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro");
    } finally {
      setCarregando(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { carregar(); }, [carregar]));

  return (
    <Tela titulo="Alertas RF e LPR" carregando={carregando} erro={erro} onRefresh={carregar}>
      {itens.map((item, i) => (
        <Linha
          key={`${item.id}-${i}`}
          esquerda={`${item.tipo || ""} · ${item.nome || item.id} · ${item.camera || ""}`}
          direita={String(item.quando || "")}
        />
      ))}
      {!itens.length && !carregando ? <Linha esquerda="Nenhum alerta recente." /> : null}
    </Tela>
  );
}
