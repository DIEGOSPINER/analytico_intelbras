import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useAuth } from "../src/auth";
import { baseUrl } from "../src/api/cliente";
import { cores, espaco } from "../src/theme";

export default function Login() {
  const { entrar } = useAuth();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function enviar() {
    setErro("");
    setCarregando(true);
    try {
      await entrar(email.trim(), senha);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha no login");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.fundo}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <View style={styles.caixa}>
        <Text style={styles.marca}>C4ISTAR</Text>
        <Text style={styles.sub}>Monitor · app móvel</Text>
        <Text style={styles.api}>API: {baseUrl()}</Text>
        <TextInput
          style={styles.input}
          placeholder="E-mail"
          placeholderTextColor={cores.muted}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Senha"
          placeholderTextColor={cores.muted}
          secureTextEntry
          value={senha}
          onChangeText={setSenha}
        />
        {erro ? <Text style={styles.erro}>{erro}</Text> : null}
        <TouchableOpacity style={styles.botao} onPress={enviar} disabled={carregando}>
          {carregando ? <ActivityIndicator color="#fff" /> : <Text style={styles.botaoTxt}>Entrar</Text>}
        </TouchableOpacity>
        <Text style={styles.nota}>
          O modelo YOLO roda no PC da instalação. Este app lê alertas e conversa com o Stive via API.
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  fundo: { flex: 1, backgroundColor: cores.fundo, justifyContent: "center", padding: espaco.lg },
  caixa: { gap: 12 },
  marca: { color: cores.texto, fontSize: 36, fontWeight: "800", letterSpacing: 1 },
  sub: { color: cores.ciano, marginBottom: 8 },
  api: { color: cores.muted, fontSize: 12, marginBottom: 8 },
  input: {
    backgroundColor: cores.painel,
    borderColor: cores.linha,
    borderWidth: 1,
    borderRadius: 12,
    color: cores.texto,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  botao: {
    backgroundColor: cores.azul,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  botaoTxt: { color: "#fff", fontWeight: "700" },
  erro: { color: cores.risco },
  nota: { color: cores.muted, fontSize: 12, marginTop: 16, lineHeight: 18 },
});
