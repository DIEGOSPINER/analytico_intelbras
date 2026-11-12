"""Acesso pelo navegador. O túnel leva estas páginas para fora de casa.

A análise continua junto das câmeras. Cada usuário entra com o próprio
e-mail e só vê a conta do seu CPF ou CNPJ. As telas de painel são uma
página leve: o quadro já publicado troca no lugar, e recarregar volta na hora.
"""

from __future__ import annotations

import csv
import hmac
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2

import acesso
import cadastro

COOKIE = "analitico"
PAINEIS = (
    ("1", "painel-1", "Contagens"),
    ("2", "painel-2", "Comportamento"),
    ("3", "painel-3", "Alertas de RF e LPR"),
    ("4", "painel-4", "Mapas"),
)
ESTILO = """
:root {
  --fundo: #070b16;
  --vidro: rgba(18, 24, 42, 0.72);
  --vidro-2: rgba(28, 36, 58, 0.55);
  --linha: rgba(255, 255, 255, 0.08);
  --texto: #f4f7fb;
  --mudo: #93a0b8;
  --azul: #4c8dff;
  --ciano: #3ee0ff;
  --verde: #3ddc97;
  --ambar: #ffb020;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; color: var(--texto); font-family: Segoe UI, sans-serif; font-size: 16px;
  background: radial-gradient(1200px 500px at 80% -10%, rgba(76, 141, 255, 0.18), transparent 55%), var(--fundo); }
.app { display: flex; min-height: 100vh; align-items: flex-start; }
aside { width: 248px; flex: none; position: sticky; top: 0; height: 100vh; overflow: auto; z-index: 1;
  padding: 22px 16px; background: rgba(10, 14, 28, 0.82);
  border-right: 1px solid var(--linha); backdrop-filter: blur(16px); }
.marca { display: flex; gap: 12px; align-items: center; margin-bottom: 28px; }
.logo { width: 42px; height: 42px; border-radius: 14px; display: grid; place-items: center; font-weight: 700;
  background: linear-gradient(160deg, #4c8dff, #3ee0ff); color: #041018; }
.marca strong { display: block; font-size: 16px; letter-spacing: 0.08em; }
.marca small { color: var(--mudo); font-size: 13px; }
.grupo { margin: 18px 8px 8px; color: var(--mudo); font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; }
nav a { display: flex; align-items: center; gap: 10px; color: var(--mudo); text-decoration: none;
  border-radius: 12px; padding: 11px 12px; margin-bottom: 4px; font-size: 15px; }
nav a svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 1.8; flex: none; }
nav a.ativo, nav a:hover { color: var(--texto); background: rgba(76, 141, 255, 0.16); }
.palco { flex: 1; min-width: 0; display: flex; flex-direction: column; position: relative; }
.palco.parede { height: 100vh; }
.topo { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 18px 22px 0; }
.topo h1 { margin: 0; font-size: 28px; font-weight: 600; }
.topo p { margin: 4px 0 0; color: var(--mudo); font-size: 15px; }
main { padding: 18px 22px 40px; display: flex; flex-direction: column; gap: 22px; position: relative; overflow: visible; }
.acoes-gestao { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.acoes-gestao form { margin: 0; display: inline; }
.acoes-gestao button { padding: 8px 12px; font-size: 13px; }
.cartoes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 0; }
.cartao, .painel, .video, figure { background: var(--vidro); border: 1px solid var(--linha); border-radius: 18px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25); backdrop-filter: blur(10px); }
.cartao { padding: 16px 18px; }
.cartao span, figcaption { color: var(--mudo); font-size: 14px; display: flex; align-items: center; gap: 8px; }
.cartao span svg, figcaption svg, button svg { width: 18px; height: 18px; stroke: var(--ciano); fill: none; stroke-width: 1.8; flex: none; }
button svg { stroke: currentColor; width: 16px; height: 16px; }
.cartao strong { display: block; margin-top: 8px; font-size: 32px; font-weight: 650; letter-spacing: -0.03em;
  transition: color 0.3s; }
.cartao strong.sobe { color: var(--verde); }
.grade { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
.atalho { display: flex; align-items: center; gap: 12px; min-height: 92px; padding: 18px; font-size: 18px;
  color: var(--texto); text-decoration: none; }
.atalho svg { width: 22px; height: 22px; stroke: var(--ciano); fill: none; stroke-width: 1.8; }
.tela { flex: 1; min-height: 0; margin: 12px 22px 18px; overflow: visible; }
.tela img, .video img { width: 100%; height: 100%; object-fit: contain; display: block; background: transparent; }
.parede .miolo { display: flex; flex-direction: column; height: 100%; }
.comandos { display: flex; gap: 8px; padding: 0 22px; }
.comandos button, button { display: inline-flex; align-items: center; gap: 8px;
  background: linear-gradient(180deg, #5b97ff, #3d74f0); color: white; border: 0;
  border-radius: 12px; padding: 11px 16px; font-size: 15px; cursor: pointer; }
label { display: block; margin: 12px 0; color: var(--mudo); font-size: 14px; }
input { width: 100%; margin-top: 6px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--linha);
  background: rgba(8, 12, 24, 0.65); color: var(--texto); font-size: 16px; }
select { width: 100%; margin-top: 6px; min-height: 48px; line-height: 1.35; appearance: auto;
  padding: 12px 14px; border-radius: 12px; font-size: 16px; color-scheme: light;
  background: #f4f7fb; color: #0b1220; border: 1px solid #c5d0e0; }
select option, select optgroup { color: #0b1220; background: #ffffff; }
.campo-lista { display: block; overflow: visible; position: relative; z-index: 1; }
.campo-lista input[list] { color-scheme: light; background: #f4f7fb; color: #0b1220; border: 1px solid #c5d0e0; }
.cartao { overflow: visible; }
.aviso { color: var(--ambar); } .ok { color: var(--verde); }
table { width: 100%; border-collapse: collapse; margin: 8px 0 20px; }
td, th { text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--linha); font-size: 15px; }
.check { width: auto; margin-right: 8px; }
.login { max-width: 420px; margin: 12vh auto; padding: 28px; }
a.texto { color: var(--ciano); }
.ranking { padding: 16px 18px 20px; }
.barra { height: 10px; border-radius: 99px; background: rgba(255,255,255,0.08); overflow: hidden; margin-top: 6px; }
.barra i { display: block; height: 100%; width: 0; border-radius: 99px;
  background: linear-gradient(90deg, #3ee0ff, #4c8dff); transition: width 0.7s ease; }
.linha-face { display: flex; justify-content: space-between; gap: 12px; margin-top: 12px; font-size: 15px; }
.coluna { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.72fr); gap: 14px; align-items: start; }
.coluna .tela { min-height: 68vh; }
.video { display: flex; flex-direction: column; min-height: 320px; overflow: hidden; }
.video img { flex: 1; min-height: 260px; background: #05080f; }
.rostos { display: flex; gap: 12px; flex-wrap: wrap; }
.rostos figure { width: 140px; margin: 0; overflow: hidden; }
.rostos img { width: 100%; height: 110px; object-fit: cover; }
.led { position: fixed; top: 16px; right: 22px; z-index: 30; width: 48px; height: 48px; border-radius: 50%; }
.led.branco { background: #f4f7fb; box-shadow: 0 0 28px #fff; animation: pisca 1.4s infinite; }
.led.verde { background: #3ddc97; box-shadow: 0 0 28px #3ddc97; animation: pisca 1.2s infinite; }
.led.amarelo { background: #ffb020; box-shadow: 0 0 28px #ffb020; animation: pisca 0.9s infinite; }
.led.vermelho { background: #ff3b3b; box-shadow: 0 0 32px #ff3b3b; animation: pisca 0.45s infinite; }
.led.preto { background: #05070c; box-shadow: 0 0 0 6px #ff3b3b, 0 0 32px #ff3b3b; animation: pisca 0.28s infinite; }
@keyframes pisca { 50% { opacity: 0.28; } }
.grafico, .mapa { width: 100%; height: 280px; border-radius: 12px; background: #101624; }
.grafico.grafico-rosca { height: 360px; }
iframe.mapa, iframe.mapa-folium { display: block; width: 100%; height: 280px; border: 0; border-radius: 12px; background: #d5e2ef; }
canvas.grafico.filtravel { cursor: pointer; }
iframe#mapa { height: 520px; }
main[data-tela="inicio"] .cartao span { font-size: 18px; gap: 12px; }
main[data-tela="inicio"] .cartao span svg { width: 40px; height: 40px; }
main[data-tela="inicio"] .cartao strong { font-size: 40px; }
.segmentador-portal { display: flex; flex-wrap: wrap; gap: 12px 18px; align-items: start; margin-bottom: 16px; }
.segmentador-portal label { display: grid; gap: 6px; min-width: min(100%, 420px); flex: 1; color: var(--mudo); font-size: 13px; }
.segmentador-portal select { width: 100%; }
.segmentador-portal .estado { margin: 8px 0 0; color: var(--ciano); font-size: 14px; flex: 1 1 100%; }
.faixa-vista { position: sticky; top: 0; z-index: 12; margin: 0 0 12px; padding: 10px 14px; border-radius: 12px; border: 1px solid rgba(76,141,255,.35); background: rgba(76,141,255,.12); color: #dce8ff; font-size: 14px; display: none; }
.faixa-vista.ativa { display: block; }
.faixa-vista a { color: var(--ciano); }
.cartao.cor-serie span { color: var(--cor-serie) !important; }
.cartao.cor-serie span svg { stroke: var(--cor-serie) !important; }
.cartao.cor-serie strong { color: var(--cor-serie) !important; }
.grade.tres { grid-template-columns: 1fr 1fr 1fr; }
.empilha { display: grid; grid-template-columns: 148px 1fr 40px; gap: 8px; align-items: center; margin: 10px 0; font-size: 14px; }
.empilha .trilha { display: flex; height: 22px; border-radius: 7px; overflow: hidden; background: rgba(255,255,255,0.06); }
.empilha i { display: grid; place-items: center; font-style: normal; font-size: 12px; color: #041018; overflow: hidden; }
.legenda-linha { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; color: var(--mudo); font-size: 13px; }
.legenda-linha b { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.fileira-fluxo { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; padding: 8px 4px 4px; }
.fileira-fluxo h2 { flex: 0 0 180px; margin: 0 0 28px; font-size: 16px; }
.tacho { width: 112px; margin: 0; }
.tacho svg { width: 100%; height: auto; display: block; }
.tacho p, .leitura p { line-height: 1.45; margin: 4px 0 0; font-size: 12px; text-align: center; }
.termo { width: 46px; text-align: center; }
.termo .tubo { height: 96px; border-radius: 12px; background: rgba(255,255,255,0.08); display: flex; align-items: flex-end; overflow: hidden; }
.termo i { display: block; width: 100%; }
.termo p { margin: 6px 0 0; font-size: 11px; }
.voz { margin: 0; min-height: 1.35em; text-align: center; font-size: 28px; font-weight: 600; line-height: 1.35; }
.voz.branco { color: #f4f7fb; }
.voz.verde { color: #3ddc97; }
.voz.amarelo { color: #ffb020; }
.voz.vermelho { color: #ff5a5a; }
.voz.preto { color: #111318; background: #f4f7fb; border-radius: 12px; padding: 12px; }
.informe.branco { color: #f4f7fb; }
.informe.verde { color: #3ddc97; }
.informe.amarelo { color: #ffb020; }
.informe.vermelho { color: #ff5a5a; }
.informe.preto { color: #111318; background: #f4f7fb; border-radius: 8px; padding: 6px 8px; }
.titulo-alerta { font-size: 14px; font-weight: 650; }
.nome-alerta { margin-left: 8px; font-size: 16px; }
.alerta-linha { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center; margin-top: 18px; }
.alerta-linha img { width: 84px; height: 52px; object-fit: cover; border-radius: 8px; }
.linha-face img, .mini { width: 28px; height: 28px; border-radius: 50%; object-fit: cover; }
.placar { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.placar div { background: rgba(8, 12, 24, 0.45); border-radius: 12px; padding: 8px 10px; }
.placar strong { font-size: 28px; letter-spacing: -0.03em; }
.odo { width: 92px; height: 92px; border-radius: 50%; display: grid; place-items: center; margin: 8px auto; }
.odo span { width: 68px; height: 68px; border-radius: 50%; background: #101624; display: grid; place-items: center; font-size: 18px; }
.odo.verde { background: conic-gradient(#3ddc97 var(--giro), rgba(255,255,255,.08) 0); }
.odo.amarelo { background: conic-gradient(#ffb020 var(--giro), rgba(255,255,255,.08) 0); }
.odo.vermelho { background: conic-gradient(#ff3b3b var(--giro), rgba(255,255,255,.08) 0); }
.sobe { animation: sobe .7s ease; }
@keyframes sobe { from { transform: translateY(28px); opacity: 0; } to { transform: none; opacity: 1; } }
.luz-alerta { width: 14px; height: 14px; border-radius: 50%; background: #ff3b3b; box-shadow: 0 0 12px #ff3b3b; animation: pisca .4s infinite; display: inline-block; }
#mapa { width: 100%; height: 520px; border-radius: 18px; background: #101624; }
.faixa { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.periodo-datas { display: flex; justify-content: space-between; color: var(--mudo); font-size: 15px; margin-bottom: 6px; }
.trilho { position: relative; height: 32px; touch-action: none; }
.trilho .fundo { position: absolute; left: 8px; right: 8px; top: 14px; height: 4px; border-radius: 99px; background: rgba(255,255,255,.12); }
.trilho .faixa-sel { position: absolute; top: 14px; height: 4px; border-radius: 99px; background: linear-gradient(90deg, #3ee0ff, #4c8dff); }
.trilho .puxador { position: absolute; top: 4px; width: 22px; height: 22px; margin-left: -11px; padding: 0; border-radius: 50%;
  background: #f4f7fb; box-shadow: 0 0 0 4px rgba(76,141,255,.35); cursor: ew-resize; }
.graos { display: flex; gap: 6px; margin: 0 0 8px; }
.graos button { background: transparent; color: var(--mudo); border: 1px solid var(--linha); padding: 6px 10px; }
.graos button.ativo { color: white; background: rgba(76,141,255,.28); border-color: #4c8dff; }
.selo { min-width: 18px; height: 18px; margin-left: auto; border-radius: 99px; background: #ff3b3b; color: white;
  font-style: normal; font-size: 11px; display: grid; place-items: center; padding: 0 5px; }
.stive { display: grid; grid-template-columns: 240px minmax(0, 1fr) minmax(240px, .8fr); gap: 22px; align-items: start; }
.stive-pagina { display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 18px; min-height: calc(100vh - 110px); }
.stive-topo { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 22px; align-items: start; }
.stive-chat-area { display: flex; flex-direction: column; width: min(760px, 100%); margin: 0 auto; gap: 12px; min-height: 0; max-height: min(58vh, 560px); }
.avatar-stive { width: 180px; height: 220px; border-radius: 24px; object-fit: cover; background: linear-gradient(160deg, #4c8dff, #3ee0ff);
  display: grid; place-items: center; color: #041018; font-size: 72px; font-weight: 700; }
.chat { display: flex; flex-direction: column; gap: 10px; min-height: 0; flex: 1 1 auto; max-height: none; overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; scroll-behavior: smooth; }
.stive-chat-area .chat { min-height: 180px; }
.stive-chat-area .chat::before { content: ""; flex: 1 0 0; min-height: 0; }
.stive-chat-area form { margin: 0; flex: 0 0 auto; }
.bolha { max-width: 92%; padding: 12px 14px; border-radius: 16px; line-height: 1.45; white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; }
.bolha.stive { background: rgba(76,141,255,.16); }
.bolha.eu { margin-left: auto; background: rgba(255,255,255,.06); }
.bolha.vizinho { background: rgba(76,141,255,.16); }
.bolha.vizinho img, .bolha.eu img { max-width: 220px; border-radius: 12px; display: block; margin-top: 6px; }
.vizinhos-layout { display: grid; grid-template-columns: minmax(240px, 300px) minmax(0, 1fr); gap: 16px; min-height: calc(100vh - 130px); }
.vizinhos-lista, .vizinhos-chat { background: var(--vidro); border: 1px solid var(--linha); border-radius: 18px; padding: 14px; display: flex; flex-direction: column; min-height: 0; }
.vizinhos-lista h2, .vizinhos-chat h2 { margin: 0 0 10px; font-size: 16px; }
.vizinho-item { display: flex; gap: 10px; align-items: center; width: 100%; text-align: left; background: transparent; border: 1px solid transparent; border-radius: 12px; padding: 8px; color: inherit; cursor: pointer; }
.vizinho-item:hover, .vizinho-item.ativo { background: rgba(76,141,255,.12); border-color: var(--linha); }
.vizinho-item img, .vizinho-avatar { width: 42px; height: 42px; border-radius: 50%; object-fit: cover; background: #0b1220; flex: 0 0 auto; }
.vizinho-item strong { display: block; font-size: 14px; }
.vizinho-item span { display: block; font-size: 12px; color: var(--mudo); }
.vizinhos-chat .chat { flex: 1; min-height: 280px; max-height: min(58vh, 520px); margin-bottom: 10px; }
.vizinhos-chat form { display: grid; grid-template-columns: 1fr auto auto; gap: 8px; align-items: end; }
.vizinhos-add { margin-top: 12px; display: grid; gap: 8px; }
.vizinhos-modal {
  position: fixed; inset: 0; background: rgba(4,10,18,.72); display: none; place-items: center;
  z-index: 40; padding: 16px;
}
.vizinhos-modal.aberto { display: grid; }
.vizinhos-modal .caixa {
  width: min(520px, 100%); max-height: min(86vh, 720px); overflow: auto;
  background: #101826; border: 1px solid var(--linha); border-radius: 18px; padding: 16px 18px;
}
.vizinhos-modal .busca-resultados { display: grid; gap: 8px; margin-top: 10px; }
.vizinhos-modal .busca-item {
  display: flex; gap: 10px; align-items: center; width: 100%; text-align: left;
  background: rgba(255,255,255,.04); border: 1px solid var(--linha); border-radius: 12px; padding: 8px 10px; color: inherit; cursor: pointer;
}
.vizinhos-pendencias { margin-top: 14px; display: grid; gap: 8px; }
.vizinhos-pendencias .pend {
  border: 1px solid var(--linha); border-radius: 12px; padding: 10px; display: grid; gap: 8px;
}
.grupos-seguranca {
  margin-top: 18px; background: var(--vidro); border: 1px solid var(--linha);
  border-radius: 18px; padding: 14px 16px;
}
.grupos-seguranca h2 { margin: 0 0 8px; font-size: 16px; }
.grupos-seguranca .grupo-carta {
  border: 1px solid var(--linha); border-radius: 14px; padding: 12px; margin-top: 10px;
  display: grid; gap: 8px;
}
.grupos-seguranca .grupo-carta strong { font-size: 15px; }
.grupos-seguranca .chips { display: flex; flex-wrap: wrap; gap: 6px; }
.grupos-seguranca .chip {
  font-size: 12px; padding: 4px 8px; border-radius: 999px;
  background: rgba(76,141,255,.12); border: 1px solid var(--linha);
}
.grupos-seguranca .acoes-grupo { display: flex; flex-wrap: wrap; gap: 8px; }
.grupos-seguranca form.criar-grupo {
  display: grid; grid-template-columns: 1fr 1fr auto; gap: 8px; align-items: end; margin-top: 10px;
}
@media (max-width: 860px) {
  .vizinhos-layout { grid-template-columns: 1fr; }
  .grupos-seguranca form.criar-grupo { grid-template-columns: 1fr; }
}
.quadro-stive { min-height: 220px; }
.acoes-fala { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }
.acoes-fala button { background: #edf2ff; color: #141820; border: 1px solid #c9d6ff; padding: 8px 12px; border-radius: 10px; font-size: 13px; }
.acoes-fala button.btn-icone { width: 42px; height: 42px; padding: 0; display: grid; place-items: center; border-radius: 50%; }
.acoes-fala button[data-reacao="1"] { color: #1a7f4b; }
.acoes-fala button[data-reacao="-1"] { background: #ffecec; border-color: #ffb3b3; color: #b42318; }
.acoes-fala button[data-fechar] { background: #f4f7fb; border-color: #d5deea; }
.satisfacao-stive { margin-top: 28px; }
.satisfacao-stive .cartoes { margin-top: 12px; }
.pendencia { display: flex; gap: 8px; align-items: center; justify-content: space-between; margin-top: 10px; }
.pendencia button { background: transparent; color: var(--texto); border: 1px solid var(--linha); }
.avatar-stive { object-position: center 22%; }
.balao-stive { position: fixed !important; right: 18px; bottom: 18px; z-index: 2147483000 !important; width: 400px;
  display: flex; flex-direction: column-reverse; align-items: flex-end; gap: 10px; pointer-events: auto; }
.balao-stive.fechado { width: auto; }
.balao-stive.arrastando { opacity: 0.96; }
.grupo-puxador { position: relative; display: flex; flex-direction: column; align-items: center; z-index: 2; }
.puxador-stive { width: 124px; height: 124px; border-radius: 50%; padding: 0; overflow: hidden; border: 3px solid #4c8dff; background: #08131f;
  cursor: grab; flex: 0 0 auto; touch-action: none; user-select: none; -webkit-user-drag: none; }
.puxador-stive:active, .balao-stive.arrastando .puxador-stive { cursor: grabbing; }
.puxador-stive img { width: 100%; height: 100%; object-fit: cover; object-position: center 22%; display: block; pointer-events: none; }
.puxador-stive.falando { animation: pisca-stive 1.15s ease; }
@keyframes pisca-stive {
  0%, 100% { opacity: 1; filter: brightness(1); }
  12%, 45%, 78% { opacity: .2; filter: brightness(1.35); }
  28%, 61%, 92% { opacity: 1; filter: brightness(1); }
}
.nome-balao-stive { display: block; margin-top: 6px; color: #f4f7fb; font-size: 13px; font-weight: 650; text-align: center; max-width: 140px; line-height: 1.25; text-shadow: 0 1px 8px #041018; }
.balao-stive.fechado form { display: none; }
.balao-stive form { width: 100%; background: var(--vidro); border: 1px solid var(--linha); border-radius: 18px; padding: 14px; box-shadow: 0 18px 40px rgba(0,0,0,.35); }
.chat-balao { max-height: min(42vh, 360px); overflow-x: hidden; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; overscroll-behavior: contain; scroll-behavior: smooth; }
.chat-balao .bolha { max-width: 100%; }
.fala-hq { position: absolute; right: calc(100% + 8px); bottom: 72px; width: min(280px, 62vw); background: #fff; color: #141820; border-radius: 22px; padding: 12px 14px 14px; line-height: 1.35; font-size: 14px; font-weight: 550; box-shadow: 0 14px 32px rgba(0,0,0,.35); z-index: 5; animation: sobe .55s ease; pointer-events: auto; }
.fala-hq::after { content: ""; position: absolute; right: -12px; bottom: 28px; width: 0; height: 0; border: 12px solid transparent; border-left-color: #fff; border-right: 0; }
.fala-hq strong { display: block; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; color: #4c6fff; margin-bottom: 4px; }
.fala-hq .pendencia { margin-top: 10px; }
.fala-hq .pendencia button { background: #edf2ff; color: #141820; border: 1px solid #c9d6ff; }
.fala-hq .foto-pendencia, .pendencia .foto-pendencia { margin: 10px 0 4px; }
.fala-hq .foto-pendencia img, .pendencia .foto-pendencia img {
  width: 132px; height: 132px; object-fit: cover; border-radius: 14px;
  border: 1px solid var(--linha); background: #05080f; display: block;
}
.foto-cliente-preview { margin: 12px 0 0; max-width: 180px; }
.foto-cliente-preview img {
  width: 160px; height: 160px; object-fit: cover; border-radius: 14px;
  border: 1px solid var(--linha); background: #05080f; display: block;
}
.foto-cliente-preview figcaption { font-size: 12px; color: var(--mudo); margin-top: 6px; }
.fala-hq .link-vivo { margin: 10px 0 0; }
.fala-hq .link-vivo a { color: #4c6fff; font-weight: 700; text-decoration: none; }
.fala-hq .link-vivo a:hover { text-decoration: underline; }
.fala-hq.pergunta { border: 2px solid #4c8dff; }
.fala-hq.risco { border: 2px solid #ff5c7a; }
.fala-hq.info { border: 2px solid #3ddc97; }
/* Lâmina RF/LPR: entra da esquerda para a direita, ancorada à direita do conteúdo */
.alerta-rf-flutuante { position: fixed; right: 24px; left: auto; top: 88px; bottom: auto; width: min(320px, calc(100vw - 48px)); max-width: 340px; background: var(--vidro); color: var(--texto); border: 1px solid var(--linha); border-radius: 18px; padding: 14px; box-shadow: 0 18px 40px rgba(0,0,0,.35); backdrop-filter: blur(16px); z-index: 32; cursor: pointer; transform-origin: left center; animation: abre-rf-esquerda .7s ease; }
.alerta-rf-flutuante.risco { border-color: rgba(255,92,122,.65); box-shadow: 0 18px 40px rgba(255,60,90,.18); }
.alerta-rf-flutuante.info { border-color: rgba(61,220,151,.45); }
.alerta-rf-flutuante.fechando { animation: fecha-rf-esquerda .65s ease forwards; pointer-events: none; }
.alerta-rf-flutuante strong { display: block; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; color: var(--ciano); margin-bottom: 6px; }
.alerta-rf-flutuante .rf-fotos { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 8px 0; }
.alerta-rf-flutuante .rf-fotos figure { margin: 0; text-align: center; }
.alerta-rf-flutuante .rf-fotos img { width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 12px; background: rgba(8,12,24,.65); border: 1px solid var(--linha); }
.alerta-rf-flutuante .rf-fotos figcaption { font-size: 11px; color: var(--mudo); margin-top: 4px; }
.alerta-rf-flutuante .rf-meta { font-size: 13px; line-height: 1.35; margin: 0; color: var(--texto); }
.alerta-rf-flutuante .rf-link { display: block; margin-top: 10px; font-size: 12px; color: var(--ciano); font-weight: 700; }
@keyframes abre-rf-esquerda {
  from { transform: translateX(-120%) rotateY(28deg); opacity: 0; }
  to { transform: none; opacity: 1; }
}
@keyframes fecha-rf-esquerda {
  from { transform: none; opacity: 1; }
  to { transform: translateX(-120%) rotateY(28deg); opacity: 0; }
}
@media (max-width: 980px) {
  .alerta-rf-flutuante { right: 18px; left: auto; top: 72px; width: min(300px, calc(100vw - 36px)); }
}
.stage-stive { position: relative; display: inline-block; }
.stage-stive .fala-hq { right: auto; left: calc(100% + 10px); bottom: 120px; }
.stage-stive .fala-hq::after { right: auto; left: -12px; border-left-color: transparent; border-right-color: #fff; }
.luz-info { width: 14px; height: 14px; border-radius: 50%; background: #3ddc97; box-shadow: 0 0 12px #3ddc97; animation: pisca .8s infinite; display: inline-block; }
.caixa-rf { display: grid; gap: 8px; margin: 10px 0 14px; padding: 12px; border: 1px solid var(--linha); border-radius: 14px; background: rgba(8,12,24,.35); }
.caixa-rf select { min-height: 110px; }
.caixa-rf.oculta { display: none; }
.esteira-audio { display: grid; gap: 10px; max-height: 420px; overflow: auto; padding-right: 4px; }
.linha-audio { display: grid; grid-template-columns: 150px 1fr; gap: 10px; padding: 10px 12px; border-radius: 12px; background: rgba(8,12,24,.42); border-left: 4px solid #4c8dff; }
.linha-audio.risco { border-left-color: #ff5a5a; background: rgba(255,60,60,.12); }
.linha-audio.atencao { border-left-color: #ffb020; background: rgba(255,176,32,.10); }
.linha-audio .meta { color: var(--mudo); font-size: 12px; }
.linha-audio .texto { margin: 4px 0 0; line-height: 1.4; }
.selo-audio-cat { display: inline-block; margin: 2px 6px 0 0; padding: 2px 8px; border-radius: 999px; font-size: 11px; background: rgba(255,255,255,.08); }
.nuvem-audio { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; min-height: 120px; }
.nuvem-audio span { line-height: 1.1; color: #d7e6ff; }
.nuvem-audio span.risco { color: #ff8f8f; font-weight: 700; }
.rank-audio { display: grid; gap: 8px; margin-top: 10px; }
.rank-audio .barra { display: grid; grid-template-columns: 1fr 48px; gap: 8px; align-items: center; font-size: 13px; }
.rank-audio .trilha { height: 10px; border-radius: 99px; background: rgba(255,255,255,.08); overflow: hidden; }
.rank-audio .trilha i { display: block; height: 100%; background: linear-gradient(90deg, #ffb020, #ff5a5a); }
@media (max-width: 1100px) {
  aside { width: 84px; } .marca div, nav a span, .grupo { display: none; }
  .cartoes, .coluna, .grade, .grade.tres, .stive, .stive-topo { grid-template-columns: 1fr; }
  nav a .selo { display: grid; }
}
"""


