"""Acesso pelo navegador. O túnel leva estas páginas para fora de casa.

A análise continua junto das câmeras. Cada usuário entra com o próprio
e-mail e só vê a conta do seu CPF ou CNPJ. As telas de painel são uma
página leve: o quadro já publicado troca no lugar, e recarregar volta na hora.
"""

from __future__ import annotations

import hmac
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
body { margin:0; background:#0c0c0c; color:#ebebeb; font-family:Segoe UI,sans-serif; }
nav { display:flex; flex-wrap:wrap; gap:8px; padding:10px 12px; background:#101018; position:sticky; top:0; z-index:2; }
nav a { color:#ebebeb; text-decoration:none; border:1px solid #30305c; padding:8px 12px; background:#161616; }
nav a.ativo { background:#148ce8; border-color:#148ce8; }
body.parede { height:100vh; display:flex; flex-direction:column; overflow:hidden; }
body.parede .tela { flex:1; min-height:0; background:#000; }
body.parede img { width:100%; height:100%; object-fit:contain; display:block; background:#000; }
main { padding:16px 20px 48px; max-width:960px; }
h1 { font-size:22px; font-weight:500; }
label { display:block; margin:12px 0; }
input, select { width:100%; box-sizing:border-box; margin-top:4px; padding:10px; background:#161616; color:#ebebeb; border:1px solid #30305c; }
button { background:#148ce8; color:#fff; border:0; padding:10px 16px; cursor:pointer; }
.aviso { color:#ffb000; }
.ok { color:#7dffa0; }
.grade { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.atalho { display:flex; align-items:center; justify-content:center; min-height:140px; font-size:20px; background:#121212; border:1px solid #30305c; color:#ebebeb; text-decoration:none; }
table { width:100%; border-collapse:collapse; margin:12px 0 24px; }
td, th { text-align:left; padding:8px; border-bottom:1px solid #30305c; vertical-align:top; }
.check { width:auto; margin-right:8px; }
.comandos { margin:8px 12px; }
.comandos button { background:#161616; color:#ebebeb; border:1px solid #30305c; margin-right:8px; }
.login { max-width:380px; margin:10vh auto; padding:24px; }
a.texto { color:#5ac4ff; }
@media (max-width:900px) { .grade { grid-template-columns:1fr; } }
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
        self._cameras = []
        self._acervo = None
        self._httpd = None

    def ligar_acervo(self, acervo):
        self._acervo = acervo

    def publicar(self, chave: str, imagem):
        if imagem is None or getattr(imagem, "size", 0) == 0:
            return
        ok, bruto = cv2.imencode(".jpg", imagem, [int(cv2.IMWRITE_JPEG_QUALITY), 68])
        if not ok:
            return
        with self._trava:
            self._imagens[chave] = bruto.tobytes()

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


def _menu(ativo: str) -> str:
    itens = [
        ("/", "Início"),
        ("/painel/1", "Contagens"),
        ("/painel/2", "Comportamento"),
        ("/painel/3", "Alertas de RF e LPR"),
        ("/painel/4", "Mapas"),
        ("/painel/cameras", "Ao vivo"),
        ("/cadastro/cliente", "Cliente"),
        ("/cadastro/cameras", "Câmeras"),
        ("/cadastro/avisos", "Avisos"),
        ("/conta", "Conta"),
        ("/sair", "Sair"),
    ]
    partes = []
    for href, titulo in itens:
        classe = " class='ativo'" if href == ativo else ""
        partes.append(f"<a href='{href}'{classe}>{titulo}</a>")
    return "<nav>" + "".join(partes) + "</nav>"


def _moldura(titulo: str, miolo: str, ativo: str, parede: bool = False) -> str:
    classe = " class='parede'" if parede else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_html_seguro(titulo)}</title>
<style>{ESTILO}</style>
</head>
<body{classe}>
{_menu(ativo)}
{miolo}
</body>
</html>"""


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
<main class="login">
<h1>C4ISTAR MONITOR</h1>
<p>Entre com o e-mail e a senha do seu usuário.</p>
{_aviso_html(aviso)}
<form method="post" action="/entrar">
{_campo("E-mail", "email", tipo="email", obrigatorio=True)}
{_campo("Senha", "senha", tipo="password", obrigatorio=True)}
<button type="submit">Entrar</button>
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
<main class="login">
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
<button type="submit">Criar e entrar</button>
</form>
<p><a class="texto" href="/entrar">Já tenho usuário</a></p>
</main>
</body>
</html>"""


def _inicio(sessao: dict) -> str:
    botoes = []
    for numero, _chave, titulo in PAINEIS:
        botoes.append(f"<a class='atalho' href='/painel/{numero}'>{titulo}</a>")
    botoes.append("<a class='atalho' href='/painel/cameras'>Ao vivo</a>")
    miolo = f"""<main>
<h1>C4ISTAR MONITOR</h1>
<p>{_html_seguro(sessao.get("email") or "")} · CPF/CNPJ {_html_seguro(_documento_visivel(sessao.get("documento") or ""))}</p>
<p>Escolha a tela. Ela permanece no navegador e o quadro troca sozinho, sem recarregar a página.</p>
<section class="grade">{"".join(botoes)}</section>
</main>"""
    return _moldura("C4ISTAR MONITOR", miolo, "/")


def _painel(numero: str, titulo: str, chave: str, mapas: bool) -> str:
    comandos = ""
    if mapas:
        comandos = """<div class="comandos">
<button type="button" data-periodo="dia">Dia</button>
<button type="button" data-periodo="semana">Semana</button>
<button type="button" data-periodo="mes">Mês</button>
<button type="button" data-desenho="pontos">Pontos</button>
<button type="button" data-desenho="calor">Calor</button>
</div>"""
    miolo = f"""{comandos}
<div class="tela"><img id="quadro" alt="{_html_seguro(titulo)}" src="/img/{chave}.jpg"></div>
<script>
const quadro = document.getElementById("quadro");
setInterval(() => {{ quadro.src = "/img/{chave}.jpg?t=" + Date.now(); }}, 5000);
document.querySelectorAll("button[data-periodo],button[data-desenho]").forEach((botao) => {{
  botao.addEventListener("click", () => {{
    const corpo = new URLSearchParams();
    if (botao.dataset.periodo) corpo.set("periodo", botao.dataset.periodo);
    if (botao.dataset.desenho) corpo.set("desenho", botao.dataset.desenho);
    fetch("/comando", {{ method: "POST", body: corpo, headers: {{ "Content-Type": "application/x-www-form-urlencoded" }} }});
  }});
}});
</script>"""
    return _moldura(f"C4ISTAR MONITOR · {titulo}", miolo, f"/painel/{numero}", parede=True)


def _ao_vivo(cameras) -> str:
    blocos = []
    for slug, nome, rua in cameras:
        legenda = _html_seguro(f"{nome} {rua}".strip())
        blocos.append(
            f"<figure><figcaption>{legenda}</figcaption>"
            f"<img alt='{legenda}' src='/img/camera-{_html_seguro(slug)}.jpg'></figure>"
        )
    grade = "".join(blocos) or "<p>Nenhuma câmera com imagem agora.</p>"
    miolo = f"""<main><h1>Ao vivo</h1><section class="grade">{grade}</section></main>
<script>
setInterval(() => {{
  document.querySelectorAll("img[src*='/img/camera-']").forEach((img) => {{
    const base = img.getAttribute("src").split("?")[0];
    img.src = base + "?t=" + Date.now();
  }});
}}, 5000);
</script>"""
    return _moldura("C4ISTAR MONITOR · Ao vivo", miolo, "/painel/cameras")


def _sem_analise() -> str:
    miolo = """<main>
<h1>Painéis</h1>
<p>As câmeras em análise nesta máquina pertencem a outro CPF. O seu cadastro continua disponível.</p>
</main>"""
    return _moldura("C4ISTAR MONITOR", miolo, "/")


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
<button type="submit">Salvar cliente</button>
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
<button type="submit">Salvar câmera</button>
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
                "<button type='submit'>Remover</button></form></td>"
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
<button type="submit">Salvar aviso</button>
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
<button type="submit">Trocar senha</button>
</form>
<h2>Novo usuário desta conta</h2>
<form method="post" action="/conta/usuario">
{_csrf(sessao)}
{_campo("Nome", "nome")}
{_campo("E-mail", "email", tipo="email", obrigatorio=True)}
{_campo("Senha", "senha", tipo="password", obrigatorio=True)}
{_campo("Confirmar senha", "confirmacao", tipo="password", obrigatorio=True)}
<button type="submit">Criar usuário</button>
</form>
</main>"""
    return _moldura("Conta · C4ISTAR MONITOR", miolo, "/conta")


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
            if caminho == "/cadastro/avisos":
                self._html(_form_avisos(sessao, _cameras_ou_vazio(documento), aviso, ok), 200)
                return
            if caminho == "/conta":
                self._html(_form_conta(sessao, aviso, ok), 200)
                return
            self.send_error(404)

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
