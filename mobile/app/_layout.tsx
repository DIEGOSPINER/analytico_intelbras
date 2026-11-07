import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { AuthProvider, useAuth } from "../src/auth";
import { cores } from "../src/theme";

function Guarda() {
  const { usuario, pronto } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (!pronto) return;
    const naLogin = segments[0] === "login";
    if (!usuario && !naLogin) router.replace("/login");
    if (usuario && naLogin) router.replace("/(tabs)/inicio");
  }, [usuario, pronto, segments, router]);

  if (!pronto) {
    return (
      <View style={{ flex: 1, backgroundColor: cores.fundo, justifyContent: "center" }}>
        <ActivityIndicator color={cores.azul} size="large" />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="light" />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: cores.fundo } }} />
    </>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <Guarda />
    </AuthProvider>
  );
}
