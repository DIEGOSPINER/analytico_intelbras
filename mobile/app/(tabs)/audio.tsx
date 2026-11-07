import { useCallback, useState } from "react";
import { Text } from "react-native";
import { useFocusEffect } from "expo-router";
import { carregarDados } from "../../src/api/cliente";
import { Cartao, Linha, Tela } from "../../src/components/Tela";
import { cores } from "../../src/theme";

export default function Audio() {
  const [audio, setAudio] = useState<Record<string, unknown>>({});
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const dados = await carregarDados();
      setAudio((dados.audio as Record<string, unknown>) || {});
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro");
    } finally {
      setCarregando(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { carregar(); }, [carregar]));

  const esteira = (audio.esteira as Array<Record<string, unknown>>) || [];
  const alertas = (audio.alertas as Array<Record<string, unknown>>) || [];

  return (
    <Tela titulo="Áudio e transcrição" carregando={carregando} erro={erro} onRefresh={carregar}>
      <Cartao titulo="Riscos sonoros abertos" valor={String(audio.risco_aberto ?? alertas.length)} destaque />
      <Text style={{ color: cores.muted, marginVertical: 8 }}>Esteira recente</Text>
      {esteira.slice(0, 30).map((item, i) => (
        <Linha
          key={i}
          esquerda={`${item.camera || ""} · ${item.texto || item.categoria || ""}`}
          direita={String(item.quando || "")}
          risco={Boolean(item.risco)}
        />
      ))}
      {!esteira.length && !carregando ? <Linha esquerda="Sem transcrições ainda." /> : null}
    </Tela>
  );
}