def slug_camera(nome: str) -> str:
    """Slug ASCII estável para URLs /video/camera-... (evita â/ç quebrando o fluxo)."""
    import unicodedata

    texto = unicodedata.normalize("NFKD", str(nome or ""))
    texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
    texto = "".join(caractere if caractere.isalnum() else "-" for caractere in texto.lower())
    while "--" in texto:
        texto = texto.replace("--", "-")
    return texto.strip("-") or "camera"


_ARQUIVO_VISTAS = Path("vista_admin.json")


def _ler_vistas_disco() -> dict:
    if not _ARQUIVO_VISTAS.exists():
        return {}
    try:
        bruto = json.loads(_ARQUIVO_VISTAS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return bruto if isinstance(bruto, dict) else {}


def _gravar_vistas_disco(mapa: dict):
    try:
        _ARQUIVO_VISTAS.write_text(
            json.dumps(mapa, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


class Portal:
    def __init__(self, senha: str, host: str = "127.0.0.1", porta: int = 8787):
        self.senha = senha
        self.host = host
        self.porta = int(porta)
        self._trava = threading.Lock()
        self._imagens = {}
        self._seq = {}
        self._resumo = {}
        self._faces = None
        self._cameras = []
        self._acervo = None
        self._httpd = None
        self._vistas_admin = {
            str(k).strip().lower(): str(v or "").strip()
            for k, v in _ler_vistas_disco().items()
        }

    def ligar_acervo(self, acervo):
        self._acervo = acervo

    def ligar_faces(self, identificador):
        self._faces = identificador

    def publicar(self, chave: str, imagem):
        if imagem is None or getattr(imagem, "size", 0) == 0:
            return
        ok, bruto = cv2.imencode(".jpg", imagem, [int(cv2.IMWRITE_JPEG_QUALITY), 68])
        if not ok:
            return
        with self._trava:
            self._imagens[chave] = bruto.tobytes()
            self._seq[chave] = self._seq.get(chave, 0) + 1

    def quadro(self, chave: str):
        with self._trava:
            return self._imagens.get(chave), self._seq.get(chave, 0)

    def definir_resumo(self, dados: dict):
        with self._trava:
            self._resumo = dict(dados)

    def resumo(self) -> dict:
        with self._trava:
            return dict(self._resumo)

    def definir_cameras(self, cameras):
        with self._trava:
            self._cameras = list(cameras)

    def imagem(self, chave: str):
        with self._trava:
            return self._imagens.get(chave)

    def cameras(self):
        with self._trava:
            return list(self._cameras)

    def abrir_sessao(self, cabecalho: str, authorization: str = ""):
        from api_mobile import token_de_headers

        token = token_de_headers(cabecalho, authorization)
        if not token:
            token = _cookie(cabecalho)
        return acesso.ler_cookie(token, self.senha)

    def ler_vista(self, email: str) -> str:
        chave = str(email or "").strip().lower()
        with self._trava:
            return str(self._vistas_admin.get(chave) or "")

    def definir_vista(self, email: str, documento: str = "") -> str:
        """Admin: '' = geral, '__admin__' = só câmeras do admin, senão CPF/CNPJ do cliente."""
        chave = str(email or "").strip().lower()
        valor = str(documento or "").strip()
        if valor not in ("", "__admin__"):
            valor = "".join(c for c in valor if c.isdigit())
        with self._trava:
            if not chave:
                return ""
            if not valor:
                self._vistas_admin.pop(chave, None)
            else:
                self._vistas_admin[chave] = valor
            _gravar_vistas_disco(dict(self._vistas_admin))
            return valor

    def iniciar(self):
        tratador = _tratador(self)
        self._httpd = ThreadingHTTPServer((self.host, self.porta), tratador)
        self._httpd.daemon_threads = True
        threading.Thread(target=self._httpd.serve_forever, name="acesso-remoto", daemon=True).start()
        try:
            import monitor_sistema

            monitor_sistema.iniciar()
        except Exception as exc:
            print(f"Monitor de sistema não iniciado: {exc}")

    def parar(self):
        try:
            import monitor_sistema

            monitor_sistema.parar()
        except Exception:
            pass
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd = None

    def ajustar_mapa(self, periodo: str, desenho: str):
        acervo = self._acervo
        if acervo is None:
            return
        if periodo in ("dia", "semana", "mes"):
            acervo.modo_periodo = periodo
            acervo._mapa_painel_chave = None
        if desenho in ("pontos", "calor"):
            acervo.modo_desenho = desenho
            acervo._mapa_painel_chave = None


def _cookie(cabecalho: str) -> str:
    for parte in str(cabecalho or "").split(";"):
        nome, _, valor = parte.strip().partition("=")
        if nome == COOKIE:
            return valor
    return ""


def _cabecalho_cookie(token: str) -> str:
    # Secure quando o acesso público é HTTPS (túnel Cloudflare/Tailscale).
    seguro = os.getenv("WEB_HTTPS", "").strip().lower() in ("1", "true", "sim", "yes")
    base = f"{COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=2592000"
    return f"{base}; Secure" if seguro else base


def _html_seguro(texto) -> str:
    return (
        str(texto if texto is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _um(campos: dict, nome: str) -> str:
    return str((campos.get(nome) or [""])[0])


def _marcado(campos: dict, nome: str) -> bool:
    valores = campos.get(nome) or []
    if not valores:
        return False
    return str(valores[-1]) in ("1", "true", "on", "sim")


def _documento_visivel(valor: str) -> str:
    digitos = "".join(caractere for caractere in str(valor or "") if caractere.isdigit())
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    if len(digitos) == 14:
        return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}"
    return digitos


def _telefone_visivel(aviso: dict) -> str:
    pais = aviso.get("codigo_pais") or ""
    ddd = aviso.get("ddd") or ""
    numero = aviso.get("numero") or ""
    if pais and ddd and numero:
        return f"+{pais} ({ddd}) {numero}"
    return str(aviso.get("telefone") or "")


def _svg(miolo: str) -> str:
    return f"<svg viewBox='0 0 24 24'>{miolo}</svg>"


_ICONES = {
    "inicio": "<path d='M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z'/>",
    "contagem": "<path d='M4 19V10M10 19V5M16 19v-7M22 19H2'/>",
    "pessoa": "<circle cx='12' cy='8' r='3'/><path d='M5 19c1.5-3 3.8-4.5 7-4.5S17.5 16 19 19'/>",
    "animal": "<path d='M5 16c.2-3.2 2.4-6 5-6 .8 0 1.4-.6 2.2-1.6.7.3 1.6 1 2.2 1.6 1.4.2 3.6 1.6 3.6 4.2V18H5z'/><path d='M8 9.2 6.5 6M11 9.2 12 6'/><circle cx='9' cy='13' r='.7'/><circle cx='13' cy='13' r='.7'/>",
    "veiculo": "<path d='M4 15h16v3H4z'/><path d='M6 15 8.2 9h7.6L18 15'/><circle cx='7.5' cy='18.2' r='1.4'/><circle cx='16.5' cy='18.2' r='1.4'/>",
    "alerta": "<path d='M12 3 3 19h18z'/><path d='M12 9v5M12 17h.01'/>",
    "mapa": "<path d='m9 18-6 3V6l6-3 6 3 6-3v15l-6 3-6-3z'/><path d='M9 3v15M15 6v15'/>",
    "camera": "<path d='M4 7h4l2-2h4l2 2h4v12H4z'/><circle cx='12' cy='13' r='3'/>",
    "cliente": "<rect x='4' y='3' width='16' height='18' rx='2'/><path d='M8 8h8M8 12h8M8 16h5'/>",
    "aviso": "<path d='M6 9a6 6 0 0 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9'/><path d='M10 20a2 2 0 0 0 4 0'/>",
    "conta": "<circle cx='12' cy='12' r='8'/><circle cx='12' cy='10' r='2.5'/><path d='M8 16.5c.8-1.5 2.2-2.2 4-2.2s3.2.7 4 2.2'/>",
    "sair": "<path d='M10 7V5a2 2 0 0 1 2-2h7v18h-7a2 2 0 0 1-2-2v-2'/><path d='M15 12H3m0 0 3-3m-3 3 3 3'/>",
    "mais": "<path d='M12 5v14M5 12h14'/>",
    "stive": "<circle cx='12' cy='8' r='3'/><path d='M6 19c1-3 3-4.5 6-4.5s5 1.5 6 4.5'/><path d='M18 5c1.5 1.2 2 2.6 2 4'/>",
    "audio": "<path d='M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4'/>",
    "sistema": "<rect x='3' y='4' width='18' height='14' rx='2'/><path d='M7 20h10M12 18v2'/><path d='M7 9h2M11 9h2M15 9h2M7 13h10'/>",
    "grafo": "<circle cx='6' cy='12' r='2.5'/><circle cx='18' cy='6' r='2.5'/><circle cx='18' cy='18' r='2.5'/><path d='M8.2 11.2 15.8 7.2M8.2 12.8 15.8 16.8M18 8.5v9'/>",
    "vizinho": "<circle cx='8' cy='9' r='2.5'/><circle cx='16' cy='9' r='2.5'/><path d='M3 18c.8-2.4 2.4-3.6 5-3.6s4.2 1.2 5 3.6M11 18c.8-2.4 2.4-3.6 5-3.6s4.2 1.2 5 3.6'/>",
}


def _menu(ativo: str, perfil: str = "") -> str:
    # Usuário (CPF/CNPJ): painéis + cadastros da própria conta.
    # Administrador: + gestão e monitoramento de armazenamento/sistema.
    navegacao = [
        ("/", "Início", "inicio"),
        ("/painel/1", "Contagens", "contagem"),
        ("/painel/2", "Comportamento", "pessoa"),
        ("/painel/3", "Alertas de RF e LPR", "alerta"),
        ("/painel/4", "Mapas", "mapa"),
        ("/painel/risco", "Detector de risco", "alerta"),
        ("/painel/stive", "Agente Stive", "stive"),
        ("/vizinhos", "Vizinhos", "vizinho"),
        ("/painel/cameras", "Ao vivo", "camera"),
    ]
    # selo preenchido em _menu via id estável
    grupos = [
        ("Navegação", navegacao),
        ("Cadastros", [
            ("/cadastro/cameras", "Câmeras", "camera"),
            ("/cadastro/pessoas", "Pessoas", "pessoa"),
            ("/cadastro/veiculos", "Placas", "veiculo"),
            ("/cadastro/avisos", "Avisos", "aviso"),
        ]),
        ("Conta", [
            ("/conta", "Conta", "conta"),
            ("/sair", "Sair", "sair"),
        ]),
    ]
    if perfil == "administrador":
        grupos.insert(2, ("Administração", [
            ("/gestao", "Gestão de ativos", "cliente"),
            ("/painel/grifos", "Grifos de relacionamento", "grafo"),
            ("/painel/audio", "Áudio e transcrição", "audio"),
            ("/cadastro/cliente", "Cliente", "cliente"),
            ("/sistema", "Armazenamento e sistema", "sistema"),
        ]))
    partes = ["<nav>"]
    selos = {
        "/painel/stive": "<i id='selo-stive' class='selo' hidden></i>",
        "/painel/3": "<i id='selo-alertas' class='selo' hidden></i>",
        "/painel/risco": "<i id='selo-risco' class='selo' hidden></i>",
        "/painel/audio": "<i id='selo-audio' class='selo' hidden></i>",
        "/vizinhos": "<i id='selo-vizinhos' class='selo' hidden></i>",
    }
    for titulo_grupo, itens in grupos:
        partes.append(f"<p class='grupo'>{titulo_grupo}</p>")
        for href, titulo, icone in itens:
            classe = " class='ativo'" if href == ativo else ""
            selo = selos.get(href, "")
            partes.append(
                f"<a href='{href}'{classe}>{_svg(_ICONES[icone])}<span>{titulo}</span>{selo}</a>"
            )
    partes.append("</nav>")
    return "".join(partes)


def _moldura(
    titulo: str,
    miolo: str,
    ativo: str,
    parede: bool = False,
    perfil: str = "",
    csrf: str = "",
    usuario: str = "",
    documento: str = "",
    vista: str = "",
) -> str:
    classe = " parede" if parede else ""
    balao = ""
    if csrf and ativo != "/painel/stive":
        balao = (
            "<div id='balao-stive' class='balao-stive fechado'>"
            "<form id='form-balao'>"
            f"<input type='hidden' name='csrf' value='{_html_seguro(csrf)}'>"
            "<div class='chat-balao' id='chat-balao'></div>"
            "<label>Mensagem<input name='pergunta' autocomplete='off' placeholder='Fale com o Stive'></label>"
            "<button type='submit'>Enviar</button>"
            "<a class='texto' href='/painel/stive'>Abrir o Agente Stive</a>"
            "</form>"
            "<div class='grupo-puxador' id='grupo-stive'>"
            "<div id='fala-hq' class='fala-hq' hidden></div>"
            "<button type='button' class='puxador-stive' id='abrir-stive' title='Fale com o Agente Stive'>"
            "<img alt='Stive' src='/agente/stive.png?v=stive2'></button>"
            "<span class='nome-balao-stive'>Fale com o Agente Stive</span>"
            "</div></div>"
        )
    toast_rf = "<div id='alerta-rf-flutuante' class='alerta-rf-flutuante' hidden></div>" if csrf else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_seguro(titulo)}</title>
<style>{ESTILO}</style>
</head>
<body data-usuario="{_html_seguro(usuario)}" data-perfil="{_html_seguro(perfil)}" data-documento="{_html_seguro(documento)}" data-csrf="{_html_seguro(csrf)}" data-vista="{_html_seguro(vista)}">
<div class="app">
<aside>
<div class="marca"><span class="logo">C</span><div><strong>C4ISTAR</strong><small>Monitor</small></div></div>
{_menu(ativo, perfil)}
</aside>
<section class="palco{classe}"><div id="faixa-vista" class="faixa-vista" hidden></div>{miolo}</section>
</div>
<div id="led" class="led branco" title="Risco"></div>
{balao}
{toast_rf}
<script src="/painel.js?v=sis182"></script>
</body>
</html>"""


def _sessao_ui(sessao: dict | None, portal: Portal | None = None) -> dict:
    sessao = sessao or {}
    vista = ""
    if portal is not None and (sessao.get("perfil") or "") == "administrador":
        vista = portal.ler_vista(sessao.get("email") or "")
    return {
        "perfil": sessao.get("perfil") or "",
        "csrf": sessao.get("csrf") or "",
        "usuario": sessao.get("email") or "",
        "documento": sessao.get("documento") or "",
        "vista": vista,
    }


def _cabeca(titulo: str, texto: str) -> str:
    return (
        f"<header class='topo'><div><h1>{_html_seguro(titulo)}</h1>"
        f"<p>{texto}</p></div></header>"
    )


def _opcoes_vista_admin() -> list[dict]:
    saida = [
        {"valor": "", "rotulo": "Geral (toda a instalação)"},
        {"valor": "__admin__", "rotulo": "Somente câmeras do administrador"},
    ]
    for item in cadastro.listar_clientes():
        doc = "".join(c for c in str(item.get("documento") or "") if c.isdigit())
        if not doc or doc == "".join(c for c in str(cadastro.DOCUMENTO_ADMIN) if c.isdigit()):
            continue
        nome = str(item.get("nome") or "") or doc
        ativo = item.get("ativo") is not False
        saida.append({
            "valor": doc,
            "rotulo": f"{nome} · {doc}" + ("" if ativo else " (inativo)"),
        })
    return saida


def _info_vista_admin(portal: Portal, sessao: dict) -> dict:
    atual = portal.ler_vista(sessao.get("email") or "")
    if not atual:
        modo, rotulo = "geral", "Geral (toda a instalação)"
    elif atual == "__admin__":
        modo, rotulo = "admin", "Somente câmeras do administrador"
    else:
        modo = "cliente"
        cli = cadastro.cliente_por_documento(atual) or {}
        rotulo = f"{cli.get('nome') or atual} · {atual}"
    return {
        "valor": atual,
        "modo": modo,
        "rotulo": rotulo,
        "opcoes": _opcoes_vista_admin(),
    }


def _escopo_analise(portal: Portal, sessao: dict) -> tuple[str, str]:
    """Documento/perfil usados nos painéis. Admin pode segmentar a vista do portal."""
    perfil = sessao.get("perfil") or ""
    documento = sessao.get("documento") or ""
    if perfil != "administrador":
        return documento, perfil
    vista = portal.ler_vista(sessao.get("email") or "")
    if not vista:
        return "", "administrador"
    if vista == "__admin__":
        return cadastro.DOCUMENTO_ADMIN, "usuario"
    return vista, "usuario"


def _inicio(sessao: dict, portal: Portal | None = None) -> str:
    miolo = _cabeca(
        "Dashboard",
        f"{_html_seguro(sessao.get('email') or '')} · {_html_seguro(_documento_visivel(sessao.get('documento') or ''))}",
    ) + "<main id='tela' data-tela='inicio'></main>"
    return _moldura("C4ISTAR MONITOR", miolo, "/", **_sessao_ui(sessao, portal))


def _ranking_html() -> str:
    return """<aside class="ranking cartao" id="ranking">
<h2>Quem mais passa</h2>
<p>Passagens de cada código de face identificado.</p>
<div id="barras"></div>
</aside>
<script>
let ultimoRanking = "";
function escapar(texto) {
  return String(texto).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
async function ranking() {
  const resposta = await fetch('/dados.json');
  if (!resposta.ok) return;
  const dados = await resposta.json();
  const lista = dados.passagens || [];
  const marca = JSON.stringify(lista);
  if (marca === ultimoRanking) return;
  ultimoRanking = marca;
  const pico = Math.max(1, ...lista.map((item) => item.total));
  const caixa = document.getElementById('barras');
  caixa.innerHTML = lista.map((item) => {
    const nome = item.nome ? escapar(item.nome) + ' · ' : '';
    const largura = Math.round(100 * item.total / pico);
    return `<div class="linha-face"><span>${nome}${escapar(item.id)}</span><strong>${item.total}</strong></div>
      <div class="barra"><i data-w="${largura}%"></i></div>`;
  }).join('') || '<p>Ainda não há passagem de face neste histórico.</p>';
  requestAnimationFrame(() => caixa.querySelectorAll('i').forEach((el) => { el.style.width = el.dataset.w; }));
}
ranking();
setInterval(ranking, 1000);
</script>"""


def _painel(
    numero: str,
    titulo: str,
    chave: str,
    mapas: bool,
    perfil: str = "",
    csrf: str = "",
    usuario: str = "",
    documento: str = "",
    vista: str = "",
) -> str:
    telas = {"1": "contagens", "2": "comportamento", "3": "alertas", "4": "mapas"}
    comandos = ""
    if mapas:
        comandos = f"""<div class="comandos">
<button type="button" data-periodo="dia">{_svg(_ICONES["mapa"])}Dia</button>
<button type="button" data-periodo="semana">{_svg(_ICONES["mapa"])}Semana</button>
<button type="button" data-periodo="mes">{_svg(_ICONES["mapa"])}Mês</button>
<button type="button" data-desenho="pontos">{_svg(_ICONES["contagem"])}Pontos</button>
<button type="button" data-desenho="calor">{_svg(_ICONES["alerta"])}Calor</button>
<button type="button" data-desenho="mancha">{_svg(_ICONES["mapa"])}Mancha</button>
</div>"""
    miolo = _cabeca(titulo, "Os quadros seguem o mesmo padrão da tela de início.") + comandos + f"<main id='tela' data-tela='{telas[numero]}'></main>"
    return _moldura(
        f"C4ISTAR MONITOR · {titulo}", miolo, f"/painel/{numero}",
        perfil=perfil, csrf=csrf, usuario=usuario, documento=documento, vista=vista,
    )


def _risco(perfil: str = "", csrf: str = "", usuario: str = "", documento: str = "", vista: str = "") -> str:
    miolo = _cabeca("Detector de risco", "Panorama do fluxo, do comportamento e de quem reaparece.") + "<main id='tela' data-tela='risco'></main>"
    return _moldura(
        "C4ISTAR MONITOR · Detector de risco", miolo, "/painel/risco",
        perfil=perfil, csrf=csrf, usuario=usuario, documento=documento, vista=vista,
    )


def _grifos(perfil: str = "", csrf: str = "", usuario: str = "", documento: str = "", vista: str = "") -> str:
    miolo = f"""{_cabeca("Grifos de relacionamento", "Grafo de vínculos entre usuários, rostos conhecidos (Stive) e medidas protetivas.")}
<main>
<article class="cartao">
  <div class="segmentador-portal" style="margin-bottom:12px">
    <label>Cliente<select id="filtro-grafo-cliente"><option value="">Todos os clientes</option></select></label>
    <label>Pessoa monitorada<select id="filtro-grafo-pessoa"><option value="">Todas as pessoas</option></select></label>
    <label>Tipo de vínculo<select id="filtro-grafo-vinculo"><option value="">Todos os vínculos</option></select></label>
  </div>
  <div class="acoes-gestao" style="margin-bottom:10px">
    <button type="button" id="recarregar-grafo">Atualizar grafo</button>
    <button type="button" id="limpar-filtro-grafo">Limpar filtros</button>
    <span id="meta-grafo" style="color:var(--mudo);font-size:13px"></span>
  </div>
  <div id="grafo-relacoes" style="height:min(72vh,720px);border:1px solid var(--linha);border-radius:16px;background:rgba(8,12,24,.55)"></div>
</article>
<section class="grade">
<article class="cartao">
  <h2>Legenda de nós</h2>
  <p>Azul: usuário · Vermelho: pessoa de risco · Roxo: medida protetiva · Rosa: demais rostos.</p>
  <h2 style="margin-top:14px">Vínculos evidenciados</h2>
  <p id="legenda-vinculos" style="color:var(--mudo);font-size:13px;line-height:1.6">Carregando…</p>
</article>
<article class="cartao">
  <h2>Resumo na vista</h2>
  <div id="resumo-vinculos"><p style="color:var(--mudo)">Carregando…</p></div>
</article>
</section>
</main>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<script>
(function () {{
  const caixa = document.getElementById("grafo-relacoes");
  const meta = document.getElementById("meta-grafo");
  const selCli = document.getElementById("filtro-grafo-cliente");
  const selPes = document.getElementById("filtro-grafo-pessoa");
  const selVin = document.getElementById("filtro-grafo-vinculo");
  const legenda = document.getElementById("legenda-vinculos");
  const resumo = document.getElementById("resumo-vinculos");
  let rede = null;
  let opcoesProntas = false;
  let cacheDados = null;
  function popularSelects(dados) {{
    if (!selCli || !selPes) return;
    if (!opcoesProntas) {{
      const cliAtual = selCli.value;
      const pesAtual = selPes.value;
      selCli.innerHTML = '<option value="">Todos os clientes</option>' + (dados.opcoes_clientes || []).map((c) =>
        `<option value="${{c.documento || ""}}">${{(c.nome || c.documento || "")}} · ${{c.documento || ""}}</option>`
      ).join("");
      selPes.innerHTML = '<option value="">Todas as pessoas</option>' + (dados.opcoes_pessoas || []).map((p) =>
        `<option value="${{p.face_id || ""}}">${{(p.nome || p.face_id || "")}} · ${{p.face_id || ""}}</option>`
      ).join("");
      if (cliAtual) selCli.value = cliAtual;
      if (pesAtual) selPes.value = pesAtual;
      opcoesProntas = true;
    }}
    if (selVin && !selVin.dataset.pronto) {{
      const tipos = dados.tipos || {{}};
      selVin.innerHTML = '<option value="">Todos os vínculos</option>' + Object.keys(tipos).map((k) =>
        `<option value="${{k}}">${{tipos[k] || k}}</option>`
      ).join("");
      selVin.dataset.pronto = "1";
    }}
    if (legenda) {{
      const tipos = dados.tipos || {{}};
      legenda.textContent = Object.keys(tipos).map((k) => tipos[k] || k).join(" · ");
    }}
  }}
  function pintarResumo(dados, edges) {{
    if (!resumo) return;
    const mapa = {{}};
    (edges || []).forEach((e) => {{
      const tipo = e.tipo || "outro";
      mapa[tipo] = (mapa[tipo] || 0) + 1;
    }});
    const tipos = (dados && dados.tipos) || {{}};
    const linhas = Object.keys(mapa).sort((a, b) => mapa[b] - mapa[a]).map((tipo) => {{
      const item = (dados.resumo_vinculos || []).find((r) => r.tipo === tipo) || {{}};
      const cor = item.cor || "#7a8799";
      const rotulo = item.rotulo || tipos[tipo] || tipo;
      return `<tr><td><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${{cor}};margin-right:6px"></span>${{rotulo}}</td><td style="text-align:right">${{mapa[tipo]}}</td></tr>`;
    }});
    resumo.innerHTML = linhas.length
      ? `<table><tr><th>Vínculo</th><th>Qtde</th></tr>${{linhas.join("")}}</table>`
      : "<p style='color:var(--mudo)'>Nenhum vínculo nesta vista.</p>";
  }}
  function desenhar(dados) {{
    if (!caixa || !window.vis) {{
      if (meta) meta.textContent = "Biblioteca de grafo indisponível.";
      return;
    }}
    const filtroVin = selVin ? String(selVin.value || "") : "";
    let edges = Array.isArray(dados.edges) ? dados.edges.slice() : [];
    if (filtroVin) edges = edges.filter((e) => String(e.tipo || "") === filtroVin);
    const usados = new Set();
    edges.forEach((e) => {{ usados.add(e.from); usados.add(e.to); }});
    let nodes = Array.isArray(dados.nodes) ? dados.nodes.slice() : [];
    if (filtroVin) nodes = nodes.filter((n) => usados.has(n.id));
    const nodesDS = new vis.DataSet(nodes);
    const edgesDS = new vis.DataSet(edges);
    if (rede) rede.destroy();
    rede = new vis.Network(caixa, {{ nodes: nodesDS, edges: edgesDS }}, {{
      nodes: {{ shape: "dot", size: 18, font: {{ color: "#e8eefc", size: 13 }} }},
      edges: {{
        font: {{ size: 12, strokeWidth: 0, align: "middle" }},
        smooth: {{ type: "continuous" }},
        arrows: {{ to: {{ enabled: true, scaleFactor: 0.7 }} }},
      }},
      physics: {{ stabilization: true, barnesHut: {{ gravitationalConstant: -12000, springLength: 160 }} }},
      interaction: {{ hover: true, tooltipDelay: 120 }},
    }});
    const doc = selCli ? selCli.value : "";
    const face = selPes ? selPes.value : "";
    const foco = [doc && ("cliente " + doc), face && ("pessoa " + face), filtroVin && ("vínculo " + filtroVin)].filter(Boolean).join(" · ");
    if (meta) meta.textContent = `${{nodes.length}} nós · ${{edges.length}} vínculos · motor ${{dados.motor || "json"}}${{foco ? " · filtro: " + foco : ""}}`;
    pintarResumo(dados, edges);
  }}
  async function carregar() {{
    const doc = selCli ? selCli.value : "";
    const face = selPes ? selPes.value : "";
    const qs = new URLSearchParams();
    if (doc) qs.set("documento", doc);
    if (face) qs.set("face_id", face);
    const resp = await fetch("/api/grafo.json?" + qs.toString());
    const dados = await resp.json().catch(() => ({{}}));
    cacheDados = dados;
    popularSelects(dados);
    desenhar(dados);
  }}
  document.getElementById("recarregar-grafo")?.addEventListener("click", carregar);
  document.getElementById("limpar-filtro-grafo")?.addEventListener("click", () => {{
    if (selCli) selCli.value = "";
    if (selPes) selPes.value = "";
    if (selVin) selVin.value = "";
    carregar();
  }});
  selCli?.addEventListener("change", carregar);
  selPes?.addEventListener("change", carregar);
  selVin?.addEventListener("change", () => {{ if (cacheDados) desenhar(cacheDados); }});
  carregar();
}})();
</script>"""
    return _moldura(
        "C4ISTAR MONITOR · Grifos de relacionamento",
        miolo,
        "/painel/grifos",
        perfil=perfil, csrf=csrf, usuario=usuario, documento=documento, vista=vista,
    )


def _audio(perfil: str = "", csrf: str = "", usuario: str = "", documento: str = "", vista: str = "") -> str:
    miolo = (
        _cabeca(
            "Áudio e transcrição",
            "Esteira de falas por câmera, nuvem de palavras e ranking de risco sonoro.",
        )
        + "<main id='tela' data-tela='audio'></main>"
    )
    return _moldura(
        "C4ISTAR MONITOR · Áudio e transcrição", miolo, "/painel/audio",
        perfil=perfil, csrf=csrf, usuario=usuario, documento=documento, vista=vista,
    )


def _vizinhos(sessao: dict, aviso: str = "", ok: bool = False) -> str:
    import grupos_seguranca as grupos
    import vizinhos as rede
    from grafo_relacoes import VINCULOS_STIVE

    documento = sessao.get("documento") or ""
    alertas = rede.listar_alertas(documento)
    contatos = rede.listar_vizinhos(documento)
    pendencias = rede.listar_solicitacoes(documento)
    meus_grupos = grupos.listar_grupos(documento)
    cliente = cadastro.cliente_por_documento(documento) or {}
    minhas_cameras = [
        {"id": str(c.get("id") or "").strip(), "nome": str(c.get("nome") or "").strip()}
        for c in (cliente.get("cameras") or [])
        if isinstance(c, dict) and c.get("ativa") is not False and (c.get("id") or c.get("nome"))
    ]
    # Ao abrir a tela, limpa o selo (mantém solicitações para aceitar).
    try:
        rede.marcar_alertas_vistos(documento)
    except Exception:
        pass
    opcoes_vinculo = "".join(
        f"<option value='{_html_seguro(chave)}'>{_html_seguro(rotulo)}</option>"
        for chave, rotulo in VINCULOS_STIVE.items()
    )
    lista_html = []
    for item in contatos:
        face = _html_seguro(item.get("foto_face_id") or "")
        avatar = (
            f"<img class='vizinho-avatar' alt='' src='/rosto/{face}.jpg' onerror=\"this.replaceWith(Object.assign(document.createElement('div'),{{className:'vizinho-avatar'}}))\""
            if face else "<div class='vizinho-avatar'></div>"
        )
        lista_html.append(
            f"<button type='button' class='vizinho-item' data-doc='{_html_seguro(item.get('documento'))}'>"
            f"{avatar}<span><strong>{_html_seguro(item.get('nome'))}</strong>"
            f"<span>{_html_seguro(item.get('vinculo') or 'Vizinho')} · {_html_seguro(item.get('ultima_mensagem') or 'Sem mensagens')}</span></span></button>"
        )
    lista = "".join(lista_html) or "<p class='mudo'>Nenhum vizinho aceito ainda.</p>"
    pend_html = []
    for item in pendencias.get("recebidas") or []:
        pend_html.append(
            f"<div class='pend' data-doc='{_html_seguro(item.get('documento'))}'>"
            f"<strong>{_html_seguro(item.get('nome'))}</strong> quer te adicionar"
            f"{(' · ' + _html_seguro(item.get('vinculo'))) if item.get('vinculo') else ''}."
            f"<span><button type='button' data-acao='aceitar'>Aceitar</button> "
            f"<button type='button' data-acao='recusar'>Recusar</button></span></div>"
        )
    for item in pendencias.get("enviadas") or []:
        pend_html.append(
            f"<div class='pend'><strong>{_html_seguro(item.get('nome'))}</strong> — solicitação enviada, aguardando.</div>"
        )
    bloco_pend = (
        f"<div class='vizinhos-pendencias'><h2>Solicitações</h2>{''.join(pend_html)}</div>"
        if pend_html else ""
    )
    notas = [
        f"<p class='ok'>{_html_seguro(item.get('texto') or '')}</p>"
        for item in alertas if item.get("tipo") in ("aceite", "info", "recusa")
    ]
    bloco_notas = "".join(notas)
    opcoes_contatos = "".join(
        f"<option value='{_html_seguro(item.get('documento'))}'>{_html_seguro(item.get('nome'))}</option>"
        for item in contatos
    )
    opcoes_cams = "".join(
        f"<option value='{_html_seguro(c.get('id') or c.get('nome'))}'>{_html_seguro(c.get('nome'))}</option>"
        for c in minhas_cameras
    )
    digitos_eu = "".join(c for c in str(documento) if c.isdigit())
    cartas_html = []
    for g in meus_grupos:
        membros_txt = ", ".join(
            _html_seguro(m.get("nome") or m.get("documento") or "")
            for m in (g.get("membros") or [])
        ) or "—"
        cams_html = "".join(
            f"<span class='chip' title='{_html_seguro(c.get('documento') or '')}'>{_html_seguro(c.get('nome'))}"
            f"<button type='button' data-acao-grupo='rm-cam' data-gid='{_html_seguro(g.get('id'))}' "
            f"data-cam='{_html_seguro(c.get('camera_id'))}' style='margin-left:4px;border:0;background:transparent;color:inherit;cursor:pointer'>×</button></span>"
            for c in (g.get("cameras") or [])
        ) or "<span class='mudo'>Nenhuma câmera compartilhada ainda.</span>"
        acoes = [
            f"<label>Adicionar vizinho<select data-gid='{_html_seguro(g.get('id'))}' class='sel-membro-grupo'>"
            f"<option value=''>Escolher contato…</option>{opcoes_contatos}</select></label>",
            f"<label>Compartilhar câmera<select data-gid='{_html_seguro(g.get('id'))}' class='sel-cam-grupo'>"
            f"<option value=''>Escolher câmera…</option>{opcoes_cams}</select></label>",
            f"<button type='button' data-acao-grupo='add-membro' data-gid='{_html_seguro(g.get('id'))}'>Incluir membro</button>",
            f"<button type='button' data-acao-grupo='add-cam' data-gid='{_html_seguro(g.get('id'))}'>Compartilhar</button>",
        ]
        if str(g.get("criador") or "") == digitos_eu:
            acoes.append(
                f"<button type='button' data-acao-grupo='excluir' data-gid='{_html_seguro(g.get('id'))}'>Excluir grupo</button>"
            )
        else:
            acoes.append(
                f"<button type='button' data-acao-grupo='sair' data-gid='{_html_seguro(g.get('id'))}'>Sair do grupo</button>"
            )
        cartas_html.append(
            f"<div class='grupo-carta' data-gid='{_html_seguro(g.get('id'))}'>"
            f"<strong>{_html_seguro(g.get('nome'))}</strong>"
            f"<span class='mudo'>{_html_seguro(g.get('descricao') or 'Grupo de segurança entre vizinhos')}</span>"
            f"<div><span class='mudo'>Membros:</span> {membros_txt}</div>"
            f"<div class='chips'>{cams_html}</div>"
            f"<div class='acoes-grupo'>{''.join(acoes)}</div>"
            f"</div>"
        )
    bloco_grupos = "".join(cartas_html) or "<p class='mudo'>Nenhum grupo ainda. Crie o primeiro abaixo.</p>"
    miolo = f"""<header class="topo"><div><h1>Vizinhos</h1>
<p>Digite o nome, escolha na lista da plataforma, envie a solicitação. Depois do aceite, a notificação aparece e já podem conversar. Crie grupos de segurança para compartilhar câmeras de ruas distintas e receber alertas em conjunto.</p></div></header>
<main>
{_aviso_html(aviso, ok)}
{bloco_notas}
<section class="vizinhos-layout">
<article class="vizinhos-lista">
<h2>Contatos</h2>
<button type="button" id="btn-abrir-add-vizinho">{_svg(_ICONES["mais"])}Adicionar vizinho</button>
<div id="lista-vizinhos" style="margin-top:12px">{lista}</div>
{bloco_pend}
</article>
<article class="vizinhos-chat">
<h2 id="titulo-chat-vizinho">Conversa</h2>
<p id="subtitulo-chat-vizinho" class="mudo">Escolha um contato à esquerda.</p>
<div class="chat" id="chat-vizinhos"></div>
<form id="form-chat-vizinho" enctype="multipart/form-data">
{_csrf(sessao)}
<input type="hidden" name="documento_vizinho" id="doc-chat-vizinho" value="">
<label style="grid-column:1 / -1">Mensagem
<input name="texto" id="texto-chat-vizinho" placeholder="Escreva como no WhatsApp" autocomplete="off" disabled>
</label>
<label>Foto<input type="file" name="foto" id="foto-chat-vizinho" accept="image/*" disabled></label>
<button type="submit" id="btn-chat-vizinho" disabled>Enviar</button>
</form>
</article>
</section>
<section class="grupos-seguranca" id="grupos-seguranca">
<h2>Grupos de segurança</h2>
<p class="mudo">Ex.: “Grupo de segurança da área do Flamengo”. Câmeras de ruas diferentes e alertas (incluindo reconhecimento facial) chegam a todos os membros; no ao vivo você também vê as câmeras compartilhadas no grupo.</p>
{bloco_grupos}
<form id="form-criar-grupo" class="criar-grupo">
{_csrf(sessao)}
<label>Nome do grupo<input name="nome" required minlength="3" placeholder="Grupo de segurança da área do Flamengo"></label>
<label>Descrição<input name="descricao" placeholder="Condomínio, família, amigos…"></label>
<button type="submit">Criar grupo</button>
</form>
</section>
</main>
<div class="vizinhos-modal" id="modal-add-vizinho" hidden>
<div class="caixa">
<h2>Adicionar vizinho</h2>
<p>Digite o nome para procurar quem já tem conta. Se não achar, envie convite por e-mail ou WhatsApp.</p>
<label>Nome
<input type="search" id="busca-vizinho-nome" placeholder="Comece a digitar o nome…" autocomplete="off" list="">
</label>
<div class="busca-resultados" id="busca-vizinho-resultados" role="listbox" aria-label="Contas encontradas"></div>
<form id="form-solicitar-vizinho" class="vizinhos-add">
{_csrf(sessao)}
<input type="hidden" name="documento_vizinho" id="doc-solicitar-vizinho" value="">
<p id="nome-solicitar-vizinho" class="mudo">Selecione uma pessoa na lista abaixo do nome.</p>
<label>Vínculo (opcional)
<select name="vinculo" id="vinculo-solicitar">
<option value="">Não informar</option>
{opcoes_vinculo}
</select></label>
<label>Avisar também
<select name="notificar" id="notificar-solicitar">
<option value="">Só na plataforma</option>
<option value="email">E-mail da conta</option>
<option value="whatsapp">WhatsApp cadastrado</option>
<option value="ambos">E-mail e WhatsApp</option>
</select></label>
<button type="submit" id="btn-solicitar-vizinho" disabled>Enviar solicitação</button>
</form>
<hr style="border:0;border-top:1px solid var(--linha);margin:16px 0">
<form id="form-convidar-externo" class="vizinhos-add">
{_csrf(sessao)}
<strong>Convidar por e-mail ou WhatsApp</strong>
<label>Nome<input name="nome" placeholder="Nome da pessoa"></label>
<label>E-mail<input type="email" name="email" placeholder="email@exemplo.com"></label>
<label>WhatsApp<input name="telefone" placeholder="5511999999999"></label>
<label>Canal
<select name="canal">
<option value="email">E-mail</option>
<option value="whatsapp">WhatsApp</option>
<option value="ambos">Ambos</option>
</select></label>
<button type="submit">Enviar convite</button>
</form>
<p style="margin-top:12px"><button type="button" id="btn-fechar-add-vizinho">Fechar</button></p>
</div>
</div>
<script>
(() => {{
  const lista = document.getElementById("lista-vizinhos");
  const chat = document.getElementById("chat-vizinhos");
  const titulo = document.getElementById("titulo-chat-vizinho");
  const sub = document.getElementById("subtitulo-chat-vizinho");
  const docCampo = document.getElementById("doc-chat-vizinho");
  const texto = document.getElementById("texto-chat-vizinho");
  const foto = document.getElementById("foto-chat-vizinho");
  const btn = document.getElementById("btn-chat-vizinho");
  const form = document.getElementById("form-chat-vizinho");
  const csrf = (form && form.querySelector("[name=csrf]") || {{}}).value || document.body.dataset.csrf || "";
  const modal = document.getElementById("modal-add-vizinho");
  const busca = document.getElementById("busca-vizinho-nome");
  const resultados = document.getElementById("busca-vizinho-resultados");
  const formSol = document.getElementById("form-solicitar-vizinho");
  const docSol = document.getElementById("doc-solicitar-vizinho");
  const nomeSol = document.getElementById("nome-solicitar-vizinho");
  const btnSol = document.getElementById("btn-solicitar-vizinho");
  let ativo = "";
  let timer = null;
  let timerBusca = null;
  function bolha(msg) {{
    const eu = msg.de === (document.body.dataset.documento || "");
    const fotoHtml = msg.foto ? `<img alt="foto" src="/vizinhos/foto/${{msg.foto}}">` : "";
    return `<div class="bolha ${{eu ? "eu" : "vizinho"}}">${{escapar(msg.texto || "")}}${{fotoHtml}}<small style="display:block;opacity:.65;margin-top:4px;font-size:11px">${{escapar(msg.quando || "")}}</small></div>`;
  }}
  function escapar(t) {{
    return String(t || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }}
  function abrirModal() {{
    modal.hidden = false;
    modal.classList.add("aberto");
    busca.focus();
  }}
  function fecharModal() {{
    modal.classList.remove("aberto");
    modal.hidden = true;
  }}
  document.getElementById("btn-abrir-add-vizinho")?.addEventListener("click", abrirModal);
  document.getElementById("btn-fechar-add-vizinho")?.addEventListener("click", fecharModal);
  modal?.addEventListener("click", (ev) => {{ if (ev.target === modal) fecharModal(); }});
  async function carregarChat(doc, nome) {{
    ativo = doc;
    docCampo.value = doc;
    texto.disabled = false; foto.disabled = false; btn.disabled = false;
    titulo.textContent = nome || "Conversa";
    sub.textContent = "Documento " + doc;
    lista.querySelectorAll(".vizinho-item").forEach((el) => el.classList.toggle("ativo", el.dataset.doc === doc));
    const resp = await fetch("/vizinhos/chat.json?documento=" + encodeURIComponent(doc));
    const dados = await resp.json().catch(() => ({{mensagens: []}}));
    chat.innerHTML = (dados.mensagens || []).map(bolha).join("") || "<p class='mudo'>Nenhuma mensagem ainda.</p>";
    chat.scrollTop = chat.scrollHeight;
  }}
  lista?.addEventListener("click", (ev) => {{
    const item = ev.target.closest(".vizinho-item");
    if (!item) return;
    const nome = item.querySelector("strong")?.textContent || "";
    carregarChat(item.dataset.doc || "", nome);
    if (timer) clearInterval(timer);
    timer = setInterval(() => {{ if (ativo) carregarChat(ativo, titulo.textContent); }}, 4000);
  }});
  form?.addEventListener("submit", async (ev) => {{
    ev.preventDefault();
    if (!ativo) return;
    const corpo = new FormData(form);
    corpo.set("csrf", csrf);
    corpo.set("documento_vizinho", ativo);
    const resp = await fetch("/vizinhos/mensagem", {{ method: "POST", body: corpo }});
    const dados = await resp.json().catch(() => ({{}}));
    if (!dados.ok) {{ alert(dados.erro || "Não foi possível enviar."); return; }}
    texto.value = "";
    foto.value = "";
    carregarChat(ativo, titulo.textContent);
  }});
  async function buscarNome() {{
    const q = (busca.value || "").trim();
    docSol.value = "";
    btnSol.disabled = true;
    nomeSol.textContent = "Selecione uma pessoa na lista.";
    if (q.length < 2) {{ resultados.innerHTML = "<p class='mudo'>Digite ao menos 2 letras.</p>"; return; }}
    const resp = await fetch("/vizinhos/buscar.json?q=" + encodeURIComponent(q));
    const dados = await resp.json().catch(() => ({{itens: []}}));
    const itens = dados.itens || [];
    if (!itens.length) {{
      resultados.innerHTML = "<p class='mudo'>Nenhuma conta na plataforma com este nome. Convide por e-mail/WhatsApp abaixo.</p>";
      return;
    }}
    resultados.innerHTML = itens.map((item) => {{
      const face = item.foto_face_id || "";
      const avatar = face
        ? `<img class="vizinho-avatar" alt="" src="/rosto/${{face}}.jpg" onerror="this.replaceWith(Object.assign(document.createElement('div'),{{className:'vizinho-avatar'}}))">`
        : `<div class="vizinho-avatar"></div>`;
      const extra = [item.rua, item.bairro].filter(Boolean).join(" · ");
      return `<button type="button" class="busca-item" role="option" data-doc="${{escapar(item.documento)}}" data-nome="${{escapar(item.nome)}}">${{avatar}}<span><strong>${{escapar(item.nome)}}</strong><span>${{escapar(extra || "Na plataforma")}}</span></span></button>`;
    }}).join("");
  }}
  busca?.addEventListener("input", () => {{
    clearTimeout(timerBusca);
    timerBusca = setTimeout(buscarNome, 180);
  }});
  busca?.addEventListener("focus", () => {{
    if ((busca.value || "").trim().length >= 2) buscarNome();
  }});
  resultados?.addEventListener("click", (ev) => {{
    const item = ev.target.closest(".busca-item");
    if (!item) return;
    docSol.value = item.dataset.doc || "";
    busca.value = item.dataset.nome || "";
    nomeSol.textContent = "Selecionado: " + (item.dataset.nome || item.dataset.doc || "");
    btnSol.disabled = !docSol.value;
    resultados.querySelectorAll(".busca-item").forEach((el) => el.classList.toggle("ativo", el === item));
  }});
  formSol?.addEventListener("submit", async (ev) => {{
    ev.preventDefault();
    if (!docSol.value) return;
    const corpo = new URLSearchParams(new FormData(formSol));
    corpo.set("csrf", csrf);
    const resp = await fetch("/vizinhos/solicitar", {{ method: "POST", headers: {{ "Content-Type": "application/x-www-form-urlencoded" }}, body: corpo }});
    const dados = await resp.json().catch(() => ({{}}));
    if (!dados.ok) {{ alert(dados.erro || "Não foi possível enviar a solicitação."); return; }}
    alert(dados.fala || "Solicitação enviada.");
    location.reload();
  }});
  document.getElementById("form-convidar-externo")?.addEventListener("submit", async (ev) => {{
    ev.preventDefault();
    const formC = ev.currentTarget;
    const corpo = new URLSearchParams(new FormData(formC));
    corpo.set("csrf", csrf);
    const resp = await fetch("/vizinhos/convidar", {{ method: "POST", headers: {{ "Content-Type": "application/x-www-form-urlencoded" }}, body: corpo }});
    const dados = await resp.json().catch(() => ({{}}));
    if (!dados.ok) {{ alert(dados.erro || "Não foi possível convidar."); return; }}
    if (dados.whatsapp_link) {{
      if (confirm((dados.fala || "Convite pronto.") + "\\nAbrir WhatsApp?")) window.open(dados.whatsapp_link, "_blank");
    }} else {{
      alert(dados.fala || "Convite enviado.");
    }}
  }});
  document.querySelector(".vizinhos-pendencias")?.addEventListener("click", async (ev) => {{
    const botao = ev.target.closest("button[data-acao]");
    const caixa = ev.target.closest(".pend");
    if (!botao || !caixa || !caixa.dataset.doc) return;
    const corpo = new URLSearchParams();
    corpo.set("csrf", csrf);
    corpo.set("documento_vizinho", caixa.dataset.doc);
    corpo.set("resposta", botao.dataset.acao || "recusar");
    const resp = await fetch("/vizinhos/responder", {{ method: "POST", headers: {{ "Content-Type": "application/x-www-form-urlencoded" }}, body: corpo }});
    const dados = await resp.json().catch(() => ({{}}));
    if (!dados.ok) {{ alert(dados.erro || "Não foi possível responder."); return; }}
    location.reload();
  }});
  async function postGrupo(acao, extras) {{
    const corpo = new URLSearchParams();
    corpo.set("csrf", csrf);
    corpo.set("acao", acao);
    Object.entries(extras || {{}}).forEach(([k, v]) => corpo.set(k, v));
    const resp = await fetch("/vizinhos/grupos", {{ method: "POST", headers: {{ "Content-Type": "application/x-www-form-urlencoded" }}, body: corpo }});
    return resp.json().catch(() => ({{}}));
  }}
  document.getElementById("form-criar-grupo")?.addEventListener("submit", async (ev) => {{
    ev.preventDefault();
    const formG = ev.currentTarget;
    const dados = await postGrupo("criar", {{
      nome: formG.nome.value || "",
      descricao: formG.descricao.value || "",
    }});
    if (!dados.ok) {{ alert(dados.erro || "Não foi possível criar o grupo."); return; }}
    location.reload();
  }});
  document.getElementById("grupos-seguranca")?.addEventListener("click", async (ev) => {{
    const botao = ev.target.closest("[data-acao-grupo]");
    if (!botao) return;
    const gid = botao.dataset.gid || "";
    const acao = botao.dataset.acaoGrupo || "";
    if (acao === "excluir" && !confirm("Excluir este grupo de segurança?")) return;
    if (acao === "sair" && !confirm("Sair deste grupo?")) return;
    let extras = {{ grupo_id: gid }};
    if (acao === "add-membro") {{
      const sel = document.querySelector(`select.sel-membro-grupo[data-gid="${{gid}}"]`);
      extras.documento_membro = (sel && sel.value) || "";
      if (!extras.documento_membro) {{ alert("Escolha um vizinho."); return; }}
    }}
    if (acao === "add-cam") {{
      const sel = document.querySelector(`select.sel-cam-grupo[data-gid="${{gid}}"]`);
      extras.camera_id = (sel && sel.value) || "";
      if (!extras.camera_id) {{ alert("Escolha uma câmera."); return; }}
    }}
    if (acao === "rm-cam") extras.camera_id = botao.dataset.cam || "";
    if (acao === "sair") extras.documento_membro = document.body.dataset.documento || "";
    const mapa = {{
      "add-membro": "membro",
      "add-cam": "camera",
      "rm-cam": "remover_camera",
      "excluir": "excluir",
      "sair": "remover_membro",
    }};
    const dados = await postGrupo(mapa[acao] || acao, extras);
    if (!dados.ok) {{ alert(dados.erro || "Não foi possível atualizar o grupo."); return; }}
    location.reload();
  }});
}})();
</script>"""
    return _moldura("Vizinhos · C4ISTAR MONITOR", miolo, "/vizinhos", **_sessao_ui(sessao))


def _ao_vivo(cameras, perfil: str = "", csrf: str = "", usuario: str = "", documento: str = "", vista: str = "") -> str:
    blocos = []
    for slug, nome, rua in cameras:
        legenda = _html_seguro(f"{nome} {rua}".strip())
        blocos.append(
            f"<figure class='video' data-camera='{_html_seguro(nome)}'>"
            f"<figcaption>{_svg(_ICONES['camera'])}{legenda}</figcaption>"
            f"<img alt='{legenda}' src='/video/camera-{_html_seguro(slug)}'>"
            f"</figure>"
        )
    grade = "".join(blocos) or (
        "<p>Nenhuma câmera visível. Cadastre ao menos uma câmera em "
        "<a class='texto' href='/cadastro/cameras'>Câmeras</a> para ver a sua rua.</p>"
    )
    miolo = (
        _cabeca(
            "Ao vivo",
            "Suas câmeras e as do mesmo logradouro, se você estiver compartilhando ao menos uma.",
        )
        + f"<main id='tela' data-tela='vivo'><section class='grade'>{grade}</section></main>"
    )
    return _moldura(
        "C4ISTAR MONITOR · Ao vivo", miolo, "/painel/cameras",
        perfil=perfil, csrf=csrf, usuario=usuario, documento=documento, vista=vista,
    )


def _stive(sessao: dict, portal: Portal | None = None) -> str:
    script = """
<script>
const chat = document.getElementById("chat-stive");
const quadro = document.getElementById("quadro-stive");
const form = document.getElementById("form-stive");
const SAUDACAO = "Posso cruzar pessoa, horário e local como analista criminal. Pergunte a chance de invasão, padrões de madrugada, ou me conte uma ocorrência.";
function chaveChatStive() {
  const u = (document.body.dataset.usuario || "").trim().toLowerCase() || "anon";
  return "stive-chat:" + u;
}
function chaveVisualStive() {
  const u = (document.body.dataset.usuario || "").trim().toLowerCase() || "anon";
  return "stive-visual:" + u;
}
function lerHistorico() {
  try {
    sessionStorage.removeItem("stive-chat");
    const bruto = JSON.parse(sessionStorage.getItem(chaveChatStive()) || "[]");
    return Array.isArray(bruto) ? bruto.filter((item) => item && item.papel && item.texto).slice(-80) : [];
  } catch (erro) { return []; }
}
function gravarHistorico(lista) {
  try { sessionStorage.setItem(chaveChatStive(), JSON.stringify((lista || []).slice(-80))); } catch (erro) {}
}
function bolha(papel, texto, gravar) {
  const p = document.createElement("p");
  p.className = "bolha " + papel;
  p.textContent = texto;
  chat.appendChild(p);
  chat.scrollTop = chat.scrollHeight;
  if (gravar !== false) {
    const lista = lerHistorico();
    lista.push({ papel, texto: String(texto || "").slice(0, 4000) });
    gravarHistorico(lista);
  }
}
function restaurarChat() {
  const lista = lerHistorico();
  chat.innerHTML = "";
  if (!lista.length) {
    bolha("stive", SAUDACAO, false);
    return;
  }
  lista.forEach((item) => bolha(item.papel, item.texto, false));
  requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });
}
function desenharVisual(visual) {
  if (!quadro) return;
  const itens = (visual && visual.itens) || [];
  const titulo = (visual && visual.titulo) || "Quadro do Stive";
  const tipo = (visual && visual.tipo) || "texto";
  if ((tipo === "barras" || tipo === "linha" || tipo === "rosca") && itens.length) {
    quadro.innerHTML = "<h2></h2><canvas class='grafico grafico-rosca' id='grafico-stive' width='640' height='280'></canvas>";
    quadro.querySelector("h2").textContent = titulo;
    const canvas = document.getElementById("grafico-stive");
    const serie = itens.map((item, indice) => ({
      rotulo: String(item.rotulo || ""),
      nome: String(item.rotulo || ""),
      total: Number(item.total) || 0,
      cor: ["#4c8dff", "#3ee0ff", "#7cffb2", "#ffb020", "#ff5c7a", "#c084fc"][indice % 6],
    }));
    if (tipo === "rosca" && typeof roscaLivre === "function") roscaLivre(canvas, serie);
    else if (typeof barrasVerticais === "function") barrasVerticais(canvas, serie);
    try { sessionStorage.setItem(chaveVisualStive(), JSON.stringify(visual)); } catch (erro) {}
    return;
  }
  quadro.innerHTML = "<h2>" + titulo.replace(/[&<>]/g, "") + "</h2>" + (itens.map((item) =>
    "<div class='linha-face'><span>" + String(item.rotulo || "") + "</span><strong>" + String(item.total ?? "") + "</strong></div>"
  ).join("") || "<p>O quadro acompanha o que você pedir na conversa.</p>");
  try { sessionStorage.setItem(chaveVisualStive(), JSON.stringify(visual || {})); } catch (erro) {}
}
function limparQuadro() {
  if (!quadro) return;
  quadro.innerHTML = "<h2>Quadro do Stive</h2><p>O que você pedir na conversa aparece aqui.</p>";
  try {
    sessionStorage.removeItem("stive-visual");
    sessionStorage.removeItem(chaveVisualStive());
  } catch (erro) {}
}
window.addEventListener("load", async () => {
  let visualServidor = null;
  try {
    const resp = await fetch("/agente/stive/historico.json");
    if (resp.ok) {
      const pacote = await resp.json();
      if (Array.isArray(pacote.itens) && pacote.itens.length) {
        gravarHistorico(pacote.itens.map((item) => ({ papel: item.papel, texto: item.texto })));
      }
      if (pacote.visual && typeof pacote.visual === "object") visualServidor = pacote.visual;
    }
  } catch (erro) {}
  restaurarChat();
  try {
    sessionStorage.removeItem("stive-visual");
    const temItens = visualServidor && Array.isArray(visualServidor.itens) && visualServidor.itens.length;
    if (temItens) desenharVisual(visualServidor);
    else limparQuadro();
  } catch (erro) { limparQuadro(); }
  const caixaAdmin = document.getElementById("historico-stive-admin");
  if (caixaAdmin && document.body.dataset.perfil === "administrador") {
    try {
      const resp = await fetch("/agente/stive/historico.json?todos=1");
      if (!resp.ok) return;
      const pacote = await resp.json();
      const itens = Array.isArray(pacote.itens) ? pacote.itens : [];
      if (!itens.length) {
        caixaAdmin.innerHTML = "<p>Ainda não há conversas registradas.</p>";
        return;
      }
      caixaAdmin.innerHTML = itens.map((item) => {
        const quem = item.email || item.origem || "usuário";
        const papel = item.papel === "eu" ? "Usuário" : "Stive";
        return "<div class='linha-face'><span>" + String(quem) + " · " + papel + "</span><strong>" + String(item.texto || "").slice(0, 240) + "</strong></div>";
      }).join("");
    } catch (erro) {}
  }
});
form.addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const campo = form.querySelector("[name=pergunta]");
  const texto = campo.value.trim();
  if (!texto) return;
  bolha("eu", texto);
  campo.value = "";
  const corpo = new URLSearchParams(new FormData(form));
  corpo.set("pergunta", texto);
  const resposta = await fetch("/agente/stive", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: corpo });
  const dados = await resposta.json().catch(() => ({}));
  bolha("stive", dados.fala || "Não consegui consultar a base agora.");
  desenharVisual(dados.visual);
  chat.scrollTop = chat.scrollHeight;
});
window.atualizarStive = (dados) => {
  const caixa = document.getElementById("pendencias-stive");
  if (!caixa) return;
  const lista = dados.pendencias || [];
  const chave = lista.map((item) => item.id + ":" + (item.foto || "")).join("|");
  if (caixa.dataset.chave === chave) return;
  caixa.dataset.chave = chave;
  caixa.innerHTML = lista.map((item) => {
    let texto = String(item.texto || "");
    let foto = String(item.foto || "");
    const tipo = String(item.tipo || "");
    const marca = texto.indexOf("Foto:");
    if (marca >= 0) {
      const trecho = texto.slice(marca).trim().split(/\\s+/)[1] || "";
      if (!foto && trecho.indexOf("/rosto/") === 0) foto = trecho;
      texto = texto.slice(0, marca).trim();
    }
    const img = foto
      ? `<figure class="foto-pendencia"><img alt="rosto" src="${foto}?t=${Date.now()}" onerror="this.parentElement.style.display='none'"></figure>`
      : "";
    const opcoesVinculo = [
      ["conhecido","Conhecido"],["amigo","Amigo(a)"],["familiar","Familiar"],
      ["irmao","Irmão(ã)"],["pai","Pai"],["mae","Mãe"],["esposa","Esposa"],["marido","Marido"],
      ["namorado","Namorado(a)"],["primo","Primo(a)"],["tio","Tio(a)"],["vizinho","Vizinho(a)"],["colega","Colega"]
    ].map(([v,r]) => `<option value="${v}">${r}</option>`).join("");
    const vinculo = tipo.indexOf("rosto_vinculo:") === 0
      ? `<label>Nome da pessoa<input type="text" name="nome_pessoa" id="nome-pessoa-stive" placeholder="Ex.: Vanessa" autocomplete="name"></label>
         <label>Relacionamento<select name="vinculo">${opcoesVinculo}</select></label>`
      : "";
    const textoAttr = String(item.texto || "").replace(/"/g, "&quot;");
    return `<div class="pendencia" data-pend-id="${item.id}"><p>${texto}</p>${img}${vinculo}
    <span><button type="button" data-id="${item.id}" data-resp="sim" data-tipo="${tipo}" data-camera="${item.camera || ""}" data-texto="${textoAttr}">${vinculo ? "Salvar vínculo" : "Sim"}</button>
    <button type="button" data-id="${item.id}" data-resp="nao" data-tipo="${tipo}" data-camera="${item.camera || ""}" data-texto="${textoAttr}">Não</button></span></div>`;
  }).join("");
};
document.getElementById("pendencias-stive").addEventListener("click", async (evento) => {
  const botao = evento.target.closest("button");
  if (!botao) return;
  const caixaPend = botao.closest(".pendencia");
  const corpo = new URLSearchParams(new FormData(form));
  corpo.set("id", botao.dataset.id || "");
  corpo.set("resposta", botao.dataset.resp || "");
  corpo.set("tipo", botao.dataset.tipo || "");
  corpo.set("camera", botao.dataset.camera || "");
  corpo.set("texto", botao.dataset.texto || (caixaPend && caixaPend.querySelector("p") ? caixaPend.querySelector("p").textContent : "") || "");
  const sel = caixaPend && caixaPend.querySelector("select[name=vinculo]");
  if (sel) corpo.set("vinculo", sel.value || "conhecido");
  const nomeInp = caixaPend && caixaPend.querySelector("input[name=nome_pessoa], #nome-pessoa-stive");
  if (nomeInp && nomeInp.value) corpo.set("nome", nomeInp.value.trim());
  const resposta = await fetch("/agente/stive/confirmar", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: corpo });
  const dados = await resposta.json().catch(() => ({}));
  bolha("stive", dados.fala || "Confirmação registrada.");
  if (dados && dados.etapa === "vinculo" && caixaPend) {
    const face = String(dados.face_id || "").toUpperCase();
    const tipoV = String(dados.tipo || ("rosto_vinculo:" + face));
    const idV = String(dados.id || botao.dataset.id || "");
    const opcoes = (dados.vinculos || []).map((item) => `<option value="${item.id}">${item.rotulo}</option>`).join("")
      || [
        ["conhecido","Conhecido"],["amigo","Amigo(a)"],["familiar","Familiar"],
        ["irmao","Irmão(ã)"],["pai","Pai"],["mae","Mãe"],["esposa","Esposa"],["marido","Marido"],
        ["namorado","Namorado(a)"],["primo","Primo(a)"],["tio","Tio(a)"],["vizinho","Vizinho(a)"],["colega","Colega"]
      ].map(([v,r]) => `<option value="${v}">${r}</option>`).join("");
    const foto = dados.foto || (face ? ("/rosto/" + face + ".jpg") : "");
    const img = foto ? `<figure class="foto-pendencia"><img alt="rosto" src="${foto}?t=${Date.now()}" onerror="this.parentElement.style.display='none'"></figure>` : "";
    caixaPend.innerHTML = `<p>${dados.fala || ("Qual o nome e o vínculo com " + face + "?")}</p>${img}
      <label>Nome da pessoa<input type="text" name="nome_pessoa" id="nome-pessoa-stive" placeholder="Ex.: Vanessa" autocomplete="name"></label>
      <label>Relacionamento<select name="vinculo">${opcoes}</select></label>
      <span><button type="button" data-id="${idV}" data-resp="sim" data-tipo="${tipoV}" data-camera="${dados.camera || "frequentes"}" data-texto="${(dados.fala || "").replace(/"/g, "&quot;")}">Salvar vínculo</button>
      <button type="button" data-id="${idV}" data-resp="nao" data-tipo="${tipoV}" data-camera="${dados.camera || "frequentes"}" data-texto="">Não conheço</button></span>`;
    return;
  }
  if (caixaPend) caixaPend.remove();
});
</script>
"""
    miolo = f"""<main>
