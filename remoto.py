"""Acesso pelo navegador. O túnel leva estas páginas para fora de casa.

A análise continua junto das câmeras. Cada usuário entra com o próprio
e-mail e só vê a conta do seu CPF ou CNPJ. As telas de painel são uma
página leve: o quadro já publicado troca no lugar, e recarregar volta na hora.
"""

from __future__ import annotations

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
.app { display: flex; min-height: 100vh; }
aside { width: 248px; flex: none; padding: 22px 16px; background: rgba(10, 14, 28, 0.82);
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
main { padding: 18px 22px 40px; }
.cartoes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 16px; }
.cartao, .painel, .video, figure { background: var(--vidro); border: 1px solid var(--linha); border-radius: 18px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25); backdrop-filter: blur(10px); }
.cartao { padding: 16px 18px; }
.cartao span, figcaption { color: var(--mudo); font-size: 14px; display: flex; align-items: center; gap: 8px; }
.cartao span svg, figcaption svg, button svg { width: 18px; height: 18px; stroke: var(--ciano); fill: none; stroke-width: 1.8; flex: none; }
button svg { stroke: currentColor; width: 16px; height: 16px; }
.cartao strong { display: block; margin-top: 8px; font-size: 32px; font-weight: 650; letter-spacing: -0.03em;
  transition: color 0.3s; }
