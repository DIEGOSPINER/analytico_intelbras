import React from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { cores, espaco } from "../theme";

export function Tela({
  titulo,
  children,
  carregando,
  erro,
  onRefresh,
}: {
  titulo: string;
  children?: React.ReactNode;
  carregando?: boolean;
  erro?: string;
  onRefresh?: () => void;
}) {
  return (
    <ScrollView
      style={styles.fundo}
      contentContainerStyle={styles.miolo}
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={!!carregando} onRefresh={onRefresh} tintColor={cores.azul} />
        ) : undefined
      }
    >
      <Text style={styles.titulo}>{titulo}</Text>
      {erro ? <Text style={styles.erro}>{erro}</Text> : null}
      {carregando && !children ? <ActivityIndicator color={cores.azul} /> : children}
    </ScrollView>
  );
}

export function Cartao({ titulo, valor, destaque }: { titulo: string; valor: string; destaque?: boolean }) {
  return (
    <View style={[styles.cartao, destaque && styles.cartaoDestaque]}>
      <Text style={styles.cartaoTitulo}>{titulo}</Text>
      <Text style={styles.cartaoValor}>{valor}</Text>
    </View>
  );
}

export function Linha({ esquerda, direita, risco }: { esquerda: string; direita?: string; risco?: boolean }) {
  return (
    <View style={styles.linha}>
      <Text style={[styles.linhaEsq, risco && { color: cores.risco }]} numberOfLines={2}>
        {esquerda}
      </Text>
      {direita ? <Text style={styles.linhaDir}>{direita}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  fundo: { flex: 1, backgroundColor: cores.fundo },
  miolo: { padding: espaco.md, gap: espaco.sm, paddingBottom: 40 },
  titulo: { color: cores.texto, fontSize: 22, fontWeight: "700", marginBottom: 8 },
  erro: { color: cores.risco, marginBottom: 8 },
  cartao: {
    backgroundColor: cores.painel,
    borderColor: cores.linha,
    borderWidth: 1,
    borderRadius: 14,
    padding: espaco.md,
    marginBottom: 8,
  },
  cartaoDestaque: { borderColor: cores.azul },
  cartaoTitulo: { color: cores.muted, fontSize: 13 },
  cartaoValor: { color: cores.texto, fontSize: 20, fontWeight: "700", marginTop: 4 },
  linha: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: cores.linha,
  },
  linhaEsq: { color: cores.texto, flex: 1 },
  linhaDir: { color: cores.muted },
});