<div class="stive-pagina">
<section class="stive-topo">
<article class="cartao">
<div class="stage-stive" id="grupo-stive">
<div id="fala-hq" class="fala-hq" hidden></div>
<img class="avatar-stive" id="abrir-stive" alt="Stive" src="/agente/stive.png?v=stive2" onerror="this.replaceWith(Object.assign(document.createElement('div'),{{className:'avatar-stive',textContent:'S'}}))">
</div>
<h2>Stive</h2>
<p>Agente de segurança. Pergunte sobre as informações do seu ambiente ou informe uma ocorrência.</p>
<div id="pendencias-stive"></div>
</article>
<article class="cartao quadro-stive" id="quadro-stive"><h2>Quadro do Stive</h2><p>O que você pedir na conversa aparece aqui.</p></article>
</section>
<section class="stive-chat-area cartao">
<div class="chat" id="chat-stive"></div>
<form id="form-stive">
{_csrf(sessao)}
<label>Mensagem<input name="pergunta" autocomplete="off" placeholder="Fale com o Stive"></label>
<button type="submit">Enviar</button>
</form>
</section>
{('<section class="cartao"><h2>Histórico de todos os usuários</h2><div id="historico-stive-admin"><p>Carregando…</p></div></section>' if (sessao.get('perfil') or '') == 'administrador' else '')}
</div>
</main>
{script}"""
    return _moldura("Agente Stive · C4ISTAR MONITOR", miolo, "/painel/stive", **_sessao_ui(sessao, portal))


def _sem_analise(perfil: str = "", csrf: str = "", usuario: str = "", documento: str = "", vista: str = "") -> str:
    miolo = """<header class="topo"><div><h1>Painéis</h1>
