import { Redirect } from "expo-router";
import { useAuth } from "../src/auth";

export default function Index() {
  const { usuario, pronto } = useAuth();
  if (!pronto) return null;
  return <Redirect href={usuario ? "/(tabs)/inicio" : "/login"} />;
}
