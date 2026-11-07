import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { carregarDados } from "../../src/api/cliente";
import { Linha, Tela } from "../../src/components/Tela";

export default function Contagens() {
  const [itens, setItens] = useState<Array<Record<string, unknown>>>([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const dados = await carregarDados();
      setItens((dados.passagens as Array<Record<string, unknown>>) || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro");
    } finally {
      setCarregando(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { carregar(); }, [carregar]));

  return (
    <Tela titulo="Contagens / RF" carregando={carregando} erro={erro} onRefresh={carregar}>
      {itens.map((item) => (
        <Linha
          key={String(item.id)}
          esquerda={`${item.nome || item.id}${item.classe ? ` · ${item.classe}` : ""}`}
          direita={String(item.total ?? 0)}
        />
      ))}
      {!itens.length && !carregando ? <Linha esquerda="Sem passagens no período." /> : null}
    </Tela>
  );
}
