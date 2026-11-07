import { useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { falarStive } from "../../src/api/cliente";
import { cores, espaco } from "../../src/theme";

type Bolha = { quem: "voce" | "stive"; texto: string };

export default function Stive() {
  const [pergunta, setPergunta] = useState("");
  const [chat, setChat] = useState<Bolha[]>([
    { quem: "stive", texto: "Sou o Stive. Pergunte sobre passagens, riscos ou o que a base registrou." },
  ]);
  const [enviando, setEnviando] = useState(false);

  async function enviar() {
    const texto = pergunta.trim();
    if (!texto || enviando) return;
    setPergunta("");
    setChat((c) => [...c, { quem: "voce", texto }]);
    setEnviando(true);
    try {
      const resp = await falarStive(texto);
      setChat((c) => [...c, { quem: "stive", texto: resp.fala || "Sem resposta." }]);
    } catch (e) {
      setChat((c) => [
        ...c,
        { quem: "stive", texto: e instanceof Error ? e.message : "Falha ao falar com o Stive." },
      ]);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <View style={styles.fundo}>
      <FlatList
        data={chat}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={{ padding: espaco.md, gap: 10 }}
        renderItem={({ item }) => (
          <View style={[styles.bolha, item.quem === "voce" ? styles.voce : styles.stive]}>
            <Text style={styles.texto}>{item.texto}</Text>
          </View>
        )}
      />
      <View style={styles.barra}>
        <TextInput
          style={styles.input}
          placeholder="Pergunte ao Stive…"
          placeholderTextColor={cores.muted}
          value={pergunta}
          onChangeText={setPergunta}
          onSubmitEditing={enviar}
        />
        <TouchableOpacity style={styles.botao} onPress={enviar} disabled={enviando}>
          {enviando ? <ActivityIndicator color="#fff" /> : <Text style={styles.botaoTxt}>Enviar</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fundo: { flex: 1, backgroundColor: cores.fundo },
  bolha: { borderRadius: 14, padding: 12, maxWidth: "92%" },
  voce: { alignSelf: "flex-end", backgroundColor: "rgba(76,141,255,0.35)" },
  stive: { alignSelf: "flex-start", backgroundColor: cores.painel, borderWidth: 1, borderColor: cores.linha },
  texto: { color: cores.texto, lineHeight: 20 },
  barra: {
    flexDirection: "row",
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: cores.linha,
    backgroundColor: cores.painel,
  },
  input: {
    flex: 1,
    color: cores.texto,
    backgroundColor: cores.fundo,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  botao: {
    backgroundColor: cores.azul,
    borderRadius: 10,
    paddingHorizontal: 16,
    justifyContent: "center",
  },
  botaoTxt: { color: "#fff", fontWeight: "700" },
});