<p>As câmeras em análise nesta máquina pertencem a outro CPF. O seu cadastro continua disponível.</p></div></header>"""
    return _moldura(
        "C4ISTAR MONITOR",
        miolo,
        "/",
        perfil=perfil,
        csrf=csrf,
        usuario=usuario,
        documento=documento,
        vista=vista,
    )


def _form_pessoas(sessao: dict, pessoas: list[dict], aviso: str = "", ok: bool = False) -> str:
    from cadastro import BASES_LEGAIS, MOTIVOS_PESSOA

    classes = ["<option value=''>Tipo da pessoa</option>"]
    for chave, rotulo in BASES_LEGAIS.items():
        if chave in ("mandado_judicial", "acompanhamento_familiar"):
            continue
        classes.append(f"<option value='{_html_seguro(chave)}'>{_html_seguro(rotulo)}</option>")
    motivos = ["<option value=''>Motivo</option>"]
    for grupo, itens in MOTIVOS_PESSOA.items():
        for chave, rotulo in itens.items():
            motivos.append(
                f"<option value='{_html_seguro(chave)}' data-classe='{_html_seguro(grupo)}'>{_html_seguro(rotulo)}</option>"
            )
    corrigir = ["<option value=''>Nova pessoa, código novo</option>"]
    rostos = []
    for pessoa in pessoas:
        face = _html_seguro(pessoa.get("face_id") or "")
        corrigir.append(f"<option value='{face}'>Corrigir {_html_seguro(pessoa.get('nome') or face)} ({face})</option>")
        rostos.append(
            "<figure><img alt='' src='/rosto/"
            f"{face}.jpg'><figcaption>{_html_seguro(pessoa.get('nome') or face)} · {face}</figcaption>"
            "<form method='post' action='/cadastro/pessoas/remover'>"
            f"{_csrf(sessao)}<input type='hidden' name='face_id' value='{face}'>"
            "<button type='submit'>Excluir</button></form></figure>"
        )
    grade = f"<div class='rostos'>{''.join(rostos)}</div>" if rostos else "<p>Nenhuma pessoa de interesse nesta conta.</p>"
    miolo = f"""<header class="topo"><div><h1>Pessoas de interesse</h1>
<p>Cada foto nova recebe o próprio código. Corrigir um código troca só a foto daquela pessoa. Se o rosto já estiver no interesse de outra conta (ruas/bairros colaborativos), o sistema compila o vínculo no grifo automaticamente.</p></div></header>
<main>
{grade}
{_aviso_html(aviso, ok)}
<form method="post" action="/cadastro/pessoas" enctype="multipart/form-data">
{_csrf(sessao)}
{_campo("Nome", "nome", obrigatorio=True)}
<label>Tipo<select name="base_legal" id="classe" required>{''.join(classes)}</select></label>
<label>Motivo<select name="motivo" id="motivo">{''.join(motivos)}</select></label>
{_campo("Referência", "referencia")}
<div id="bloco-medida" hidden>
  <label>Medida favorece<select name="favorecido" id="favorecido">
    <option value="">Selecione</option>
    <option value="eu">A mim (sou a pessoa protegida)</option>
    <option value="amigo">A um amigo(a) perseguido e protegido pela justiça</option>
  </select></label>
  {_campo("Nome do protegido (se amigo)", "nome_protegido")}
  <p style="color:var(--mudo);font-size:13px">Obrigatório em medida protetiva: o vínculo entra no grafo de relacionamentos do administrador.</p>
</div>
<label>Código existente<select name="face_id">{''.join(corrigir)}</select></label>
<label>Foto do rosto
  <input type="file" name="foto" id="foto-arquivo" accept="image/*" capture="user">
</label>
<div class="caixa-rf" style="margin-top:8px">
  <p id="dica-camera">No celular use <strong>Tirar foto nativa</strong> (abre a câmera do iPhone/Android). Webcam ao vivo exige HTTPS.</p>
  <video id="video-captura" autoplay playsinline muted webkit-playsinline style="width:100%;max-width:360px;border-radius:12px;background:#05080f"></video>
  <canvas id="canvas-captura" hidden></canvas>
  <input type="hidden" name="foto_base64" id="foto-base64" value="">
  <div class="acoes-gestao" style="margin-top:8px">
    <button type="button" id="foto-nativa">Tirar foto nativa</button>
    <button type="button" id="abrir-camera">Abrir webcam</button>
    <button type="button" id="tirar-foto">Capturar frame</button>
    <button type="button" id="fechar-camera">Fechar câmera</button>
  </div>
  <img id="preview-captura" alt="" style="display:none;margin-top:8px;max-width:220px;border-radius:12px">
</div>
<button type="submit">{_svg(_ICONES["mais"])}Incluir e monitorar</button>
</form>
<script>
const classe = document.getElementById("classe");
const motivo = document.getElementById("motivo");
function filtrarMotivo() {{
  const atual = classe.value;
  let visivel = 0;
  motivo.querySelectorAll("option").forEach((opcao, indice) => {{
    const mostra = indice === 0 || opcao.dataset.classe === atual;
    opcao.hidden = !mostra;
    if (mostra) visivel += 1;
  }});
  motivo.required = visivel > 1;
  if (motivo.selectedOptions[0] && motivo.selectedOptions[0].hidden) motivo.value = "";
}}
classe.addEventListener("change", filtrarMotivo);
filtrarMotivo();
(function () {{
  const bloco = document.getElementById("bloco-medida");
  const favorecido = document.getElementById("favorecido");
  function syncMedida() {{
    const mp = classe.value === "medida_protetiva";
    if (bloco) bloco.hidden = !mp;
    if (favorecido) favorecido.required = mp;
  }}
  classe.addEventListener("change", syncMedida);
  syncMedida();
}})();
(function () {{
  const video = document.getElementById("video-captura");
  const canvas = document.getElementById("canvas-captura");
  const hidden = document.getElementById("foto-base64");
  const arquivo = document.getElementById("foto-arquivo");
  const preview = document.getElementById("preview-captura");
  const dica = document.getElementById("dica-camera");
  const movel = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
  const seguro = window.isSecureContext === true || location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1";
  let stream = null;
  if (dica && movel && !seguro) {{
    dica.textContent = "Neste celular o site está em HTTP: use Tirar foto nativa (abre a câmera do aparelho). A webcam ao vivo só funciona em HTTPS.";
  }}
  function mostrarPreviewArquivo(file) {{
    if (!file || !preview) return;
    const leitor = new FileReader();
    leitor.onload = () => {{
      preview.src = leitor.result;
      preview.style.display = "block";
    }};
    leitor.readAsDataURL(file);
  }}
  async function pedirStream(constraints) {{
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
      throw new Error("sem-media");
    }}
    return navigator.mediaDevices.getUserMedia(constraints);
  }}
  async function abrir() {{
    if (!seguro) {{
      if (arquivo) arquivo.click();
      else alert("Abra o portal em HTTPS ou use Tirar foto nativa / Foto do rosto.");
      return;
    }}
    const tentativas = [
      {{ video: {{ facingMode: {{ ideal: "user" }}, width: {{ ideal: 1280 }}, height: {{ ideal: 720 }} }}, audio: false }},
      {{ video: {{ facingMode: "user" }}, audio: false }},
      {{ video: {{ facingMode: "environment" }}, audio: false }},
      {{ video: true, audio: false }},
    ];
    let ultimo = null;
    for (const opc of tentativas) {{
      try {{
        if (stream) stream.getTracks().forEach((t) => t.stop());
        stream = await pedirStream(opc);
        video.setAttribute("playsinline", "true");
        video.setAttribute("webkit-playsinline", "true");
        video.muted = true;
        video.srcObject = stream;
        try {{ await video.play(); }} catch (_) {{}}
        return;
      }} catch (erro) {{
        ultimo = erro;
      }}
    }}
    const msg = (ultimo && ultimo.name) ? ultimo.name : "erro";
    if (arquivo && (movel || msg === "NotAllowedError" || msg === "NotFoundError" || msg === "sem-media")) {{
      alert("Não foi possível abrir a webcam ao vivo (" + msg + "). Vou abrir a câmera nativa do aparelho.");
      arquivo.click();
      return;
    }}
    alert("Não foi possível abrir a câmera (" + msg + "). No celular use Tirar foto nativa, ou acesse o portal em HTTPS.");
  }}
  function fechar() {{
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
    video.srcObject = null;
  }}
  function capturar() {{
    if (!video.videoWidth) {{ alert("Abra a webcam antes de capturar, ou use Tirar foto nativa."); return; }}
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    const data = canvas.toDataURL("image/jpeg", 0.92);
    hidden.value = data;
    if (arquivo) arquivo.value = "";
    preview.src = data;
    preview.style.display = "block";
  }}
  document.getElementById("foto-nativa").addEventListener("click", () => {{
    if (arquivo) arquivo.click();
  }});
  document.getElementById("abrir-camera").addEventListener("click", abrir);
  document.getElementById("tirar-foto").addEventListener("click", capturar);
  document.getElementById("fechar-camera").addEventListener("click", fechar);
  if (arquivo) arquivo.addEventListener("change", () => {{
    hidden.value = "";
    if (arquivo.files && arquivo.files[0]) mostrarPreviewArquivo(arquivo.files[0]);
    else preview.style.display = "none";
  }});
  window.addEventListener("pagehide", fechar);
}})();
</script>
</main>"""
    return _moldura("Pessoas · C4ISTAR MONITOR", miolo, "/cadastro/pessoas", **_sessao_ui(sessao))


def _veiculos_da_conta(documento: str) -> list[dict]:
    try:
        conta = cadastro.consultar(documento)
    except Exception:
        return []
    return list(conta.get("veiculos") or [])


def _form_veiculos(sessao: dict, veiculos: list[dict], aviso: str = "", ok: bool = False) -> str:
    linhas = []
    for item in veiculos:
        placa = _html_seguro(item.get("placa") or "")
        linhas.append(
            "<tr>"
            f"<td>{placa}</td>"
            f"<td>{_html_seguro(item.get('nome') or '')}</td>"
            f"<td>{_html_seguro(item.get('motivo') or '')}</td>"
            "<td><form method='post' action='/cadastro/veiculos/remover'>"
            f"{_csrf(sessao)}<input type='hidden' name='placa' value='{placa}'>"
            "<button type='submit'>Excluir</button></form></td></tr>"
        )
    tabela = (
        "<table><tr><th>Placa</th><th>Nome</th><th>Motivo</th><th></th></tr>"
        + "".join(linhas)
        + "</table>"
    ) if linhas else "<p>Nenhuma placa de interesse nesta conta.</p>"
    miolo = f"""<header class="topo"><div><h1>Placas de interesse</h1>
