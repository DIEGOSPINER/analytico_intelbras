import { useCallback, useState } from "react";
import { Text, TouchableOpacity, StyleSheet } from "react-native";
import { useFocusEffect } from "expo-router";
import { carregarCustos, baseUrl } from "../../src/api/cliente";
import { usandoNuvem, nuvemUrl } from "../../src/api/nuvem";
import { useAuth } from "../../src/auth";
import { Cartao, Linha, Tela } from "../../src/components/Tela";
import { cores, espaco } from "../../src/theme";

export default function Conta() {
  const { usuario, sair } = useAuth();
  const [custos, setCustos] = useState<{
    total_usd?: number;
    itens?: Array<{ canal: string; direcao: string; mensagens: number; usd: number }>;
    ano?: number;
    mes?: number;
  } | null>(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      setCustos(await carregarCustos());
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro");
    } finally {
      setCarregando(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { carregar(); }, [carregar]));

  return (
    <Tela titulo="Conta e custos" carregando={carregando} erro={erro} onRefresh={carregar}>
      <Cartao titulo="Usuário" valor={usuario?.email || "—"} />
      <Cartao titulo="Documento" valor={usuario?.documento || "—"} />
      <Cartao titulo="API atual" valor={baseUrl()} />
      <Cartao
        titulo="Nuvem (futuro)"
        valor={usandoNuvem() ? nuvemUrl() : "Não configurada — use EXPO_PUBLIC_NUVEM_API_URL"}
      />
      <Cartao
        titulo={`Custo estimado ${custos?.mes || "—"}/${custos?.ano || "—"}`}
        valor={`US$ ${Number(custos?.total_usd || 0).toFixed(4)}`}
        destaque
      />
      {(custos?.itens || []).map((item, i) => (
        <Linha
          key={i}
          esquerda={`${item.canal} · ${item.direcao} · ${item.mensagens} msg`}
          direita={`US$ ${Number(item.usd).toFixed(4)}`}
        />
      ))}
      <Text style={styles.nota}>
        WhatsApp interativo (Meta) e e-mail entram neste ledger. Configure tarifas no .env do servidor.
      </Text>
      <TouchableOpacity style={styles.sair} onPress={() => sair()}>
        <Text style={styles.sairTxt}>Sair</Text>
      </TouchableOpacity>
    </Tela>
  );
}

const styles = StyleSheet.create({
  nota: { color: cores.muted, fontSize: 12, marginTop: espaco.md, lineHeight: 18 },
  sair: {
    marginTop: espaco.lg,
    backgroundColor: "rgba(255,107,107,0.2)",
    borderRadius: 12,
    padding: 14,
    alignItems: "center",
  },
  sairTxt: { color: cores.risco, fontWeight: "700" },
});
