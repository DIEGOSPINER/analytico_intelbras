"""Mapa Folium dos painéis. O navegador recebe a folha pronta e só atualiza os pontos."""

from __future__ import annotations

import folium
from folium.plugins import HeatMap

_HTML = ""  # reinicia ao recarregar o módulo após mudanças no script

_SCRIPT = """
<script>
const mapaFolium = {nome};
let grupoFolium = L.layerGroup().addTo(mapaFolium);
let calorFolium = null;
let ajustouFolium = false;
let estadoFolium = null;
mapaFolium.eachLayer((camada) => {{
  if (camada._heat) mapaFolium.removeLayer(camada);
}});
function rotuloQuandoFolium(quando) {{
  const texto = String(quando || "").trim();
  const achado = texto.match(/(\\d{{4}})-(\\d{{2}})-(\\d{{2}})[ T](\\d{{2}}):(\\d{{2}})/);
  if (achado) return achado[3] + "/" + achado[2] + " " + achado[4] + ":" + achado[5];
  return texto.slice(0, 16);
}}
function setaFolium(a, b, cor) {{
  const meio = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  const angulo = Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
  const icone = L.divIcon({{
    className: "seta-rf",
    html: `<div style="width:18px;height:18px;display:grid;place-items:center;transform:rotate(${{angulo}}deg)"><div style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:14px solid ${{cor || "#4c8dff"}};filter:drop-shadow(0 1px 2px rgba(0,0,0,.35))"></div></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  }});
  L.marker(meio, {{ icon: icone, interactive: false }}).addTo(grupoFolium);
}}
function setasRotaFolium(latlngs, cor) {{
  if (!latlngs || latlngs.length < 2) return;
  const passo = Math.max(1, Math.floor((latlngs.length - 1) / 8));
  for (let i = 0; i < latlngs.length - 1; i += passo) {{
    setaFolium(latlngs[i], latlngs[Math.min(i + 1, latlngs.length - 1)], cor);
  }}
  if ((latlngs.length - 2) % passo !== 0) {{
    setaFolium(latlngs[latlngs.length - 2], latlngs[latlngs.length - 1], cor);
  }}
}}
function desenharRastroRf(pontos, trilhas) {{
  const porPessoa = {{}};
  const mapaTrilha = {{}};
  (trilhas || []).forEach((item) => {{
    const chave = String(item.id || "");
    const caminho = (item.caminho || []).map((par) => [Number(par[0]), Number(par[1])]).filter((par) => Number.isFinite(par[0]) && Number.isFinite(par[1]));
    if (chave && caminho.length) mapaTrilha[chave] = {{ caminho, cor: item.cor }};
  }});
  pontos.forEach((ponto) => {{
    const chave = String(ponto.id || ponto.nome || "pessoa");
    (porPessoa[chave] = porPessoa[chave] || []).push(ponto);
  }});
  Object.entries(porPessoa).forEach(([chave, lista]) => {{
    lista.sort((a, b) => String(a.quando || "").localeCompare(String(b.quando || "")));
    const trilha = mapaTrilha[chave];
    const cor = (trilha && trilha.cor) || lista[0].cor || "#4c8dff";
    const latlngs = (trilha && trilha.caminho && trilha.caminho.length >= 2)
      ? trilha.caminho
      : lista.map((ponto) => [ponto.lat, ponto.lon]);
    if (latlngs.length >= 2) {{
      L.polyline(latlngs, {{ color: cor, weight: 5, opacity: 0.9 }}).addTo(grupoFolium);
      setasRotaFolium(latlngs, cor);
    }}
    lista.forEach((ponto, indice) => {{
      const foto = String(ponto.foto || "").replace(/"/g, "");
      const nome = String(ponto.nome || ponto.id || "").replace(/</g, "");
      const quando = rotuloQuandoFolium(ponto.quando);
      const camera = String(ponto.camera || "").replace(/</g, "");
      const icone = L.divIcon({{
        className: "marcador-rf",
        html: `<div style="display:flex;flex-direction:column;align-items:center;gap:4px">
          <div style="width:46px;height:46px;border-radius:50%;overflow:hidden;border:3px solid #fff;box-shadow:0 4px 14px rgba(0,0,0,.35);background:#101624"><img alt="" src="${{foto}}" style="width:100%;height:100%;object-fit:cover"></div>
          <span style="padding:3px 7px;border-radius:8px;background:#fff;color:#141820;font:700 11px Segoe UI,sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.28);white-space:nowrap">${{quando || (indice + 1)}}</span>
        </div>`,
        iconSize: [120, 72],
        iconAnchor: [60, 28],
      }});
      const marca = L.marker([ponto.lat, ponto.lon], {{ icon: icone }});
      const texto = [nome, camera, quando].filter(Boolean).join(" · ");
      if (texto) marca.bindTooltip(texto, {{ direction: "top" }});
      marca.addTo(grupoFolium);
    }});
  }});
}}
function desenharFolium(mensagem) {{
  estadoFolium = mensagem;
  grupoFolium.clearLayers();
  if (calorFolium) {{
    mapaFolium.removeLayer(calorFolium);
    calorFolium = null;
  }}
  const pontos = (mensagem.pontos || []).map((ponto) => ({{
    ...ponto,
    lat: Number(ponto.lat),
    lon: Number(ponto.lon),
  }})).filter((ponto) => Number.isFinite(ponto.lat) && Number.isFinite(ponto.lon) && Math.abs(ponto.lat) <= 90 && Math.abs(ponto.lon) <= 180);
  if (!pontos.length) return;
  const desenho = mensagem.desenho || "pontos";
  if (desenho === "calor" || desenho === "mancha") {{
    calorFolium = L.heatLayer(pontos.map((ponto) => [ponto.lat, ponto.lon, desenho === "mancha" ? 0.9 : 0.55]), {{
      radius: desenho === "mancha" ? 46 : 28,
      blur: 22,
      minOpacity: 0.25,
    }}).addTo(mapaFolium);
  }}
  if (desenho === "rf" || desenho === "fotos") {{
    desenharRastroRf(pontos, mensagem.trilhas || []);
  }} else if (desenho === "pontos" || mensagem.fixo) {{
    const maior = Math.max(1, ...pontos.map((ponto) => Number(ponto.valor) || 0));
    pontos.forEach((ponto) => {{
      const raio = mensagem.fixo ? 8 : 7 + Math.sqrt((Number(ponto.valor) || 0) / maior) * 18;
      const marca = L.circleMarker([ponto.lat, ponto.lon], {{
        radius: raio,
        color: ponto.risco === "preto" ? "#ff3b3b" : (ponto.cor || "#4c8dff"),
        weight: ponto.risco === "preto" ? 3 : 1,
        fillColor: ponto.cor || "#4c8dff",
        fillOpacity: 0.88,
      }});
      const texto = mensagem.fixo ? (ponto.nome || "") : [ponto.nome || "", ponto.valor || ""].filter(Boolean).join(" · ");
      if (texto && mensagem.rotulos) marca.bindTooltip(texto, {{permanent: true, direction: "right", opacity: 0.9}});
      else if (texto) marca.bindTooltip(texto, {{direction: "top"}});
      marca.addTo(grupoFolium);
    }});
  }}
  const limites = pontos.map((ponto) => [ponto.lat, ponto.lon]);
  (mensagem.trilhas || []).forEach((item) => {{
    (item.caminho || []).forEach((par) => {{
      const lat = Number(par[0]);
      const lon = Number(par[1]);
      if (Number.isFinite(lat) && Number.isFinite(lon)) limites.push([lat, lon]);
    }});
  }});
  const chave = pontos.map((ponto) => ponto.lat + "," + ponto.lon + "," + (ponto.id || "") + "," + (ponto.quando || "")).join("|")
    + "|" + (mensagem.trilhas || []).map((item) => (item.caminho || []).length).join(",");
  if (!ajustouFolium || mapaFolium._ultimaChave !== chave) {{
    mapaFolium.fitBounds(limites, {{padding: [28, 28], maxZoom: 17}});
    mapaFolium._ultimaChave = chave;
    ajustouFolium = true;
  }}
}}
window.addEventListener("message", (evento) => {{
  if (evento.origin !== location.origin) return;
  if (!evento.data || evento.data.tipo !== "mapa") return;
  desenharFolium(evento.data);
}});
window.parent.postMessage({{ tipo: "mapa-pronto" }}, location.origin);
setInterval(() => {{
  if (!estadoFolium || !estadoFolium.pisca) return;
  const aceso = (Date.now() % 900) < 560;
  grupoFolium.eachLayer((camada) => {{
    if (camada.setStyle) camada.setStyle({{fillOpacity: aceso ? 0.9 : 0.22, opacity: aceso ? 1 : 0.35}});
  }});
}}, 180);
</script>
"""


def html_folha() -> str:
    global _HTML
    if _HTML:
        return _HTML
    mapa = folium.Map(
        location=[-15.78, -47.93],
        zoom_start=4,
        tiles="OpenStreetMap",
        control_scale=True,
        zoom_control=True,
    )
    HeatMap([[-15.78, -47.93, 0.01]], radius=1, blur=1, min_opacity=0).add_to(mapa)
    pagina = mapa.get_root().render()
    script = _SCRIPT.format(nome=mapa.get_name())
    _HTML = pagina.replace("</html>", script + "\n</html>") if "</html>" in pagina else pagina + script
    return _HTML
