"""Acesso pelo navegador. O túnel leva estas páginas para fora de casa.

A análise continua junto das câmeras. Cada usuário entra com o próprio
e-mail e só vê a conta do seu CPF ou CNPJ. As telas de painel são uma
página leve: o quadro já publicado troca no lugar, e recarregar volta na hora.
"""

from __future__ import annotations

import csv
import hmac
import json
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
aside { width: 248px; flex: none; position: sticky; top: 0; height: 100vh; overflow: auto;
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
.palco { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.palco.parede { height: 100vh; }
.topo { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 18px 22px 0; }
.topo h1 { margin: 0; font-size: 28px; font-weight: 600; }
.topo p { margin: 4px 0 0; color: var(--mudo); font-size: 15px; }
main { padding: 18px 22px 40px; display: flex; flex-direction: column; gap: 22px; }
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
.tela { flex: 1; min-height: 0; margin: 12px 22px 18px; overflow: hidden; }
.tela img, .video img { width: 100%; height: 100%; object-fit: contain; display: block; background: transparent; }
.parede .miolo { display: flex; flex-direction: column; height: 100%; }
.comandos { display: flex; gap: 8px; padding: 0 22px; }
.comandos button, button { display: inline-flex; align-items: center; gap: 8px;
  background: linear-gradient(180deg, #5b97ff, #3d74f0); color: white; border: 0;
  border-radius: 12px; padding: 11px 16px; font-size: 15px; cursor: pointer; }
label { display: block; margin: 12px 0; color: var(--mudo); font-size: 14px; }
input, select { width: 100%; margin-top: 6px; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--linha);
  background: rgba(8, 12, 24, 0.65); color: var(--texto); font-size: 16px; }
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
iframe.mapa, iframe.mapa-folium { display: block; width: 100%; height: 280px; border: 0; border-radius: 12px; background: #d5e2ef; }
iframe#mapa { height: 520px; }
main[data-tela="inicio"] .cartao span { font-size: 18px; gap: 12px; }
main[data-tela="inicio"] .cartao span svg { width: 40px; height: 40px; }
main[data-tela="inicio"] .cartao strong { font-size: 40px; }
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
.voz { margin: 0; text-align: center; font-size: 28px; font-weight: 600; line-height: 1.35; }
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
.stive-pagina { display: grid; grid-template-rows: auto 1fr; gap: 18px; min-height: calc(100vh - 110px); }
.stive-topo { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 22px; align-items: start; }
.stive-chat-area { display: flex; flex-direction: column; justify-content: flex-end; width: min(760px, 100%); margin: 0 auto; gap: 12px; }
.avatar-stive { width: 180px; height: 220px; border-radius: 24px; object-fit: cover; background: linear-gradient(160deg, #4c8dff, #3ee0ff);
  display: grid; place-items: center; color: #041018; font-size: 72px; font-weight: 700; }
.chat { display: flex; flex-direction: column; gap: 10px; min-height: 360px; max-height: 62vh; overflow: auto; }
.stive-chat-area .chat { min-height: 280px; max-height: 52vh; justify-content: flex-end; }
.stive-chat-area form { margin: 0; }
.bolha { max-width: 92%; padding: 12px 14px; border-radius: 16px; line-height: 1.4; }
.bolha.stive { background: rgba(76,141,255,.16); }
.bolha.eu { margin-left: auto; background: rgba(255,255,255,.06); }
.quadro-stive { min-height: 220px; }
.acoes-fala { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.acoes-fala button { background: #edf2ff; color: #141820; border: 1px solid #c9d6ff; padding: 8px 12px; border-radius: 10px; font-size: 13px; }
.acoes-fala button[data-reacao="-1"] { background: #ffecec; border-color: #ffb3b3; }
.acoes-fala button[data-fechar] { background: #f4f7fb; border-color: #d5deea; }
.satisfacao-stive { margin-top: 28px; }
.satisfacao-stive .cartoes { margin-top: 12px; }
.pendencia { display: flex; gap: 8px; align-items: center; justify-content: space-between; margin-top: 10px; }
.pendencia button { background: transparent; color: var(--texto); border: 1px solid var(--linha); }
.avatar-stive { object-position: center 18%; }
.balao-stive { position: fixed; right: 18px; bottom: 18px; z-index: 34; width: 400px; display: flex; flex-direction: column-reverse; align-items: flex-end; gap: 10px; }
.balao-stive.fechado { width: auto; }
.grupo-puxador { position: relative; display: flex; flex-direction: column; align-items: center; }
.puxador-stive { width: 124px; height: 124px; border-radius: 50%; padding: 0; overflow: hidden; border: 3px solid #4c8dff; background: #08131f; cursor: grab; flex: 0 0 auto; }
.puxador-stive img { width: 100%; height: 100%; object-fit: cover; object-position: center 18%; display: block; }
.puxador-stive.falando { animation: pisca-stive 1.15s ease; }
@keyframes pisca-stive {
  0%, 100% { opacity: 1; filter: brightness(1); }
  12%, 45%, 78% { opacity: .2; filter: brightness(1.35); }
  28%, 61%, 92% { opacity: 1; filter: brightness(1); }
}
.nome-balao-stive { display: block; margin-top: 6px; color: #f4f7fb; font-size: 13px; font-weight: 650; text-align: center; max-width: 140px; line-height: 1.25; text-shadow: 0 1px 8px #041018; }
.balao-stive.fechado form { display: none; }
.balao-stive form { width: 100%; background: var(--vidro); border: 1px solid var(--linha); border-radius: 18px; padding: 14px; box-shadow: 0 18px 40px rgba(0,0,0,.35); }
.chat-balao { max-height: 260px; overflow: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 8px; }
.fala-hq { position: absolute; right: calc(100% + 8px); bottom: 72px; width: min(280px, 62vw); background: #fff; color: #141820; border-radius: 22px; padding: 12px 14px 14px; line-height: 1.35; font-size: 14px; font-weight: 550; box-shadow: 0 14px 32px rgba(0,0,0,.35); z-index: 2; animation: sobe .55s ease; }
.fala-hq::after { content: ""; position: absolute; right: -12px; bottom: 28px; width: 0; height: 0; border: 12px solid transparent; border-left-color: #fff; border-right: 0; }
.fala-hq strong { display: block; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; color: #4c6fff; margin-bottom: 4px; }
.fala-hq .pendencia { margin-top: 10px; }
.fala-hq .pendencia button { background: #edf2ff; color: #141820; border: 1px solid #c9d6ff; }
.fala-hq.pergunta { border: 2px solid #4c8dff; }
.fala-hq.risco { border: 2px solid #ff5c7a; }
.fala-hq.info { border: 2px solid #3ddc97; }
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
    texto = "".join(caractere if caractere.isalnum() else "-" for caractere in str(nome or ""))
    return texto.strip("-").lower() or "camera"


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

    def abrir_sessao(self, cabecalho: str):
        return acesso.ler_cookie(_cookie(cabecalho), self.senha)

    def iniciar(self):
        tratador = _tratador(self)
        self._httpd = ThreadingHTTPServer((self.host, self.porta), tratador)
        self._httpd.daemon_threads = True
        threading.Thread(target=self._httpd.serve_forever, name="acesso-remoto", daemon=True).start()

    def parar(self):
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
    return f"{COOKIE}={token}; HttpOnly; Path=/; SameSite=Lax; Max-Age=2592000"


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
}


def _menu(ativo: str, perfil: str = "") -> str:
    itens = [
        ("/", "Início", "inicio"),
        ("/painel/1", "Contagens", "contagem"),
        ("/painel/2", "Comportamento", "pessoa"),
        ("/painel/3", "Alertas de RF e LPR", "alerta"),
        ("/painel/4", "Mapas", "mapa"),
        ("/painel/risco", "Detector de risco", "alerta"),
        ("/painel/audio", "Áudio e transcrição", "audio"),
        ("/painel/cameras", "Ao vivo", "camera"),
        ("/painel/stive", "Agente Stive", "stive"),
        ("/gestao", "Gestão de ativos", "cliente"),
        ("/cadastro/cliente", "Cliente", "cliente"),
        ("/cadastro/cameras", "Câmeras", "camera"),
        ("/cadastro/pessoas", "Pessoas", "pessoa"),
        ("/cadastro/avisos", "Avisos", "aviso"),
        ("/conta", "Conta", "conta"),
        ("/sair", "Sair", "sair"),
    ]
    partes = ["<p class='grupo'>Navegação</p><nav>"]
    for href, titulo, icone in itens:
        if href == "/gestao" and perfil != "administrador":
            continue
        if href == "/gestao" or (href == "/cadastro/cliente" and perfil != "administrador"):
            partes.append("<p class='grupo'>Conta</p>")
        classe = " class='ativo'" if href == ativo else ""
        selos = {
            "/painel/stive": "<i id='selo-stive' class='selo' hidden></i>",
            "/painel/3": "<i id='selo-alertas' class='selo' hidden></i>",
            "/painel/risco": "<i id='selo-risco' class='selo' hidden></i>",
            "/painel/audio": "<i id='selo-audio' class='selo' hidden></i>",
        }
        selo = selos.get(href, "")
        partes.append(
            f"<a href='{href}'{classe}>{_svg(_ICONES[icone])}<span>{titulo}</span>{selo}</a>"
        )
    partes.append("</nav>")
    return "".join(partes)


def _moldura(titulo: str, miolo: str, ativo: str, parede: bool = False, perfil: str = "", csrf: str = "") -> str:
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
            "<img alt='Stive' src='/agente/stive.png'></button>"
            "<span class='nome-balao-stive'>Fale com o Agente Stive</span>"
            "</div></div>"
        )
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_seguro(titulo)}</title>
<style>{ESTILO}</style>
</head>
<body>
<div class="app">
<aside>
<div class="marca"><span class="logo">C</span><div><strong>C4ISTAR</strong><small>Monitor</small></div></div>
{_menu(ativo, perfil)}
</aside>
<section class="palco{classe}">{miolo}</section>
</div>
<div id="led" class="led branco" title="Risco"></div>
{balao}
<script src="/painel.js"></script>
</body>
</html>"""


def _cabeca(titulo: str, texto: str) -> str:
    return (
        f"<header class='topo'><div><h1>{_html_seguro(titulo)}</h1>"
        f"<p>{texto}</p></div></header>"
    )


def _inicio(sessao: dict) -> str:
    miolo = _cabeca(
        "Dashboard",
        f"{_html_seguro(sessao.get('email') or '')} · {_html_seguro(_documento_visivel(sessao.get('documento') or ''))}",
    ) + "<main id='tela' data-tela='inicio'></main>"
    return _moldura("C4ISTAR MONITOR", miolo, "/", perfil=sessao.get("perfil") or "", csrf=sessao.get("csrf") or "")


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


def _painel(numero: str, titulo: str, chave: str, mapas: bool, perfil: str = "", csrf: str = "") -> str:
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
    return _moldura(f"C4ISTAR MONITOR · {titulo}", miolo, f"/painel/{numero}", perfil=perfil, csrf=csrf)


def _risco(perfil: str = "", csrf: str = "") -> str:
    miolo = _cabeca("Detector de risco", "Panorama do fluxo, do comportamento e de quem reaparece.") + "<main id='tela' data-tela='risco'></main>"
    return _moldura("C4ISTAR MONITOR · Detector de risco", miolo, "/painel/risco", perfil=perfil, csrf=csrf)


def _audio(perfil: str = "", csrf: str = "") -> str:
    miolo = (
        _cabeca(
            "Áudio e transcrição",
            "Esteira de falas por câmera, nuvem de palavras e ranking de risco sonoro.",
        )
        + "<main id='tela' data-tela='audio'></main>"
    )
    return _moldura("C4ISTAR MONITOR · Áudio e transcrição", miolo, "/painel/audio", perfil=perfil, csrf=csrf)


def _ao_vivo(cameras, perfil: str = "", csrf: str = "") -> str:
    blocos = []
    for slug, nome, rua in cameras:
        legenda = _html_seguro(f"{nome} {rua}".strip())
        blocos.append(
            f"<figure class='video' data-camera='{_html_seguro(nome)}'>"
            f"<figcaption>{_svg(_ICONES['camera'])}{legenda}</figcaption>"
            f"<img alt='{legenda}' src='/video/camera-{_html_seguro(slug)}'>"
            f"<div class='placar-camera'></div></figure>"
        )
    grade = "".join(blocos) or "<p>Nenhuma câmera com imagem agora.</p>"
    miolo = _cabeca("Ao vivo", "O placar mostra a cena agora e o acumulado de cada câmera.") + f"<main data-tela='vivo'><section class='grade'>{grade}</section></main>"
    return _moldura("C4ISTAR MONITOR · Ao vivo", miolo, "/painel/cameras", perfil=perfil, csrf=csrf)


def _stive(sessao: dict) -> str:
    script = """
<script>
const chat = document.getElementById("chat-stive");
const quadro = document.getElementById("quadro-stive");
const form = document.getElementById("form-stive");
function bolha(papel, texto) {
  const p = document.createElement("p");
  p.className = "bolha " + papel;
  p.textContent = texto;
  chat.appendChild(p);
  chat.scrollTop = chat.scrollHeight;
}
function desenharVisual(visual) {
  if (!quadro) return;
  const itens = (visual && visual.itens) || [];
  const titulo = (visual && visual.titulo) || "Quadro do Stive";
  const tipo = (visual && visual.tipo) || "texto";
  if ((tipo === "barras" || tipo === "linha" || tipo === "rosca") && itens.length) {
    quadro.innerHTML = "<h2></h2><canvas class='grafico' id='grafico-stive' width='640' height='280'></canvas>";
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
    return;
  }
  quadro.innerHTML = "<h2>" + titulo.replace(/[&<>]/g, "") + "</h2>" + (itens.map((item) =>
    "<div class='linha-face'><span>" + String(item.rotulo || "") + "</span><strong>" + String(item.total ?? "") + "</strong></div>"
  ).join("") || "<p>O quadro acompanha o que você pedir na conversa.</p>");
}
window.addEventListener("load", () => {
  try {
    const salvo = sessionStorage.getItem("stive-visual");
    if (salvo) desenharVisual(JSON.parse(salvo));
  } catch (erro) {}
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
});
window.atualizarStive = (dados) => {
  const caixa = document.getElementById("pendencias-stive");
  if (!caixa) return;
  const lista = dados.pendencias || [];
  const chave = lista.map((item) => item.id).join("|");
  if (caixa.dataset.chave === chave) return;
  caixa.dataset.chave = chave;
  caixa.innerHTML = lista.map((item) => `<div class="pendencia"><p>${item.texto}</p>
    <span><button type="button" data-id="${item.id}" data-resp="sim" data-tipo="${item.tipo}" data-camera="${item.camera}">Sim</button>
    <button type="button" data-id="${item.id}" data-resp="nao" data-tipo="${item.tipo}" data-camera="${item.camera}">Não</button></span></div>`).join("");
};
document.getElementById("pendencias-stive").addEventListener("click", async (evento) => {
  const botao = evento.target.closest("button");
  if (!botao) return;
  const corpo = new URLSearchParams(new FormData(form));
  corpo.set("id", botao.dataset.id || "");
  corpo.set("resposta", botao.dataset.resp || "");
  corpo.set("tipo", botao.dataset.tipo || "");
  corpo.set("camera", botao.dataset.camera || "");
  corpo.set("texto", botao.parentElement.parentElement.querySelector("p").textContent);
  const resposta = await fetch("/agente/stive/confirmar", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: corpo });
  const dados = await resposta.json().catch(() => ({}));
  bolha("stive", dados.fala || "Confirmação registrada.");
  botao.parentElement.parentElement.remove();
});
</script>
"""
    miolo = f"""<main>
<div class="stive-pagina">
<section class="stive-topo">
<article class="cartao">
<div class="stage-stive" id="grupo-stive">
<div id="fala-hq" class="fala-hq" hidden></div>
<img class="avatar-stive" id="abrir-stive" alt="Stive" src="/agente/stive.png" onerror="this.replaceWith(Object.assign(document.createElement('div'),{{className:'avatar-stive',textContent:'S'}}))">
</div>
<h2>Stive</h2>
<p>Agente de segurança. Pergunte sobre as informações do seu ambiente ou informe uma ocorrência.</p>
<div id="pendencias-stive"></div>
</article>
<article class="cartao quadro-stive" id="quadro-stive"><h2>Quadro do Stive</h2><p>O que você pedir na conversa aparece aqui.</p></article>
</section>
<section class="stive-chat-area cartao">
<div class="chat" id="chat-stive"><p class="bolha stive">Posso cruzar pessoa, horário e local como analista criminal. Pergunte a chance de invasão, padrões de madrugada, ou me conte uma ocorrência.</p></div>
<form id="form-stive">
{_csrf(sessao)}
<label>Mensagem<input name="pergunta" autocomplete="off" placeholder="Fale com o Stive"></label>
<button type="submit">Enviar</button>
</form>
</section>
</div>
</main>
{script}"""
    return _moldura("Agente Stive · C4ISTAR MONITOR", miolo, "/painel/stive", perfil=sessao.get("perfil") or "", csrf=sessao.get("csrf") or "")


def _sem_analise(perfil: str = "", csrf: str = "") -> str:
    miolo = """<header class="topo"><div><h1>Painéis</h1>
<p>As câmeras em análise nesta máquina pertencem a outro CPF. O seu cadastro continua disponível.</p></div></header>"""
    return _moldura("C4ISTAR MONITOR", miolo, "/", perfil=perfil, csrf=csrf)


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
<p>Cada foto nova recebe o próprio código. Corrigir um código troca só a foto daquela pessoa.</p></div></header>
<main>
{grade}
{_aviso_html(aviso, ok)}
<form method="post" action="/cadastro/pessoas" enctype="multipart/form-data">
{_csrf(sessao)}
{_campo("Nome", "nome", obrigatorio=True)}
<label>Tipo<select name="base_legal" id="classe" required>{''.join(classes)}</select></label>
<label>Motivo<select name="motivo" id="motivo">{''.join(motivos)}</select></label>
{_campo("Referência", "referencia")}
<label>Código existente<select name="face_id">{''.join(corrigir)}</select></label>
<label>Foto do rosto<input type="file" name="foto" accept="image/*" required></label>
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
</script>
</main>"""
    return _moldura("Pessoas · C4ISTAR MONITOR", miolo, "/cadastro/pessoas", perfil=sessao.get("perfil") or "", csrf=sessao.get("csrf") or "")


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
    miolo = f"""<main>
<h1>Cliente</h1>
<p>Estes dados são da conta do CPF ou CNPJ com o qual você entrou.</p>
{_aviso_html(aviso, ok)}
<form method="post" action="/cadastro/cliente">
{_csrf(sessao)}
{_campo("Nome", "nome", cliente.get("nome") or "")}
{_campo("RG", "rg", cliente.get("rg") or "")}
{_campo("CPF ou CNPJ", "documento", _documento_visivel(cliente.get("documento") or sessao.get("documento") or ""), obrigatorio=True)}
{_campo("E-mail da conta", "email", cliente.get("email") or "", tipo="email")}
<button type="submit">{_svg(_ICONES["mais"])}Salvar cliente</button>
</form>
{novo}
</main>"""
    return _moldura("Cliente · C4ISTAR MONITOR", miolo, "/cadastro/cliente", perfil=sessao.get("perfil") or "", csrf=sessao.get("csrf") or "")


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
            "<td>"
            f"<form method='post' action='/gestao/{acao}'>{_csrf(sessao)}"
            f"<input type='hidden' name='documento' value='{documento}'>"
            f"<button type='submit'>{acao.capitalize()}</button></form>"
            f"<form method='post' action='/gestao/excluir'>{_csrf(sessao)}"
            f"<input type='hidden' name='documento' value='{documento}'>"
            "<button type='submit'>Excluir</button></form>"
            "</td></tr>"
        )
    tabela = (
        "<table><tr><th>Cliente</th><th>Documento</th><th>E-mail</th><th>Câmeras</th><th></th><th></th></tr>"
        + "".join(linhas) + "</table>"
    ) if linhas else "<p>Nenhum cliente cadastrado.</p>"
    miolo = f"""<main>
<h1>Gestão de ativos</h1>
<p>Visão de todas as contas. A análise desta máquina continua na conta do administrador.</p>
{_aviso_html(aviso, ok)}
<section class="cartoes">{cards}</section>
{tabela}
</main>"""
    return _moldura("Gestão de ativos · C4ISTAR MONITOR", miolo, "/gestao", perfil="administrador", csrf=sessao.get("csrf") or "")


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
{tabela}
<h2>{'Editar câmera' if ident else 'Nova câmera'}</h2>
{_aviso_html(aviso, ok)}
{acesso_gravado}
<form method="post" action="/cadastro/cameras">
{_csrf(sessao)}
<input type="hidden" name="id_anterior" value="{_html_seguro(ident)}">
{_campo("Identificador", "id", ident)}
{_campo("Nome", "nome", atual.get("nome") or "", obrigatorio=True)}
{_campo("Marca", "marca", atual.get("marca") or "Intelbras")}
{_campo("Modelo", "modelo", atual.get("modelo") or "", obrigatorio=True)}
{_check("ativa", "Câmera ativa", atual.get("ativa", True))}
{_campo("Host", "host", atual.get("host") or "")}
{_campo("Porta", "porta", _valor_campo(atual, "porta", 554))}
{_campo("Usuário", "usuario", atual.get("usuario") or "")}
{_campo("Senha", "senha", tipo="password")}
{_campo("Canal", "canal", _valor_campo(atual, "canal", 1))}
{_campo("Subtype", "subtype", _valor_campo(atual, "subtype", 0))}
{_campo("Rua", "rua", atual.get("rua") or "")}
{_campo("Bairro", "bairro", atual.get("bairro") or "")}
{_campo("Cidade", "cidade", atual.get("cidade") or "")}
{_campo("Latitude", "latitude", atual.get("latitude") if atual.get("latitude") != "" else "")}
{_campo("Longitude", "longitude", atual.get("longitude") if atual.get("longitude") != "" else "")}
<button type="submit">{_svg(_ICONES["mais"])}Salvar câmera</button>
</form>
</main>"""
    return _moldura("Câmeras · C4ISTAR MONITOR", miolo, "/cadastro/cameras", perfil=sessao.get("perfil") or "", csrf=sessao.get("csrf") or "")


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
    return _moldura("Avisos · C4ISTAR MONITOR", miolo, "/cadastro/avisos", perfil=sessao.get("perfil") or "", csrf=sessao.get("csrf") or "")


def _form_conta(sessao: dict, aviso: str = "", ok: bool = False) -> str:
    usuarios = acesso.da_conta(sessao.get("documento") or "")
    linhas = "".join(
        f"<tr><td>{_html_seguro(item.get('nome'))}</td><td>{_html_seguro(item.get('email'))}</td></tr>"
        for item in usuarios
    )
    miolo = f"""<main>
<h1>Conta</h1>
<p>Usuários deste CPF/CNPJ {_html_seguro(_documento_visivel(sessao.get("documento") or ""))}.</p>
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
    return _moldura("Conta · C4ISTAR MONITOR", miolo, "/conta", perfil=sessao.get("perfil") or "", csrf=sessao.get("csrf") or "")


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
    caminho = Path("historico_faces.csv")
    if not caminho.exists() or not nomes:
        return []
    try:
        locais = {str(item.get("nome") or "").strip().lower(): item for item in cadastro.locais_cameras()}
    except Exception:
        locais = {}
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


def _dados_json(portal) -> dict:
    from identidade import contar_passagens_faces

    linhas = contar_passagens_faces(100000)
    nomes = {}
    classes = {}
    try:
        interesse = cadastro.interesse_ativo() or {}
    except Exception:
        interesse = {}
    for pessoa in interesse.get("pessoas") or []:
        ident = str(pessoa.get("face_id") or "").upper()
        if not ident:
            continue
        nomes[ident] = str(pessoa.get("nome") or "")
        classes[ident] = cadastro.classe_pessoa(pessoa)
    linhas = [(ident, total) for ident, total in linhas if ident in nomes]
    contagem = {ident: total for ident, total in linhas}
    resumo = dict(portal.resumo())
    match = resumo.get("match")
    if isinstance(match, dict):
        match = dict(match)
        match["passagens"] = int(contagem.get(str(match.get("id") or "").upper(), 0))
        resumo["match"] = match
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
        ],
        "pessoas_interesse": pessoas,
        "rastros_rf": _rastros_rf_lpr(nomes),
    })
    return resumo


def _tratador(portal: Portal):
    class Tratador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, formato, *args):
            return

        def do_GET(self):
            caminho, consulta = _caminho(self.path)
            if caminho == "/entrar":
                self._html(_pagina_senha(), 200)
                return
            if caminho == "/criar":
                self._html(_pagina_criar(), 200)
                return
            if caminho == "/sair":
                self._html(_pagina_senha(), 200, f"{COOKIE}=; HttpOnly; Path=/; Max-Age=0")
                return
            sessao = portal.abrir_sessao(self.headers.get("Cookie"))
            if sessao is None:
                self._html(_pagina_senha(), 200)
                return
            self._pagina_autenticada(caminho, consulta, sessao)

        def do_POST(self):
            caminho, _consulta = _caminho(self.path)
            if caminho == "/cadastro/pessoas":
                sessao = portal.abrir_sessao(self.headers.get("Cookie"))
                if sessao is None:
                    self._html(_pagina_senha(), 200)
                    return
                self._salvar_pessoa(sessao)
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
            sessao = portal.abrir_sessao(self.headers.get("Cookie"))
            if sessao is None:
                self._html(_pagina_senha(), 200)
                return
            if caminho != "/comando" and not _csrf_confere(sessao, campos):
                self._html(_moldura("C4ISTAR MONITOR", "<main><p class='aviso'>Atualize a página e tente de novo.</p></main>", "/"), 403)
                return
            if caminho == "/comando":
                if cadastro.pode_ver_analise(sessao.get("documento") or ""):
                    portal.ajustar_mapa(_um(campos, "periodo"), _um(campos, "desenho"))
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if caminho == "/cadastro/cliente":
                self._salvar_cliente(sessao, campos)
                return
            if caminho == "/cadastro/cliente/novo":
                self._criar_cliente(sessao, campos)
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
            if caminho == "/cadastro/avisos":
                self._salvar_aviso(sessao, campos)
                return
            if caminho == "/cadastro/avisos/remover":
                self._remover_aviso(sessao, campos)
                return
            if caminho == "/cadastro/pessoas/remover":
                self._remover_pessoa(sessao, campos)
                return
            if caminho == "/conta/senha":
                self._trocar_senha(sessao, campos)
                return
            if caminho == "/conta/usuario":
                self._criar_usuario(sessao, campos)
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

        def _pagina_autenticada(self, caminho: str, consulta: dict, sessao: dict):
            documento = sessao.get("documento") or ""
            perfil = sessao.get("perfil") or ""
            if sessao.get("trocar_no_acesso") and caminho not in ("/conta", "/sair") and not caminho.startswith("/conta"):
                self._html(_form_conta(sessao, "No primeiro acesso, troque a senha enviada por e-mail."), 200)
                return
            ver = cadastro.pode_ver_analise(documento)
            if caminho == "/agente/stive.png":
                self._avatar_stive()
                return
            if caminho == "/painel.js":
                self._bytes(Path("painel_web.js").read_bytes(), "text/javascript; charset=utf-8")
                return
            if caminho == "/":
                self._html(_inicio(sessao), 200)
                return
            if caminho.startswith("/painel/"):
                if not ver:
                    self._html(_sem_analise(perfil, sessao.get("csrf") or ""), 200)
                    return
                numero = caminho.removeprefix("/painel/")
                if numero == "cameras":
                    self._html(_ao_vivo(portal.cameras(), perfil, sessao.get("csrf") or ""), 200)
                    return
                if numero == "risco":
                    self._html(_risco(perfil, sessao.get("csrf") or ""), 200)
                    return
                if numero == "audio":
                    self._html(_audio(perfil, sessao.get("csrf") or ""), 200)
                    return
                if numero == "stive":
                    self._html(_stive(sessao), 200)
                    return
                for item, chave, titulo in PAINEIS:
                    if item == numero:
                        self._html(_painel(item, titulo, chave, mapas=item == "4", perfil=perfil, csrf=sessao.get("csrf") or ""), 200)
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
            if caminho == "/dados.json":
                if not ver:
                    self.send_error(404)
                    return
                self._json(_dados_json(portal))
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
            try:
                if portal._faces is None:
                    raise ValueError("O monitoramento de faces ainda não está pronto.")
                face_id = _um(campos, "face_id").upper()
                if face_id:
                    portal._faces.substituir_foto(face_id, imagem)
                else:
                    face_id, _nova = portal._faces.inscrever_foto(imagem)
                cadastro.cadastrar_pessoa(documento, {
                    "face_id": face_id,
                    "nome": _um(campos, "nome"),
                    "classe": _um(campos, "base_legal"),
                    "base_legal": _um(campos, "base_legal"),
                    "referencia": _um(campos, "referencia"),
                    "motivo": _um(campos, "motivo"),
                })
            except ValueError as exc:
                self._html(_form_pessoas(sessao, _pessoas_da_conta(documento), str(exc)), 400)
                return
            self._redirecionar("/cadastro/pessoas?ok=salvo")

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

        def _json(self, corpo: dict):
            dados = json.dumps(corpo).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(dados)

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

        def _salvar_cliente(self, sessao: dict, campos: dict):
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
            cookie = ""
            if cliente.get("documento") != sessao.get("documento"):
                usuario = {
                    "email": sessao.get("email"),
                    "documento": cliente.get("documento"),
                    "marca": sessao.get("marca"),
                }
                cookie = _cabecalho_cookie(acesso.emitir_cookie(usuario, portal.senha))
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

            try:
                saida = responder(sessao.get("documento") or "", _um(campos, "pergunta"), portal.resumo())
            except ValueError as exc:
                self._json({"fala": str(exc), "visual": {}})
                return
            except Exception:
                self._json({"fala": "A base respondeu com erro. Tente de novo em instantes.", "visual": {}})
                return
            self._json({"fala": saida.get("fala") or "", "visual": saida.get("visual") or {}})

        def _confirmar_stive(self, sessao: dict, campos: dict):
            from agente.stive import confirmar

            try:
                fala = confirmar(
                    sessao.get("documento") or "",
                    _um(campos, "id"),
                    _um(campos, "resposta"),
                    _um(campos, "texto"),
                    _um(campos, "camera"),
                    _um(campos, "tipo"),
                )
            except ValueError as exc:
                self._json({"fala": str(exc)})
                return
            self._json({"fala": fala})

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
    }
    return textos.get(codigo, ""), bool(codigo in textos)


def _cameras_ou_vazio(documento: str) -> list[dict]:
    try:
        return cadastro.cameras_publicas(documento)
    except ValueError:
        return []