.cartao strong.sobe { color: var(--verde); }
.grade { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
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
.led { position: fixed; top: 18px; right: 22px; z-index: 30; width: 16px; height: 16px; border-radius: 50%; }
.led.branco { background: #f4f7fb; box-shadow: 0 0 14px #fff; animation: pisca 1.4s infinite; }
.led.amarelo { background: #ffb020; box-shadow: 0 0 14px #ffb020; animation: pisca 0.9s infinite; }
.led.vermelho { background: #ff3b3b; box-shadow: 0 0 16px #ff3b3b; animation: pisca 0.45s infinite; }
.led.preto { background: #05070c; box-shadow: 0 0 0 3px #ff3b3b, 0 0 16px #ff3b3b; animation: pisca 0.28s infinite; }
@keyframes pisca { 50% { opacity: 0.28; } }
.grafico, .mapa { width: 100%; height: 280px; border-radius: 12px; background: #101624; }
main[data-tela="inicio"] .cartao span { font-size: 18px; gap: 12px; }
main[data-tela="inicio"] .cartao span svg { width: 40px; height: 40px; }
main[data-tela="inicio"] .cartao strong { font-size: 40px; }
.grade.tres { grid-template-columns: 1fr 1fr 1fr; }
.empilha { display: grid; grid-template-columns: 148px 1fr 40px; gap: 8px; align-items: center; margin: 10px 0; font-size: 14px; }
.empilha .trilha { display: flex; height: 22px; border-radius: 7px; overflow: hidden; background: rgba(255,255,255,0.06); }
.empilha i { display: grid; place-items: center; font-style: normal; font-size: 12px; color: #041018; overflow: hidden; }
.legenda-linha { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; color: var(--mudo); font-size: 13px; }
.legenda-linha b { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
.tacho { width: min(280px, 100%); margin: 8px auto 0; }
.tacho svg { width: 100%; height: auto; display: block; }
.tacho p, .leitura p { line-height: 1.45; }
.alerta-linha { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center; margin-top: 12px; }
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
@media (max-width: 1100px) {
  aside { width: 84px; } .marca div, nav a span, .grupo { display: none; }
  .cartoes, .coluna, .grade, .grade.tres { grid-template-columns: 1fr; }
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
}


def _menu(ativo: str) -> str:
    itens = [
        ("/", "Início", "inicio"),
        ("/painel/1", "Contagens", "contagem"),
        ("/painel/2", "Comportamento", "pessoa"),
        ("/painel/3", "Alertas de RF e LPR", "alerta"),
        ("/painel/4", "Mapas", "mapa"),
        ("/painel/risco", "Detector de risco", "alerta"),
        ("/painel/cameras", "Ao vivo", "camera"),
        ("/cadastro/cliente", "Cliente", "cliente"),
        ("/cadastro/cameras", "Câmeras", "camera"),
        ("/cadastro/pessoas", "Pessoas", "pessoa"),
        ("/cadastro/avisos", "Avisos", "aviso"),
        ("/conta", "Conta", "conta"),
        ("/sair", "Sair", "sair"),
    ]
    partes = ["<p class='grupo'>Navegação</p><nav>"]
    for href, titulo, icone in itens:
        if href == "/cadastro/cliente":
            partes.append("<p class='grupo'>Conta</p>")
        classe = " class='ativo'" if href == ativo else ""
        partes.append(
            f"<a href='{href}'{classe}>{_svg(_ICONES[icone])}<span>{titulo}</span></a>"
        )
    partes.append("</nav>")
    return "".join(partes)


def _moldura(titulo: str, miolo: str, ativo: str, parede: bool = False) -> str:
    classe = " parede" if parede else ""
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
{_menu(ativo)}
</aside>
<section class="palco{classe}">{miolo}</section>
</div>
<div id="led" class="led branco" title="Risco"></div>
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
    return _moldura("C4ISTAR MONITOR", miolo, "/")


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


def _painel(numero: str, titulo: str, chave: str, mapas: bool) -> str:
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
    return _moldura(f"C4ISTAR MONITOR · {titulo}", miolo, f"/painel/{numero}")


def _risco() -> str:
    miolo = _cabeca("Detector de risco", "Panorama do fluxo, do comportamento e de quem reaparece.") + "<main id='tela' data-tela='risco'></main>"
    return _moldura("C4ISTAR MONITOR · Detector de risco", miolo, "/painel/risco")


def _ao_vivo(cameras) -> str:
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
    return _moldura("C4ISTAR MONITOR · Ao vivo", miolo, "/painel/cameras")


def _sem_analise() -> str:
    miolo = """<header class="topo"><div><h1>Painéis</h1>
<p>As câmeras em análise nesta máquina pertencem a outro CPF. O seu cadastro continua disponível.</p></div></header>"""
    return _moldura("C4ISTAR MONITOR", miolo, "/")


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
            f"{face}.jpg'><figcaption>{_html_seguro(pessoa.get('nome') or face)} · {face}</figcaption></figure>"
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
    return _moldura("Pessoas · C4ISTAR MONITOR", miolo, "/cadastro/pessoas")


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
</main>"""
    return _moldura("Cliente · C4ISTAR MONITOR", miolo, "/cadastro/cliente")


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
            "</tr>"
        )
    tabela = (
        "<table><tr><th>Câmera</th><th>Rua</th><th>Cidade</th><th></th><th></th></tr>"
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
    return _moldura("Câmeras · C4ISTAR MONITOR", miolo, "/cadastro/cameras")


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
    return _moldura("Avisos · C4ISTAR MONITOR", miolo, "/cadastro/avisos")


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
    return _moldura("Conta · C4ISTAR MONITOR", miolo, "/conta")


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
    contagem = {ident: total for ident, total in linhas}
    resumo = dict(portal.resumo())
    match = resumo.get("match")
    if isinstance(match, dict):
        match = dict(match)
        match["passagens"] = int(contagem.get(str(match.get("id") or "").upper(), 0))
        resumo["match"] = match
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
            if caminho == "/cadastro/cameras":
                self._salvar_camera(sessao, campos)
                return
            if caminho == "/cadastro/avisos":
                self._salvar_aviso(sessao, campos)
                return
            if caminho == "/cadastro/avisos/remover":
                self._remover_aviso(sessao, campos)
                return
            if caminho == "/conta/senha":
                self._trocar_senha(sessao, campos)
                return
            if caminho == "/conta/usuario":
                self._criar_usuario(sessao, campos)
                return
            self.send_error(404)

        def _pagina_autenticada(self, caminho: str, consulta: dict, sessao: dict):
            documento = sessao.get("documento") or ""
            ver = cadastro.pode_ver_analise(documento)
            if caminho == "/painel.js":
                self._bytes(Path("painel_web.js").read_bytes(), "text/javascript; charset=utf-8")
                return
            if caminho == "/":
                self._html(_inicio(sessao), 200)
                return
            if caminho.startswith("/painel/"):
                if not ver:
                    self._html(_sem_analise(), 200)
                    return
                numero = caminho.removeprefix("/painel/")
                if numero == "cameras":
                    self._html(_ao_vivo(portal.cameras()), 200)
                    return
                if numero == "risco":
                    self._html(_risco(), 200)
                    return
                for item, chave, titulo in PAINEIS:
                    if item == numero:
                        self._html(_painel(item, titulo, chave, mapas=item == "4"), 200)
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
            self._redirecionar("/", _cabecalho_cookie(acesso.emitir_cookie(usuario, portal.senha)))

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
        "removido": "Aviso removido.",
        "senha": "Senha atualizada. Os outros acessos desta conta precisam entrar de novo.",
        "usuario": "Usuário criado. Ele entra com o e-mail e a senha informados.",
    }
    return textos.get(codigo, ""), bool(codigo in textos)


def _cameras_ou_vazio(documento: str) -> list[dict]:
    try:
        return cadastro.cameras_publicas(documento)
    except ValueError:
        return []
