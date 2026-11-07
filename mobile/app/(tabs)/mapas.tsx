import { useCallback, useState } from "react";
import { useFocusEffect } from "expo-router";
import { carregarDados } from "../../src/api/cliente";
import { Linha, Tela } from "../../src/components/Tela";

export default function Mapas() {
  const [rastros, setRastros] = useState<Array<Record<string, unknown>>>([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const dados = await carregarDados();
      setRastros((dados.rastros_rf as Array<Record<string, unknown>>) || []);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro");
    } finally {
      setCarregando(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { carregar(); }, [carregar]));

  return (
    <Tela titulo="Mapas / rastros RF" carregando={carregando} erro={erro} onRefresh={carregar}>
      {rastros.slice(-40).reverse().map((p, i) => (
        <Linha
          key={`${p.id}-${p.quando}-${i}`}
          esquerda={`${p.nome || p.id} · ${p.camera || ""}`}
          direita={`${p.lat}, ${p.lon}`}
        />
      ))}
      {!rastros.length && !carregando ? (
        <Linha esquerda="Sem rastros georreferenciados. Cadastre lat/lon nas câmeras." />
      ) : null}
    </Tela>
  );
}