<p>As placas entram na busca OCR/LPR e no ranking de Alertas de RF e LPR.</p></div></header>
<main>
{tabela}
{_aviso_html(aviso, ok)}
<form method="post" action="/cadastro/veiculos">
{_csrf(sessao)}
{_campo("Placa", "placa", obrigatorio=True)}
{_campo("Nome / descrição", "nome")}
{_campo("Motivo", "motivo")}
<button type="submit">{_svg(_ICONES["mais"])}Incluir placa</button>
</form>
</main>"""
    return _moldura("Placas · C4ISTAR MONITOR", miolo, "/cadastro/veiculos", **_sessao_ui(sessao))


def _aviso_html(texto: str, ok: bool = False) -> str:
    if not texto:
        return ""
    classe = "ok" if ok else "aviso"
    return f"<p class='{classe}'>{_html_seguro(texto)}</p>"


def _valor_campo(atual: dict, nome: str, padrao):
    valor = atual.get(nome)
    if valor in (None, ""):
        return padrao
    return valor


def _campo(rotulo: str, nome: str, valor="", tipo: str = "text", obrigatorio: bool = False) -> str:
    req = " required" if obrigatorio else ""
    return (
        f"<label>{_html_seguro(rotulo)}"
        f"<input type='{tipo}' name='{nome}' value='{_html_seguro(valor)}'{req}></label>"
    )


def _campo_lista(
    rotulo: str,
    nome: str,
    valor: str = "",
    opcoes: list | tuple = (),
    obrigatorio: bool = False,
    grupo: str = "",
    placeholder: str = "",
) -> str:
    """Campo com sugestões (datalist): evita bug do <select> no Chrome com aside sticky."""
    del grupo  # datalist não tem optgroup; mantido só por compatibilidade de chamada
    req = " required" if obrigatorio else ""
    atual = str(valor or "").strip()
    lista_id = f"lista-{nome}"
    dica = placeholder or f"Escolha ou digite {rotulo.lower()}"
    vistos = set()
    corpo = []
    for item in opcoes:
        texto = str(item or "").strip()
        if not texto:
            continue
        chave = cadastro.normalizar_rua(texto)
        if chave in vistos:
            continue
        vistos.add(chave)
        corpo.append(f"<option value='{_html_seguro(texto)}'>")
    if atual and cadastro.normalizar_rua(atual) not in vistos:
        corpo.insert(0, f"<option value='{_html_seguro(atual)}'>")
    return (
        f"<label class='campo-lista'>{_html_seguro(rotulo)}"
        f"<input type='text' name='{nome}' list='{lista_id}' value='{_html_seguro(atual)}'"
        f" autocomplete='off' placeholder='{_html_seguro(dica)}'{req}>"
        f"<datalist id='{lista_id}'>{''.join(corpo)}</datalist></label>"
    )


def _campo_logradouro(valor: str = "", obrigatorio: bool = True) -> str:
    stella = list(cadastro.LOGRADOUROS_STELLA_MARIS)
    demais = [item for item in cadastro.LOGRADOUROS_SALVADOR if item not in stella]
    return _campo_lista(
        "Logradouro",
        "rua",
        valor or "",
        stella + demais,
        obrigatorio=obrigatorio,
        placeholder="Escolha ou digite o logradouro",
    )


def _campo_bairro(valor: str = "") -> str:
    return _campo_lista("Bairro", "bairro", valor or "Stella Maris", cadastro.BAIRROS_SALVADOR)


def _campo_municipio(valor: str = "") -> str:
    return _campo_lista("Município", "cidade", valor or "Salvador", cadastro.MUNICIPIOS_BAHIA)


def _campo_marca(valor: str = "") -> str:
    return _campo_lista(
        "Marca",
        "marca",
        valor or "Intelbras",
        cadastro.MARCAS_CAMERA,
        placeholder="Escolha ou digite a marca",
    )


def _campo_modelo(valor: str = "") -> str:
    return _campo_lista(
        "Modelo",
        "modelo",
        valor or "",
        cadastro.MODELOS_CAMERA,
        obrigatorio=True,
        placeholder="Escolha ou digite o modelo",
    )


def _csrf(sessao: dict) -> str:
    return f"<input type='hidden' name='csrf' value='{_html_seguro(sessao.get('csrf') or '')}'>"


def _check(nome: str, rotulo: str, ligado: bool = True) -> str:
    marcado = " checked" if ligado else ""
    return (
        f"<input type='hidden' name='{nome}' value='0'>"
        f"<label><input class='check' type='checkbox' name='{nome}' value='1'{marcado}>"
        f"{_html_seguro(rotulo)}</label>"
    )


def _pagina_senha(aviso: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>C4ISTAR MONITOR</title>
<style>{ESTILO}</style>
</head>
<body>
<main class="login cartao">
<h1>C4ISTAR MONITOR</h1>
<p>Entre com o e-mail e a senha do seu usuário.</p>
{_aviso_html(aviso)}
<form method="post" action="/entrar">
{_campo("E-mail", "email", tipo="email", obrigatorio=True)}
{_campo("Senha", "senha", tipo="password", obrigatorio=True)}
<button type="submit">{_svg(_ICONES["mais"])}Entrar</button>
</form>
<p><a class="texto" href="/criar">Criar usuário</a></p>
</main>
</body>
</html>"""


def _pagina_criar(aviso: str = "") -> str:
    if acesso.listar():
        return _pagina_senha("Já existe usuário. Entre para criar outro na mesma conta.")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Criar usuário · C4ISTAR MONITOR</title>
<style>{ESTILO}</style>
</head>
<body>
<main class="login cartao">
<h1>Criar usuário</h1>
<p>O primeiro usuário fica ligado ao CPF ou CNPJ da conta desta instalação. A senha da instalação é a que já está no sistema.</p>
{_aviso_html(aviso)}
<form method="post" action="/criar">
{_campo("Nome", "nome")}
{_campo("E-mail", "email", tipo="email", obrigatorio=True)}
{_campo("CPF ou CNPJ", "documento", obrigatorio=True)}
{_campo("Senha", "senha", tipo="password", obrigatorio=True)}
{_campo("Confirmar senha", "confirmacao", tipo="password", obrigatorio=True)}
{_campo("Senha da instalação", "chave", tipo="password", obrigatorio=True)}
<button type="submit">{_svg(_ICONES["mais"])}Criar e entrar</button>
</form>
<p><a class="texto" href="/entrar">Já tenho usuário</a></p>
</main>
</body>
</html>"""


def _form_cliente(sessao: dict, cliente: dict, aviso: str = "", ok: bool = False) -> str:
    novo = ""
    if sessao.get("perfil") == "administrador":
        from agente.stive import resumo_satisfacao

        sat = resumo_satisfacao(sessao.get("documento") or "")
        mes = sat.get("mes") or {}
        ano = sat.get("ano") or {}
        total = sat.get("total") or {}
        serie = sat.get("serie_mes") or []
        novo = f"""<h2>Novo cliente</h2>
<p>Ao criar, o cliente recebe no e-mail o login e uma senha provisória, que deve ser trocada no primeiro acesso.</p>
<form method="post" action="/cadastro/cliente/novo">
{_csrf(sessao)}
{_campo("Nome", "nome_novo")}
{_campo("CPF ou CNPJ", "documento_novo", obrigatorio=True)}
{_campo("E-mail", "email_novo", tipo="email", obrigatorio=True)}
<button type="submit">{_svg(_ICONES["mais"])}Criar cliente e enviar acesso</button>
</form>
<section class="satisfacao-stive">
<h2>Satisfação com o Stive</h2>
<p>Reações Legal e Não legal nas falas do agente, para medir se o conteúdo agrada.</p>
<div class="cartoes">
<article class="cartao"><span>Mês</span><strong>{mes.get('percentual', 0)}%</strong><p>{mes.get('positivos', 0)} legal · {mes.get('negativos', 0)} não legal</p></article>
<article class="cartao"><span>Ano</span><strong>{ano.get('percentual', 0)}%</strong><p>{ano.get('positivos', 0)} legal · {ano.get('negativos', 0)} não legal</p></article>
<article class="cartao"><span>Total</span><strong>{total.get('percentual', 0)}%</strong><p>{total.get('positivos', 0)} legal · {total.get('negativos', 0)} não legal</p></article>
</div>
<article class="cartao"><h2>Positivos por mês</h2><canvas class="grafico" id="grafico-satisfacao" width="640" height="280"></canvas></article>
<script>
window.addEventListener("load", () => {{
  const serie = {json.dumps(serie, ensure_ascii=False)};
  const canvas = document.getElementById("grafico-satisfacao");
  if (!canvas || typeof barrasVerticais !== "function") return;
  barrasVerticais(canvas, serie.map((item) => ({{
    rotulo: item.rotulo,
    total: item.percentual,
    cor: item.percentual >= 60 ? "#3ddc97" : (item.percentual >= 40 ? "#ffb020" : "#ff5c7a"),
  }})));
}});
</script>
</section>"""
    foto_id = str(cliente.get("foto_face_id") or "").strip().upper()
    preview = ""
    if foto_id:
        preview = (
            f"<figure class='foto-cliente-preview'>"
            f"<img alt='foto do cliente' src='/rosto/{_html_seguro(foto_id)}.jpg?t={int(time.time())}' "
            f"onerror=\"this.parentElement.style.display='none'\">"
            f"<figcaption>Foto atual · {_html_seguro(foto_id)}"
            f"{' · próprio usuário' if cliente.get('eh_proprio') else ''}</figcaption></figure>"
        )
    miolo = f"""<main>
<h1>Cliente</h1>
<p>Estes dados são da conta do CPF ou CNPJ com o qual você entrou.</p>
<p>Se você também é morador da rua monitorada, envie sua foto: o sistema associa passagens nas câmeras ao seu perfil no grifo.</p>
{_aviso_html(aviso, ok)}
<form method="post" action="/cadastro/cliente" enctype="multipart/form-data">
{_csrf(sessao)}
{_campo("Nome", "nome", cliente.get("nome") or "")}
{_campo("RG", "rg", cliente.get("rg") or "")}
{_campo("CPF ou CNPJ", "documento", _documento_visivel(cliente.get("documento") or sessao.get("documento") or ""), obrigatorio=True)}
{_campo("E-mail da conta", "email", cliente.get("email") or "", tipo="email")}
<label>Foto do cliente (morador da rua)
<input type="file" name="foto" accept="image/*" capture="user">
</label>
{preview}
<button type="submit">{_svg(_ICONES["mais"])}Salvar cliente</button>
</form>
{novo}
</main>"""
    return _moldura("Cliente · C4ISTAR MONITOR", miolo, "/cadastro/cliente", **_sessao_ui(sessao))


def _gestao(sessao: dict, portal, aviso: str = "", ok: bool = False) -> str:
    clientes = cadastro.resumo_clientes()
    resumo = portal.resumo()
    periodos = (resumo.get("periodos") or {}).get("total") or {}
    online = len(portal.cameras())
    cadastradas = sum(item["cameras"] for item in clientes)
    cards = "".join(
        f"<article class='cartao'><span>{rotulo}</span><strong>{valor}</strong></article>"
        for rotulo, valor in (
            ("Clientes cadastrados", len(clientes)),
            ("Câmeras online", online),
            ("Câmeras cadastradas", cadastradas),
            ("Pessoas contabilizadas", int(periodos.get("Pessoa") or 0)),
            ("Veículos contabilizados", int(periodos.get("Veiculo") or 0)),
        )
    )
    linhas = []
    for item in clientes:
        documento = _html_seguro(item.get("documento") or "")
        estado = "ativo" if item.get("ativo") else "inativo"
        acao = "inativar" if item.get("ativo") else "ativar"
        linhas.append(
            "<tr>"
            f"<td>{_html_seguro(item.get('nome'))}</td>"
            f"<td>{_html_seguro(_documento_visivel(item.get('documento') or ''))}</td>"
            f"<td>{_html_seguro(item.get('email'))}</td>"
            f"<td>{item.get('cameras')}</td>"
            f"<td>{estado}</td>"
            "<td class='acoes-gestao'>"
            f"<a class='texto' href='/gestao/editar?documento={documento}'>Editar</a>"
            f"<form method='post' action='/gestao/reset-senha'>{_csrf(sessao)}"
            f"<input type='hidden' name='documento' value='{documento}'>"
            "<button type='submit'>Reset senha</button></form>"
            f"<form method='post' action='/gestao/{acao}'>{_csrf(sessao)}"
            f"<input type='hidden' name='documento' value='{documento}'>"
            f"<button type='submit'>{acao.capitalize()}</button></form>"
            f"<form method='post' action='/gestao/excluir' onsubmit=\"return confirm('Excluir este cliente?');\">{_csrf(sessao)}"
            f"<input type='hidden' name='documento' value='{documento}'>"
            "<button type='submit'>Excluir</button></form>"
            "</td></tr>"
        )
    tabela = (
        "<table><tr><th>Cliente</th><th>Documento</th><th>E-mail</th><th>Câmeras</th><th>Status</th><th>Ações</th></tr>"
        + "".join(linhas) + "</table>"
    ) if linhas else "<p>Nenhum cliente cadastrado.</p>"
    miolo = f"""<main>
<h1>Gestão de ativos</h1>
<p>Visão de todas as contas. Edite dados, reenvie senha provisória por e-mail, ative ou exclua clientes.</p>
{_aviso_html(aviso, ok)}
<section class="cartoes">{cards}</section>
{tabela}
</main>"""
    return _moldura("Gestão de ativos · C4ISTAR MONITOR", miolo, "/gestao", **{**_sessao_ui(sessao), "perfil": "administrador"})


def _gestao_editar(sessao: dict, documento: str, aviso: str = "", ok: bool = False) -> str:
    cliente = cadastro.cliente_por_documento(documento) or {}
    if not cliente:
        miolo = "<main><p class='aviso'>Cliente não encontrado.</p><p><a class='texto' href='/gestao'>Voltar</a></p></main>"
        return _moldura(
            "Gestão de ativos · C4ISTAR MONITOR",
            miolo,
            "/gestao",
            **{**_sessao_ui(sessao), "perfil": "administrador"},
        )
    usuarios = acesso.da_conta(documento)
    opcoes = "".join(
        f"<option value='{_html_seguro(item.get('email') or '')}'>{_html_seguro(item.get('nome') or item.get('email') or '')} · {_html_seguro(item.get('email') or '')}</option>"
        for item in usuarios
    ) or f"<option value='{_html_seguro(cliente.get('email') or '')}'>{_html_seguro(cliente.get('email') or '')}</option>"
    miolo = f"""<main>
<h1>Editar cliente</h1>
<p><a class="texto" href="/gestao">← Voltar à gestão</a></p>
{_aviso_html(aviso, ok)}
<form method="post" action="/gestao/editar">
{_csrf(sessao)}
<input type="hidden" name="documento_atual" value="{_html_seguro(cliente.get('documento') or documento)}">
{_campo("Nome", "nome", cliente.get("nome") or "")}
{_campo("RG", "rg", cliente.get("rg") or "")}
{_campo("CPF ou CNPJ", "documento", _documento_visivel(cliente.get("documento") or ""), obrigatorio=True)}
{_campo("E-mail da conta", "email", cliente.get("email") or "", tipo="email", obrigatorio=True)}
<button type="submit">{_svg(_ICONES["mais"])}Salvar alterações</button>
</form>
<h2>Reset de senha</h2>
<p>Gera senha provisória e envia ao e-mail escolhido. No próximo acesso a troca será obrigatória.</p>
<form method="post" action="/gestao/reset-senha">
{_csrf(sessao)}
<input type="hidden" name="documento" value="{_html_seguro(cliente.get('documento') or documento)}">
<label>Usuário / e-mail
<select name="email">{opcoes}</select>
</label>
<button type="submit">Enviar reset de senha</button>
</form>
</main>"""
    return _moldura(
        "Editar cliente · C4ISTAR MONITOR",
        miolo,
        "/gestao",
        **{**_sessao_ui(sessao), "perfil": "administrador"},
    )


def _form_camera(sessao: dict, cameras: list[dict], atual: dict | None, aviso: str = "", ok: bool = False) -> str:
    linhas = []
    for camera in cameras:
        estado = "ativa" if camera.get("ativa") else "oculta"
        linhas.append(
            "<tr>"
            f"<td>{_html_seguro(camera.get('nome'))}</td>"
            f"<td>{_html_seguro(camera.get('rua'))}</td>"
            f"<td>{_html_seguro(camera.get('cidade'))}</td>"
            f"<td>{estado}</td>"
            f"<td><a class='texto' href='/cadastro/cameras?id={_html_seguro(camera.get('id'))}'>Editar</a></td>"
            "<td><form method='post' action='/cadastro/cameras/remover'>"
            f"{_csrf(sessao)}<input type='hidden' name='id' value='{_html_seguro(camera.get('id'))}'>"
            "<button type='submit'>Excluir</button></form></td>"
            "</tr>"
        )
    tabela = (
        "<table><tr><th>Câmera</th><th>Rua</th><th>Cidade</th><th></th><th></th><th></th></tr>"
        + "".join(linhas)
        + "</table>"
    ) if linhas else "<p>Nenhuma câmera nesta conta.</p>"
    atual = atual or {}
    acesso_gravado = ""
    if atual.get("tem_acesso") and not atual.get("host"):
        acesso_gravado = "<p>O acesso desta câmera já está gravado. Preencha host, usuário e senha só para substituir.</p>"
    ident = atual.get("id") or ""
    miolo = f"""<main>
<h1>Câmeras</h1>
<p>Com pelo menos uma câmera cadastrada, você compartilha e vê os dados das câmeras do mesmo logradouro. Sem câmera, a rua permanece oculta.</p>
{tabela}
<h2>{'Editar câmera' if ident else 'Nova câmera'}</h2>
{_aviso_html(aviso, ok)}
{acesso_gravado}
<form method="post" action="/cadastro/cameras">
{_csrf(sessao)}
<input type="hidden" name="id_anterior" value="{_html_seguro(ident)}">
{_campo("Identificador", "id", ident)}
{_campo("Nome", "nome", atual.get("nome") or "", obrigatorio=True)}
{_campo_marca(atual.get("marca") or "Intelbras")}
{_campo_modelo(atual.get("modelo") or "")}
{_check("ativa", "Câmera ativa", atual.get("ativa", True))}
{_campo("Host", "host", atual.get("host") or "")}
{_campo("Porta", "porta", _valor_campo(atual, "porta", 554))}
{_campo("Usuário", "usuario", atual.get("usuario") or "")}
{_campo("Senha", "senha", tipo="password")}
{_campo("Canal", "canal", _valor_campo(atual, "canal", 1))}
{_campo("Subtype", "subtype", _valor_campo(atual, "subtype", 0))}
{_campo_logradouro(atual.get("rua") or "")}
{_campo_bairro(atual.get("bairro") or "Stella Maris")}
{_campo_municipio(atual.get("cidade") or "Salvador")}
{_campo("Latitude", "latitude", atual.get("latitude") if atual.get("latitude") != "" else "")}
{_campo("Longitude", "longitude", atual.get("longitude") if atual.get("longitude") != "" else "")}
<button type="submit">{_svg(_ICONES["mais"])}Salvar câmera</button>
</form>
</main>"""
    return _moldura("Câmeras · C4ISTAR MONITOR", miolo, "/cadastro/cameras", **_sessao_ui(sessao))


def _form_avisos(sessao: dict, cameras: list[dict], aviso: str = "", ok: bool = False) -> str:
    opcoes = ["<option value=''>Escolha a câmera</option>"]
    blocos = []
    for camera in cameras:
        opcoes.append(
            f"<option value='{_html_seguro(camera.get('id'))}'>{_html_seguro(camera.get('nome'))}</option>"
        )
        linhas = []
        for indice, item in enumerate(camera.get("avisos") or []):
            linhas.append(
                "<tr>"
                f"<td>{_html_seguro(_telefone_visivel(item))}</td>"
                f"<td>{_html_seguro(item.get('email'))}</td>"
                f"<td>{'sim' if item.get('recebe_alerta', True) else 'não'}</td>"
                f"<td>{'sim' if item.get('recebe_relatorio', True) else 'não'}</td>"
                "<td><form method='post' action='/cadastro/avisos/remover'>"
                f"{_csrf(sessao)}"
                f"<input type='hidden' name='camera_id' value='{_html_seguro(camera.get('id'))}'>"
                f"<input type='hidden' name='indice' value='{indice}'>"
                "<button type='submit'>" + _svg(_ICONES["sair"]) + "Remover</button></form></td>"
                "</tr>"
            )
        if linhas:
            blocos.append(
                f"<h2>{_html_seguro(camera.get('nome'))}</h2>"
                "<table><tr><th>Telefone completo</th><th>E-mail</th><th>Alertas</th><th>Relatório</th><th></th></tr>"
                + "".join(linhas)
                + "</table>"
            )
    lista = "".join(blocos) or "<p>Nenhum aviso cadastrado.</p>"
    miolo = f"""<main>
<h1>Avisos da câmera</h1>
<p>O e-mail recebe os alertas e o relatório da câmera escolhida. O telefone guarda o código do país, o DDD e o número, no formato completo.</p>
{lista}
{_aviso_html(aviso, ok)}
<form method="post" action="/cadastro/avisos">
{_csrf(sessao)}
<label>Câmera<select name="camera_id" required>{"".join(opcoes)}</select></label>
{_campo("Código do país", "codigo_pais", "55", obrigatorio=True)}
{_campo("DDD", "ddd", obrigatorio=True)}
{_campo("Número", "numero", obrigatorio=True)}
{_campo("E-mail", "email", tipo="email", obrigatorio=True)}
{_check("recebe_alerta", "Recebe alertas e notificações", True)}
{_check("recebe_relatorio", "Recebe o relatório", True)}
<button type="submit">{_svg(_ICONES["mais"])}Salvar aviso</button>
</form>
</main>"""
    return _moldura("Avisos · C4ISTAR MONITOR", miolo, "/cadastro/avisos", **_sessao_ui(sessao))


def _sistema(sessao: dict) -> str:
    miolo = _cabeca(
        "Armazenamento e sistema",
        "Host, capacidade por câmera (latência/FPS/CPU/RAM), testes 1/2/4 câmeras, GPT e nuvem. Somente administrador.",
    ) + "<main id='tela' data-tela='sistema'></main>"
    return _moldura(
        "Sistema · C4ISTAR MONITOR",
        miolo,
        "/sistema",
        **_sessao_ui(sessao),
    )


def _sistema_json(documento_filtro: str = "") -> dict:
    """Pacote admin: geral = cluster (todos + adm); filtro = fatia daquele cliente."""
    import monitor_sistema

    digitos = "".join(c for c in str(documento_filtro or "") if c.isdigit())
    clientes = []
    total_cams = 0
    cams_cliente = 0
    pessoas_cliente = 0
    nome_cliente = ""
    for item in cadastro.listar_clientes():
        doc = "".join(c for c in str(item.get("documento") or "") if c.isdigit())
        if not doc:
            continue
        nomes = cadastro.nomes_cameras_conta(doc)
        total_cams += len(nomes)
        clientes.append({
            "documento": doc,
            "nome": str(item.get("nome") or "") or doc,
            "ativo": item.get("ativo") is not False,
            "cameras": len(nomes),
        })
        if digitos and doc == digitos:
            cams_cliente = len(nomes)
            pessoas_cliente = len(item.get("pessoas") or [])
            nome_cliente = str(item.get("nome") or "") or digitos
    clientes.sort(key=lambda c: (c.get("nome") or "").lower())

    # Sem filtro: host completo do cluster. Com filtro: estima a fatia do computador/cliente.
    if digitos:
        fator = (cams_cliente / total_cams) if total_cams else 0.0
        escopo = "cliente"
    else:
        fator = 1.0
        escopo = "cluster"
    pacote = monitor_sistema.resumo(fator=fator, escopo=escopo)
    mb_estimado = float(pacote.get("total_armazenado_mb") or 0)

    try:
        from db import custos as ledger

        financeiro = ledger.monitor_financeiro(digitos, dias=30)
    except Exception as exc:
        financeiro = {"erro": str(exc), "gpt_usd_diario": [], "gpt_tokens_diario": [], "por_cliente_mes": []}

    return {
        **pacote,
        "filtro_documento": digitos,
        "clientes": clientes,
        "cliente": {
            "documento": digitos,
            "nome": nome_cliente,
            "cameras": cams_cliente,
            "pessoas": pessoas_cliente,
            "mb_estimado_local": mb_estimado,
            "monitoramento": True,
            "fator": round(fator, 4),
        } if digitos else None,
        "cluster": {
            "clientes": len(clientes),
            "cameras": total_cams,
            "rotulo": "Cluster total (todos os clientes + administrador)",
        },
        "custos": financeiro,
        "nuvem": {
            "status": "preparado",
            "usado_mb": None,
            "cota_mb": None,
            "aviso": (
                f"Espaço em nuvem do cliente {nome_cliente or digitos} — medição por CPF quando o provedor estiver ligado."
                if digitos
                else "Espaço em nuvem do cluster — medição agregada por cliente quando o provedor estiver ligado."
            ),
        },
    }


def _form_conta(sessao: dict, aviso: str = "", ok: bool = False) -> str:
    usuarios = acesso.da_conta(sessao.get("documento") or "")
    linhas = "".join(
        f"<tr><td>{_html_seguro(item.get('nome'))}</td><td>{_html_seguro(item.get('email'))}</td></tr>"
        for item in usuarios
    )
    miolo = f"""<main>
