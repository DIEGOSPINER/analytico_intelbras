import { Tabs } from "expo-router";
import { Text } from "react-native";
import { cores } from "../../src/theme";

function Icone({ label }: { label: string }) {
  return <Text style={{ color: cores.azul, fontSize: 11 }}>{label}</Text>;
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: cores.painel },
        headerTintColor: cores.texto,
        tabBarStyle: { backgroundColor: cores.painel, borderTopColor: cores.linha },
        tabBarActiveTintColor: cores.ciano,
        tabBarInactiveTintColor: cores.muted,
      }}
    >
      <Tabs.Screen name="inicio" options={{ title: "Início", tabBarIcon: () => <Icone label="⌂" /> }} />
      <Tabs.Screen name="contagens" options={{ title: "Contagens", tabBarIcon: () => <Icone label="∑" /> }} />
      <Tabs.Screen name="alertas" options={{ title: "Alertas", tabBarIcon: () => <Icone label="!" /> }} />
      <Tabs.Screen name="risco" options={{ title: "Risco", tabBarIcon: () => <Icone label="⚠" /> }} />
      <Tabs.Screen name="audio" options={{ title: "Áudio", tabBarIcon: () => <Icone label="♪" /> }} />
      <Tabs.Screen name="mapas" options={{ title: "Mapas", tabBarIcon: () => <Icone label="◎" /> }} />
      <Tabs.Screen name="stive" options={{ title: "Stive", tabBarIcon: () => <Icone label="S" /> }} />
      <Tabs.Screen name="conta" options={{ title: "Conta", tabBarIcon: () => <Icone label="☺" /> }} />
    </Tabs>
  );
}
