# C4ISTAR Monitor — app iOS / Android

App Expo (React Native) espelhando o portal web. A **inferência YOLO fica no PC** (borda); o celular só consome a API (`/api/mobile/*`) e conversa com o Stive.

## Pré-requisitos

1. **Node.js 20+** — [nodejs.org](https://nodejs.org/) (nesta máquina ainda não estava no PATH).
2. Portal do analítico rodando (`WEB_SENHA` / usuários) em `http://IP_DO_PC:8787`.
3. Celular e PC na mesma rede **ou** túnel (`abrir_tunel.ps1` / Cloudflare).

## Desenvolvimento

```bash
cd mobile
npm install
# IP do PC na LAN (não use 127.0.0.1 no aparelho físico)
set EXPO_PUBLIC_API_URL=http://192.168.0.10:8787
npx expo start
```

- Escaneie o QR com **Expo Go** (Android/iOS) ou pressione `a` / `i` com emulador.
- Login: mesmo e-mail/senha do portal web.
- Endpoints: `POST /api/mobile/login`, `GET /api/mobile/dados`, `POST /api/mobile/stive`, `GET /api/mobile/custos`.

Nuvem futura (só URL):

```bash
set EXPO_PUBLIC_NUVEM_API_URL=https://sua-api.exemplo.com
```

## Build interno (APK / TestFlight)

Conta Expo + [EAS](https://docs.expo.dev/eas/):

```bash
npm i -g eas-cli
eas login
eas build:configure
eas build -p android --profile preview   # APK para instalação direta
eas build -p ios --profile preview       # exige Apple Developer + Mac ou EAS cloud
```

Instalar Android: baixe o APK do painel EAS e permita fontes desconhecidas.  
iOS: envie o build para **TestFlight** (`eas submit -p ios`).

## Lojas (produção)

```bash
eas build -p android --profile production
eas build -p ios --profile production
eas submit -p android
eas submit -p ios
```

Checklist: política de privacidade (câmeras/faces), conta Apple Developer (US$ 99/ano), Google Play Console.

## WhatsApp + custos

No servidor (`.env`):

- `WHATSAPP_MODO=meta` + `WHATSAPP_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` + `WHATSAPP_VERIFY_TOKEN`
- Webhook nuvem: `GET/POST /v1/whatsapp` (Meta → Stive → resposta)
- Tarifas: `WHATSAPP_USD_MSG_OUT`, `EMAIL_USD_MSG_OUT`, `OPENAI_USD_1K_TOKENS`
- Tabela: `db/schema_custos.sql` — resumo no app em **Conta**

CallMeBot (`WHATSAPP_MODO=callmebot`) continua só para envio unidirecional de alertas.

## Telas ↔ portal

| App | Portal |
|-----|--------|
| Início | `/` |
| Contagens | `/painel/1` |
| Alertas | `/painel/3` |
| Mapas | `/painel/4` |
| Risco | `/painel/risco` |
| Áudio | `/painel/audio` |
| Stive | `/painel/stive` |
| Conta | `/conta` + custos |