<h1>Conta</h1>
<p>Usuários deste CPF/CNPJ {_html_seguro(_documento_visivel(sessao.get("documento") or ""))}.</p>
<p>Cada usuário navega em Início, Contagens, Comportamento, Alertas, Mapas, Detector de risco, Agente Stive e Ao vivo — somente com as câmeras deste CPF/CNPJ. Também acessa Cadastros (Câmeras, Pessoas, Avisos) e Conta. A detecção de áudio segue ativa no modelo; a página de áudio e transcrição fica só com o administrador.</p>
<table><tr><th>Nome</th><th>E-mail</th></tr>{linhas}</table>
{_aviso_html(aviso, ok)}
<h2>Nova senha</h2>
<form method="post" action="/conta/senha">
{_csrf(sessao)}
{_campo("Senha atual", "atual", tipo="password", obrigatorio=True)}
{_campo("Senha nova", "nova", tipo="password", obrigatorio=True)}
{_campo("Confirmar senha nova", "confirmacao", tipo="password", obrigatorio=True)}
<button type="submit">{_svg(_ICONES["mais"])}Trocar senha</button>
</form>
<h2>Novo usuário desta conta</h2>
<form method="post" action="/conta/usuario">
{_csrf(sessao)}
{_campo("Nome", "nome")}
{_campo("E-mail", "email", tipo="email", obrigatorio=True)}
{_campo("Senha", "senha", tipo="password", obrigatorio=True)}
{_campo("Confirmar senha", "confirmacao", tipo="password", obrigatorio=True)}
<button type="submit">{_svg(_ICONES["mais"])}Criar usuário</button>
</form>
</main>"""
    return _moldura("Conta · C4ISTAR MONITOR", miolo, "/conta", **_sessao_ui(sessao))


def np_from(foto: bytes):
    import numpy as np

    return np.frombuffer(foto, dtype=np.uint8)


def _multipart(corpo: bytes, fronteira: str):
    marca = b"--" + fronteira.encode("utf-8", "replace")
    campos = {}
    arquivos = {}
    for parte in corpo.split(marca):
        if parte.startswith(b"\r\n"):
            parte = parte[2:]
        if not parte or parte.startswith(b"--"):
            continue
        cabeca, sep, conteudo = parte.partition(b"\r\n\r\n")
        if not sep:
            continue
        if conteudo.endswith(b"\r\n"):
            conteudo = conteudo[:-2]
        texto = cabeca.decode("utf-8", "replace")
        if 'name="' not in texto:
            continue
        nome = texto.split('name="', 1)[1].split('"', 1)[0]
        if "filename=" in texto:
            arquivos[nome] = conteudo
        else:
            campos.setdefault(nome, []).append(conteudo.decode("utf-8", "replace"))
    return campos, arquivos


def _pessoas_da_conta(documento: str) -> list[dict]:
    cliente = cadastro.cliente_por_documento(documento) or {}
    return [
        {
            "face_id": str(pessoa.get("face_id") or "").upper(),
            "nome": pessoa.get("nome") or "",
        }
        for pessoa in cliente.get("pessoas") or []
        if isinstance(pessoa, dict) and pessoa.get("face_id")
    ]


def _rastros_rf_lpr(nomes: dict) -> list[dict]:
    if not nomes:
        return []
    try:
        locais = {str(item.get("nome") or "").strip().lower(): item for item in cadastro.locais_cameras()}
    except Exception:
        locais = {}
    try:
        from db.leitura import rastros_faces

        do_banco = rastros_faces(nomes, locais)
        if do_banco:
            return do_banco
    except Exception:
        pass
    caminho = Path("historico_faces.csv")
    if not caminho.exists():
        return []
    rastros = []
    try:
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.DictReader(arquivo, delimiter=";")
            for linha in leitor:
                ident = str(linha.get("Face_ID") or "").strip().upper()
                if ident not in nomes:
                    continue
                camera = str(linha.get("Camera") or "").strip()
                local = locais.get(camera.lower()) or {}
                lat, lon = local.get("latitude"), local.get("longitude")
                if lat is None or lon is None:
                    continue
                rastros.append({
                    "id": ident,
                    "nome": nomes.get(ident) or ident,
                    "camera": camera,
                    "quando": f"{linha.get('Data') or ''} {linha.get('Hora') or ''}".strip(),
                    "lat": float(lat),
                    "lon": float(lon),
                    "foto": f"/rosto/{ident}.jpg",
                    "valor": 1,
                })
    except OSError:
        return []
    rastros.sort(key=lambda item: str(item.get("quando") or ""))
    return rastros[-240:]


_CACHE_DADOS = {"quando": 0.0, "extra": None, "nomes_chave": ""}


_PERIODO_ZERO = {
    "Pessoa": 0, "Veiculo": 0, "Animal": 0, "Objeto": 0,
    "Comportamento": 0, "MatchFace": 0, "MatchPlaca": 0,
}


def _resumo_vazio_cliente(resumo: dict, documento: str = "") -> dict:
    """Painéis do cliente sem câmeras/dados locais: cards zerados, sem alertas."""
    base = dict(resumo or {})
    zero = dict(_PERIODO_ZERO)
    base.update({
        "periodos": {
            "dia": dict(zero),
            "semana": dict(zero),
            "mes": dict(zero),
            "total": dict(zero),
        },
        "cameras_vivo": [],
        "serie": [],
        "serie_dias": [],
        "dias_empilhados": [],
        "horas": {},
        "horas_prioridade": {},
        "classes": [],
        "classes_web": [],
        "tipos": [],
        "geo": [],
        "riscos": {},
        "pontos": [],
        "app_linhas": [],
        "cubo": [],
        "pendencias": [],
        "led": "branco",
        "match": None,
        "narracao": "",
        "narracao_ia": "",
        "historico": [],
        "memorias": [],
        "informes": [],
        "insights": [],
        "app": [],
        "voz": "",
        "audio": {"esteira": [], "alertas": [], "cameras": {}, "risco_aberto": 0},
        "passagens": [],
        "pessoas_interesse": [],
        "rastros_rf": [],
        "itens": 0,
        "faces": 0,
        "topo": 0,
        "cameras": 0,
        "resumo": "",
        "assessoramento": "",
        "aprendizado": "",
        "relatorio": "",
        "fonte_dados": "cliente",
        "cliente_documento": documento or "",
    })
    return base


_RISCO_POR_CLASSE = {
    "Em_Pe": "Informativo",
    "Sentado": "Informativo",
    "Caminhando": "Informativo",
    "Bracos_Levantados": "Informativo",
    "Agachado": "Atencao",
    "Deitado": "Atencao",
    "Correndo": "Atencao",
    "Permanencia": "Atencao",
    "Interacao_Proxima": "Atencao",
    "Aglomeracao": "Atencao",
    "Levantando": "Atencao",
    "Possivel_Queda": "Prioritario",
    "Possivel_Briga": "Prioritario",
    "Possivel_Arma_Fogo": "Critico",
}


def _reconstruir_periodos(cubo: list, tipos: list) -> dict:
    from datetime import date, timedelta

    hoje = date.today().isoformat()
    inicio_semana = (date.today() - timedelta(days=6)).isoformat()
    inicio_mes = hoje[:8] + "01"
    zero = dict(_PERIODO_ZERO)
    # tipos no painel é o recorte de hoje; usa o mesmo valor nos períodos que incluem hoje.
    comportamento_hoje = sum(
        int(total or 0)
        for item in tipos
        for total in (item.get("cameras") or {}).values()
    )

    def bloco(inicio: str) -> dict:
        base = dict(zero)
        for item in cubo:
            dia = str(item.get("d") or "")
            if inicio and dia < inicio:
                continue
            chave = str(item.get("k") or "") or "Outro"
            if chave in base:
                base[chave] = int(base.get(chave) or 0) + int(item.get("n") or 0)
        if not inicio or inicio <= hoje:
            base["Comportamento"] = comportamento_hoje
        return base

    return {
        "dia": bloco(hoje),
        "semana": bloco(inicio_semana),
        "mes": bloco(inicio_mes),
        "total": bloco(""),
    }


def _reconstruir_horas(cubo: list) -> dict:
    from datetime import date

    hoje = date.today().isoformat()
    horas = {nome: [0] * 24 for nome in ("Veiculo", "Pessoa", "Objeto", "Animal")}
    for item in cubo:
        if str(item.get("d") or "") != hoje:
            continue
        chave = str(item.get("k") or "")
        if chave not in horas:
            continue
        try:
            hora = int(item.get("h") or 0)
        except (TypeError, ValueError):
            hora = 0
        if 0 <= hora <= 23:
            horas[chave][hora] += int(item.get("n") or 0)
    return horas


def _reconstruir_series(cubo: list) -> tuple[list, list]:
    from datetime import date, timedelta

    categorias = ("Veiculo", "Pessoa", "Objeto", "Animal")
    dias = [(date.today() - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]
    serie_dias = []
    dias_empilhados = []
    for dia in dias:
        item = {"rotulo": f"{dia[8:10]}/{dia[5:7]}"}
        por_cam = {}
        for reg in cubo:
            if str(reg.get("d") or "") != dia:
                continue
            cat = str(reg.get("k") or "")
            if cat not in categorias:
                continue
            item[cat] = int(item.get(cat) or 0) + int(reg.get("n") or 0)
            cam = str(reg.get("c") or "")
            slot = por_cam.setdefault(cam, {nome: 0 for nome in categorias})
            slot[cat] = int(slot.get(cat) or 0) + int(reg.get("n") or 0)
        for nome in categorias:
            item.setdefault(nome, 0)
        serie_dias.append(item)
        dias_empilhados.append({"rotulo": item["rotulo"], "cameras": por_cam})
    return serie_dias, dias_empilhados


def _anexar_vizinhos(resumo: dict, documento: str) -> dict:
    digitos = "".join(c for c in str(documento or "") if c.isdigit())
    try:
        import vizinhos as rede

        alertas = rede.listar_alertas(digitos) if digitos else []
    except Exception:
        alertas = []
    resumo["vizinhos"] = {
        "alertas": alertas,
        "pendentes": len([a for a in alertas if a.get("tipo") == "solicitacao"]),
        "total": len(alertas),
    }
    return resumo


def _filtrar_resumo_conta(resumo: dict, documento: str, perfil: str) -> dict:
    """Cliente só vê dados das próprias câmeras/CPF; admin vê tudo."""
    digitos = "".join(c for c in str(documento or "") if c.isdigit())
    if perfil == "administrador" or not digitos:
        saida = dict(resumo or {})
        saida["cliente_documento"] = digitos or (saida.get("cliente_documento") or "")
        saida["perfil_sessao"] = perfil or ""
        return _anexar_vizinhos(saida, digitos)
    permitidas = cadastro.nomes_cameras_visiveis(digitos, perfil)
    if not permitidas:
        vazio = _resumo_vazio_cliente(resumo, digitos)
        vazio["perfil_sessao"] = perfil or ""
        return _anexar_vizinhos(vazio, digitos)

    resumo = dict(resumo or {})
    vivo = [
        item for item in (resumo.get("cameras_vivo") or [])
        if (item.get("nome") or "") in permitidas
    ]
    resumo["cameras_vivo"] = vivo
    resumo["cameras"] = len(vivo)

    cubo = [item for item in (resumo.get("cubo") or []) if (item.get("c") or "") in permitidas]
    resumo["cubo"] = cubo
    # Cubo de risco: próprias câmeras + demais do mesmo bairro (alerta colaborativo).
    _ruas_cli, bairros_cli, _cidades_cli = cadastro._escopos_geograficos(digitos)

    def _camera_no_bairro_cli(nome_cam: str) -> bool:
        if not nome_cam or not bairros_cli:
            return False
        bairro = cadastro._bairro_da_camera(nome_cam)
        return bool(bairro and bairro in bairros_cli)

    cubo_risco = [
        item for item in (resumo.get("cubo_risco") or [])
        if (item.get("c") or "") in permitidas or _camera_no_bairro_cli(str(item.get("c") or ""))
    ]
    resumo["cubo_risco"] = cubo_risco
    cubo_faixa = [item for item in (resumo.get("cubo_faixa") or []) if (item.get("c") or "") in permitidas]
    resumo["cubo_faixa"] = cubo_faixa

    tipos = []
    for item in resumo.get("tipos") or []:
        cams = {
            nome: int(total or 0)
            for nome, total in (item.get("cameras") or {}).items()
            if nome in permitidas
        }
        if cams:
            tipos.append({"classe": item.get("classe") or "", "cameras": cams})
    resumo["tipos"] = tipos

    resumo["periodos"] = _reconstruir_periodos(cubo, tipos)
    resumo["horas"] = _reconstruir_horas(cubo)
    serie_dias, dias_empilhados = _reconstruir_series(cubo)
    resumo["serie_dias"] = serie_dias
    resumo["dias_empilhados"] = dias_empilhados

    riscos = {nome: 0 for nome in ("Informativo", "Atencao", "Prioritario", "Critico")}
    if cubo_risco:
        from datetime import date as _date

        hoje = _date.today().isoformat()
        for item in cubo_risco:
            if str(item.get("d") or "") != hoje:
                continue
            nome = str(item.get("r") or "")
            if nome in riscos:
                riscos[nome] += int(item.get("n") or 0)
    else:
        for item in tipos:
            nome = _RISCO_POR_CLASSE.get(str(item.get("classe") or ""), "Informativo")
            riscos[nome] = riscos.get(nome, 0) + sum(int(v or 0) for v in (item.get("cameras") or {}).values())
    resumo["riscos"] = riscos

    horas_prioridade = {nome: [0] * 24 for nome in ("Comportamento", "Interacao", "Alerta")}
    from datetime import date as _date

    hoje = _date.today().isoformat()
    for item in cubo_faixa:
        if str(item.get("d") or "") != hoje:
            continue
        faixa = str(item.get("f") or "")
        if faixa not in horas_prioridade:
            continue
        try:
            hora = int(item.get("h") or 0)
        except (TypeError, ValueError):
            hora = 0
        if 0 <= hora <= 23:
            horas_prioridade[faixa][hora] += int(item.get("n") or 0)
    resumo["horas_prioridade"] = horas_prioridade

    classes = {}
    for item in tipos:
        classe = str(item.get("classe") or "")
        if not classe:
            continue
        classes[classe] = classes.get(classe, 0) + sum(int(v or 0) for v in (item.get("cameras") or {}).values())
    resumo["classes"] = [
        {"nome": nome, "total": total}
        for nome, total in sorted(classes.items(), key=lambda par: -par[1])[:8]
    ]

    audio = dict(resumo.get("audio") or {})
    if audio.get("esteira"):
        audio["esteira"] = [item for item in audio["esteira"] if (item.get("camera") or "") in permitidas]
    if audio.get("alertas"):
        audio["alertas"] = [item for item in audio["alertas"] if (item.get("camera") or "") in permitidas]
    if isinstance(audio.get("cameras"), dict):
        audio["cameras"] = {k: v for k, v in audio["cameras"].items() if k in permitidas}
    audio["risco_aberto"] = len(audio.get("alertas") or [])
    resumo["audio"] = audio

    resumo["pendencias"] = [
        item for item in (resumo.get("pendencias") or [])
        if (item.get("camera") or "") in permitidas
        or str(item.get("camera") or "") in ("frequentes", "")
        or str(item.get("tipo") or "").startswith("rosto_")
    ]
    def _historico_visivel(item: dict) -> bool:
        if cadastro.pode_ver_match_interesse(digitos, item):
            return True
        # Admin em vista do cliente: POIs da conta entram mesmo sem câmera no item.
        try:
            tipo_m = str(item.get("tipo") or "").upper()
            ident_m = str(item.get("id") or "")
            if tipo_m == "PLACA":
                cli_m, _ = cadastro.veiculo_por_placa(ident_m)
            else:
                cli_m, _ = cadastro.pessoa_por_face(ident_m)
            if cli_m and cadastro._digitos(cli_m.get("documento")) == digitos:
                return True
        except Exception:
            pass
        cam = item.get("camera") or ""
        return bool(cam) and cam in permitidas

    resumo["historico"] = [
        item for item in (resumo.get("historico") or [])
        if _historico_visivel(item)
    ]
    resumo["geo"] = [
        item for item in (resumo.get("geo") or [])
        if (item.get("camera") or item.get("nome") or "") in permitidas
    ]
    resumo["pontos"] = [
        item for item in (resumo.get("pontos") or [])
        if cadastro.item_no_bairro_visivel(
            digitos, item.get("camera") or "", item.get("rua") or item.get("bairro") or "",
        )
    ]
    resumo["app_linhas"] = [
        item for item in (resumo.get("app_linhas") or [])
        if cadastro.item_no_bairro_visivel(
            digitos,
            item.get("camera") or "",
            item.get("rua") or item.get("endereco") or item.get("bairro") or "",
        )
    ]
    resumo["informes"] = [
        item for item in (resumo.get("informes") or [])
        if (not item.get("camera") or (item.get("camera") or "") in permitidas)
    ]
    resumo["fluxo_eventos"] = [
        item for item in (resumo.get("fluxo_eventos") or [])
        if (item.get("camera") or "") in permitidas
    ]
    resumo["insights"] = list(resumo.get("insights") or [])
    resumo["itens"] = sum(int(item.get("n") or 0) for item in cubo if str(item.get("d") or "") == hoje)

    match = resumo.get("match")
    if isinstance(match, dict):
        # Risco no bairro: Vanessa vê invasor na Carlos Ott mesmo sem ter essa câmera no ao vivo.
        if not cadastro.pode_ver_match_interesse(digitos, match):
            resumo["match"] = None
            resumo["narracao"] = ""
            resumo["narracao_ia"] = ""
            resumo["voz"] = ""
            match = None

    # LED/termômetro: sobe com o match de risco do bairro, não só com câmeras próprias.
    ordem_led = {"branco": 0, "verde": 1, "amarelo": 2, "vermelho": 3, "preto": 4}
    led = "branco"
    for camera in vivo:
        risco = camera.get("risco") or "branco"
        if ordem_led.get(risco, 0) > ordem_led.get(led, 0):
            led = risco
    if isinstance(match, dict):
        alvo = "vermelho" if match.get("risco") else "verde"
        if ordem_led.get(alvo, 0) > ordem_led.get(led, 0):
            led = alvo
        cam_alerta = str(match.get("camera") or "").strip()
        if match.get("risco") and cam_alerta and cam_alerta not in {c.get("nome") for c in vivo}:
            # Inclui a câmera do alerta no detector para o termômetro ir a vermelho.
            vivo = list(vivo) + [{
                "nome": cam_alerta,
                "rua": "",
                "slug": "",
                "agora": {"Pessoa": 0, "Veiculo": 0, "Objeto": 0, "Animal": 0},
                "acumulado": {"Pessoa": 0, "Veiculo": 0, "Objeto": 0, "Animal": 0},
                "comportamentos": [],
                "frase": f"Pessoa de risco no bairro: {match.get('nome') or match.get('id') or ''}",
                "fluxo": {},
                "fluxo_veiculo": {},
                "permanencias": [],
                "risco": "vermelho",
                "audio_vivo": None,
                "cena": "",
            }]
            resumo["cameras_vivo"] = vivo
            resumo["cameras"] = len(vivo)
        if match.get("risco"):
            riscos = dict(resumo.get("riscos") or {})
            riscos["Critico"] = int(riscos.get("Critico") or 0) + 1
            resumo["riscos"] = riscos
            if not str(resumo.get("voz") or "").strip() or "observação" in str(resumo.get("voz") or "").lower():
                resumo["voz"] = (
                    f"Atenção: {match.get('nome') or match.get('id')} "
                    f"(risco) em {cam_alerta or 'câmera do bairro'}."
                )
    # Prefixo Stive / RF: alertas canalizados por grupo de segurança.
    try:
        from grupos_seguranca import grupos_visiveis_na_camera, prefixo_alerta, prefixo_reconhecimento

        cam_grupo = ""
        match_vivo = resumo.get("match")
        if isinstance(match_vivo, dict):
            cam_grupo = str(match_vivo.get("camera") or "").strip()
        if not cam_grupo:
            for cam in resumo.get("cameras_vivo") or []:
                if (cam.get("risco") or "branco") in ("amarelo", "vermelho", "preto"):
                    cam_grupo = str(cam.get("nome") or "").strip()
                    if cam_grupo:
                        break
        if cam_grupo:
            grupos = grupos_visiveis_na_camera(digitos, cam_grupo)
            if grupos:
                pref = prefixo_alerta(digitos, cam_grupo)
                voz = str(resumo.get("voz") or "").strip()
                if pref and voz and not voz.lower().startswith("alerta do grupo"):
                    resumo["voz"] = pref + voz
                if isinstance(match_vivo, dict):
                    match_vivo = dict(match_vivo)
                    match_vivo["grupos"] = grupos
                    trecho_grupo = prefixo_reconhecimento(digitos, cam_grupo)
                    if trecho_grupo and match_vivo.get("tipo") == "FACE":
                        base = (
                            f"Reconhecimento facial {trecho_grupo}: "
                            f"{match_vivo.get('nome') or match_vivo.get('id') or 'uma pessoa'} "
                            f"na {cam_grupo}."
                        )
                        narr = str(resumo.get("narracao_ia") or resumo.get("narracao") or "").strip()
                        if narr:
                            base = f"{base} {narr}"
                        if not voz or "reconhecimento facial" in voz.lower() or "atenção:" in voz.lower():
                            resumo["voz"] = (pref + base) if pref else base
                    resumo["match"] = match_vivo
    except Exception:
        pass
    resumo["led"] = led
    resumo["cliente_documento"] = digitos
    resumo["perfil_sessao"] = perfil or ""
    return _anexar_vizinhos(resumo, digitos)


def _nome_camera_item(item) -> str:
    if isinstance(item, dict):
        return str(item.get("nome") or "").strip()
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return str(item[1] or "").strip()
    return ""


def _cameras_ao_vivo(portal, documento: str, perfil: str) -> list:
    # Catalogo do portal: [(slug, nome, rua), ...]
    cameras = list(portal.cameras() or [])
    if perfil == "administrador":
        return cameras
    permitidas = cadastro.nomes_cameras_visiveis(documento, perfil)
    if not permitidas:
        return []
    return [item for item in cameras if _nome_camera_item(item) in permitidas]


def _cameras_sessao(portal, sessao: dict) -> list:
    doc, perfil = _escopo_analise(portal, sessao)
    return _cameras_ao_vivo(portal, doc, perfil)


def _dados_json(portal, documento: str = "", perfil: str = "") -> dict:
    import time
    from identidade import contar_passagens_faces, contar_passagens_placas

    nomes = {}
    classes = {}
    placas_interesse = {}
    # Admin geral: toda a base. Vista de cliente / usuário: só o cadastro daquele CPF.
    if perfil == "administrador" or not documento:
        try:
            interesse = cadastro.interesse_deteccao_global() or {}
        except Exception:
            interesse = {"pessoas": [], "veiculos": []}
    else:
        try:
            conta = cadastro.consultar(documento)
            pessoas_conta = list(conta.get("pessoas") or [])
            # Inclui risco do bairro (ex.: invasor do Diego aparece para Vanessa).
            vistos = {
                str(p.get("face_id") or "").upper()
                for p in pessoas_conta if p.get("face_id")
            }
            for pessoa in cadastro.risco_visivel_para(documento):
                face = str(pessoa.get("face_id") or "").upper()
                if face and face not in vistos:
                    pessoas_conta.append(pessoa)
                    vistos.add(face)
            interesse = {
                "pessoas": pessoas_conta,
                "veiculos": list(conta.get("veiculos") or []),
            }
        except Exception:
            interesse = {"pessoas": [], "veiculos": []}
    for pessoa in interesse.get("pessoas") or []:
        ident = str(pessoa.get("face_id") or "").upper()
        if not ident:
            continue
        nomes[ident] = str(pessoa.get("nome") or "")
        classes[ident] = cadastro.classe_pessoa(pessoa)
    for veiculo in interesse.get("veiculos") or []:
        placa = "".join(c for c in str(veiculo.get("placa") or "").upper() if c.isalnum())
        if placa:
            placas_interesse[placa] = str(veiculo.get("nome") or placa)

    # Memoriza no ranking os 5 rostos mais frequentes ainda não cadastrados.
    cadastrados = set(nomes)
    for ident, total in contar_passagens_faces(100000):
        if ident in cadastrados:
            continue
        if total < 3:
            continue
        nomes[ident] = f"Rosto frequente {ident}"
        classes[ident] = "frequente"
        if sum(1 for c in classes.values() if c == "frequente") >= 5:
            break

    resumo = dict(portal.resumo())
    agora = time.time()
    chave_nomes = f"{perfil}|{documento}|" + ",".join(sorted(nomes)) + "|" + ",".join(sorted(placas_interesse))
    # Cache 2s das leituras pesadas (Postgres/CSV): o poll do portal é 1s.
    extra = _CACHE_DADOS.get("extra")
    if (
        not extra
        or agora - float(_CACHE_DADOS.get("quando") or 0) > 2.0
        or _CACHE_DADOS.get("nomes_chave") != chave_nomes
    ):
        historico_matches = None
        audio_esteira = None
        contagem_faces = None
        try:
            from db.leitura import audio_esteira as _audio_esteira
            from db.leitura import contagem_faces as _contagem_faces
            from db.leitura import historico_matches as _historico_matches

            historico_matches = _historico_matches
            audio_esteira = _audio_esteira
            contagem_faces = _contagem_faces
        except Exception:
            pass

        linhas = []
        try:
            ids_face = {ident for ident, classe in classes.items() if classe != "frequente"}
            ids_face |= {ident for ident, classe in classes.items() if classe == "frequente"}
            if contagem_faces and ids_face:
                linhas = contagem_faces(ids_face)
            if not linhas:
                linhas = [(ident, total) for ident, total in contar_passagens_faces(100000) if ident in nomes]
        except Exception:
            linhas = [(ident, total) for ident, total in contar_passagens_faces(100000) if ident in nomes]
        # Garante top 5 frequentes mesmo se o filtro do banco omitir.
        vistos = {ident for ident, _total in linhas}
        for ident, total in contar_passagens_faces(100000):
            if classes.get(ident) != "frequente" or ident in vistos:
                continue
            linhas.append((ident, total))
            if sum(1 for i, _t in linhas if classes.get(i) == "frequente") >= 5:
                break
        linhas = sorted(linhas, key=lambda item: (-int(item[1] or 0), item[0]))

        contagem = {ident: total for ident, total in linhas}
        hist_db = []
        try:
            if historico_matches:
                hist_db = historico_matches(set(nomes), limite=40)
            for item in hist_db:
                if item.get("tipo") == "FACE":
                    item["nome"] = nomes.get(item.get("id") or "", item.get("nome") or "")
        except Exception:
            hist_db = []

        audio_extra = None
        try:
            from audio_registro import tokens_nuvem

            if audio_esteira:
                esteira = audio_esteira(limite=80)
                if esteira:
                    audio_extra = {"esteira": esteira}
                    cameras = {}
                    for item in esteira:
                        cam = item.get("camera") or "Camera"
                        slot = cameras.setdefault(cam, {"nuvem": {}, "ranking_risco": {}})
                        for token in tokens_nuvem(item.get("texto") or ""):
                            slot["nuvem"][token] = slot["nuvem"].get(token, 0) + 1
                        cats = [c.strip() for c in str(item.get("categoria") or "risco").split(",") if c.strip()]
                        for palavra in item.get("palavras") or []:
                            cat = cats[0] if cats else "risco"
                            chave = f"{cat}:{palavra}"
                            slot["ranking_risco"][chave] = slot["ranking_risco"].get(chave, 0) + 1
                    audio_extra["alertas"] = [item for item in esteira if item.get("risco")][:20]
                    audio_extra["risco_aberto"] = len(audio_extra["alertas"])
                    audio_extra["cameras"] = {
                        nome: {
                            "nuvem": [{"rotulo": k, "total": v} for k, v in sorted(vals["nuvem"].items(), key=lambda p: -p[1])[:24]],
                            "ranking_risco": [{"rotulo": k, "total": v} for k, v in sorted(vals["ranking_risco"].items(), key=lambda p: -p[1])[:12]],
                        }
                        for nome, vals in cameras.items()
                    }
        except Exception:
            audio_extra = None

        pessoas = [
            {
                "id": ident,
                "nome": nomes.get(ident, ""),
                "classe": classes.get(ident, ""),
                "foto": f"/rosto/{ident}.jpg",
                "total": contagem.get(ident, 0),
            }
            for ident in nomes
        ]
        pessoas.sort(key=lambda item: (-int(item.get("total") or 0), item.get("nome") or item.get("id")))
        extra = {
            "linhas": linhas,
            "contagem": contagem,
            "hist_db": hist_db,
            "audio_extra": audio_extra,
            "pessoas": pessoas,
            "rastros_rf": _rastros_rf_lpr(nomes),
            "fonte_dados": "postgres" if contagem_faces else "csv",
        }
        _CACHE_DADOS["quando"] = agora
        _CACHE_DADOS["extra"] = extra
        _CACHE_DADOS["nomes_chave"] = chave_nomes

    contagem = extra["contagem"]
    linhas = extra["linhas"]
    match = resumo.get("match")
    if isinstance(match, dict):
        match = dict(match)
        match["passagens"] = int(contagem.get(str(match.get("id") or "").upper(), 0))
        if match.get("id") and not match.get("nome"):
            match["nome"] = nomes.get(str(match.get("id") or "").upper(), match.get("nome") or "")
        resumo["match"] = match

    if extra.get("hist_db"):
        resumo["historico"] = extra["hist_db"]

    audio = dict(resumo.get("audio") or {})
    if not audio.get("esteira") and extra.get("audio_extra"):
        audio.update(extra["audio_extra"])
        resumo["audio"] = audio

    placar_placas = []
    try:
        for placa, total in contar_passagens_placas(100000):
            if placa not in placas_interesse:
                continue
            placar_placas.append({
                "id": placa,
                "nome": placas_interesse.get(placa) or placa,
                "total": total,
                "classe": "placa",
            })
            if len(placar_placas) >= 12:
                break
    except Exception:
        placar_placas = []

    resumo.update({
        "itens": int(resumo.get("itens") or 0),
        "faces": len(linhas),
        "topo": linhas[0][1] if linhas else 0,
        "cameras": int(resumo.get("cameras") or len(portal.cameras())),
        "passagens": [
            {
                "id": ident,
                "nome": nomes.get(ident, ""),
                "total": total,
                "classe": classes.get(ident, ""),
            }
            for ident, total in linhas[:12]
        ] + placar_placas,
        "pessoas_interesse": extra["pessoas"],
        "veiculos_interesse": [
            {"placa": placa, "nome": nome}
            for placa, nome in list(placas_interesse.items())[:40]
        ],
        "rastros_rf": extra["rastros_rf"],
        "fonte_dados": extra.get("fonte_dados") or (resumo.get("fonte_dados") or "csv"),
    })
    return _filtrar_resumo_conta(resumo, documento, perfil)


def _tratador(portal: Portal):
    class Tratador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, formato, *args):
            return

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            caminho, consulta = _caminho(self.path)
            if caminho.startswith("/api/mobile/"):
                self._api_mobile_get(caminho)
                return
            if caminho == "/entrar":
                self._html(_pagina_senha(), 200)
                return
            if caminho == "/criar":
                self._html(_pagina_criar(), 200)
                return
            if caminho == "/sair":
                self._html(_pagina_senha(), 200, f"{COOKIE}=; HttpOnly; Path=/; Max-Age=0")
                return
            sessao = portal.abrir_sessao(self.headers.get("Cookie"), self.headers.get("Authorization"))
            if sessao is None:
                self._html(_pagina_senha(), 200)
                return
            self._pagina_autenticada(caminho, consulta, sessao)

        def do_POST(self):
            caminho, _consulta = _caminho(self.path)
            if caminho.startswith("/api/mobile/"):
                self._api_mobile_post(caminho)
                return
            if caminho == "/cadastro/pessoas":
                sessao = portal.abrir_sessao(self.headers.get("Cookie"), self.headers.get("Authorization"))
                if sessao is None:
                    self._html(_pagina_senha(), 200)
                    return
                self._salvar_pessoa(sessao)
                return
            if caminho == "/cadastro/cliente":
                sessao = portal.abrir_sessao(self.headers.get("Cookie"), self.headers.get("Authorization"))
                if sessao is None:
                    self._html(_pagina_senha(), 200)
                    return
                self._salvar_cliente(sessao)
                return
            if caminho == "/vizinhos/mensagem":
                sessao = portal.abrir_sessao(self.headers.get("Cookie"), self.headers.get("Authorization"))
                if sessao is None:
                    self._json_status(401, {"ok": False, "erro": "Faça login."})
                    return
                self._enviar_mensagem_vizinho(sessao)
                return
            campos = self._ler_formulario()
            if campos is None:
                return
            if caminho == "/entrar":
                self._entrar(campos)
                return
            if caminho == "/criar":
                self._criar_primeiro(campos)
                return
            sessao = portal.abrir_sessao(self.headers.get("Cookie"), self.headers.get("Authorization"))
            if sessao is None:
                self._html(_pagina_senha(), 200)
                return
            if caminho != "/comando" and not _csrf_confere(sessao, campos):
                if caminho == "/vista" or caminho.startswith("/agente/"):
                    self._json_status(403, {"ok": False, "erro": "Atualize a página e tente de novo."})
                else:
                    self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Atualize a página e tente de novo.</p></main>", "/"), 403)
                return
            if caminho == "/comando":
                if cadastro.pode_ver_analise(sessao.get("documento") or ""):
                    portal.ajustar_mapa(_um(campos, "periodo"), _um(campos, "desenho"))
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if caminho == "/cadastro/cliente/novo":
                self._criar_cliente(sessao, campos)
                return
            if caminho == "/vizinhos/solicitar":
                self._solicitar_vizinho(sessao, campos)
                return
            if caminho == "/vizinhos/responder":
                self._responder_vizinho(sessao, campos)
                return
            if caminho == "/vizinhos/convidar":
                self._convidar_vizinho(sessao, campos)
                return
            if caminho == "/vizinhos/grupos":
                self._gerir_grupo_seguranca(sessao, campos)
                return
            if caminho == "/cadastro/cameras":
                self._salvar_camera(sessao, campos)
                return
            if caminho == "/cadastro/cameras/remover":
                self._remover_camera(sessao, campos)
                return
            if caminho in ("/gestao/ativar", "/gestao/inativar", "/gestao/excluir"):
                self._gerir_cliente(sessao, campos, caminho.rsplit("/", 1)[-1])
                return
            if caminho == "/gestao/editar":
                self._editar_cliente_gestao(sessao, campos)
                return
            if caminho == "/gestao/reset-senha":
                self._reset_senha_gestao(sessao, campos)
                return
            if caminho == "/cadastro/avisos":
                self._salvar_aviso(sessao, campos)
                return
            if caminho == "/cadastro/avisos/remover":
                self._remover_aviso(sessao, campos)
                return
            if caminho == "/cadastro/pessoas/remover":
                self._remover_pessoa(sessao, campos)
                return
            if caminho == "/cadastro/veiculos":
                self._salvar_veiculo(sessao, campos)
                return
            if caminho == "/cadastro/veiculos/remover":
                self._remover_veiculo(sessao, campos)
                return
            if caminho == "/conta/senha":
                self._trocar_senha(sessao, campos)
                return
            if caminho == "/conta/usuario":
                self._criar_usuario(sessao, campos)
                return
            if caminho == "/vista":
                self._definir_vista(sessao, campos)
                return
            if caminho == "/sistema/teste-capacidade":
                if (sessao.get("perfil") or "") != "administrador":
                    self._json_status(403, {"ok": False, "erro": "Somente o administrador registra testes de capacidade."})
                    return
                try:
                    import monitor_sistema

                    n = int(_um(campos, "n_cameras") or _um(campos, "n") or 0)
                    self._json(monitor_sistema.registrar_teste_capacidade(n))
                except Exception as exc:
                    self._json_status(500, {"ok": False, "erro": str(exc)})
                return
            if caminho == "/agente/stive":
                self._falar_stive(sessao, campos)
                return
            if caminho == "/agente/stive/confirmar":
                self._confirmar_stive(sessao, campos)
                return
            if caminho == "/agente/stive/reacao":
                self._reacao_stive(sessao, campos)
                return
            self.send_error(404)

        def _definir_vista(self, sessao: dict, campos: dict):
            if (sessao.get("perfil") or "") != "administrador":
                self._json_status(403, {"ok": False, "erro": "Somente o administrador segmenta a vista."})
                return
            valor = _um(campos, "documento") or _um(campos, "vista")
            if valor not in ("", "__admin__"):
                digitos = "".join(c for c in valor if c.isdigit())
                if digitos == "".join(c for c in str(cadastro.DOCUMENTO_ADMIN) if c.isdigit()):
                    valor = "__admin__"
                elif cadastro.cliente_por_documento(digitos) is None:
                    self._json_status(400, {"ok": False, "erro": "Cliente não encontrado."})
                    return
                else:
                    valor = digitos
            aplicado = portal.definir_vista(sessao.get("email") or "", valor)
            self._json({
                "ok": True,
                "vista_portal": _info_vista_admin(portal, sessao),
                "valor": aplicado,
            })

        def _pagina_autenticada(self, caminho: str, consulta: dict, sessao: dict):
            documento = sessao.get("documento") or ""
            perfil = sessao.get("perfil") or ""
            if sessao.get("trocar_no_acesso") and caminho not in ("/conta", "/sair") and not caminho.startswith("/conta"):
                # Redireciona de verdade para /conta (antes a URL mudava e o HTML continuava em Conta).
                self._redirecionar("/conta?ok=primeiro")
                return
            ver = cadastro.pode_ver_analise(documento)
            if caminho == "/agente/stive.png":
                self._avatar_stive()
                return
            if caminho == "/agente/stive/historico.json":
                from agente.stive import historico as historico_stive
                from agente.stive import visual_usuario

                email = sessao.get("email") or ""
                perfil = sessao.get("perfil") or ""
                quer_todos = (consulta.get("todos") or [""])[0] in ("1", "true", "sim")
                if quer_todos and perfil != "administrador":
                    self._json_status(403, {"itens": [], "visual": {}, "erro": "Somente o administrador vê o histórico completo."})
                    return
                itens = historico_stive(
                    documento=documento,
                    email="" if quer_todos else email,
                    perfil=perfil,
                    todos=quer_todos and perfil == "administrador",
                )
                # Quadro sempre do usuário logado — nunca o visual de outro.
                visual = {} if quer_todos else visual_usuario(documento=documento, email=email)
                self._json({
                    "itens": itens,
                    "visual": visual,
                    "escopo": "todos" if quer_todos else "usuario",
                })
                return
            if caminho == "/painel.js":
                self._bytes(Path("painel_web.js").read_bytes(), "text/javascript; charset=utf-8")
                return
            if caminho == "/":
                self._html(_inicio(sessao, portal), 200)
                return
            if caminho.startswith("/painel/"):
                if not ver:
                    ui = _sessao_ui(sessao, portal)
                    self._html(_sem_analise(**ui), 200)
                    return
                numero = caminho.removeprefix("/painel/")
                ui = _sessao_ui(sessao, portal)
                if numero == "cameras":
                    self._html(
                        _ao_vivo(_cameras_sessao(portal, sessao), **ui),
                        200,
                    )
                    return
                if numero == "risco":
                    self._html(_risco(**ui), 200)
                    return
                if numero == "grifos":
                    if perfil != "administrador":
                        self.send_error(403)
                        return
                    self._html(_grifos(**ui), 200)
                    return
                if numero == "audio":
                    if perfil != "administrador":
                        self._html(
                            _moldura(
                                "C4ISTAR MONITOR",
                                "<main><p class='aviso'>Áudio e transcrição é tela do administrador. A detecção de áudio continua ativa para a sua conta.</p></main>",
                                "/",
                                **ui,
                            ),
                            403,
                        )
                        return
                    self._html(_audio(**ui), 200)
                    return
                if numero == "stive":
                    self._html(_stive(sessao, portal), 200)
                    return
                for item, chave, titulo in PAINEIS:
                    if item == numero:
                        self._html(
                            _painel(item, titulo, chave, mapas=item == "4", **ui),
                            200,
                        )
                        return
                self.send_error(404)
                return
            if caminho.startswith("/img/") and caminho.endswith(".jpg"):
                if not ver:
                    self.send_error(404)
                    return
                dados = portal.imagem(caminho[5:-4])
                if dados is None:
                    self.send_error(404)
                    return
                self._bytes(dados, "image/jpeg")
                return
            aviso, ok = _mensagem(consulta)
            if caminho == "/vizinhos":
                self._html(_vizinhos(sessao, aviso, ok), 200)
                return
            if caminho == "/vizinhos/buscar.json":
                import vizinhos as rede

                q = (consulta.get("q") or [""])[0]
                itens = rede.buscar_contas(q, sessao.get("documento") or "")
                self._json({"ok": True, "itens": itens})
                return
            if caminho == "/vizinhos/chat.json":
                import vizinhos as rede

                doc_outro = (consulta.get("documento") or [""])[0]
                try:
                    msgs = rede.historico_chat(sessao.get("documento") or "", doc_outro)
                except ValueError as exc:
                    self._json({"ok": False, "erro": str(exc), "mensagens": []})
                    return
                self._json({"ok": True, "mensagens": msgs})
                return
            if caminho == "/vizinhos/grupos.json":
                import grupos_seguranca as grupos

                self._json({
                    "ok": True,
                    "grupos": grupos.listar_grupos(sessao.get("documento") or ""),
                })
                return
            if caminho.startswith("/vizinhos/foto/"):
                import vizinhos as rede

                nome = caminho.rsplit("/", 1)[-1]
                caminho_f = rede.caminho_foto(nome)
                if caminho_f is None:
                    self.send_error(404)
                    return
                dados = caminho_f.read_bytes()
                tipo = "image/jpeg"
                if nome.lower().endswith(".png"):
                    tipo = "image/png"
                elif nome.lower().endswith(".webp"):
                    tipo = "image/webp"
                self._bytes(dados, tipo)
                return
            if caminho == "/mapa/folha":
                if not ver:
                    self.send_error(404)
                    return
                from folium_mapa import html_folha
                self._html(html_folha(), 200)
                return
            if caminho == "/mapa/rota.json":
                if not ver:
                    self.send_error(404)
                    return
                from rota_vias import caminho_dirigindo
                bruto = (consulta.get("pontos") or [""])[0]
                pontos = []
                for pedaco in str(bruto or "").split(";"):
                    pedaco = pedaco.strip()
                    if not pedaco or "," not in pedaco:
                        continue
                    a, b = pedaco.split(",", 1)
                    try:
                        lon, lat = float(a), float(b)
                    except ValueError:
                        continue
                    if abs(lat) <= 90 and abs(lon) <= 180:
                        pontos.append((lat, lon))
                self._json({"caminho": caminho_dirigindo(pontos)})
                return
            if caminho.startswith("/mapa/") and caminho.endswith(".png"):
                pedacos = caminho.strip("/").split("/")
                if len(pedacos) == 4:
                    try:
                        self._tile(int(pedacos[1]), int(pedacos[2]), int(pedacos[3][:-4]))
                    except ValueError:
                        self.send_error(404)
                    return
            if caminho == "/gestao":
                if perfil != "administrador":
                    self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Esta tela é do administrador.</p></main>", "/", perfil=perfil), 403)
                    return
                self._html(_gestao(sessao, portal, aviso, ok), 200)
                return
            if caminho == "/gestao/editar":
                if perfil != "administrador":
                    self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Esta tela é do administrador.</p></main>", "/", perfil=perfil), 403)
                    return
                documento_edit = (consulta.get("documento") or [""])[0]
                self._html(_gestao_editar(sessao, documento_edit, aviso, ok), 200)
                return
            if caminho == "/sistema":
                if perfil != "administrador":
                    self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Esta tela é do administrador.</p></main>", "/", perfil=perfil), 403)
                    return
                self._html(_sistema(sessao), 200)
                return
            if caminho == "/sistema.json":
                if perfil != "administrador":
                    self.send_error(403)
                    return
                try:
                    filtro = (consulta.get("documento") or [""])[0]
                    self._json(_sistema_json(filtro))
                except Exception as exc:
                    self._json({"erro": str(exc)})
                return
            if caminho == "/cadastro/cliente":
                cliente = cadastro.cliente_por_documento(documento) or {}
                self._html(_form_cliente(sessao, cliente, aviso, ok), 200)
                return
            if caminho == "/cadastro/cameras":
                cameras = _cameras_ou_vazio(documento)
                ident = (consulta.get("id") or [""])[0]
                atual = next((item for item in cameras if item.get("id") == ident), None)
                self._html(_form_camera(sessao, cameras, atual, aviso, ok), 200)
                return
            if caminho == "/cadastro/pessoas":
                self._html(_form_pessoas(sessao, _pessoas_da_conta(documento), aviso, ok), 200)
                return
            if caminho == "/cadastro/veiculos":
                self._html(_form_veiculos(sessao, _veiculos_da_conta(documento), aviso, ok), 200)
                return
            if caminho == "/dados.json":
                if not ver:
                    self.send_error(404)
                    return
                doc_escopo, perfil_escopo = _escopo_analise(portal, sessao)
                pacote = _dados_json(portal, doc_escopo, perfil_escopo)
                if perfil == "administrador":
                    pacote["vista_portal"] = _info_vista_admin(portal, sessao)
                self._json(pacote)
                return
            if caminho == "/api/grafo.json":
                if perfil != "administrador":
                    self._json_status(403, {"ok": False, "erro": "Somente o administrador."})
                    return
                try:
                    from grafo_relacoes import exportar_vis
                    doc_f = (consulta.get("documento") or [""])[0]
                    face_f = (consulta.get("face_id") or [""])[0]
                    self._json(exportar_vis(documento=doc_f, face_id=face_f))
                except Exception as exc:
                    self._json_status(500, {"ok": False, "erro": str(exc), "nodes": [], "edges": []})
                return
            if caminho.startswith("/video/"):
                if not ver:
                    self.send_error(404)
                    return
                self._fluxo(caminho[len("/video/"):])
                return
            if caminho.startswith("/rosto/") and caminho.endswith(".jpg"):
                self._rosto(documento, caminho[len("/rosto/"):-4])
                return
            if caminho == "/cadastro/avisos":
                self._html(_form_avisos(sessao, _cameras_ou_vazio(documento), aviso, ok), 200)
                return
            if caminho == "/conta":
                self._html(_form_conta(sessao, aviso, ok), 200)
                return
            self.send_error(404)

        def _salvar_pessoa(self, sessao: dict):
            documento = sessao.get("documento") or ""
            try:
                campos, arquivos = self._ler_multipart()
            except ValueError as exc:
                self._html(_form_pessoas(sessao, _pessoas_da_conta(documento), str(exc)), 400)
                return
            if not _csrf_confere(sessao, campos):
                self._html(_form_pessoas(sessao, _pessoas_da_conta(documento), "Atualize a página e tente de novo."), 403)
                return
            foto = arquivos.get("foto") or b""
            imagem = cv2.imdecode(np_from(foto), cv2.IMREAD_COLOR) if foto else None
            if imagem is None:
                bruto = _um(campos, "foto_base64")
                if bruto.startswith("data:image"):
                    import base64
                    try:
                        parte = bruto.split(",", 1)[1]
                        imagem = cv2.imdecode(np_from(base64.b64decode(parte)), cv2.IMREAD_COLOR)
                    except Exception:
                        imagem = None
            if imagem is None:
                self._html(_form_pessoas(sessao, _pessoas_da_conta(documento), "Envie um arquivo ou capture a foto pela câmera."), 400)
                return
            try:
                if portal._faces is None:
                    raise ValueError("O monitoramento de faces ainda não está pronto.")
                face_id = _um(campos, "face_id").upper()
                if face_id:
                    portal._faces.substituir_foto(face_id, imagem)
                else:
                    face_id, _nova = portal._faces.inscrever_foto(imagem)
                registro = cadastro.cadastrar_pessoa(documento, {
                    "face_id": face_id,
                    "nome": _um(campos, "nome"),
                    "classe": _um(campos, "base_legal"),
                    "base_legal": _um(campos, "base_legal"),
                    "referencia": _um(campos, "referencia"),
                    "motivo": _um(campos, "motivo"),
                    "favorecido": _um(campos, "favorecido"),
                    "nome_protegido": _um(campos, "nome_protegido"),
                }, faces_engine=portal._faces)
            except ValueError as exc:
                self._html(_form_pessoas(sessao, _pessoas_da_conta(documento), str(exc)), 400)
                return
            cruz = list((registro or {}).get("_cruzamentos") or [])
            if cruz:
                self._redirecionar(f"/cadastro/pessoas?ok=cruzado&n={len(cruz)}")
            else:
                self._redirecionar("/cadastro/pessoas?ok=salvo")

        def _salvar_veiculo(self, sessao: dict, campos: dict):
            documento = sessao.get("documento") or ""
            try:
                cadastro.cadastrar_veiculo(documento, {
                    "placa": _um(campos, "placa"),
                    "nome": _um(campos, "nome"),
                    "motivo": _um(campos, "motivo"),
                })
            except ValueError as exc:
                self._html(_form_veiculos(sessao, _veiculos_da_conta(documento), str(exc)), 400)
                return
            self._redirecionar("/cadastro/veiculos?ok=salvo")

        def _remover_veiculo(self, sessao: dict, campos: dict):
            documento = sessao.get("documento") or ""
            try:
                cadastro.remover_veiculo(documento, _um(campos, "placa"))
            except ValueError as exc:
                self._html(_form_veiculos(sessao, _veiculos_da_conta(documento), str(exc)), 400)
                return
            self._redirecionar("/cadastro/veiculos?ok=removido")

        def _remover_pessoa(self, sessao: dict, campos: dict):
            documento = sessao.get("documento") or ""
            face_id = _um(campos, "face_id").upper()
            try:
                cadastro.remover_pessoa(documento, face_id)
                if portal._faces is not None:
                    portal._faces.remover_foto(face_id)
            except ValueError as exc:
                self._html(_form_pessoas(sessao, _pessoas_da_conta(documento), str(exc)), 400)
                return
            self._redirecionar("/cadastro/pessoas?ok=removido")

        def _ler_multipart(self):
            tipo = self.headers.get("Content-Type") or ""
            if "boundary=" not in tipo:
                raise ValueError("Envie a foto pelo formulário.")
            limite = self.headers.get("Content-Length") or "0"
            try:
                tamanho = int(limite)
            except ValueError:
                tamanho = -1
            if tamanho < 0 or tamanho > 8 * 1024 * 1024:
                raise ValueError("A foto precisa ter até 8 MB.")
            corpo = self.rfile.read(tamanho)
            fronteira = tipo.split("boundary=", 1)[1].strip().strip('"')
            return _multipart(corpo, fronteira)

        def _fluxo(self, chave: str):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=quadro")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            ultimo = -1
            try:
                while True:
                    jpeg, seq = portal.quadro(chave)
                    if not jpeg or seq == ultimo:
                        time.sleep(0.04)
                        continue
                    ultimo = seq
                    cabeca = (
                        b"--quadro\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpeg)).encode("ascii")
                        + b"\r\n\r\n"
                    )
                    self.wfile.write(cabeca + jpeg + b"\r\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError, OSError):
                return

        def _rosto(self, documento: str, face_id: str):
            ident = "".join(caractere for caractere in face_id if caractere.isalnum()).upper()
            conhecidos = {item.get("face_id") for item in _pessoas_da_conta(documento)}
            if ident not in conhecidos and not cadastro.pode_ver_analise(documento):
                self.send_error(404)
                return
            caminho = Path("evidencias") / "faces" / ident / "referencia.jpg"
            if not caminho.is_file():
                self.send_error(404)
                return
            self._bytes(caminho.read_bytes(), "image/jpeg")

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def _json(self, corpo: dict):
            self._json_status(200, corpo)

        def _json_status(self, status: int, corpo: dict):
            dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                self.send_header("Cache-Control", "no-store")
                self._cors()
                self.end_headers()
                self.wfile.write(dados)
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
                # Cliente fechou o poll (F5 / aba) — normal, não deve poluir o console.
                return

        def _api_mobile_sessao(self):
            return portal.abrir_sessao(self.headers.get("Cookie"), self.headers.get("Authorization"))

        def _api_mobile_get(self, caminho: str):
            import api_mobile

            if caminho == "/api/mobile/saude":
                self._json_status(200, api_mobile.saude())
                return
            sessao = self._api_mobile_sessao()
            if sessao is None:
                self._json_status(401, {"ok": False, "erro": "Faça login."})
                return
            if caminho == "/api/mobile/dados":
                status, corpo = api_mobile.dados(portal, sessao, _dados_json)
                self._json_status(status, corpo)
                return
            if caminho == "/api/mobile/custos":
                status, corpo = api_mobile.custos(sessao)
                self._json_status(status, corpo)
                return
            self._json_status(404, {"ok": False, "erro": "Rota mobile desconhecida."})

        def _api_mobile_post(self, caminho: str):
            import api_mobile

            payload = api_mobile.corpo_json(self.rfile, self.headers.get("Content-Length") or "0")
            if caminho == "/api/mobile/login":
                status, corpo = api_mobile.login(portal, payload.get("email") or "", payload.get("senha") or "")
                self._json_status(status, corpo)
                return
            sessao = self._api_mobile_sessao()
            if sessao is None:
                self._json_status(401, {"ok": False, "erro": "Faça login."})
                return
            if caminho == "/api/mobile/stive":
                resumo = _dados_json(
                    portal,
                    sessao.get("documento") or "",
                    sessao.get("perfil") or "",
                )
                status, corpo = api_mobile.stive(
                    portal,
                    sessao,
                    payload.get("pergunta") or "",
                    resumo=resumo,
                )
                self._json_status(status, corpo)
                return
            self._json_status(404, {"ok": False, "erro": "Rota mobile desconhecida."})

        def _entrar(self, campos: dict):
            try:
                usuario = acesso.autenticar(_um(campos, "email"), _um(campos, "senha"))
            except ValueError as exc:
                self._html(_pagina_senha(str(exc)), 401)
                return
            conta = cadastro.cliente_por_documento(usuario.get("documento") or "")
            if conta is not None and conta.get("ativo") is False and usuario.get("perfil") != "administrador":
                self._html(_pagina_senha("Esta conta está inativa."), 403)
                return
            destino = "/conta" if usuario.get("trocar_no_acesso") else "/"
            self._redirecionar(destino, _cabecalho_cookie(acesso.emitir_cookie(usuario, portal.senha)))

        def _criar_primeiro(self, campos: dict):
            try:
                usuario = acesso.criar_primeiro(
                    _um(campos, "chave"),
                    portal.senha,
                    _um(campos, "nome"),
                    _um(campos, "email"),
                    _um(campos, "senha"),
                    _um(campos, "confirmacao"),
                    _um(campos, "documento"),
                )
                usuario = acesso.autenticar(usuario["email"], _um(campos, "senha"))
            except ValueError as exc:
                self._html(_pagina_criar(str(exc)), 400)
                return
            self._redirecionar("/", _cabecalho_cookie(acesso.emitir_cookie(usuario, portal.senha)))

        def _salvar_cliente(self, sessao: dict, campos: dict | None = None, arquivos: dict | None = None):
            tipo = self.headers.get("Content-Type") or ""
            if "multipart/form-data" in tipo:
                try:
                    campos, arquivos = self._ler_multipart()
                except ValueError as exc:
                    atual = cadastro.cliente_por_documento(sessao.get("documento") or "") or {}
                    self._html(_form_cliente(sessao, atual, str(exc)), 400)
                    return
            else:
                campos = campos if campos is not None else (self._ler_formulario() or {})
                arquivos = arquivos or {}
            if not _csrf_confere(sessao, campos or {}):
                atual = cadastro.cliente_por_documento(sessao.get("documento") or "") or {}
                self._html(_form_cliente(sessao, atual, "Atualize a página e tente de novo."), 403)
                return
            try:
                cliente = cadastro.salvar_cliente(
                    sessao.get("documento") or "",
                    _um(campos, "nome"),
                    _um(campos, "rg"),
                    _um(campos, "documento"),
                    _um(campos, "email"),
                )
            except ValueError as exc:
                atual = cadastro.cliente_por_documento(sessao.get("documento") or "") or {}
                self._html(_form_cliente(sessao, atual, str(exc)), 400)
                return
            foto = (arquivos or {}).get("foto") or b""
            if foto:
                imagem = cv2.imdecode(np_from(foto), cv2.IMREAD_COLOR)
                if imagem is None:
                    self._html(_form_cliente(sessao, cliente, "Não consegui ler a foto enviada."), 400)
                    return
                try:
                    if portal._faces is None:
                        raise ValueError("O monitoramento de faces ainda não está pronto.")
                    face_atual = str(cliente.get("foto_face_id") or "").strip().upper()
                    if face_atual:
                        portal._faces.substituir_foto(face_atual, imagem)
                        face_id = face_atual
                    else:
                        face_id, _nova = portal._faces.inscrever_foto(imagem)
                    cliente = cadastro.definir_foto_cliente(
                        cliente.get("documento") or "",
                        face_id,
                        eh_proprio=True,
                        faces_engine=portal._faces,
                    )
                except ValueError as exc:
                    self._html(_form_cliente(sessao, cliente, str(exc)), 400)
                    return
            cookie = ""
            if cliente.get("documento") != sessao.get("documento"):
                usuario = {
                    "email": sessao.get("email"),
                    "documento": cliente.get("documento"),
                    "marca": sessao.get("marca"),
                }
                cookie = _cabecalho_cookie(acesso.emitir_cookie(usuario, portal.senha))
            cruz = list((cliente or {}).get("_cruzamentos") or [])
            if cruz:
                self._redirecionar(f"/cadastro/cliente?ok=cruzado&n={len(cruz)}", cookie)
            else:
                self._redirecionar("/cadastro/cliente?ok=salvo", cookie)

        def _criar_cliente(self, sessao: dict, campos: dict):
            if sessao.get("perfil") != "administrador":
                self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Esta ação é do administrador.</p></main>", "/", perfil=sessao.get("perfil") or ""), 403)
                return
            import secrets
            import string
            from agente.envio import enviar_email

            nome = _um(campos, "nome_novo")
            documento = _um(campos, "documento_novo")
            email = _um(campos, "email_novo").strip().lower()
            senha = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            try:
                cadastro.criar_cliente(nome, documento, email)
                acesso.criar_convite(documento, nome, email, senha)
            except ValueError as exc:
                try:
                    cadastro.excluir_cliente(documento)
                except ValueError:
                    pass
                atual = cadastro.cliente_por_documento(sessao.get("documento") or "") or {}
                self._html(_form_cliente(sessao, atual, str(exc)), 400)
                return
            enviado = enviar_email(
                "Acesso ao C4ISTAR MONITOR",
                "Seu acesso ao C4ISTAR MONITOR foi criado.\n\n"
                f"Login: {email}\n"
                f"Senha provisória: {senha}\n\n"
                "No primeiro acesso, troque esta senha. Ela não é reenviada.",
                destinos=[email],
            )
            if not enviado:
                try:
                    cadastro.excluir_cliente(documento)
                except ValueError:
                    pass
                atual = cadastro.cliente_por_documento(sessao.get("documento") or "") or {}
                self._html(_form_cliente(sessao, atual, "O e-mail de acesso não saiu. O cliente não foi criado."), 400)
                return
            self._redirecionar("/cadastro/cliente?ok=criado")

        def _solicitar_vizinho(self, sessao: dict, campos: dict):
            import vizinhos as rede

            try:
                saida = rede.solicitar_vizinho(
                    sessao.get("documento") or "",
                    _um(campos, "documento_vizinho"),
                    _um(campos, "vinculo"),
                    nome=str((cadastro.cliente_por_documento(sessao.get("documento") or "") or {}).get("nome") or ""),
                    email=sessao.get("email") or "",
                    notificar=_um(campos, "notificar"),
                )
            except ValueError as exc:
                self._json({"ok": False, "erro": str(exc)})
                return
            self._json({
                "ok": True,
                "fala": f"Solicitação enviada para {saida.get('nome') or 'o vizinho'}.",
                "solicitacao": saida,
            })

        def _responder_vizinho(self, sessao: dict, campos: dict):
            import vizinhos as rede

            aceitar = _um(campos, "resposta").lower() in ("aceitar", "sim", "1", "aceito")
            try:
                saida = rede.responder_solicitacao(
                    sessao.get("documento") or "",
                    _um(campos, "documento_vizinho"),
                    aceitar,
                    vinculo=_um(campos, "vinculo"),
                    nome=str((cadastro.cliente_por_documento(sessao.get("documento") or "") or {}).get("nome") or ""),
                    email=sessao.get("email") or "",
                )
            except ValueError as exc:
                self._json({"ok": False, "erro": str(exc)})
                return
            self._json({"ok": True, "resultado": saida})

        def _convidar_vizinho(self, sessao: dict, campos: dict):
            import vizinhos as rede

            try:
                saida = rede.convidar_externo(
                    sessao.get("documento") or "",
                    nome=_um(campos, "nome"),
                    email_destino=_um(campos, "email"),
                    telefone=_um(campos, "telefone"),
                    canal=_um(campos, "canal") or "email",
                )
            except ValueError as exc:
                self._json({"ok": False, "erro": str(exc)})
                return
            partes = []
            if saida.get("email"):
                partes.append("e-mail enviado")
            if saida.get("whatsapp"):
                partes.append("WhatsApp enviado")
            elif saida.get("whatsapp_link"):
                partes.append("link do WhatsApp pronto")
            self._json({
                "ok": True,
                "fala": "Convite: " + (", ".join(partes) if partes else "registrado"),
                "whatsapp_link": saida.get("whatsapp_link") or "",
                "convite": saida,
            })

        def _gerir_grupo_seguranca(self, sessao: dict, campos: dict):
            import grupos_seguranca as grupos
            import vizinhos as rede

            documento = sessao.get("documento") or ""
            acao = (_um(campos, "acao") or "").strip().lower()
            grupo_id = _um(campos, "grupo_id")
            try:
                if acao == "criar":
                    saida = grupos.criar_grupo(
                        documento,
                        _um(campos, "nome"),
                        descricao=_um(campos, "descricao"),
                    )
                    self._json({"ok": True, "grupo": saida})
                    return
                if acao in ("membro", "add-membro", "adicionar_membro"):
                    membro = _um(campos, "documento_membro")
                    aceitos = {
                        "".join(c for c in str(v.get("documento") or "") if c.isdigit())
                        for v in rede.listar_vizinhos(documento)
                    }
                    dig_membro = "".join(c for c in membro if c.isdigit())
                    if dig_membro not in aceitos:
                        raise ValueError("Só é possível incluir vizinhos já aceitos no grupo.")
                    saida = grupos.adicionar_membro(grupo_id, documento, membro)
                    self._json({"ok": True, "grupo": saida})
                    return
                if acao in ("remover_membro", "sair"):
                    saida = grupos.remover_membro(
                        grupo_id, documento, _um(campos, "documento_membro") or documento
                    )
                    self._json({"ok": True, "grupo": saida})
                    return
                if acao in ("camera", "add-cam", "compartilhar"):
                    saida = grupos.compartilhar_camera(
                        grupo_id, documento, _um(campos, "camera_id")
                    )
                    self._json({"ok": True, "grupo": saida})
                    return
                if acao in ("remover_camera", "rm-cam"):
                    saida = grupos.remover_camera(
                        grupo_id, documento, _um(campos, "camera_id")
                    )
                    self._json({"ok": True, "grupo": saida})
                    return
                if acao == "excluir":
                    grupos.excluir_grupo(grupo_id, documento)
                    self._json({"ok": True})
                    return
                if acao in ("listar", "lista"):
                    self._json({"ok": True, "grupos": grupos.listar_grupos(documento)})
                    return
                raise ValueError("Ação de grupo desconhecida.")
            except ValueError as exc:
                self._json({"ok": False, "erro": str(exc)})

        def _enviar_mensagem_vizinho(self, sessao: dict):
            import vizinhos as rede

            tipo = self.headers.get("Content-Type") or ""
            try:
                if "multipart/form-data" in tipo:
                    campos, arquivos = self._ler_multipart()
                else:
                    campos = self._ler_formulario() or {}
                    arquivos = {}
            except ValueError as exc:
                self._json({"ok": False, "erro": str(exc)})
                return
            if not _csrf_confere(sessao, campos or {}):
                self._json_status(403, {"ok": False, "erro": "Atualize a página e tente de novo."})
                return
            foto = (arquivos or {}).get("foto") or b""
            try:
                msg = rede.enviar_mensagem(
                    sessao.get("documento") or "",
                    _um(campos, "documento_vizinho"),
                    _um(campos, "texto"),
                    foto_bytes=foto if foto else None,
                )
            except ValueError as exc:
                self._json({"ok": False, "erro": str(exc)})
                return
            self._json({"ok": True, "mensagem": msg})

        def _salvar_camera(self, sessao: dict, campos: dict):
            documento = sessao.get("documento") or ""
            try:
                cadastro.salvar_camera(documento, {
                    "id": _um(campos, "id"),
                    "nome": _um(campos, "nome"),
                    "marca": _um(campos, "marca"),
                    "modelo": _um(campos, "modelo"),
                    "ativa": _marcado(campos, "ativa"),
                    "host": _um(campos, "host"),
                    "porta": _um(campos, "porta"),
                    "usuario": _um(campos, "usuario"),
                    "senha": _um(campos, "senha"),
                    "canal": _um(campos, "canal"),
                    "subtype": _um(campos, "subtype"),
                    "rua": _um(campos, "rua"),
                    "bairro": _um(campos, "bairro"),
                    "cidade": _um(campos, "cidade"),
                    "latitude": _um(campos, "latitude"),
                    "longitude": _um(campos, "longitude"),
                }, _um(campos, "id_anterior"))
            except ValueError as exc:
                cameras = _cameras_ou_vazio(documento)
                self._html(_form_camera(sessao, cameras, None, str(exc)), 400)
                return
            self._redirecionar("/cadastro/cameras?ok=salvo")

        def _remover_camera(self, sessao: dict, campos: dict):
            documento = sessao.get("documento") or ""
            try:
                cadastro.remover_camera(documento, _um(campos, "id"))
            except ValueError as exc:
                self._html(_form_camera(sessao, _cameras_ou_vazio(documento), None, str(exc)), 400)
                return
            self._redirecionar("/cadastro/cameras?ok=removido")

        def _gerir_cliente(self, sessao: dict, campos: dict, acao: str):
            if sessao.get("perfil") != "administrador":
                self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Esta ação é do administrador.</p></main>", "/", perfil=sessao.get("perfil") or ""), 403)
                return
            documento = _um(campos, "documento")
            try:
                if acao == "excluir":
                    cadastro.excluir_cliente(documento)
                else:
                    cadastro.definir_atividade(documento, acao == "ativar")
            except ValueError as exc:
                self._html(_gestao(sessao, portal, str(exc)), 400)
                return
            self._redirecionar(f"/gestao?ok={acao}")

        def _editar_cliente_gestao(self, sessao: dict, campos: dict):
            if sessao.get("perfil") != "administrador":
                self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Esta ação é do administrador.</p></main>", "/", perfil=sessao.get("perfil") or ""), 403)
                return
            documento_atual = _um(campos, "documento_atual")
            nome = _um(campos, "nome")
            rg = _um(campos, "rg")
            documento = _um(campos, "documento")
            email = _um(campos, "email").strip().lower()
            atual = cadastro.cliente_por_documento(documento_atual) or {}
            email_antigo = str(atual.get("email") or "").strip().lower()
            try:
                cliente = cadastro.salvar_cliente(documento_atual, nome, rg, documento, email)
                acesso.atualizar_usuario_principal(
                    cliente.get("documento") or documento,
                    nome=nome,
                    email_novo=email,
                    email_antigo=email_antigo or email,
                )
            except ValueError as exc:
                self._html(_gestao_editar(sessao, documento_atual or documento, str(exc)), 400)
                return
            digitos = "".join(c for c in str(cliente.get("documento") or documento) if c.isdigit())
            self._redirecionar(f"/gestao/editar?documento={digitos}&ok=salvo")

        def _reset_senha_gestao(self, sessao: dict, campos: dict):
            if sessao.get("perfil") != "administrador":
                self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Esta ação é do administrador.</p></main>", "/", perfil=sessao.get("perfil") or ""), 403)
                return
            from agente.envio import enviar_email

            documento = _um(campos, "documento")
            email = _um(campos, "email").strip().lower()
            digitos = "".join(c for c in str(documento) if c.isdigit())
            try:
                reset = acesso.resetar_senha(documento, email)
            except ValueError as exc:
                if "editar" in (self.headers.get("Referer") or ""):
                    self._html(_gestao_editar(sessao, digitos, str(exc)), 400)
                else:
                    self._html(_gestao(sessao, portal, str(exc)), 400)
                return
            enviado = enviar_email(
                "Reset de senha · C4ISTAR MONITOR",
                "Seu acesso ao C4ISTAR MONITOR teve a senha redefinida pelo administrador.\n\n"
                f"Login: {reset.get('email')}\n"
                f"Senha provisória: {reset.get('senha')}\n\n"
                "No próximo acesso, troque esta senha.",
                destinos=[reset.get("email")],
            )
            if not enviado:
                self._html(_gestao_editar(sessao, digitos, "A senha foi gerada, mas o e-mail não saiu. Verifique o SMTP."), 400)
                return
            self._redirecionar(f"/gestao/editar?documento={digitos}&ok=reset")

        def _avatar_stive(self):
            from agente.stive import caminho_avatar

            caminho = caminho_avatar()
            if caminho is None:
                self.send_error(404)
                return
            imagem = cv2.imread(str(caminho))
            if imagem is None or getattr(imagem, "size", 0) == 0:
                self.send_error(404)
                return
            ok, bruto = cv2.imencode(".png", imagem)
            if not ok:
                self.send_error(404)
                return
            self._bytes(bruto.tobytes(), "image/png")

        def _falar_stive(self, sessao: dict, campos: dict):
            from agente.stive import responder
            from custos.estimativa import registrar_envio

            documento = sessao.get("documento") or ""
            perfil = sessao.get("perfil") or ""
            email = sessao.get("email") or ""
            doc_escopo, perfil_escopo = _escopo_analise(portal, sessao)
            # Cliente: CPF da sessão. Admin: geral ou vista segmentada.
            resumo = _dados_json(portal, doc_escopo, perfil_escopo)
            try:
                saida = responder(
                    doc_escopo or documento,
                    _um(campos, "pergunta"),
                    resumo,
                    email=email,
                    perfil=perfil if not doc_escopo else perfil_escopo,
                )
            except ValueError as exc:
                self._json({"fala": str(exc), "visual": {}})
                return
            except Exception:
                self._json({"fala": "A base respondeu com erro. Tente de novo em instantes.", "visual": {}})
                return
            try:
                registrar_envio("openai", "out", unidades=1.0, detalhe="stive-web", documento=documento)
            except Exception:
                pass
            self._json({"fala": saida.get("fala") or "", "visual": saida.get("visual") or {}})

        def _confirmar_stive(self, sessao: dict, campos: dict):
            from agente.stive import confirmar

            try:
                saida = confirmar(
                    sessao.get("documento") or "",
                    _um(campos, "id"),
                    _um(campos, "resposta"),
                    _um(campos, "texto"),
                    _um(campos, "camera"),
                    _um(campos, "tipo"),
                    _um(campos, "vinculo"),
                    _um(campos, "nome"),
                    faces_engine=portal._faces,
                )
            except ValueError as exc:
                self._json({"fala": str(exc), "ok": False})
                return
            if isinstance(saida, dict):
                self._json(saida)
            else:
                self._json({"fala": str(saida or ""), "ok": True})

        def _reacao_stive(self, sessao: dict, campos: dict):
            from agente.stive import registrar_reacao

            try:
                saida = registrar_reacao(
                    sessao.get("documento") or "",
                    _um(campos, "chave"),
                    _um(campos, "titulo"),
                    _um(campos, "texto"),
                    _um(campos, "nota") or "0",
                    _um(campos, "tipo"),
                )
            except Exception:
                self._json({"ok": False})
                return
            self._json(saida)

        def _tile(self, zoom: int, x: int, y: int):
            from mapa import _baixar

            imagem = _baixar(zoom, x, y)
            if imagem is None or getattr(imagem, "size", 0) == 0:
                self.send_error(404)
                return
            ok, bruto = cv2.imencode(".png", imagem)
            if not ok:
                self.send_error(404)
                return
            self._bytes(bruto.tobytes(), "image/png")

        def _salvar_aviso(self, sessao: dict, campos: dict):
            documento = sessao.get("documento") or ""
            try:
                cadastro.cadastrar_aviso(documento, _um(campos, "camera_id"), {
                    "codigo_pais": _um(campos, "codigo_pais"),
                    "ddd": _um(campos, "ddd"),
                    "numero": _um(campos, "numero"),
                    "email": _um(campos, "email"),
                    "recebe_alerta": _marcado(campos, "recebe_alerta"),
                    "recebe_relatorio": _marcado(campos, "recebe_relatorio"),
                })
            except ValueError as exc:
                self._html(_form_avisos(sessao, _cameras_ou_vazio(documento), str(exc)), 400)
                return
            self._redirecionar("/cadastro/avisos?ok=salvo")

        def _remover_aviso(self, sessao: dict, campos: dict):
            documento = sessao.get("documento") or ""
            try:
                cadastro.remover_aviso(documento, _um(campos, "camera_id"), int(_um(campos, "indice") or "-1"))
            except (ValueError, TypeError) as exc:
                texto = str(exc) if isinstance(exc, ValueError) else "Aviso não encontrado."
                self._html(_form_avisos(sessao, _cameras_ou_vazio(documento), texto), 400)
                return
            self._redirecionar("/cadastro/avisos?ok=removido")

        def _trocar_senha(self, sessao: dict, campos: dict):
            try:
                usuario = acesso.trocar_senha(
                    sessao.get("email") or "",
                    _um(campos, "atual"),
                    _um(campos, "nova"),
                    _um(campos, "confirmacao"),
                )
            except ValueError as exc:
                self._html(_form_conta(sessao, str(exc)), 400)
                return
            self._redirecionar(
                "/conta?ok=senha",
                _cabecalho_cookie(acesso.emitir_cookie(usuario, portal.senha)),
            )

        def _criar_usuario(self, sessao: dict, campos: dict):
            try:
                acesso.criar_usuario(
                    sessao.get("documento") or "",
                    _um(campos, "nome"),
                    _um(campos, "email"),
                    _um(campos, "senha"),
                    _um(campos, "confirmacao"),
                )
            except ValueError as exc:
                self._html(_form_conta(sessao, str(exc)), 400)
                return
            self._redirecionar("/conta?ok=usuario")

        def _ler_formulario(self):
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                tamanho = -1
            if tamanho < 0 or tamanho > 48 * 1024:
                self.send_error(413)
                return None
            corpo = self.rfile.read(tamanho).decode("utf-8", "replace") if tamanho else ""
            return parse_qs(corpo, keep_blank_values=True)

        def _html(self, corpo: str, status: int, cookie: str = ""):
            dados = corpo.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(dados)

        def _bytes(self, dados: bytes, tipo: str):
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(dados)

        def _redirecionar(self, local: str, cookie: str = ""):
            self.send_response(303)
            self.send_header("Location", local)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()

    return Tratador


def _caminho(path: str) -> tuple[str, dict]:
    url = urlparse(path)
    return url.path.rstrip("/") or "/", parse_qs(url.query)


def _csrf_confere(sessao: dict, campos: dict) -> bool:
    enviado = _um(campos, "csrf").encode("utf-8")
    esperado = str(sessao.get("csrf") or "").encode("utf-8")
    if not esperado or not enviado:
        return False
    return hmac.compare_digest(enviado, esperado)


def _mensagem(consulta: dict) -> tuple[str, bool]:
    codigo = (consulta.get("ok") or [""])[0]
    textos = {
        "salvo": "Salvo.",
        "removido": "Removido.",
        "criado": "Cliente criado. O acesso foi enviado para o e-mail informado.",
        "ativar": "Cliente ativado.",
        "inativar": "Cliente inativado.",
        "excluir": "Cliente excluído.",
        "senha": "Senha atualizada. Os outros acessos desta conta precisam entrar de novo.",
        "usuario": "Usuário criado. Ele entra com o e-mail e a senha informados.",
        "reset": "Senha provisória gerada e enviada por e-mail. No próximo acesso a troca será obrigatória.",
        "primeiro": "No primeiro acesso, troque a senha enviada por e-mail. Depois as telas do seu CPF/CNPJ ficam liberadas.",
        "cruzado": (
            "Salvo. Este rosto também é pessoa de interesse em outra conta; "
            "o vínculo colaborativo foi compilado no grifo/Neo4j."
        ),
        "vizinho": "Vizinho adicionado à rede. O vínculo informado foi refletido no grifo.",
    }
    if codigo == "cruzado":
        try:
            n = int((consulta.get("n") or ["0"])[0])
        except ValueError:
            n = 0
        if n > 1:
            textos["cruzado"] = (
                f"Salvo. Este rosto corresponde a interesse em {n} outras contas; "
                "os vínculos colaborativos foram compilados no grifo/Neo4j."
            )
    return textos.get(codigo, ""), bool(codigo in textos)


def _cameras_ou_vazio(documento: str) -> list[dict]:
    try:
        return cadastro.cameras_publicas(documento)
    except ValueError:
        return []
