const SVG = {
  pessoa: "<svg viewBox='0 0 24 24'><circle cx='12' cy='8' r='3'/><path d='M5 19c1.5-3 3.8-4.5 7-4.5S17.5 16 19 19'/></svg>",
  animal: "<svg viewBox='0 0 24 24'><path d='M5 16c.2-3.2 2.4-6 5-6 .8 0 1.4-.6 2.2-1.6.7.3 1.6 1 2.2 1.6 1.4.2 3.6 1.6 3.6 4.2V18H5z'/><path d='M8 9.2 6.5 6M11 9.2 12 6'/></svg>",
  veiculo: "<svg viewBox='0 0 24 24'><path d='M4 15h16v3H4z'/><path d='M6 15 8.2 9h7.6L18 15'/><circle cx='7.5' cy='18.2' r='1.4'/><circle cx='16.5' cy='18.2' r='1.4'/></svg>",
  camera: "<svg viewBox='0 0 24 24'><path d='M4 7h4l2-2h4l2 2h4v12H4z'/><circle cx='12' cy='13' r='3'/></svg>",
  alerta: "<svg viewBox='0 0 24 24'><path d='M12 3 3 19h18z'/><path d='M12 9v5M12 17h.01'/></svg>",
};

const CLASSES = ["Veiculo", "Pessoa", "Objeto", "Animal"];
const NOME_CLASSE = { Veiculo: "Veículo", Pessoa: "Pessoa", Objeto: "Objeto", Animal: "Animal" };
const CORES = { Veiculo: "#28c4dc", Pessoa: "#ff8c28", Objeto: "#148ceb", Animal: "#aa3cb4" };
const CORES_CAMERA = ["#148ceb", "#ff8c28", "#60d25a", "#28c4dc", "#aa3cb4", "#dc50b4", "#ffb000", "#f03c3c"];
const CORES_RISCO = { Informativo: "#148ceb", Atencao: "#ffb000", Prioritario: "#ff8c28", Critico: "#f03c3c" };
const NOME_RISCO = { Informativo: "Informativo", Atencao: "Atenção", Prioritario: "Prioritário", Critico: "Crítico" };
const CORES_FAIXA = { Comportamento: "#148ceb", Interacao: "#5ac4ff", Alerta: "#f03c3c" };
const NOME_FAIXA = { Comportamento: "Comportamento", Interacao: "Interação", Alerta: "Alerta" };
const NOME_TIPO = {
  Em_Pe: "Em pé", Sentado: "Sentado", Caminhando: "Caminhando", Bracos_Levantados: "Braços levantados",
  Agachado: "Agachado", Deitado: "Deitado", Correndo: "Correndo", Permanencia: "Parado",
  Interacao_Proxima: "Interação próxima", Aglomeracao: "Aglomeração", Levantando: "Levantando",
  Possivel_Queda: "Possível queda", Possivel_Briga: "Possível briga", Possivel_Arma_Fogo: "Possível arma",
};
const COR_LED = { branco: "#f4f7fb", verde: "#3ddc97", amarelo: "#ffb020", vermelho: "#ff3b3b", preto: "#05070c" };
/** Filtro cruzado estilo Power BI: { dimensao, valor, rotulo, origem } */
let filtroPagina = null;

function ler(dados, caminho) {
  return String(caminho).split(".").reduce((acc, chave) => (acc == null ? undefined : acc[chave]), dados);
}

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function corSerie(caminho) {
  const chave = String(caminho || "").split(".").pop();
  if (chave === "Comportamento" || chave === "MatchFace" || chave === "MatchPlaca") {
    return "#f03c3c";
  }
  if (CORES[chave]) return CORES[chave];
  return "";
}

function cartao(icone, rotulo, caminho) {
  const cor = corSerie(caminho);
  let svg = SVG[icone] || "";
  if (cor && svg) {
    svg = svg.replace("<svg ", `<svg style="stroke:${cor}" `);
  }
  const estilo = cor ? ` style="color:${cor} !important"` : "";
  return `<article class="cartao"><span${estilo}>${svg}${rotulo}</span><strong data-num="${caminho}"${estilo}>0</strong></article>`;
}

function animar(dados) {
  document.querySelectorAll("[data-num]").forEach((el) => {
    if (el.dataset.travado) return;
    const fim = Number(ler(dados, el.dataset.num) || 0);
    const inicio = Number(el.dataset.valor || 0);
    if (inicio === fim) return;
    const t0 = performance.now();
    const passo = (agora) => {
      const p = Math.min(1, (agora - t0) / 700);
      el.textContent = Math.round(inicio + (fim - inicio) * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(passo);
      else el.dataset.valor = String(fim);
    };
    requestAnimationFrame(passo);
  });
}

function corCamera(nome, indice) {
  const digitos = String(nome || "").replace(/\D/g, "");
  const i = digitos ? Math.max(parseInt(digitos, 10) - 1, 0) : indice;
  return CORES_CAMERA[i % CORES_CAMERA.length];
}

function nomeTipo(classe) {
  return NOME_TIPO[classe] || String(classe || "").replaceAll("_", " ");
}

function seriesClasse(origem, lerValor) {
  return CLASSES.map((nome) => ({
    nome: NOME_CLASSE[nome],
    chave: nome,
    cor: CORES[nome],
    valores: lerValor(nome),
  }));
}

function definirFiltroPagina(filtro) {
  if (filtro && filtroPagina && filtroPagina.dimensao === filtro.dimensao && String(filtroPagina.valor) === String(filtro.valor)) {
    filtroPagina = null;
  } else {
    filtroPagina = filtro;
  }
  if (ultimoDados) ciclo();
}

function dadosComFiltro(dados) {
  if (!filtroPagina || !dados) return dados;
  const { dimensao, valor } = filtroPagina;
  const chave = String(valor);
  const copia = { ...dados };
  if (dimensao === "classe") {
    copia.cubo = (dados.cubo || []).filter((item) => String(item.k) === chave);
    const riscos = { ...(dados.riscos || {}) };
    // mantém riscos; cards usam periodos filtrados abaixo
  } else if (dimensao === "camera") {
    copia.cubo = (dados.cubo || []).filter((item) => String(item.c) === chave);
    copia.app_linhas = (dados.app_linhas || []).filter((item) => String(item.camera || "") === chave);
    copia.geo = (dados.geo || []).filter((item) => String(item.nome || item.camera || "") === chave);
  } else if (dimensao === "risco") {
    const mapa = { Informativo: "Informativo", Atencao: "Atencao", Atenção: "Atencao", Prioritario: "Prioritario", Prioritário: "Prioritario", Critico: "Critico", Crítico: "Critico" };
    const alvo = mapa[chave] || chave;
    copia.riscos = Object.fromEntries(Object.entries(dados.riscos || {}).map(([nome, total]) => [nome, nome === alvo ? total : 0]));
  } else if (dimensao === "natureza") {
    copia.app_linhas = (dados.app_linhas || []).filter((item) => String(item.natureza || "") === chave);
  } else if (dimensao === "rua" || dimensao === "bairro" || dimensao === "cidade") {
    copia.app_linhas = (dados.app_linhas || []).filter((item) => {
      const atual = String(item[dimensao] || "").trim() || "Sem informação";
      return atual === chave;
    });
  } else if (dimensao === "periodo") {
    copia.cubo = (dados.cubo || []).filter((item) => String(item.d || "").includes(chave) || String(item.d || "").endsWith(chave));
  }
  if (dimensao === "classe" || dimensao === "camera" || dimensao === "periodo") {
    const base = { Pessoa: 0, Veiculo: 0, Objeto: 0, Animal: 0, Comportamento: 0, MatchFace: 0, MatchPlaca: 0 };
    (copia.cubo || dados.cubo || []).forEach((item) => {
      if (dimensao === "classe" && String(item.k) !== chave) return;
      if (dimensao === "camera" && String(item.c) !== chave) return;
      if (dimensao === "periodo" && !(String(item.d || "").includes(chave) || String(item.d || "").endsWith(chave))) return;
      const k = item.k;
      if (k in base) base[k] += Number(item.n || 0);
    });
    copia.periodos = {
      ...(dados.periodos || {}),
      dia: { ...(dados.periodos || {}).dia, ...base },
    };
  }
  return copia;
}

function hitCanvas(canvas, evento) {
  const hits = canvas._hits || [];
  const rect = canvas.getBoundingClientRect();
  const x = ((evento.clientX - rect.left) / Math.max(rect.width, 1)) * (canvas.clientWidth || rect.width);
  const y = ((evento.clientY - rect.top) / Math.max(rect.height, 1)) * (canvas.clientHeight || rect.height);
  for (let i = hits.length - 1; i >= 0; i -= 1) {
    const hit = hits[i];
    if (hit.tipo === "arco") {
      const dx = x - hit.cx;
      const dy = y - hit.cy;
      const dist = Math.hypot(dx, dy);
      if (dist < hit.raio * 0.58 || dist > hit.raio) continue;
      let ang = Math.atan2(dy, dx);
      const ini = hit.ini;
      const fim = hit.fim;
      while (ang < ini) ang += Math.PI * 2;
      while (ang >= ini + Math.PI * 2) ang -= Math.PI * 2;
      if (ang >= ini && ang <= fim) return hit;
      continue;
    }
    if (hit.tipo === "ponto") {
      if (Math.hypot(x - hit.x, y - hit.y) <= (hit.r || 12)) return hit;
      continue;
    }
    if (x >= hit.x && x <= hit.x + hit.w && y >= hit.y && y <= hit.y + hit.h) return hit;
  }
  return null;
}

function cliqueGrafico(canvas, evento) {
  const hit = hitCanvas(canvas, evento);
  if (!hit || !hit.filtro) return;
  definirFiltroPagina(hit.filtro);
}

function prepararVisualizacoes(raiz) {
  if (!raiz) return;
  raiz.querySelectorAll("#filtro-pagina, .filtro-pagina").forEach((barra) => barra.remove());
  // Remove botões/wrappers de zoom (recurso retirado).
  raiz.querySelectorAll(".viz-wrap").forEach((wrap) => {
    wrap.querySelectorAll(".viz-zoom").forEach((botao) => botao.remove());
    const filho = wrap.querySelector("canvas.grafico, iframe.mapa, iframe.mapa-folium");
    if (filho && wrap.parentNode) {
      wrap.parentNode.insertBefore(filho, wrap);
      wrap.remove();
    }
  });
  raiz.querySelectorAll(".viz-zoom").forEach((botao) => botao.remove());
  const modal = document.getElementById("viz-modal");
  if (modal) modal.remove();
  // Mantém clique filtrável nos gráficos.
  raiz.querySelectorAll("canvas.grafico").forEach((el) => {
    if (el.closest(".cartoes")) return;
    el.classList.add("filtravel");
    if (!el.dataset.filtroLigado) {
      el.dataset.filtroLigado = "1";
      el.addEventListener("click", (evento) => cliqueGrafico(el, evento));
    }
  });
}

function linha(canvas, series, rotulos, eixoX, opcoes) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 640;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  const hits = [];
  const fonte = (opcoes && opcoes.fonte) || 12;
  const esquerda = fonte >= 15 ? 72 : 48;
  const topo = 28;
  const direita = 12;
  const baixo = fonte >= 15 ? 56 : 42;
  const w = Math.max(10, largura - esquerda - direita);
  const h = Math.max(10, altura - topo - baixo);
  const base = series.filter((serie) => !serie.teto);
  const pico = Math.max(1, ...base.flatMap((serie) => serie.valores || [0]));
  ctx.font = `${fonte}px Segoe UI`;
  ctx.fillStyle = "#93a0b8";
  ctx.fillText("contagens", 4, 16);
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 1;
  [0, 0.5, 1].forEach((fracao) => {
    const y = topo + h - fracao * h;
    ctx.beginPath();
    ctx.moveTo(esquerda, y);
    ctx.lineTo(esquerda + w, y);
    ctx.stroke();
    ctx.fillStyle = "#93a0b8";
    ctx.fillText(String(Math.round(pico * fracao)), 2, y + 4);
  });
  const n = Math.max(rotulos.length, 1);
  const passo = Math.max(1, Math.ceil(rotulos.length / 6));
  rotulos.forEach((rotulo, indice) => {
    if (indice % passo) return;
    const x = esquerda + (n <= 1 ? w / 2 : (indice / (n - 1)) * w);
    ctx.fillStyle = "#93a0b8";
    ctx.fillText(String(rotulo), x - 10, topo + h + 16);
    hits.push({
      tipo: "ret", x: x - 18, y: topo + h, w: 36, h: 28,
      filtro: { dimensao: "periodo", valor: String(rotulo), rotulo: `Período ${rotulo}`, origem: canvas.id },
    });
  });
  ctx.fillText(eixoX || "", esquerda, altura - 6);
  const xDe = (indice, total) => esquerda + (total <= 1 ? w / 2 : (indice / (total - 1)) * w);
  series.forEach((serie) => {
    const valores = serie.valores || [];
    const pontos = valores.map((valor, indice) => ({
      x: xDe(indice, valores.length),
      y: topo + h - ((serie.teto ? (valor ? 1 : 0) : valor / pico) * h),
      valor,
      rotulo: rotulos[indice],
    }));
    const ativo = filtroPagina && filtroPagina.dimensao === "classe" && String(filtroPagina.valor) === String(serie.chave || serie.nome);
    ctx.beginPath();
    ctx.strokeStyle = serie.cor;
    ctx.lineWidth = ativo ? 3.5 : 2;
    ctx.globalAlpha = filtroPagina && filtroPagina.dimensao === "classe" && !ativo ? 0.28 : 1;
    pontos.forEach((ponto, indice) => (indice === 0 ? ctx.moveTo(ponto.x, ponto.y) : ctx.lineTo(ponto.x, ponto.y)));
    ctx.stroke();
    ctx.globalAlpha = 1;
    const marcarTodos = valores.length <= 8;
    let picoIndice = 0;
    valores.forEach((valor, indice) => {
      if (valor > (valores[picoIndice] || 0)) picoIndice = indice;
    });
    ctx.fillStyle = serie.cor;
    pontos.forEach((ponto, indice) => {
      if (!ponto.valor) return;
      if (!marcarTodos && indice !== picoIndice) return;
      ctx.fillText(String(ponto.valor), ponto.x + 2, Math.max(14, ponto.y - 4));
      hits.push({
        tipo: "ponto", x: ponto.x, y: ponto.y, r: 14,
        filtro: {
          dimensao: "classe",
          valor: serie.chave || serie.nome,
          rotulo: serie.nome,
          origem: canvas.id,
        },
      });
    });
  });
  let lx = esquerda;
  series.forEach((serie) => {
    const ativo = filtroPagina && filtroPagina.dimensao === "classe" && String(filtroPagina.valor) === String(serie.chave || serie.nome);
    ctx.globalAlpha = filtroPagina && filtroPagina.dimensao === "classe" && !ativo ? 0.35 : 1;
    ctx.fillStyle = serie.cor;
    ctx.fillRect(lx, 6, 10, 10);
    ctx.fillStyle = "#f4f7fb";
    ctx.fillText(serie.nome, lx + 14, 15);
    const larguraLegenda = ctx.measureText(serie.nome).width + 28;
    hits.push({
      tipo: "ret", x: lx, y: 0, w: larguraLegenda, h: 22,
      filtro: { dimensao: "classe", valor: serie.chave || serie.nome, rotulo: serie.nome, origem: canvas.id },
    });
    lx += larguraLegenda;
    ctx.globalAlpha = 1;
  });
  canvas._hits = hits;
}

function barras(itens) {
  const pico = Math.max(1, ...itens.map((item) => item.total));
  if (!itens.length) return "<p>Ainda sem contagem neste período.</p>";
  return itens.map((item) => {
    const foto = item.id ? `<img class="mini" alt="" src="/rosto/${encodeURIComponent(item.id)}.jpg" onerror="this.style.display='none'">` : (SVG[item.icone] || "");
    const nome = item.nome ? `${escapar(item.nome)} · ` : "";
    return `<div class="linha-face"><span>${foto}${nome}${escapar(item.rotulo)}</span><strong>${item.total}</strong></div>
      <div class="barra"><i style="width:${Math.round(100 * item.total / pico)}%"></i></div>`;
  }).join("");
}

function barrasEmpilhadas(canvas, dias, opcoes) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 640;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  const cameras = [];
  dias.forEach((dia) => Object.keys(dia.cameras || {}).forEach((nome) => {
    if (!cameras.includes(nome)) cameras.push(nome);
  }));
  const grupos = Math.max(dias.length, 1);
  const fontePedida = (opcoes && opcoes.fonte) || 11;
  const muitos = grupos > 8;
  const fonte = muitos ? Math.min(fontePedida, 11) : Math.min(fontePedida, 13);
  const esquerda = fonte >= 15 ? 64 : 42;
  const topo = 18;
  const baixo = fonte >= 15 ? 58 : 46;
  const h = Math.max(10, altura - topo - baixo);
  const barrasPorGrupo = CLASSES.length;
  const larguraGrupo = (largura - esquerda - 8) / grupos;
  const larguraBarra = Math.max(6, Math.min(18, (larguraGrupo - 16) / barrasPorGrupo));
  let pico = 1;
  dias.forEach((dia) => CLASSES.forEach((classe) => {
    const total = cameras.reduce((soma, camera) => soma + Number((dia.cameras?.[camera] || {})[classe] || 0), 0);
    pico = Math.max(pico, total);
  }));
  ctx.font = `${fonte}px Segoe UI`;
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  [0, 0.5, 1].forEach((fracao) => {
    const y = topo + h - fracao * h;
    ctx.beginPath();
    ctx.moveTo(esquerda, y);
    ctx.lineTo(largura - 8, y);
    ctx.stroke();
    ctx.fillStyle = "#93a0b8";
    ctx.fillText(String(Math.round(pico * fracao)), 2, y + 4);
  });
  const hits = [];
  dias.forEach((dia, indiceDia) => {
    const x0 = esquerda + indiceDia * larguraGrupo + 8;
    CLASSES.forEach((classe, indiceClasse) => {
      const x = x0 + indiceClasse * (larguraBarra + 3);
      let y = topo + h;
      let total = 0;
      const yTopoClasse = topo + h;
      cameras.forEach((camera, indiceCamera) => {
        const valor = Number((dia.cameras?.[camera] || {})[classe] || 0);
        if (!valor) return;
        const alturaBarra = (valor / pico) * h;
        y -= alturaBarra;
        total += valor;
        const ativoCam = filtroPagina && filtroPagina.dimensao === "camera" && String(filtroPagina.valor) === String(camera);
        const ativoClasse = filtroPagina && filtroPagina.dimensao === "classe" && String(filtroPagina.valor) === String(classe);
        ctx.globalAlpha = filtroPagina && !(ativoCam || ativoClasse) ? 0.28 : 1;
        ctx.fillStyle = corCamera(camera, indiceCamera);
        ctx.fillRect(x, y, larguraBarra, alturaBarra);
        ctx.globalAlpha = 1;
        hits.push({
          tipo: "ret", x, y, w: larguraBarra, h: alturaBarra,
          filtro: { dimensao: "camera", valor: camera, rotulo: camera, origem: canvas.id },
        });
        if (!muitos && alturaBarra >= 16 && larguraBarra >= 16) {
          ctx.fillStyle = "#041018";
          ctx.font = "10px Segoe UI";
          ctx.fillText(String(valor), x + 1, y + 12);
          ctx.font = `${fonte}px Segoe UI`;
        }
      });
      if (total) {
        hits.push({
          tipo: "ret", x, y, w: larguraBarra, h: Math.max(8, yTopoClasse - y),
          filtro: { dimensao: "classe", valor: classe, rotulo: NOME_CLASSE[classe] || classe, origem: canvas.id },
        });
      }
      if (total && larguraBarra >= 18) {
        ctx.fillStyle = "#f4f7fb";
        ctx.font = "11px Segoe UI";
        ctx.fillText(String(total), x, y - 3);
        ctx.font = `${fonte}px Segoe UI`;
      }
      if (!muitos) {
        ctx.fillStyle = CORES[classe];
        ctx.font = "11px Segoe UI";
        ctx.fillText(NOME_CLASSE[classe].slice(0, 3), x, topo + h + 14);
        ctx.font = `${fonte}px Segoe UI`;
      }
    });
    const passoRotulo = muitos ? Math.ceil(grupos / 8) : 1;
    if (indiceDia % passoRotulo === 0) {
      ctx.fillStyle = "#93a0b8";
      ctx.font = "11px Segoe UI";
      ctx.fillText(dia.rotulo || "", x0, altura - 8);
      ctx.font = `${fonte}px Segoe UI`;
      hits.push({
        tipo: "ret", x: x0, y: altura - 22, w: Math.max(24, larguraGrupo - 8), h: 20,
        filtro: { dimensao: "periodo", valor: String(dia.rotulo || ""), rotulo: `Período ${dia.rotulo || ""}`, origem: canvas.id },
      });
    }
  });
  ctx.fillStyle = "#93a0b8";
  ctx.fillText("contagens", 2, 12);
  canvas._hits = hits;
  return cameras;
}

function legendaCameras(cameras) {
  if (!cameras.length) return "";
  return `<div class="legenda-linha">${cameras.map((nome, indice) => `<span><b style="background:${corCamera(nome, indice)}"></b>${escapar(nome)}</span>`).join("")}</div>`;
}

function rosca(canvas, riscos) {
  if (!canvas) return;
  const ordem = ["Informativo", "Atencao", "Prioritario", "Critico"];
  const fatias = ordem
    .map((nome) => ({
      nome: NOME_RISCO[nome],
      rotulo: NOME_RISCO[nome],
      chave: nome,
      dimensao: "risco",
      total: Number(riscos[nome] || 0),
      cor: CORES_RISCO[nome],
    }))
    .filter((item) => item.total > 0);
  roscaLivre(canvas, fatias.length ? fatias : [{ nome: "Sem prioridade", rotulo: "Sem prioridade", total: 0, cor: "#93a0b8" }], {
    rotulosExternos: true,
    vazio: "Sem prioridade hoje",
  });
}

function tiposHtml(tipos) {
  const lista = tipos || [];
  if (!lista.length) return "<p>Nenhum tipo de comportamento hoje.</p>";
  const cameras = [];
  lista.forEach((item) => Object.keys(item.cameras || {}).forEach((nome) => {
    if (!cameras.includes(nome)) cameras.push(nome);
  }));
  const pico = Math.max(1, ...lista.map((item) => Object.values(item.cameras || {}).reduce((s, n) => s + Number(n || 0), 0)));
  const linhas = lista.map((item) => {
    const total = Object.values(item.cameras || {}).reduce((s, n) => s + Number(n || 0), 0);
    const partes = cameras.map((camera, indice) => {
      const valor = Number((item.cameras || {})[camera] || 0);
      if (!valor) return "";
      const largura = Math.max(8, Math.round((100 * valor) / pico));
      return `<i style="width:${largura}%;background:${corCamera(camera, indice)}">${valor}</i>`;
    }).join("");
    return `<div class="empilha"><span>${escapar(nomeTipo(item.classe))}</span><div class="trilha">${partes}</div><strong>${total}</strong></div>`;
  }).join("");
  return linhas + legendaCameras(cameras);
}

function pontosGeo(dados, campo) {
  const vivo = {};
  (dados.cameras_vivo || []).forEach((camera) => { vivo[camera.nome] = camera; });
  return (dados.geo || []).filter((ponto) => ponto.lat != null && ponto.lon != null).map((ponto) => ({
    ...ponto,
    valor: Number(ponto[campo] || 0),
    risco: (vivo[ponto.nome] || {}).risco || "branco",
    frase: (vivo[ponto.nome] || {}).frase || "",
  }));
}

let ultimoDados = null;

function isoLocal(data) {
  const mes = String(data.getMonth() + 1).padStart(2, "0");
  const dia = String(data.getDate()).padStart(2, "0");
  return `${data.getFullYear()}-${mes}-${dia}`;
}

function numeroDia(iso) {
  const partes = String(iso || "").split("-").map(Number);
  if (partes.length < 3 || !partes[0]) return null;
  return Math.floor(Date.UTC(partes[0], partes[1] - 1, partes[2]) / 86400000);
}

function isoDe(numero) {
  const data = new Date(numero * 86400000);
  const mes = String(data.getUTCMonth() + 1).padStart(2, "0");
  const dia = String(data.getUTCDate()).padStart(2, "0");
  return `${data.getUTCFullYear()}-${mes}-${dia}`;
}

function dentro(dia, inicio, fim) {
  return (!inicio || dia >= inicio) && (!fim || dia <= fim);
}

function ligarPeriodo(host, minimo, maximo, inicioInicial, fimInicial) {
  if (!host || host.dataset.ligado) return;
  host.dataset.ligado = "1";
  let a = numeroDia(inicioInicial);
  let b = numeroDia(fimInicial);
  if (a == null) a = minimo;
  if (b == null) b = maximo;
  a = Math.max(minimo, Math.min(a, maximo));
  b = Math.max(a, Math.min(b, maximo));
  host.innerHTML = `<div class="periodo-datas"><span></span><span></span></div>
    <div class="trilho"><i class="fundo"></i><i class="faixa-sel"></i>
    <button type="button" class="puxador" data-lado="ini"></button>
    <button type="button" class="puxador" data-lado="fim"></button></div>`;
  const desenhar = () => {
    const span = Math.max(1, maximo - minimo);
    const esquerda = (a - minimo) / span;
    const largura = (b - a) / span;
    const faixa = host.querySelector(".faixa-sel");
    faixa.style.left = `calc(8px + (100% - 16px) * ${esquerda})`;
    faixa.style.width = `calc((100% - 16px) * ${largura})`;
    host.querySelector("[data-lado=ini]").style.left = `calc(8px + (100% - 16px) * ${esquerda})`;
    host.querySelector("[data-lado=fim]").style.left = `calc(8px + (100% - 16px) * ${esquerda + largura})`;
    const rotulos = host.querySelectorAll(".periodo-datas span");
    rotulos[0].textContent = isoDe(a).split("-").reverse().join("/");
    rotulos[1].textContent = isoDe(b).split("-").reverse().join("/");
    host.dataset.ini = isoDe(a);
    host.dataset.fim = isoDe(b);
  };
  desenhar();
  let lado = "";
  host.querySelectorAll(".puxador").forEach((botao) => {
    botao.addEventListener("pointerdown", (evento) => {
      lado = botao.dataset.lado;
      botao.setPointerCapture(evento.pointerId);
    });
  });
  host.addEventListener("pointermove", (evento) => {
    if (!lado) return;
    const rect = host.querySelector(".trilho").getBoundingClientRect();
    const t = Math.min(1, Math.max(0, (evento.clientX - rect.left - 8) / Math.max(1, rect.width - 16)));
    const dia = Math.round(minimo + t * (maximo - minimo));
    if (lado === "ini") a = Math.min(dia, b);
    else b = Math.max(dia, a);
    host.dataset.mexeu = "1";
    desenhar();
    const tela = document.getElementById("tela");
    if (ultimoDados && tela && render[tela.dataset.tela]) render[tela.dataset.tela](tela, ultimoDados);
  });
  host.addEventListener("pointerup", () => { lado = ""; });
  host._definir = (inicio, fim) => {
    const ni = numeroDia(inicio);
    const nf = numeroDia(fim);
    a = Math.max(minimo, Math.min(ni == null ? minimo : ni, maximo));
    b = Math.max(a, Math.min(nf == null ? maximo : nf, maximo));
    host.dataset.mexeu = "1";
    desenhar();
    const tela = document.getElementById("tela");
    if (ultimoDados && tela && render[tela.dataset.tela]) render[tela.dataset.tela](tela, ultimoDados);
  };
}

function botoesGrao(ativo) {
  return ["hora", "dia", "mes", "ano"].map((grao) => {
    const nome = { hora: "Hora", dia: "Dia", mes: "Mês", ano: "Ano" }[grao];
    return `<button type="button" data-grao="${grao}" class="${grao === ativo ? "ativo" : ""}">${nome}</button>`;
  }).join("");
}

function agregarContagens(dados, inicio, fim, grao) {
  const baldes = new Map();
  (dados.cubo || []).forEach((item) => {
    if (!dentro(item.d, inicio, fim)) return;
    let chave = item.d;
    let rotulo = `${String(item.d || "").slice(8, 10)}/${String(item.d || "").slice(5, 7)}`;
    if (grao === "hora") {
      chave = String(item.h).padStart(2, "0");
      rotulo = `${chave}h`;
    } else if (grao === "mes") {
      chave = String(item.d || "").slice(0, 7);
      rotulo = `${chave.slice(5)}/${chave.slice(2, 4)}`;
    } else if (grao === "ano") {
      chave = String(item.d || "").slice(0, 4);
      rotulo = chave;
    }
    if (!baldes.has(chave)) baldes.set(chave, { rotulo, ordem: chave, cameras: {} });
    const camera = baldes.get(chave).cameras[item.c] || (baldes.get(chave).cameras[item.c] = {});
    camera[item.k] = (camera[item.k] || 0) + Number(item.n || 0);
  });
  if (grao === "hora") {
    return Array.from({ length: 24 }, (_, hora) => {
      const chave = String(hora).padStart(2, "0");
      return baldes.get(chave) || { rotulo: `${chave}h`, cameras: {} };
    });
  }
  return [...baldes.values()].sort((um, outro) => (um.ordem < outro.ordem ? -1 : 1));
}

function somarClasse(baldes, classe) {
  return baldes.map((balde) => Object.values(balde.cameras || {}).reduce((soma, camera) => soma + Number(camera[classe] || 0), 0));
}

function barrasVerticais(canvas, itens) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 640;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  ctx.font = "15px Segoe UI";
  const hits = [];
  if (!itens.length) {
    ctx.fillStyle = "#93a0b8";
    ctx.fillText("Sem ocorrência neste período.", 16, 36);
    canvas._hits = hits;
    return;
  }
  const esquerda = 52;
  const baixo = 64;
  const topo = 16;
  const h = Math.max(10, altura - topo - baixo);
  const pico = Math.max(1, ...itens.map((item) => item.total));
  const passo = (largura - esquerda - 12) / itens.length;
  itens.forEach((item, indice) => {
    const alturaBarra = (item.total / pico) * h;
    const x = esquerda + indice * passo + 8;
    const y = topo + h - alturaBarra;
    const larguraBarra = Math.max(8, passo - 16);
    const dimensao = item.dimensao || (item.chave && CLASSES.includes(item.chave) ? "classe" : "natureza");
    const valor = item.chave || item.rotulo || item.nome;
    const ativo = filtroPagina && filtroPagina.dimensao === dimensao && String(filtroPagina.valor) === String(valor);
    ctx.globalAlpha = filtroPagina && !ativo ? 0.28 : 1;
    ctx.fillStyle = item.cor || "#4c8dff";
    ctx.fillRect(x, y, larguraBarra, alturaBarra);
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#f4f7fb";
    ctx.fillText(String(item.total), x, Math.max(14, y - 4));
    ctx.fillStyle = "#93a0b8";
    ctx.save();
    ctx.translate(x, topo + h + 8);
    ctx.rotate(itens.length > 8 ? -0.7 : 0);
    ctx.fillText(String(item.rotulo).slice(0, 18), 0, 12);
    ctx.restore();
    hits.push({
      tipo: "ret", x, y, w: larguraBarra, h: Math.max(alturaBarra, 8),
      filtro: { dimensao, valor, rotulo: String(item.rotulo || item.nome || valor), origem: canvas.id },
    });
  });
  canvas._hits = hits;
}

function roscaLivre(canvas, fatias, opcoes) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 320;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  const total = fatias.reduce((soma, item) => soma + Number(item.total || 0), 0);
  // Padrão: rótulos fora da rosca, com linha guia (não sobrepostos).
  const externos = !(opcoes && opcoes.rotulosExternos === false);
  const cx = largura * 0.5;
  const cy = altura * 0.5;
  const raio = Math.min(largura, altura) * (externos ? 0.28 : 0.32);
  let angulo = -Math.PI / 2;
  const fatiasDesenhadas = [];
  const hits = [];
  fatias.forEach((item) => {
    const fatia = total ? (Number(item.total || 0) / total) * Math.PI * 2 : 0;
    if (fatia <= 0) return;
    const ini = angulo;
    const fim = angulo + fatia;
    const chave = String(item.chave || item.nome || item.rotulo || "");
    const dimensao = item.dimensao || (Object.prototype.hasOwnProperty.call(CORES_RISCO, item.chave || item.nome) ? "risco" : "natureza");
    const ativo = filtroPagina && filtroPagina.dimensao === dimensao && String(filtroPagina.valor) === chave;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.fillStyle = item.cor;
    ctx.globalAlpha = filtroPagina && !ativo ? 0.28 : 1;
    ctx.arc(cx, cy, raio, ini, fim);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;
    fatiasDesenhadas.push({
      ...item,
      meio: ini + fatia / 2,
      pct: total ? Math.round((1000 * Number(item.total || 0)) / total) / 10 : 0,
    });
    hits.push({
      tipo: "arco", cx, cy, raio, ini, fim,
      filtro: { dimensao, valor: chave, rotulo: String(item.nome || item.rotulo || chave), origem: canvas.id },
    });
    angulo = fim;
  });
  canvas._hits = hits;
  ctx.beginPath();
  ctx.fillStyle = "#12182a";
  ctx.arc(cx, cy, raio * 0.58, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#f4f7fb";
  ctx.font = "22px Segoe UI";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(total), cx, cy);
  if (externos) {
    const raioLinha = raio + 12;
    const raioTexto = raio + Math.max(42, Math.min(largura, altura) * 0.18);
    fatiasDesenhadas.forEach((item) => {
      const cos = Math.cos(item.meio);
      const sin = Math.sin(item.meio);
      const x1 = cx + cos * raio;
      const y1 = cy + sin * raio;
      const x2 = cx + cos * raioLinha;
      const y2 = cy + sin * raioLinha;
      const x3 = cx + cos * raioTexto;
      const y3 = cy + sin * raioTexto;
      const direita = cos >= 0;
      ctx.strokeStyle = item.cor || "#93a0b8";
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.lineTo(x3 + (direita ? 10 : -10), y3);
      ctx.stroke();
      const nome = String(item.nome || item.rotulo || "Natureza");
      const curto = nome.length > 22 ? `${nome.slice(0, 20)}…` : nome;
      const texto = `${curto} · ${item.pct}% · ${item.total}`;
      ctx.fillStyle = "#f4f7fb";
      ctx.font = "600 14px Segoe UI";
      ctx.textAlign = direita ? "left" : "right";
      ctx.textBaseline = "middle";
      const tx = Math.max(8, Math.min(largura - 8, x3 + (direita ? 12 : -12)));
      const ty = Math.max(14, Math.min(altura - 14, y3));
      ctx.fillText(texto, tx, ty);
    });
  } else {
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.font = "14px Segoe UI";
    fatias.slice(0, 8).forEach((item, indice) => {
      const pct = total ? Math.round((1000 * Number(item.total || 0)) / total) / 10 : 0;
      const y = 28 + indice * 22;
      ctx.fillStyle = item.cor;
      ctx.fillRect(8, y - 10, 10, 10);
      ctx.fillStyle = "#f4f7fb";
      ctx.fillText(`${item.nome || item.rotulo || ""}  ${pct}%  (${item.total})`, 24, y);
    });
  }
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
  if (!total) {
    ctx.fillStyle = "#93a0b8";
    ctx.font = "14px Segoe UI";
    ctx.fillText((opcoes && opcoes.vazio) || "Sem ocorrência neste período.", 16, 28);
  }
}

function enviarMapa(id, pontos, opcoes) {
  const frame = document.getElementById(id);
  if (!frame || frame.tagName !== "IFRAME") return;
  const carga = {
    tipo: "mapa",
    desenho: (opcoes && opcoes.desenho) || "pontos",
    fixo: !!(opcoes && opcoes.fixo),
    pisca: !!(opcoes && opcoes.pisca),
    novoMatch: !!(opcoes && opcoes.novoMatch),
    rotulos: !(opcoes && opcoes.semRotulo),
    trilhas: (opcoes && opcoes.trilhas) || [],
    pontos: (pontos || []).map((ponto, indice) => {
      const lat = Number(ponto.lat);
      const lon = Number(ponto.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
      if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return null;
      return {
        lat,
        lon,
        id: ponto.id || "",
        nome: ponto.nome || ponto.tipo || "",
        camera: ponto.camera || "",
        quando: ponto.quando || "",
        foto: ponto.foto || "",
        valor: Number(ponto.valor || 0),
        risco: ponto.risco || "",
        cor: ponto.cor || ((opcoes && opcoes.pisca && ponto.risco) ? (COR_LED[ponto.risco] || corCamera(ponto.nome, indice)) : corCamera(ponto.nome || ponto.tipo, indice)),
      };
    }).filter(Boolean),
  };
  const mandar = () => {
    if (frame.contentWindow) frame.contentWindow.postMessage(carga, location.origin);
  };
  const pronto = () => {
    frame.dataset.pronto = "1";
    mandar();
  };
  if (frame.dataset.pronto === "1") mandar();
  else if (frame.contentDocument && frame.contentDocument.readyState === "complete") pronto();
  else frame.addEventListener("load", pronto, { once: true });
}

const cacheRotasRf = {};
const pendenciaMapaRf = {};

function corPessoaRf(id) {
  return `hsl(${(Array.from(String(id || "")).reduce((soma, car) => soma + car.charCodeAt(0), 0) * 17) % 360} 70% 48%)`;
}

function popularSelRf(sel, pessoas) {
  if (!sel) return;
  const marca = (pessoas || []).map((item) => item.id).join("|");
  if (sel.dataset.marca === marca) return;
  const escolhidos = new Set(Array.from(sel.selectedOptions || []).map((opcao) => opcao.value));
  sel.innerHTML = (pessoas || []).map((pessoa) => `<option value="${escapar(pessoa.id)}"${escolhidos.has(pessoa.id) ? " selected" : ""}>${escapar(pessoa.nome || pessoa.id)}</option>`).join("");
  sel.dataset.marca = marca;
}

function rastrosRfFiltrados(dados, sel) {
  const selecionados = Array.from((sel && sel.selectedOptions) || []).map((opcao) => opcao.value);
  const filtro = new Set(selecionados);
  return (dados.rastros_rf || []).filter((item) => !filtro.size || filtro.has(item.id)).map((item) => ({
    ...item,
    id: item.id || "",
    lat: Number(item.lat),
    lon: Number(item.lon),
    nome: item.nome || item.id,
    camera: item.camera || "",
    quando: item.quando || "",
    foto: item.foto || `/rosto/${item.id}.jpg`,
    valor: 1,
    cor: corPessoaRf(item.id),
  })).filter((item) => Number.isFinite(item.lat) && Number.isFinite(item.lon))
    .sort((a, b) => String(a.quando || "").localeCompare(String(b.quando || "")));
}

async function pedirRotaVias(pontos) {
  if (!pontos || pontos.length < 2) return (pontos || []).map((ponto) => [ponto.lat, ponto.lon]);
  const consulta = pontos.map((ponto) => `${ponto.lon},${ponto.lat}`).join(";");
  try {
    const resposta = await fetch(`/mapa/rota.json?pontos=${encodeURIComponent(consulta)}`);
    const dados = await resposta.json();
    if (dados.caminho && dados.caminho.length >= 2) return dados.caminho;
  } catch (_erro) {
    /* fallback reto */
  }
  return pontos.map((ponto) => [ponto.lat, ponto.lon]);
}

async function trilhasRfDe(rastros) {
  const porPessoa = {};
  (rastros || []).forEach((ponto) => {
    const chave = String(ponto.id || ponto.nome || "pessoa");
    (porPessoa[chave] = porPessoa[chave] || []).push(ponto);
  });
  const trilhas = [];
  for (const [id, lista] of Object.entries(porPessoa)) {
    lista.sort((a, b) => String(a.quando || "").localeCompare(String(b.quando || "")));
    const chave = `${id}|${lista.map((ponto) => `${ponto.quando}@${ponto.lat},${ponto.lon}`).join(">")}`;
    if (!cacheRotasRf[chave]) cacheRotasRf[chave] = await pedirRotaVias(lista);
    trilhas.push({ id, cor: lista[0].cor || corPessoaRf(id), caminho: cacheRotasRf[chave] });
  }
  return trilhas;
}

const ultimaAssinaturaRf = {};
const ultimaAssinaturaDadosRf = {};
const cacheTrilhasRfMapa = {};

function assinaturaPontosRf(rastros) {
  return (rastros || []).map((p) => `${p.id}@${p.quando}@${p.lat},${p.lon}`).join(">");
}

function enviarMapaRf(id, rastros, opcoes) {
  const sel = (opcoes && opcoes.sel) || null;
  const filtro = Array.from((sel && sel.selectedOptions) || []).map((o) => o.value).join(",");
  const pontosSig = assinaturaPontosRf(rastros);
  const assinatura = `${filtro}|${pontosSig}`;
  const dadosSig = (opcoes && opcoes.assinaturaDados) || pontosSig;
  // Sem mudança de filtro nem de rastros: mantém o mapa estático.
  if (ultimaAssinaturaRf[id] === assinatura && cacheTrilhasRfMapa[assinatura]) {
    return;
  }
  const houveNovoMatch = !!(ultimaAssinaturaDadosRf[id] && ultimaAssinaturaDadosRf[id] !== dadosSig);
  ultimaAssinaturaDadosRf[id] = dadosSig;
  ultimaAssinaturaRf[id] = assinatura;
  const token = (pendenciaMapaRf[id] = (pendenciaMapaRf[id] || 0) + 1);
  const base = { ...(opcoes || {}), desenho: "rf", semRotulo: true, pisca: false, novoMatch: houveNovoMatch };
  if (cacheTrilhasRfMapa[assinatura]) {
    enviarMapa(id, rastros, { ...base, trilhas: cacheTrilhasRfMapa[assinatura] });
    return;
  }
  // Só redesenha com trilhas prontas (evita piscar com linha vazia → rota).
  trilhasRfDe(rastros).then((trilhas) => {
    if (pendenciaMapaRf[id] !== token) return;
    cacheTrilhasRfMapa[assinatura] = trilhas;
    enviarMapa(id, rastros, { ...base, trilhas });
  });
}

function atualizarLegendaRf(id, rastros, sel) {
  const legenda = document.getElementById(id);
  if (!legenda) return;
  const filtro = Array.from((sel && sel.selectedOptions) || []).length;
  legenda.textContent = rastros.length
    ? `${rastros.length} passagem(ns) · rota pelas vias do passado ao presente${filtro ? ` · ${filtro} pessoa(s)` : " · todas as pessoas de interesse"}`
    : "Sem passagem georreferenciada das pessoas selecionadas.";
}

const pulso = { canvas: null, pontos: [], opcoes: null };

function pedirTile(z, x, y) {
  const n = 2 ** z;
  if (x < 0 || y < 0 || x >= n || y >= n) return null;
  const chave = `${z}/${x}/${y}`;
  if (cacheTile[chave]) return cacheTile[chave].img;
  const item = { img: null };
  const imagem = new Image();
  imagem.onload = () => {
    item.img = imagem;
    if (pulso.canvas && document.body.contains(pulso.canvas)) mapaCameras(pulso.canvas, pulso.pontos, pulso.opcoes);
    if (ocorrenciaRedraw) ocorrenciaRedraw();
  };
  imagem.src = `/mapa/${z}/${x}/${y}.png`;
  cacheTile[chave] = item;
  return null;
}

function mercator(lat, lon, zoom) {
  const n = 2 ** zoom;
  const x = (Number(lon) + 180) / 360 * n;
  const limitado = Math.max(-85, Math.min(85, Number(lat)));
  const rad = limitado * Math.PI / 180;
  const y = (1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2 * n;
  return [x, y];
}

function projetarRuas(ctx, largura, altura, pontos) {
  if (!pontos.length) return null;
  let zoom = pontos.length <= 1 ? 17 : 16;
  const lats = pontos.map((ponto) => Number(ponto.lat));
  const lons = pontos.map((ponto) => Number(ponto.lon));
  const span = Math.max(Math.max(...lats) - Math.min(...lats), Math.max(...lons) - Math.min(...lons), 0.0004);
  for (let candidato = 17; candidato >= 13; candidato -= 1) {
    if (span / (360 / (2 ** candidato)) <= 1.5) {
      zoom = candidato;
      break;
    }
    zoom = candidato;
  }
  const fracoes = pontos.map((ponto) => mercator(ponto.lat, ponto.lon, zoom));
  const xs = fracoes.map((item) => item[0]);
  const ys = fracoes.map((item) => item[1]);
  const margem = 0.7;
  const x0 = Math.min(...xs) - margem;
  const x1 = Math.max(...xs) + margem;
  const y0 = Math.min(...ys) - margem;
  const y1 = Math.max(...ys) + margem;
  for (let ty = Math.floor(y0); ty <= Math.floor(y1); ty += 1) {
    for (let tx = Math.floor(x0); tx <= Math.floor(x1); tx += 1) {
      const imagem = pedirTile(zoom, tx, ty);
      if (!imagem) continue;
      const dx = (tx - x0) / (x1 - x0) * largura;
      const dy = (ty - y0) / (y1 - y0) * altura;
      ctx.drawImage(imagem, dx, dy, largura / (x1 - x0) + 1, altura / (y1 - y0) + 1);
    }
  }
  return (indice) => {
    const [fx, fy] = fracoes[indice];
    return [(fx - x0) / (x1 - x0) * largura, (fy - y0) / (y1 - y0) * altura];
  };
}

function mapaCameras(canvas, pontos, opcoes) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 640;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#101624";
  ctx.fillRect(0, 0, largura, altura);
  if (!pontos.length) {
    ctx.fillStyle = "#93a0b8";
    ctx.font = "16px Segoe UI";
    ctx.fillText("Câmeras sem latitude.", 24, 40);
    return;
  }
  const projetor = projetarRuas(ctx, largura, altura, pontos);
  const maior = Math.max(1, ...pontos.map((ponto) => ponto.valor || 0));
  ctx.font = "13px Segoe UI";
  pontos.forEach((ponto, indice) => {
    const [x, y] = projetor(indice);
    const raio = opcoes && opcoes.fixo ? 9 : 10 + Math.sqrt((ponto.valor || 0) / maior) * 26;
    const risco = opcoes && opcoes.pisca ? (ponto.risco || "branco") : "";
    const cor = risco ? (COR_LED[risco] || corCamera(ponto.nome, indice)) : corCamera(ponto.nome, indice);
    const periodo = { branco: 1400, amarelo: 900, vermelho: 450, preto: 280 }[risco] || 0;
    const visivel = !periodo || (Date.now() % periodo) < periodo * 0.62;
    ctx.globalAlpha = visivel ? 0.92 : 0.28;
    ctx.beginPath();
    ctx.fillStyle = cor;
    ctx.arc(x, y, raio, 0, Math.PI * 2);
    ctx.fill();
    if (risco === "preto") {
      ctx.strokeStyle = "#ff3b3b";
      ctx.lineWidth = 3;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#f4f7fb";
    ctx.fillText(ponto.nome || "", x + raio + 4, y - 4);
    if (!(opcoes && opcoes.fixo)) {
      ctx.fillStyle = "#93a0b8";
      ctx.fillText(String(ponto.valor || 0), x + raio + 4, y + 12);
    }
  });
}

function observarMapa(canvas, pontos, opcoes) {
  pulso.canvas = canvas;
  pulso.pontos = pontos;
  pulso.opcoes = opcoes;
  mapaCameras(canvas, pontos, opcoes);
}

function horasDoDia() {
  return Array.from({ length: 24 }, (_, hora) => `${String(hora).padStart(2, "0")}h`);
}

function csrfPortal() {
  return (document.body.dataset.csrf || "").trim();
}

function atualizarFaixaVista(vista) {
  const faixa = document.getElementById("faixa-vista");
  if (!faixa) return;
  if (document.body.dataset.perfil !== "administrador") {
    faixa.hidden = true;
    faixa.classList.remove("ativa");
    return;
  }
  const valor = vista && vista.valor != null ? String(vista.valor) : (document.body.dataset.vista || "");
  const rotulo = (vista && vista.rotulo) || "";
  if (!valor) {
    faixa.hidden = true;
    faixa.classList.remove("ativa");
    faixa.innerHTML = "";
    document.body.dataset.vista = "";
    return;
  }
  document.body.dataset.vista = valor;
  faixa.hidden = false;
  faixa.classList.add("ativa");
  faixa.innerHTML = `Vista do portal: <strong>${escapar(rotulo || valor)}</strong> · <a href="/">alterar no início</a>`;
}

async function aplicarVistaPortal(valor) {
  const corpo = new URLSearchParams();
  corpo.set("csrf", csrfPortal());
  corpo.set("vista", valor == null ? "" : String(valor));
  const resp = await fetch("/vista", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: corpo,
  });
  const pacote = await resp.json().catch(() => ({}));
  if (!resp.ok || !pacote.ok) {
    throw new Error((pacote && pacote.erro) || "Não foi possível aplicar a vista.");
  }
  atualizarFaixaVista(pacote.vista_portal || { valor: String(valor || "") });
  if ((location.pathname || "").indexOf("/painel/cameras") >= 0) {
    location.reload();
    return pacote;
  }
  if (typeof ciclo === "function") await ciclo();
  return pacote;
}

function montarSegmentadorInicio(tela, dados) {
  if (document.body.dataset.perfil !== "administrador") return;
  let caixa = document.getElementById("segmentador-portal");
  const vista = (dados && dados.vista_portal) || {};
  const opcoes = Array.isArray(vista.opcoes) ? vista.opcoes : [];
  if (!caixa) {
    caixa = document.createElement("section");
    caixa.id = "segmentador-portal";
    caixa.className = "cartao segmentador-portal";
    caixa.innerHTML = `<label class="campo-lista">Segmentar dados do portal
<select id="vista-portal-sel" title="Segmentar dados do portal"></select>
</label>
<p class="estado" id="vista-portal-estado"></p>`;
    if (tela.firstChild) tela.insertBefore(caixa, tela.firstChild);
    else tela.appendChild(caixa);
    const sel = caixa.querySelector("#vista-portal-sel");
    sel.addEventListener("change", async () => {
      const estado = document.getElementById("vista-portal-estado");
      try {
        if (estado) estado.textContent = "Aplicando…";
        sel.disabled = true;
        await aplicarVistaPortal(sel.value);
        if (estado) estado.textContent = "Vista aplicada em todo o portal.";
      } catch (erro) {
        if (estado) estado.textContent = erro.message || "Falha ao aplicar a vista.";
      } finally {
        sel.disabled = false;
      }
    });
  }
  const sel = document.getElementById("vista-portal-sel");
  const estado = document.getElementById("vista-portal-estado");
  if (sel && (!sel.dataset.pronto || sel.options.length <= 1)) {
    sel.innerHTML = (opcoes.length ? opcoes : [
      { valor: "", rotulo: "Geral (toda a instalação)" },
      { valor: "__admin__", rotulo: "Somente câmeras do administrador" },
    ]).map((item) => `<option value="${escapar(item.valor)}">${escapar(item.rotulo)}</option>`).join("");
    sel.dataset.pronto = "1";
  }
  if (sel && vista.valor != null) sel.value = String(vista.valor || "");
  if (estado && vista.rotulo) estado.textContent = `Ativo: ${vista.rotulo}`;
  atualizarFaixaVista(vista);
}

function inicio(tela, dados) {
  // v5: segmentador admin + matches/comportamentos em vermelho
  if (tela.dataset.pronto !== "inicio-v5") {
    const blocos = [
      ["pessoa", "Pessoas hoje", "periodos.dia.Pessoa"],
      ["pessoa", "Pessoas no mês", "periodos.mes.Pessoa"],
      ["pessoa", "Pessoas acumulado", "periodos.total.Pessoa"],
      ["alerta", "Comportamentos hoje", "periodos.dia.Comportamento"],
      ["veiculo", "Veículos hoje", "periodos.dia.Veiculo"],
      ["veiculo", "Veículos no mês", "periodos.mes.Veiculo"],
      ["veiculo", "Veículos acumulado", "periodos.total.Veiculo"],
      ["pessoa", "Match de pessoa hoje", "periodos.dia.MatchFace"],
      ["animal", "Animais hoje", "periodos.dia.Animal"],
      ["animal", "Animais no mês", "periodos.mes.Animal"],
      ["animal", "Animais acumulado", "periodos.total.Animal"],
      ["veiculo", "Match de placa hoje", "periodos.dia.MatchPlaca"],
    ];
    tela.innerHTML = `<section class="cartoes">${blocos.map((item) => cartao(item[0], item[1], item[2])).join("")}</section>
      <section class="cartao"><h2>Movimento do dia</h2><canvas class="grafico" id="movimento"></canvas></section>`;
    tela.dataset.pronto = "inicio-v5";
  }
  montarSegmentadorInicio(tela, dados);
  const dias = dados.serie_dias || [];
  linha(document.getElementById("movimento"), seriesClasse(dias, (nome) => dias.map((dia) => Number(dia[nome] || 0))), dias.map((dia) => dia.rotulo || ""), "dias");
}

function contagens(tela, dados) {
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<section class="cartoes">
      ${cartao("pessoa", "Pessoas hoje", "periodos.dia.Pessoa")}
      ${cartao("veiculo", "Veículos hoje", "periodos.dia.Veiculo")}
      ${cartao("animal", "Animais hoje", "periodos.dia.Animal")}
      ${cartao("camera", "Objetos hoje", "periodos.dia.Objeto")}
    </section>
    <div id="periodo-contagens"></div>
    <article class="cartao"><h2>Mapa das câmeras</h2><iframe class="mapa mapa-folium" id="mapa-contagens" title="Mapa das câmeras" src="/mapa/folha"></iframe><div id="legenda-contagens"></div></article>
    <section class="grade">
      <article class="cartao"><h2>Últimos dias</h2><div class="graos" data-grafico="dias">${botoesGrao("dia")}</div><canvas class="grafico" id="dias"></canvas><div id="legenda-dias"></div></article>
      <article class="cartao"><h2>Histórico do dia</h2><div class="graos" data-grafico="horas">${botoesGrao("hora")}</div><canvas class="grafico" id="horas"></canvas></article>
    </section>`;
    tela.dataset.pronto = "1";
    tela.querySelectorAll(".graos").forEach((grupo) => {
      grupo.addEventListener("click", (evento) => {
        const botao = evento.target.closest("button[data-grao]");
        if (!botao) return;
        grupo.querySelectorAll("button").forEach((item) => item.classList.remove("ativo"));
        botao.classList.add("ativo");
        if (ultimoDados) contagens(tela, ultimoDados);
      });
    });
  }
  const hoje = new Date();
  const fimPadrao = isoLocal(hoje);
  const inicioPadrao = isoLocal(new Date(hoje.getTime() - 6 * 86400000));
  const datas = (dados.cubo || []).map((item) => numeroDia(item.d)).filter((item) => item != null);
  const minimo = datas.length ? Math.min(...datas) : numeroDia(inicioPadrao);
  const maximo = datas.length ? Math.max(...datas) : numeroDia(fimPadrao);
  ligarPeriodo(document.getElementById("periodo-contagens"), minimo, maximo, inicioPadrao, fimPadrao);
  const periodo = document.getElementById("periodo-contagens");
  const graoDias = document.querySelector("[data-grafico=dias] button.ativo")?.dataset.grao || "dia";
  const graoHoras = document.querySelector("[data-grafico=horas] button.ativo")?.dataset.grao || "hora";
  const filtrado = periodo && periodo.dataset.mexeu === "1";
  const ini = (periodo && periodo.dataset.ini) || inicioPadrao;
  const fim = (periodo && periodo.dataset.fim) || fimPadrao;
  const baldeDias = (filtrado || graoDias !== "dia") ? agregarContagens(dados, ini, fim, graoDias) : null;
  const baldeHoras = (filtrado || graoHoras !== "hora") ? agregarContagens(dados, ini, fim, graoHoras) : null;
  const pontos = pontosGeo(dados, "itens").map((ponto) => {
    if (!filtrado) return ponto;
    const total = (dados.cubo || []).filter((item) => item.c === ponto.nome && dentro(item.d, ini, fim)).reduce((soma, item) => soma + Number(item.n || 0), 0);
    return { ...ponto, valor: total };
  });
  enviarMapa("mapa-contagens", pontos, null);
  document.getElementById("legenda-contagens").innerHTML = legendaCameras(pontos.map((ponto) => ponto.nome));
  const diasFonte = baldeDias || dados.dias_empilhados || [];
  const cameras = barrasEmpilhadas(document.getElementById("dias"), diasFonte, { fonte: 12 });
  document.getElementById("legenda-dias").innerHTML = legendaCameras(cameras || []);
  if (baldeHoras) {
    linha(document.getElementById("horas"), seriesClasse(baldeHoras, (nome) => somarClasse(baldeHoras, nome)), baldeHoras.map((item) => item.rotulo), graoHoras, { fonte: 16 });
  } else {
    const horas = dados.horas || {};
    linha(document.getElementById("horas"), seriesClasse(horas, (nome) => horas[nome] || []), horasDoDia(), "horas", { fonte: 16 });
  }
  ["Pessoa", "Veiculo", "Animal", "Objeto"].forEach((classe) => {
    const el = document.querySelector(`[data-num="periodos.dia.${classe}"]`);
    if (!el) return;
    if (!filtrado) {
      delete el.dataset.travado;
      return;
    }
    const total = (dados.cubo || []).filter((item) => item.k === classe && dentro(item.d, ini, fim)).reduce((soma, item) => soma + Number(item.n || 0), 0);
    el.dataset.travado = "1";
    el.textContent = String(total);
  });
}

function comportamento(tela, dados) {
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<section class="cartoes">
      ${cartao("alerta", "Comportamentos hoje", "periodos.dia.Comportamento")}
      ${cartao("alerta", "No mês", "periodos.mes.Comportamento")}
      ${cartao("alerta", "Acumulado", "periodos.total.Comportamento")}
    </section>
    <section class="grade">
      <article class="cartao"><h2>Tipo de comportamento</h2><div id="tipos"></div></article>
      <article class="cartao"><h2>Prioridade</h2><canvas class="grafico grafico-rosca" id="rosca"></canvas><div id="legenda-risco"></div></article>
    </section>
    <article class="cartao"><h2>Prioridade ao longo das horas</h2><canvas class="grafico" id="horas-prioridade"></canvas></article>
    <section class="grade">
      <article class="cartao"><h2>Mapa dos comportamentos</h2><iframe class="mapa mapa-folium" id="mapa-comp" title="Mapa dos comportamentos" src="/mapa/folha"></iframe></article>
      <article class="cartao"><h2>Leitura do risco</h2><div id="frase-comp" class="leitura"></div></article>
    </section>
    <article class="cartao"><h2>Últimas ocorrências do aplicativo</h2><div id="app"></div></article>`;
    tela.dataset.pronto = "1";
  }
  document.getElementById("tipos").innerHTML = tiposHtml(dados.tipos);
  rosca(document.getElementById("rosca"), dados.riscos || {});
  const ordem = ["Informativo", "Atencao", "Prioritario", "Critico"];
  document.getElementById("legenda-risco").innerHTML = `<div class="legenda-linha">${ordem.map((nome) => `<span><b style="background:${CORES_RISCO[nome]}"></b>${NOME_RISCO[nome]} ${Number((dados.riscos || {})[nome] || 0)}</span>`).join("")}</div>`;
  const prioridade = dados.horas_prioridade || {};
  linha(
    document.getElementById("horas-prioridade"),
    ["Comportamento", "Interacao", "Alerta"].map((nome) => ({
      nome: NOME_FAIXA[nome],
      cor: CORES_FAIXA[nome],
      valores: prioridade[nome] || [],
    })),
    horasDoDia(),
    "horas",
    { fonte: 16 },
  );
  const pontos = pontosGeo(dados, "comportamento");
  enviarMapa("mapa-comp", pontos, { pisca: true });
  const frases = (dados.cameras_vivo || [])
    .filter((camera) => camera.risco && camera.risco !== "branco" && camera.frase)
    .map((camera) => camera.frase);
  document.getElementById("frase-comp").innerHTML = frases.length
    ? frases.map((frase) => `<p>${escapar(frase)}</p>`).join("")
    : "<p>Sem comportamento de risco agora.</p>";
  const app = (dados.app || []).slice(0, 6);
  document.getElementById("app").innerHTML = app.length
    ? app.map((item) => `<p><strong>${escapar(item.quando)}</strong><br>${escapar(item.titulo)} · ${escapar(item.lugar)}</p>`).join("")
    : "<p>Sem ocorrência informada pelo aplicativo.</p>";
}

function fotos(ref, agora) {
  return `<div class="rostos">
    <figure><img alt="Referência" src="${ref}" onerror="this.style.display='none'"><figcaption>Referência</figcaption></figure>
    <figure><img alt="Agora" src="${agora}" onerror="this.style.display='none'"><figcaption>Agora</figcaption></figure>
  </div>`;
}

function alertas(tela, dados) {
  if (tela.dataset.pronto !== "alertas-rf-v2") {
    tela.innerHTML = `<section class="coluna"><div>
      <article class="cartao" id="comparacao"></article>
      <article class="cartao"><h2>Últimos alertas</h2><div id="historico"></div></article>
      <article class="cartao"><h2>Mapa de rastreamento de pessoa de interesse</h2>
        <div id="caixa-rf-alertas" class="caixa-rf">
          <label>Pessoas de interesse<select id="sel-rf-alertas" multiple></select></label>
          <p>Selecione uma ou várias pessoas para rastrear as câmeras por onde passaram. A seta segue a rota de trânsito pelas vias.</p>
        </div>
        <iframe class="mapa mapa-folium" id="mapa-rf-alertas" title="Mapa de rastreamento" src="/mapa/folha"></iframe>
        <div id="legenda-rf-alertas"></div>
      </article>
      <article class="cartao"><h2>Pessoa na área</h2><div id="frase-face" class="leitura"></div></article>
    </div>
    <aside class="cartao"><h2>Quem mais passa</h2><div id="faces"></div></aside></section>`;
    tela.dataset.pronto = "alertas-rf-v2";
    const selAlertas = document.getElementById("sel-rf-alertas");
    if (selAlertas) {
      selAlertas.addEventListener("change", () => {
        if (ultimoDados) alertas(tela, ultimoDados);
      });
    }
  }
  const match = dados.match || null;
  const chaveMatch = match ? `${match.id}|${match.taxa}|${match.passagens}|${match.risco}|${match.narracao_ia || match.narracao || ""}` : "";
  const comparacao = document.getElementById("comparacao");
  if (comparacao.dataset.chave !== chaveMatch) {
    const avisoRisco = match && match.risco
      ? `<p><span class="luz-alerta"></span> Atenção, Pessoa de risco na área!</p>`
      : (match ? `<p><span class="luz-info"></span> Presença informativa na área.</p>` : "");
    if (match) {
      comparacao.className = `cartao sobe${match.risco ? "" : " verde"}`;
      comparacao.innerHTML = `${avisoRisco}<h2>${escapar(match.nome || match.id)}</h2>
        <p>Código ${escapar(match.id || "")} · similaridade ${Number(match.taxa || 0).toFixed(2)} · reapareceu ${match.passagens || 0} vezes · ${escapar(match.camera || "")}</p>
        ${fotos(`/img/match-ref.jpg?t=${Date.now()}`, `/img/match-agora.jpg?t=${Date.now()}`)}
        <p>${escapar(match.narracao_ia || match.narracao || "")}</p>`;
    } else {
      comparacao.className = "cartao";
      comparacao.innerHTML = "<h2>Comparação</h2><p>Nenhuma pessoa de interesse na câmera neste momento.</p>";
    }
    comparacao.dataset.chave = chaveMatch;
  }
  const historico = (dados.historico || []).slice(0, 4);
  const chaveHist = historico.map((item) => `${item.quando}|${item.id}|${item.taxa}`).join(";");
  const caixaHist = document.getElementById("historico");
  if (caixaHist.dataset.chave !== chaveHist) {
    caixaHist.innerHTML = historico.map((item) => {
      const nome = item.nome || item.id || "";
      const codigo = item.id || "";
      return `<div class="alerta-linha">
      <div><strong class="titulo-alerta">${escapar(item.tipo || "")} ${escapar(nome)}</strong><span class="nome-alerta">${escapar(codigo)}</span>
      <p>${escapar(item.quando)} · ${escapar(item.rotulo || "SIM")} ${Number(item.taxa || 0).toFixed(2)} · ${escapar(codigo)} · ${escapar(item.camera || "")}</p></div>
      ${fotos(`${item.ref}?t=${encodeURIComponent(item.quando)}`, `${item.agora}?t=${encodeURIComponent(item.quando)}`)}
    </div>`;
    }).join("") || "<p>Nenhum alerta de rosto ou placa ainda.</p>";
    caixaHist.dataset.chave = chaveHist;
  }
  const selRf = document.getElementById("sel-rf-alertas");
  popularSelRf(selRf, dados.pessoas_interesse || []);
  const rastros = rastrosRfFiltrados(dados, selRf);
  enviarMapaRf("mapa-rf-alertas", rastros, {
    sel: selRf,
    assinaturaDados: assinaturaPontosRf(dados.rastros_rf || []),
  });
  atualizarLegendaRf("legenda-rf-alertas", rastros, selRf);
  const texto = match
    ? (match.risco
      ? `Pessoa de risco na área. ${match.narracao_ia || match.narracao || "O movimento aparece quando o rosto é acompanhado."}`
      : `Presença informativa na área. ${match.narracao_ia || match.narracao || "Morador ou pessoa sem classificação de risco."}`)
    : "Nenhuma pessoa de interesse na área agora.";
  document.getElementById("frase-face").textContent = texto;
  document.getElementById("faces").innerHTML = barras((dados.passagens || []).map((item) => ({
    id: item.id, nome: item.nome, rotulo: item.id, total: item.total,
  })));
}

function faixaFluxo(minuto) {
  if (minuto > 10) return "vermelho";
  if (minuto >= 4) return "amarelo";
  return "verde";
}

function arco(cx, cy, raio, a0, a1) {
  const p = (angulo) => [cx + raio * Math.cos(angulo), cy + raio * Math.sin(angulo)];
  const [x0, y0] = p(a0);
  const [x1, y1] = p(a1);
  const grande = a1 - a0 > Math.PI ? 1 : 0;
  return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${raio} ${raio} 0 ${grande} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}

function svgTacho(chave, rotulo) {
  const inicio = (150 * Math.PI) / 180;
  const fim = ((150 + 240) * Math.PI) / 180;
  const verde = inicio + (4 / 12) * (fim - inicio);
  const amarelo = inicio + (10 / 12) * (fim - inicio);
  return `<div class="tacho" data-agulha="${escapar(chave)}">
    <svg viewBox="0 0 200 150">
      <path d="${arco(100, 108, 72, inicio, verde)}" fill="none" stroke="#3ddc97" stroke-width="14"/>
      <path d="${arco(100, 108, 72, verde, amarelo)}" fill="none" stroke="#ffb020" stroke-width="14"/>
      <path d="${arco(100, 108, 72, amarelo, fim)}" fill="none" stroke="#ff3b3b" stroke-width="14"/>
      <line class="agulha" x1="100" y1="108" x2="46" y2="139" stroke="#3ddc97" stroke-width="3" stroke-linecap="round"/>
      <circle cx="100" cy="108" r="5" fill="#f4f7fb"/>
      <text class="marca" x="100" y="96" text-anchor="middle" fill="#f4f7fb" font-size="20">0</text>
    </svg>
    <p>${rotulo}</p>
  </div>`;
}

function fileiraFluxo(camera) {
  const nome = escapar(camera.nome);
  const relogios = [
    ["pessoa", "segundo", "Pessoas / s", 2],
    ["pessoa", "minuto", "Pessoas / min", 12],
    ["pessoa", "hora", "Pessoas / h", 120],
    ["veiculo", "segundo", "Veículos / s", 2],
    ["veiculo", "minuto", "Veículos / min", 12],
    ["veiculo", "hora", "Veículos / h", 120],
  ];
  return `<article class="cartao"><div class="fileira-fluxo">
    <h2>Monitor de Fluxo: ${nome}</h2>
    ${relogios.map(([tipo, faixa, rotulo]) => svgTacho(`${camera.nome}|${tipo}|${faixa}`, rotulo)).join("")}
    <div class="termo" data-termo="${nome}"><div class="tubo"><i></i></div><p>Risco</p></div>
  </div></article>`;
}

function desenharAgulha(artigo, graus) {
  const rad = (graus * Math.PI) / 180;
  const agulha = artigo.querySelector(".agulha");
  if (!agulha) return;
  agulha.setAttribute("x2", (100 + Math.cos(rad) * 62).toFixed(1));
  agulha.setAttribute("y2", (108 + Math.sin(rad) * 62).toFixed(1));
}

function posicionarAgulha(artigo, valor, topo) {
  const limitado = Math.max(0, Math.min(Number(valor) || 0, topo));
  artigo._alvo = 150 + (limitado / topo) * 240;
  if (artigo._atual == null) artigo._atual = artigo._alvo;
  const fracao = (Number(valor) || 0) / topo;
  const cor = fracao > 0.84 ? "#ff3b3b" : fracao >= 0.4 ? "#ffb020" : "#3ddc97";
  const agulha = artigo.querySelector(".agulha");
  if (agulha) agulha.setAttribute("stroke", cor);
  const marca = artigo.querySelector(".marca");
  if (marca) marca.textContent = String(Math.round(Number(valor) || 0));
}

function risco(tela, dados) {
  const cameras = dados.cameras_vivo || [];
  const assinatura = `risco-v4|${cameras.map((camera) => camera.nome).join("|")}`;
  if (tela.dataset.pronto !== assinatura) {
    tela.innerHTML = `<article class="cartao"><p id="voz" class="voz branco"></p></article>
    <div id="odometros">${cameras.map((camera) => fileiraFluxo(camera)).join("") || "<p>Nenhuma câmera em análise.</p>"}</div>
    <article class="cartao"><h2>Mapa de risco</h2><iframe class="mapa mapa-folium" id="mapa-risco" title="Mapa de risco" src="/mapa/folha"></iframe></article>
    <article class="cartao"><h2>Telemetria</h2><canvas class="grafico" id="esteira"></canvas></article>
    <section class="grade">
      <article class="cartao"><h2>Memórias de rua</h2><div id="memorias"></div></article>
      <article class="cartao"><h2>Últimos informes</h2><p id="relatorio"></p><div id="informes-risco"></div></article>
    </section>
    <section class="grade tres">
      <article class="cartao"><h2>Resumo</h2><p id="resumo" class="leitura"></p></article>
      <article class="cartao"><h2>Assessoramento</h2><p id="assessoramento" class="leitura"></p></article>
      <article class="cartao"><h2>Aprendizado</h2><p id="aprendizado" class="leitura"></p></article>
    </section>
    <article class="cartao" id="subida"></article>`;
    tela.dataset.pronto = assinatura;
  }
  const voz = document.getElementById("voz");
  if (voz) {
    const texto = String(dados.voz || "").trim();
    const silencio = !texto || /área está em observação|area esta em observacao|nenhum risco acima|a área está|a area esta/i.test(texto);
    // Em silêncio o card dinâmico fica em branco — não mantém a última mensagem.
    voz.textContent = silencio ? "" : texto;
    voz.className = "voz " + ((silencio ? "branco" : dados.led) || "branco");
  }
  const topos = { segundo: 2, minuto: 12, hora: 120 };
  cameras.forEach((camera) => {
    [["pessoa", camera.fluxo || {}], ["veiculo", camera.fluxo_veiculo || {}]].forEach(([tipo, fluxo]) => {
      ["segundo", "minuto", "hora"].forEach((faixa) => {
        const artigo = document.querySelector(`[data-agulha="${CSS.escape(`${camera.nome}|${tipo}|${faixa}`)}"]`);
        if (artigo) posicionarAgulha(artigo, fluxo[faixa] || 0, topos[faixa]);
      });
    });
    const termo = document.querySelector(`[data-termo="${CSS.escape(camera.nome)}"] i`);
    const altura = { branco: "18%", verde: "32%", amarelo: "46%", vermelho: "74%", preto: "100%" }[camera.risco] || "18%";
    const cor = COR_LED[camera.risco] || "#f4f7fb";
    if (termo) {
      termo.style.height = altura;
      termo.style.background = cor;
    }
  });
  enviarMapa("mapa-risco", pontosGeo(dados, "itens").map((ponto) => ({ ...ponto, valor: 1 })), { pisca: true, fixo: true });
  const pontos = dados.serie || [];
  const rotulos = pontos.map((ponto) => new Date((ponto.t || 0) * 1000).toTimeString().slice(0, 8));
  const series = ["Pessoa", "Animal", "Veiculo", "Objeto"].map((nome) => ({
    nome: NOME_CLASSE[nome],
    cor: CORES[nome],
    valores: pontos.map((ponto) => Number(ponto[nome] || 0)),
  }));
  if (pontos.some((ponto) => ponto.Risco)) {
    series.push({ nome: "Risco", cor: "#ff3b3b", teto: true, valores: pontos.map((ponto) => (ponto.Risco ? 1 : 0)) });
  }
  linha(document.getElementById("esteira"), series, rotulos.map((rotulo) => String(rotulo).slice(0, 5)), "tempo", { fonte: 16 });
  const memorias = document.getElementById("memorias");
  if (memorias) {
    memorias.innerHTML = (dados.memorias || []).map((item) => `<p><strong>${escapar(item.quando)}</strong><br>${escapar(item.texto)}</p>`).join("") || "<p>Sem memória registrada.</p>";
  }
  const relatorio = document.getElementById("relatorio");
  if (relatorio) relatorio.textContent = dados.relatorio || "";
  const caixaInforme = document.getElementById("informes-risco");
  if (caixaInforme) {
    caixaInforme.innerHTML = (dados.informes || []).map((item) => {
      const texto = `${item.descricao || item.tipo || ""}`;
      const baixo = texto.toLowerCase();
      let cor = "branco";
      if (dados.led === "preto" || /disparo|arma/.test(baixo)) cor = "preto";
      else if (/briga|queda|interesse|risco|alerta/.test(baixo)) cor = "vermelho";
      else if (/deitad|intera|suspeito|áudio|audio/.test(baixo)) cor = "amarelo";
      else if (dados.led === "verde" || /morador|visitante|prestador/.test(baixo)) cor = "verde";
      return `<p class="informe ${cor}"><strong>${escapar(item.quando)}</strong><br>${escapar(texto)}</p>`;
    }).join("") || "<p>Nenhum informe enviado.</p>";
  }
  const resumo = document.getElementById("resumo");
  if (resumo) resumo.textContent = dados.resumo || "O relatório do dia ainda não tem resumo. O agente grava este texto no fechamento do dia.";
  const assessoramento = document.getElementById("assessoramento");
  if (assessoramento) assessoramento.textContent = dados.assessoramento || "O assessoramento entra no relatório, com a conclusão de risco e a orientação do período.";
  const aprendizado = document.getElementById("aprendizado");
  if (aprendizado) aprendizado.textContent = dados.aprendizado || "O aprendizado da rua entra quando o relatório fecha o dia.";
  const subida = document.getElementById("subida");
  const match = dados.match;
  const chaveSubida = match ? `${match.id}|${match.taxa}|${match.passagens}|${match.risco}|${match.narracao_ia || match.narracao || ""}` : "";
  if (subida && subida.dataset.chave !== chaveSubida) {
    if (match) {
      subida.className = `cartao sobe${match.risco ? "" : " verde"}`;
      subida.innerHTML = match.risco
        ? `<p><span class="luz-alerta"></span> Pessoa de risco detectada</p>
        <h2>${escapar(match.nome || match.id)}</h2>
        <p>Similaridade ${Number(match.taxa || 0).toFixed(2)} · reapareceu ${match.passagens || 0} vezes</p>
        <div class="rostos"><figure><img alt="" src="/img/match-agora.jpg?t=${Date.now()}"></figure></div>
        <p>${escapar(match.narracao_ia || match.narracao || "")}</p>`
        : `<p><span class="luz-info"></span> Presença informativa</p>
        <h2>${escapar(match.nome || match.id)}</h2>
        <p>Similaridade ${Number(match.taxa || 0).toFixed(2)} · reapareceu ${match.passagens || 0} vezes</p>
        <div class="rostos"><figure><img alt="" src="/img/match-agora.jpg?t=${Date.now()}"></figure></div>
        <p>${escapar(match.narracao_ia || match.narracao || "Morador ou pessoa sem classificação de risco.")}</p>`;
    } else {
      subida.className = "cartao";
      subida.innerHTML = "<h2>Match</h2><p>O cartão sobe quando uma pessoa cadastrada reaparece.</p>";
    }
    subida.dataset.chave = chaveSubida;
  }
}

function vivo(_tela, _dados) {
  // Ao vivo: só a imagem das câmeras — sem cards de contagem/placar.
}

function pontosDo(dados) {
  const periodo = document.querySelector("button[data-periodo].ativo")?.dataset.periodo
    || document.body.dataset.periodo
    || "mes";
  const hoje = new Date();
  const iso = (data) => data.toISOString().slice(0, 10);
  let corte = "0000-00-00";
  if (periodo === "dia") corte = iso(hoje);
  if (periodo === "semana") corte = iso(new Date(hoje.getTime() - 6 * 86400000));
  if (periodo === "mes") corte = iso(new Date(hoje.getTime() - 29 * 86400000));
  return (dados.pontos || []).filter((ponto) => !ponto.data || ponto.data >= corte);
}

function desenhoAtual() {
  return document.querySelector("button[data-desenho].ativo")?.dataset.desenho || "pontos";
}

function linhasApp(dados) {
  const base = (dados.app_linhas && dados.app_linhas.length) ? dados.app_linhas : (dados.pontos || []);
  const periodo = document.getElementById("periodo-mapas");
  const ini = periodo && periodo.dataset.ini;
  const fim = periodo && periodo.dataset.fim;
  if (!ini || !fim) return base;
  return base.filter((item) => dentro(item.data, ini, fim));
}

function contarCampo(linhas, campo) {
  const totais = {};
  linhas.forEach((item) => {
    const chave = String(item[campo] || "").trim() || "Sem informação";
    totais[chave] = (totais[chave] || 0) + 1;
  });
  return Object.entries(totais).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([rotulo, total], indice) => ({
    rotulo, chave: rotulo, dimensao: campo, total, cor: CORES_CAMERA[indice % CORES_CAMERA.length],
  }));
}

function mapas(tela, dados) {
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<div id="periodo-mapas"></div>
      <div class="faixa"><button type="button" id="btn-rf-lpr" data-rf="0">RF e LPR</button></div>
      <div id="caixa-rf" class="caixa-rf oculta">
        <label>Pessoas de interesse<select id="sel-rf" multiple></select></label>
        <p>Selecione uma ou várias pessoas para rastrear as câmeras por onde passaram.</p>
      </div>
      <article class="cartao"><h2>Mancha criminal</h2><iframe class="mapa-folium" id="mapa" title="Mancha criminal" src="/mapa/folha"></iframe><div id="legenda"></div></article>
      <article class="cartao"><h2>Ocorrências por dia da semana</h2><canvas class="grafico" id="semana-app"></canvas><div id="legenda-semana"></div></article>
      <section class="grade">
        <article class="cartao"><h2>Por hora do dia</h2><canvas class="grafico" id="hora-app"></canvas><div id="legenda-hora"></div></article>
        <article class="cartao"><h2>Por natureza</h2><canvas class="grafico grafico-rosca" id="rosca-app"></canvas></article>
      </section>
      <section class="grade">
        <article class="cartao"><h2>Por logradouro</h2><canvas class="grafico" id="rua-app"></canvas><div id="legenda-rua"></div></article>
        <article class="cartao"><h2>Por bairro</h2><canvas class="grafico" id="bairro-app"></canvas><div id="legenda-bairro"></div></article>
      </section>
      <article class="cartao"><h2>Por cidade</h2><canvas class="grafico" id="cidade-app"></canvas><div id="legenda-cidade"></div></article>`;
    tela.dataset.pronto = "1";
    document.querySelectorAll("button[data-periodo],button[data-desenho]").forEach((botao) => {
      botao.addEventListener("click", () => {
        document.querySelectorAll(`button[data-${botao.dataset.periodo ? "periodo" : "desenho"}]`).forEach((item) => item.classList.remove("ativo"));
        botao.classList.add("ativo");
        if (botao.dataset.periodo) {
          const hoje = new Date();
          const fim = isoLocal(hoje);
          const dias = botao.dataset.periodo === "dia" ? 0 : botao.dataset.periodo === "semana" ? 6 : 29;
          const inicio = isoLocal(new Date(hoje.getTime() - dias * 86400000));
          const host = document.getElementById("periodo-mapas");
          if (host && host._definir) host._definir(inicio, fim);
        }
        const corpo = new URLSearchParams();
        if (botao.dataset.periodo) corpo.set("periodo", botao.dataset.periodo);
        if (botao.dataset.desenho) corpo.set("desenho", botao.dataset.desenho);
        fetch("/comando", { method: "POST", body: corpo, headers: { "Content-Type": "application/x-www-form-urlencoded" } });
        if (ultimoDados) mapas(tela, ultimoDados);
      });
    });
    const mes = document.querySelector('button[data-periodo="mes"]');
    const pontos = document.querySelector('button[data-desenho="pontos"]');
    if (mes) mes.classList.add("ativo");
    if (pontos) pontos.classList.add("ativo");
    const botaoRf = document.getElementById("btn-rf-lpr");
    const caixaRf = document.getElementById("caixa-rf");
    const selRf = document.getElementById("sel-rf");
    if (botaoRf) {
      botaoRf.addEventListener("click", () => {
        const ativo = botaoRf.dataset.rf === "1";
        botaoRf.dataset.rf = ativo ? "0" : "1";
        botaoRf.classList.toggle("ativo", !ativo);
        if (caixaRf) caixaRf.classList.toggle("oculta", ativo);
        if (ultimoDados) mapas(tela, ultimoDados);
      });
    }
    if (selRf) {
      selRf.addEventListener("change", () => {
        if (ultimoDados) mapas(tela, ultimoDados);
      });
    }
  }
  const selRf = document.getElementById("sel-rf");
  popularSelRf(selRf, dados.pessoas_interesse || []);
  const modoRf = document.getElementById("btn-rf-lpr")?.dataset.rf === "1";
  const base = (dados.app_linhas && dados.app_linhas.length) ? dados.app_linhas : (dados.pontos || []);
  const datas = base.map((item) => numeroDia(item.data)).filter((item) => item != null);
  const hojeNum = numeroDia(isoLocal(new Date()));
  const minimo = datas.length ? Math.min(...datas) : hojeNum - 29;
  const maximo = datas.length ? Math.max(hojeNum, ...datas) : hojeNum;
  ligarPeriodo(document.getElementById("periodo-mapas"), minimo, maximo, isoDe(minimo), isoDe(maximo));
  const linhas = linhasApp(dados);
  const tipos = {};
  linhas.forEach((ponto) => { tipos[ponto.natureza || ponto.tipo || "Ocorrência"] = (tipos[ponto.natureza || ponto.tipo || "Ocorrência"] || 0) + 1; });
  const legenda = document.getElementById("legenda");
  if (modoRf) {
    const rastros = rastrosRfFiltrados(dados, selRf);
    enviarMapaRf("mapa", rastros, {
      sel: selRf,
      assinaturaDados: assinaturaPontosRf(dados.rastros_rf || []),
    });
    atualizarLegendaRf("legenda", rastros, selRf);
  } else {
  const lista = linhas.map((ponto) => {
    const lat = Number(ponto.lat);
    const lon = Number(ponto.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    return {
      ...ponto,
      lat,
      lon,
      nome: ponto.natureza || ponto.tipo || "Ocorrência",
      valor: 1,
      cor: `hsl(${(Array.from(String(ponto.natureza || ponto.tipo || "")).reduce((s, c) => s + c.charCodeAt(0), 0) * 17) % 360} 70% 48%)`,
    };
  }).filter(Boolean);
  enviarMapa("mapa", lista, { desenho: desenhoAtual(), semRotulo: true });
  if (legenda) {
    const textoTipos = Object.entries(tipos).map(([tipo, total]) => `${tipo}: ${total}`).join(" · ");
    legenda.textContent = lista.length
      ? `${lista.length} ponto(s) no mapa · ${textoTipos}`
      : (textoTipos || "Sem ocorrência do aplicativo neste período.");
  }
  }
  const semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"].map((rotulo) => ({ rotulo, cameras: {} }));
  const nomes = [];
  linhas.forEach((item) => {
    const numero = numeroDia(item.data);
    if (numero == null) return;
    const indice = (new Date(numero * 86400000).getUTCDay() + 6) % 7;
    const camera = item.camera || "Sem câmera";
    if (!nomes.includes(camera)) nomes.push(camera);
    const slot = semana[indice].cameras[camera] || (semana[indice].cameras[camera] = { Pessoa: 0 });
    slot.Pessoa += 1;
  });
  const antigo = CLASSES.slice();
  try {
    CLASSES.splice(0, CLASSES.length, "Pessoa");
    barrasEmpilhadas(document.getElementById("semana-app"), semana, { fonte: 15 });
  } finally {
    CLASSES.splice(0, CLASSES.length, ...antigo);
  }
  const caixaSemana = document.getElementById("legenda-semana");
  if (caixaSemana) caixaSemana.innerHTML = legendaCameras(nomes);
  const nomesNatureza = Object.keys(tipos);
  const horasEmpilhadas = Array.from({ length: 24 }, (_, hora) => {
    const cameras = {};
    linhas.forEach((item) => {
      if (Number(item.hora) !== hora) return;
      const natureza = item.natureza || item.tipo || "Ocorrência";
      const slot = cameras[natureza] || (cameras[natureza] = { Pessoa: 0 });
      slot.Pessoa += 1;
    });
    return { rotulo: `${String(hora).padStart(2, "0")}h`, cameras };
  }).filter((item) => Object.keys(item.cameras).length);
  const ruasGrafico = contarCampo(linhas, "rua");
  const bairrosGrafico = contarCampo(linhas, "bairro");
  const cidadesGrafico = contarCampo(linhas, "cidade");
  const naturezasGrafico = Object.entries(tipos).map(([nome, total], indice) => ({
    nome, rotulo: nome, chave: nome, dimensao: "natureza", total, cor: CORES_CAMERA[indice % CORES_CAMERA.length],
  }));
  const antigoHora = CLASSES.slice();
  try {
    CLASSES.splice(0, CLASSES.length, "Pessoa");
    barrasEmpilhadas(document.getElementById("hora-app"), horasEmpilhadas, { fonte: 12 });
  } finally {
    CLASSES.splice(0, CLASSES.length, ...antigoHora);
  }
  barrasVerticais(document.getElementById("rua-app"), ruasGrafico);
  barrasVerticais(document.getElementById("bairro-app"), bairrosGrafico);
  barrasVerticais(document.getElementById("cidade-app"), cidadesGrafico);
  roscaLivre(document.getElementById("rosca-app"), naturezasGrafico);
  const caixaHora = document.getElementById("legenda-hora");
  if (caixaHora) caixaHora.innerHTML = legendaCameras(nomesNatureza);
  const legendas = {
    "legenda-rua": ruasGrafico,
    "legenda-bairro": bairrosGrafico,
    "legenda-cidade": cidadesGrafico,
  };
  Object.entries(legendas).forEach(([id, itens]) => {
    const caixa = document.getElementById(id);
    if (caixa) caixa.innerHTML = legendaBarras(itens);
  });
}

function legendaBarras(itens) {
  const visiveis = (itens || []).filter((item) => item.total);
  if (!visiveis.length) return "";
  return `<div class="legenda-linha">${visiveis.map((item) => `<span><b style="background:${item.cor || "#4c8dff"}"></b>${escapar(item.rotulo || item.nome || "")}</span>`).join("")}</div>`;
}

function nivelAudioClasse(item) {
  const nivel = Number(item.nivel || 0);
  if (nivel >= 3 || item.risco) return "risco";
  if (nivel >= 2) return "atencao";
  return "";
}

function nuvemHtml(itens, ranking) {
  const risco = new Set((ranking || []).map((item) => String(item.rotulo || "").split(":").pop()));
  const lista = itens || [];
  if (!lista.length) return "<p>Sem palavras ainda nesta câmera.</p>";
  const maior = Math.max(1, ...lista.map((item) => Number(item.total) || 0));
  return `<div class="nuvem-audio">${lista.map((item) => {
    const total = Number(item.total) || 0;
    const tamanho = 12 + Math.round((total / maior) * 22);
    const classe = risco.has(String(item.rotulo || "")) ? "risco" : "";
    return `<span class="${classe}" style="font-size:${tamanho}px">${escapar(item.rotulo)} <small>${total}</small></span>`;
  }).join("")}</div>`;
}

function rankingAudioHtml(itens) {
  const lista = itens || [];
  if (!lista.length) return "<p>Nenhuma palavra de risco ranqueada.</p>";
  const maior = Math.max(1, ...lista.map((item) => Number(item.total) || 0));
  return `<div class="rank-audio">${lista.map((item) => {
    const total = Number(item.total) || 0;
    const pct = Math.max(8, Math.round((total / maior) * 100));
    const rotulo = String(item.rotulo || "").replace(":", " · ");
    return `<div class="barra"><div><strong>${escapar(rotulo)}</strong><div class="trilha"><i style="width:${pct}%"></i></div></div><span>${total}</span></div>`;
  }).join("")}</div>`;
}

function audio(tela, dados) {
  const pacote = dados.audio || {};
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<article class="cartao"><h2>Esteira de transcrição</h2><div id="esteira-audio" class="esteira-audio"></div></article>
      <article class="cartao"><h2>Nuvem e ranking de risco por câmera</h2><div id="nuvens-audio"></div></article>`;
    tela.dataset.pronto = "1";
  }
  const esteira = pacote.esteira || [];
  const caixa = document.getElementById("esteira-audio");
  if (caixa) {
    caixa.innerHTML = esteira.map((item) => {
      const cats = String(item.categoria || "").split(",").filter(Boolean)
        .map((cat) => `<span class="selo-audio-cat">${escapar(cat)}</span>`).join("");
      return `<div class="linha-audio ${nivelAudioClasse(item)}">
        <div class="meta"><strong>${escapar(item.camera || "")}</strong><br>${escapar(item.quando || "")}<br>${cats || "<span class='selo-audio-cat'>transcrição</span>"}</div>
        <div><p class="texto">${escapar(item.texto || item.detalhe || "Evento de áudio")}</p>
        ${(item.palavras || []).length ? `<p class="meta">Risco: ${escapar((item.palavras || []).join(", "))}</p>` : ""}</div>
      </div>`;
    }).join("") || "<p>Aguardando áudio das câmeras. A esteira sobe conforme a escuta e a transcrição.</p>";
  }
  const nuvens = document.getElementById("nuvens-audio");
  if (nuvens) {
    const cameras = pacote.cameras || {};
    const nomes = Object.keys(cameras);
    nuvens.innerHTML = nomes.map((nome) => {
      const bloco = cameras[nome] || {};
      return `<section style="margin-top:18px">
        <h3 style="margin:0 0 8px">${escapar(nome)}</h3>
        ${nuvemHtml(bloco.nuvem || [], bloco.ranking_risco || [])}
        <h4 style="margin:14px 0 6px;font-size:14px;color:var(--mudo)">Ranking de risco</h4>
        ${rankingAudioHtml(bloco.ranking_risco || [])}
      </section>`;
    }).join("") || "<p>Sem nuvem ainda. Quando houver fala nas câmeras, as palavras aparecem aqui.</p>";
  }
}

function serieSimples(itens, cor) {
  return [{
    nome: "serie",
    cor: cor || "#4c8dff",
    valores: (itens || []).map((item) => Number(item.valor || 0)),
  }];
}

async function sistema(tela) {
  if (tela.dataset.pronto !== "sistema-v3") {
    tela.innerHTML = `<section class="cartao" style="margin-bottom:14px">
<label>Segmentação por cliente
<select id="sis-cliente"><option value="">Cluster total (clientes + administrador)</option></select>
</label>
<p id="sis-cliente-info" style="color:var(--mudo);margin:.6rem 0 0"></p>
</section>
<section class="cartoes" id="sistema-cards"></section>
<section class="grade">
<article class="cartao"><h2>Tabelas no Postgres</h2><div id="sistema-tabelas"><p>Carregando…</p></div></article>
<article class="cartao"><h2>Host agora</h2><div id="sistema-agora"><p>Carregando…</p></div></article>
</section>
<section class="grade tres">
<article class="cartao"><h2>Crescimento diário (MB dados)</h2><canvas class="grafico" id="sis-diario"></canvas></article>
<article class="cartao"><h2>Crescimento mensal (MB)</h2><canvas class="grafico" id="sis-mensal"></canvas></article>
<article class="cartao"><h2>Acumulado 90 dias (MB)</h2><canvas class="grafico" id="sis-acumulado"></canvas></article>
</section>
<section class="grade tres">
<article class="cartao"><h2>CPU diária (%)</h2><canvas class="grafico" id="sis-cpu"></canvas></article>
<article class="cartao"><h2>RAM diária (%)</h2><canvas class="grafico" id="sis-ram"></canvas></article>
<article class="cartao"><h2>Disco do sistema (MB)</h2><canvas class="grafico" id="sis-disco"></canvas></article>
</section>
<section class="grade">
<article class="cartao"><h2>GPT · custo diário (USD)</h2><canvas class="grafico" id="sis-gpt-usd"></canvas></article>
<article class="cartao"><h2>GPT · tokens/unidades diários</h2><canvas class="grafico" id="sis-gpt-tok"></canvas></article>
</section>
<section class="grade">
<article class="cartao"><h2>Custos GPT por cliente (mês)</h2><div id="sistema-custos-cli"><p>Carregando…</p></div></article>
<article class="cartao"><h2>Espaço em nuvem</h2><div id="sistema-nuvem"><p>Preparando medição por cliente…</p></div></article>
</section>`;
    tela.dataset.pronto = "sistema-v3";
    const sel = document.getElementById("sis-cliente");
    if (sel && !sel._sisBound) {
      sel._sisBound = true;
      sel.addEventListener("change", () => {
        tela._sisQuando = 0;
        sistema(tela);
      });
    }
  }
  if (tela._sisBusy) return;
  const agoraMs = Date.now();
  if (tela._sisQuando && agoraMs - tela._sisQuando < 8000) return;
  tela._sisBusy = true;
  try {
    const sel = document.getElementById("sis-cliente");
    const filtro = sel ? String(sel.value || "") : "";
    const resposta = await fetch(`/sistema.json?documento=${encodeURIComponent(filtro)}`);
    if (!resposta.ok) throw new Error("sem acesso");
    const pacote = await resposta.json();
    tela._sisQuando = agoraMs;
    if (sel && !sel.dataset.opcoes) {
      const opts = ['<option value="">Cluster total (clientes + administrador)</option>'].concat(
        (pacote.clientes || []).map((c) =>
          `<option value="${escapar(c.documento)}">${escapar(c.nome || c.documento)} · ${escapar(c.documento)}</option>`
        )
      );
      sel.innerHTML = opts.join("");
      sel.dataset.opcoes = "1";
      if (filtro) sel.value = filtro;
    }
    const info = document.getElementById("sis-cliente-info");
    const cli = pacote.cliente;
    const cluster = pacote.cluster || {};
    if (info) {
      info.textContent = cli
        ? `Computador/escopo do cliente ${cli.nome || cli.documento}: página filtrada (${cli.cameras || 0} câmera(s), fatia ~${Math.round((Number(cli.fator) || 0) * 100)}% do host, ~${Number(cli.mb_estimado_local || 0).toLocaleString("pt-BR")} MB).`
        : `${cluster.rotulo || "Cluster total"}: ${cluster.clientes || 0} conta(s), ${cluster.cameras || 0} câmera(s). Sem seleção = soma de todo o cluster.`;
    }
    const agora = pacote.agora || {};
    const custos = pacote.custos || {};
    const pref = cli ? "Cliente · " : "Cluster · ";
    const cards = document.getElementById("sistema-cards");
    if (cards) {
      cards.innerHTML = [
        [pref + "dados (MB)", agora.tabelas_mb || pacote.total_armazenado_mb || 0, "#4c8dff"],
        [pref + "CPU %", agora.cpu_pct || 0, "#ff8c28"],
        [pref + "RAM %", agora.ram_pct || 0, "#aa3cb4"],
        [pref + "disco (MB)", agora.disco_usado_mb || 0, "#28c4dc"],
        [pref + "GPT USD (mês)", custos.openai_usd_mes || 0, "#3ddc97"],
        [pref + "GPT tokens (mês)", custos.openai_tokens_mes || 0, "#ffb020"],
      ].map(([rotulo, valor, cor]) =>
        `<article class="cartao"><span style="color:${cor} !important">${rotulo}</span><strong style="color:${cor} !important">${Number(valor).toLocaleString("pt-BR")}</strong></article>`
      ).join("");
    }
    const tabela = document.getElementById("sistema-tabelas");
    if (tabela) {
      const linhas = (pacote.tabelas || []).map((item) =>
        `<tr><td>${escapar(item.tabela)}</td><td>${Number(item.linhas || 0).toLocaleString("pt-BR")}</td><td>${Number(item.mb || 0).toLocaleString("pt-BR")} MB</td></tr>`
      ).join("");
      tabela.innerHTML = `<table><tr><th>Tabela</th><th>Linhas</th><th>Tamanho</th></tr>${linhas || "<tr><td colspan='3'>Sem Postgres ou sem tabelas.</td></tr>"}</table>`;
    }
    const host = document.getElementById("sistema-agora");
    if (host) {
      const tituloHost = cli ? `Host do cliente (estimativa ${Math.round((Number(cli.fator) || 0) * 100)}%)` : "Host do cluster";
      host.innerHTML = `<p><strong>${escapar(tituloHost)}</strong></p>
        <p>CPU ${agora.cpu_pct || 0}% · RAM ${agora.ram_pct || 0}% (${agora.ram_usada_mb || 0} / ${agora.ram_total_mb || 0} MB)</p>
        <p>Disco ${agora.disco_usado_mb || 0} / ${agora.disco_total_mb || 0} MB · Dados nas tabelas ${agora.tabelas_mb || 0} MB</p>
        <p style="color:var(--mudo)">Amostra ${escapar(agora.quando || "")} · escopo ${escapar(pacote.escopo || "")}</p>`;
    }
    const custosCli = document.getElementById("sistema-custos-cli");
    if (custosCli) {
      const lista = custos.por_cliente_mes || [];
      if (filtro) {
        custosCli.innerHTML = `<p>Filtro ${escapar(filtro)} · GPT mês: USD ${Number(custos.openai_usd_mes || 0).toLocaleString("pt-BR")} · tokens ${Number(custos.openai_tokens_mes || 0).toLocaleString("pt-BR")}</p>
          <p>Total canais no mês: USD ${Number(custos.total_usd_mes || 0).toLocaleString("pt-BR")}</p>`;
      } else {
        const linhas = lista.map((item) =>
          `<tr><td>${escapar(item.documento)}</td><td>${Number(item.unidades || 0).toLocaleString("pt-BR")}</td><td>${Number(item.usd || 0).toLocaleString("pt-BR")}</td></tr>`
        ).join("");
        custosCli.innerHTML = `<table><tr><th>CPF/CNPJ</th><th>Tokens/unid.</th><th>USD</th></tr>${linhas || "<tr><td colspan='3'>Sem uso GPT registrado neste mês.</td></tr>"}</table>`;
      }
    }
    const nuvem = document.getElementById("sistema-nuvem");
    if (nuvem) {
      const n = pacote.nuvem || {};
      nuvem.innerHTML = `<p><strong>Status:</strong> ${escapar(n.status || "preparado")}</p>
        <p>Usado: ${n.usado_mb == null ? "—" : Number(n.usado_mb).toLocaleString("pt-BR") + " MB"} · Cota: ${n.cota_mb == null ? "—" : Number(n.cota_mb).toLocaleString("pt-BR") + " MB"}</p>
        <p style="color:var(--mudo)">${escapar(n.aviso || "Medição de nuvem por cliente em preparação.")}</p>`;
    }
    linha(document.getElementById("sis-diario"), serieSimples(pacote.crescimento_diario, "#4c8dff"), (pacote.crescimento_diario || []).map((i) => i.rotulo), "dias");
    linha(document.getElementById("sis-mensal"), serieSimples(pacote.crescimento_mensal, "#148ceb"), (pacote.crescimento_mensal || []).map((i) => i.rotulo), "meses");
    linha(document.getElementById("sis-acumulado"), serieSimples(pacote.crescimento_acumulado, "#3ddc97"), (pacote.crescimento_acumulado || []).map((i) => i.rotulo), "dias");
    linha(document.getElementById("sis-cpu"), serieSimples(pacote.cpu_diario, "#ff8c28"), (pacote.cpu_diario || []).map((i) => i.rotulo), "dias");
    linha(document.getElementById("sis-ram"), serieSimples(pacote.ram_diario, "#aa3cb4"), (pacote.ram_diario || []).map((i) => i.rotulo), "dias");
    linha(document.getElementById("sis-disco"), serieSimples(pacote.disco_diario, "#28c4dc"), (pacote.disco_diario || []).map((i) => i.rotulo), "dias");
    linha(document.getElementById("sis-gpt-usd"), serieSimples(custos.gpt_usd_diario, "#3ddc97"), (custos.gpt_usd_diario || []).map((i) => i.rotulo), "dias");
    linha(document.getElementById("sis-gpt-tok"), serieSimples(custos.gpt_tokens_diario, "#ffb020"), (custos.gpt_tokens_diario || []).map((i) => i.rotulo), "dias");
  } catch (erro) {
    const tabela = document.getElementById("sistema-tabelas");
    if (tabela) tabela.innerHTML = "<p class='aviso'>Não foi possível carregar o monitor. Confirme o perfil administrador.</p>";
  } finally {
    tela._sisBusy = false;
  }
}

const render = { inicio, contagens, comportamento, alertas, mapas, risco, vivo, audio, sistema };

function pulsar() {
  document.querySelectorAll("[data-agulha]").forEach((artigo) => {
    if (artigo._alvo == null) return;
    const atual = artigo._atual == null ? artigo._alvo : artigo._atual;
    artigo._atual = atual + (artigo._alvo - atual) * 0.12;
    desenharAgulha(artigo, artigo._atual);
  });
  requestAnimationFrame(pulsar);
}
requestAnimationFrame(pulsar);

async function ciclo() {
  let dados;
  try {
    const resposta = await fetch("/dados.json");
    if (!resposta.ok) return;
    dados = await resposta.json();
  } catch (erro) {
    return;
  }
  ultimoDados = dados;
  const led = document.getElementById("led");
  if (dados.vista_portal) atualizarFaixaVista(dados.vista_portal);
  atualizarSelosNav(dados);
  if (window.atualizarStive) window.atualizarStive(dados);
  atualizarFalaStive(dados);
  atualizarAlertaRfFlutuante(dados);
  if (led) led.className = "led " + (dados.led || "branco");
  const tela = document.getElementById("tela");
  const vista = dadosComFiltro(dados);
  if (tela && render[tela.dataset.tela]) {
    if (tela.dataset.tela === "sistema") render.sistema(tela);
    else render[tela.dataset.tela](tela, vista);
  }
  animar(vista);
  prepararVisualizacoes(tela);
  if (tela && tela.dataset.tela === "vivo" && !document.querySelector(".video")) {
    setTimeout(() => location.reload(), 2000);
  }
}

const SELOS_NAV = {
  stive: { id: "selo-stive", path: "/painel/stive" },
  alertas: { id: "selo-alertas", path: "/painel/3" },
  risco: { id: "selo-risco", path: "/painel/risco" },
  audio: { id: "selo-audio", path: "/painel/audio" },
};

function caminhoAtual() {
  return (location.pathname || "/").replace(/\/$/, "") || "/";
}

function chaveSeloStorage(tipo) {
  return `selo-visto-${tipo}`;
}

function lerChavesSelo(tipo) {
  try {
    const bruto = JSON.parse(sessionStorage.getItem(chaveSeloStorage(tipo)) || "null");
    return Array.isArray(bruto) ? bruto.map(String) : null;
  } catch (erro) {
    return null;
  }
}

function gravarChavesSelo(tipo, chaves) {
  try {
    sessionStorage.setItem(chaveSeloStorage(tipo), JSON.stringify((chaves || []).slice(-300)));
  } catch (erro) {}
}

function eventosSelo(tipo, dados) {
  if (tipo === "stive") {
    return (dados.pendencias || []).map((item) => `pend:${item.id}`);
  }
  if (tipo === "alertas") {
    const chaves = (dados.historico || []).map(
      (item) => `hist:${item.quando || ""}|${item.id || ""}|${item.taxa || ""}|${item.camera || ""}`,
    );
    if (dados.match && dados.match.id) {
      chaves.push(`match:${dados.match.id}|${dados.match.taxa || ""}|${dados.match.risco ? 1 : 0}|${dados.match.camera || ""}`);
    }
    return chaves;
  }
  if (tipo === "audio") {
    return ((dados.audio || {}).alertas || []).map(
      (item) => `audio:${item.quando || ""}|${item.camera || ""}|${item.categoria || ""}|${item.texto || item.detalhe || ""}`,
    );
  }
  if (tipo === "risco") {
    const chaves = [];
    if (["amarelo", "vermelho", "preto"].includes(dados.led)) chaves.push(`led:${dados.led}`);
    const voz = String(dados.voz || "").trim();
    if (voz) chaves.push(`voz:${voz.slice(0, 120)}`);
    (dados.cameras_vivo || []).forEach((camera) => {
      if (camera.fluxo_anormal) chaves.push(`fluxo:${camera.nome || ""}`);
      (camera.permanencias || []).forEach((frase) => chaves.push(`perm:${camera.nome}|${frase}`));
    });
    return chaves;
  }
  return [];
}

function tipoSeloDaRota(path) {
  const atual = (path || caminhoAtual()).replace(/\/$/, "") || "/";
  return Object.keys(SELOS_NAV).find((tipo) => SELOS_NAV[tipo].path.replace(/\/$/, "") === atual) || "";
}

function marcarSeloVisto(tipo, dados) {
  if (!tipo) return;
  gravarChavesSelo(tipo, eventosSelo(tipo, dados || ultimoDados || {}));
  const el = document.getElementById((SELOS_NAV[tipo] || {}).id || "");
  if (el) {
    el.hidden = true;
    el.textContent = "";
  }
}

function novosDoSelo(tipo, dados) {
  const atuais = eventosSelo(tipo, dados);
  // Na própria tela: marca tudo como visto e não mostra selo.
  if (tipoSeloDaRota() === tipo) {
    gravarChavesSelo(tipo, atuais);
    return 0;
  }
  const vistos = lerChavesSelo(tipo);
  // Primeira carga da sessão: baseline sem notificar o que já existe.
  if (vistos == null) {
    gravarChavesSelo(tipo, atuais);
    return 0;
  }
  const base = new Set(vistos);
  return atuais.filter((chave) => !base.has(chave)).length;
}

function atualizarSelosNav(dados) {
  Object.keys(SELOS_NAV).forEach((tipo) => {
    const el = document.getElementById(SELOS_NAV[tipo].id);
    if (!el) return;
    const total = novosDoSelo(tipo, dados);
    el.hidden = !total;
    if (!total) {
      el.textContent = "";
      return;
    }
    el.textContent = tipo === "risco" && total === 1 ? "!" : String(total);
  });
}

function iniciarSelosNav() {
  if (document.body.dataset.selosProntos) return;
  document.body.dataset.selosProntos = "1";
  document.querySelectorAll("aside nav a[href]").forEach((link) => {
    const href = (link.getAttribute("href") || "").replace(/\/$/, "") || "/";
    const tipo = Object.keys(SELOS_NAV).find((nome) => SELOS_NAV[nome].path.replace(/\/$/, "") === href);
    if (!tipo) return;
    link.addEventListener("click", () => {
      marcarSeloVisto(tipo, ultimoDados);
    });
  });
  const tipoAtual = tipoSeloDaRota();
  if (tipoAtual && ultimoDados) marcarSeloVisto(tipoAtual, ultimoDados);
}

ciclo();
setInterval(ciclo, 1500);
iniciarSelosNav();

function csrfDoBalao() {
  const form = document.getElementById("form-balao") || document.getElementById("form-stive");
  const campo = form && form.querySelector("[name=csrf]");
  return campo ? campo.value : "";
}

async function confirmarPendencia(botao) {
  const corpo = new URLSearchParams();
  corpo.set("csrf", csrfDoBalao());
  corpo.set("id", botao.dataset.id || "");
  corpo.set("resposta", botao.dataset.resp || "");
  corpo.set("tipo", botao.dataset.tipo || "");
  corpo.set("camera", botao.dataset.camera || "");
  corpo.set("texto", botao.dataset.texto || "");
  const resposta = await fetch("/agente/stive/confirmar", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: corpo,
  });
  return resposta.json().catch(() => ({}));
}

const filaFalaStive = [];
const falasVistas = new Set();
let falandoStive = false;
let falaAtivaStive = null;
function chaveFalaAtiva() {
  return `stive-fala-ativa:${usuarioStive()}`;
}

function chaveFalaVivo() {
  return `stive-fala-vivo:${usuarioStive()}`;
}

function piscarStive() {
  const avatar = document.querySelector("#abrir-stive");
  if (!avatar) return;
  avatar.classList.remove("falando");
  void avatar.offsetWidth;
  avatar.classList.add("falando");
  setTimeout(() => avatar.classList.remove("falando"), 1200);
}

function linkAoVivoHtml() {
  return linkFalaHtml({ linkHref: "/painel/cameras", linkTexto: "Visualize ao vivo" });
}

function linkFalaHtml(item) {
  const href = (item && item.linkHref) || (item && item.linkVivo ? "/painel/cameras" : "");
  if (!href) return "";
  const texto = (item && item.linkTexto) || (href.indexOf("/cameras") >= 0 ? "Visualize ao vivo" : "Acompanhe na tela...");
  return `<p class="link-vivo"><a href="${escapar(href)}" data-stive-link="1" data-stive-destino="${escapar(href)}">${escapar(texto)}</a></p>`;
}

function salvarFalaAtiva(item) {
  falaAtivaStive = item || null;
  try {
    if (item) sessionStorage.setItem(chaveFalaAtiva(), JSON.stringify(item));
    else sessionStorage.removeItem(chaveFalaAtiva());
  } catch (erro) {}
}

function lerFalaAtiva() {
  if (falaAtivaStive) return falaAtivaStive;
  try {
    const bruto = JSON.parse(sessionStorage.getItem(chaveFalaAtiva()) || "null");
    if (bruto && bruto.texto) {
      falaAtivaStive = bruto;
      return bruto;
    }
  } catch (erro) {}
  return null;
}

function mereceLinkAoVivo(texto, opcoes) {
  if (opcoes && (opcoes.linkHref || opcoes.linkTexto)) return false;
  if (opcoes && opcoes.linkVivo === false) return false;
  if (opcoes && opcoes.linkVivo) return true;
  const tipo = String((opcoes && opcoes.tipo) || "").toLowerCase();
  if (tipo === "pendencia" || tipo === "pessoa" || tipo === "veiculo" || tipo === "veículo") return true;
  if (tipo === "fluxo") return false;
  const classe = String((opcoes && opcoes.classe) || "").toLowerCase();
  if (classe === "risco" || classe === "pergunta") return true;
  const baixo = String(texto || "").toLowerCase();
  if (/fluxo de pessoas fora do normal/.test(baixo)) return false;
  return /parada|parado|permanece|veícul|veicul|pessoa|risco|disparo|briga|queda|atenção|atencao|confirma/.test(baixo);
}

function acoesFalaHtml(item) {
  const extra = item.html || "";
  const like = `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M2 20h4V9H2v11zm20-9c0-1.1-.9-2-2-2h-6.3l.9-4.4.1-.9c0-.4-.2-.8-.4-1.1L13.2 1 6.6 7.6C6.2 8 6 8.5 6 9v9c0 1.1.9 2 2 2h8c.8 0 1.5-.5 1.8-1.2l3-7c.1-.3.2-.5.2-.8v-2z"/></svg>`;
  const dislike = `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M22 4h-4v11h4V4zM2 13c0 1.1.9 2 2 2h6.3l-.9 4.4-.1.9c0 .4.2.8.4 1.1L10.8 23l6.6-6.6c.4-.4.6-.9.6-1.4V6c0-1.1-.9-2-2-2H8c-.8 0-1.5.5-1.8 1.2l-3 7c-.1.3-.2.5-.2.8v2z"/></svg>`;
  return `${extra}<div class="acoes-fala">
    <button type="button" class="btn-icone" data-reacao="1" title="Gostei" aria-label="Gostei" data-chave="${escapar(item.chave || "")}" data-titulo="${escapar(item.titulo || "")}" data-texto="${escapar(item.texto || "")}" data-tipo="${escapar(item.tipo || "")}">${like}</button>
    <button type="button" class="btn-icone" data-reacao="-1" title="Não gostei" aria-label="Não gostei" data-chave="${escapar(item.chave || "")}" data-titulo="${escapar(item.titulo || "")}" data-texto="${escapar(item.texto || "")}" data-tipo="${escapar(item.tipo || "")}">${dislike}</button>
    <button type="button" data-fechar="1" data-chave="${escapar(item.chave || "")}" data-titulo="${escapar(item.titulo || "")}" data-texto="${escapar(item.texto || "")}" data-tipo="${escapar(item.tipo || "")}">Fechar</button>
  </div>`;
}

function mostrarFalaHq(item) {
  const caixa = document.getElementById("fala-hq");
  if (!caixa || !item) return;
  const classe = item.classe || "";
  caixa.hidden = false;
  caixa.dataset.travado = "1";
  caixa.className = `fala-hq sobe${classe ? ` ${classe}` : ""}`;
  const comLinkVivo = !!item.linkVivo && !item.linkHref;
  const link = item.linkHref || comLinkVivo ? linkFalaHtml(item.linkHref ? item : { linkHref: "/painel/cameras", linkTexto: "Visualize ao vivo" }) : "";
  caixa.innerHTML = `<strong>${escapar(item.titulo || "Stive")}</strong><p>${escapar(item.texto || "")}</p>${link}${acoesFalaHtml(item)}`;
  falandoStive = true;
  salvarFalaAtiva(item);
  piscarStive();
}

function enfileirarFalaStive(chave, titulo, texto, opcoes) {
  if (!chave || !texto || falasVistas.has(chave)) return false;
  // Um assunto por vez: não empilha informe + disparo + confirmação juntos.
  if (falandoStive || filaFalaStive.length || lerFalaAtiva()) return false;
  falasVistas.add(chave);
  if (falasVistas.size > 80) {
    const antigo = falasVistas.values().next().value;
    falasVistas.delete(antigo);
  }
  filaFalaStive.push({
    chave,
    titulo: titulo || "Stive",
    texto,
    tipo: (opcoes && opcoes.tipo) || "",
    classe: (opcoes && opcoes.classe) || "",
    html: (opcoes && opcoes.html) || "",
    linkVivo: mereceLinkAoVivo(texto, opcoes),
    linkHref: (opcoes && opcoes.linkHref) || "",
    linkTexto: (opcoes && opcoes.linkTexto) || "",
  });
  processarFilaFalaStive();
  return true;
}

function processarFilaFalaStive() {
  if (falandoStive || lerFalaAtiva()) return;
  const caixa = document.getElementById("fala-hq");
  if (!caixa) return;
  const item = filaFalaStive.shift();
  if (!item) {
    caixa.hidden = true;
    caixa.innerHTML = "";
    caixa.dataset.travado = "";
    return;
  }
  mostrarFalaHq(item);
}

function restaurarFalaStive() {
  const item = lerFalaAtiva();
  if (!item) return;
  mostrarFalaHq(item);
  // Após clicar no hiperlink, aguarda visualização da tela destino e fecha.
  try {
    const destino = sessionStorage.getItem(chaveFalaVivo()) || "";
    if (destino && destino !== "visto" && location.pathname.replace(/\/$/, "") === destino.replace(/\/$/, "")) {
      sessionStorage.setItem(chaveFalaVivo(), "visto");
      setTimeout(() => {
        if (sessionStorage.getItem(chaveFalaVivo()) === "visto") fecharFalaStive();
      }, 5000);
    }
  } catch (erro) {}
}

function chavesFalaBase(dados) {
  const chaves = [];
  const voz = String(dados.voz || "").trim();
  if (voz) chaves.push(`voz:${voz}`);
  (dados.informes || []).forEach((item) => {
    const textoBase = String(item.descricao || item.tipo || "").trim();
    if (textoBase) chaves.push(`inf:${item.quando}|${textoBase}`);
  });
  (dados.app || []).forEach((item) => {
    chaves.push(`app:${item.quando}|${String(item.titulo || "Ocorrência").trim()}|${item.lugar || ""}`);
  });
  (dados.insights || []).forEach((item) => {
    const texto = String(item.descricao || item.nome || "").trim();
    if (texto) chaves.push(`ins:${item.quando}|${texto}`);
  });
  (dados.pendencias || []).forEach((item) => chaves.push(`pend:${item.id}`));
  if (dados.match) chaves.push(`match:${dados.match.id}|${dados.match.taxa}|${dados.match.risco}`);
  ((dados.audio || {}).alertas || []).forEach((item) => {
    const trecho = String(item.texto || item.detalhe || item.categoria || "").trim();
    if (trecho) chaves.push(`audio:${item.quando}|${item.camera}|${trecho}`);
  });
  (dados.cameras_vivo || []).forEach((camera) => {
    if (camera.fluxo_anormal) {
      chaves.push(`fluxo:${camera.nome}:${Math.floor(Date.now() / 120000)}`);
    }
  });
  return chaves;
}

let ultimaVozBaixaEm = 0;

function vozDeBaixoRisco(dados, voz) {
  const led = dados.led || "branco";
  if (led === "amarelo" || led === "vermelho" || led === "preto") return false;
  const baixo = String(voz || "").toLowerCase();
  return /observação|observacao|nenhum risco|sem comportamento de risco|área está|area esta|tranquila|ronda/.test(baixo) || !baixo;
}

function falarFluxoAnormalStive(dados) {
  const cameras = dados.cameras_vivo || [];
  for (const camera of cameras) {
    if (!camera.fluxo_anormal) continue;
    const nome = camera.nome || "câmera";
    const minuto = Number((camera.fluxo || {}).minuto || 0);
    const chave = `fluxo:${nome}:${Math.floor(Date.now() / 120000)}`;
    const texto = `Fluxo de pessoas fora do normal identificado na ${nome}${minuto ? ` (${minuto}/min)` : ""}.`;
    if (enfileirarFalaStive(chave, "Fluxo anormal", texto, {
      tipo: "fluxo",
      classe: "risco",
      linkVivo: false,
      linkHref: "/painel/risco",
      linkTexto: "Acompanhe na tela...",
    })) return true;
  }
  return false;
}

function falarVozStive(dados) {
  const voz = String(dados.voz || "").trim();
  if (!voz) return;
  const classe = dados.led === "verde" ? "info" : (dados.led === "branco" ? "" : "risco");
  if (vozDeBaixoRisco(dados, voz)) {
    const agora = Date.now();
    if (agora - ultimaVozBaixaEm < 10 * 60 * 1000) return;
    ultimaVozBaixaEm = agora;
    enfileirarFalaStive(`voz:baixa:${Math.floor(agora / 600000)}`, "Detector de risco", voz, { classe, linkVivo: false });
    return;
  }
  enfileirarFalaStive(`voz:${voz}`, "Detector de risco", voz, { classe, linkVivo: true });
}

function atualizarFalaStive(dados) {
  if (!document.getElementById("fala-hq")) return;
  if (!window._stiveBasePronto) {
    chavesFalaBase(dados).forEach((chave) => falasVistas.add(chave));
    window._stiveBasePronto = true;
    restaurarFalaStive();
    return;
  }
  // Já há um balão ativo (inclusive restaurado da sessão) ou na fila: não mistura assuntos.
  if (falandoStive || filaFalaStive.length || lerFalaAtiva()) return;

  const pendencias = dados.pendencias || [];
  if (pendencias[0]) {
    const item = pendencias[0];
    enfileirarFalaStive(
      `pend:${item.id}`,
      "O que está acontecendo?",
      item.texto || "Confirma esta situação?",
      {
        tipo: "pendencia",
        classe: "pergunta",
        linkVivo: true,
        html: `<div class="pendencia"><span>
          <button type="button" data-id="${escapar(item.id)}" data-resp="sim" data-tipo="${escapar(item.tipo || "")}" data-camera="${escapar(item.camera || "")}" data-texto="${escapar(item.texto || "")}">Sim</button>
          <button type="button" data-id="${escapar(item.id)}" data-resp="nao" data-tipo="${escapar(item.tipo || "")}" data-camera="${escapar(item.camera || "")}" data-texto="${escapar(item.texto || "")}">Não</button>
        </span></div>`,
      },
    );
    return;
  }

  for (const item of (dados.informes || []).slice(0, 6)) {
    const textoBase = String(item.descricao || item.tipo || "").trim();
    if (!textoBase) continue;
    const baixo = textoBase.toLowerCase();
    const camera = item.camera ? ` na ${item.camera}` : "";
    let fala = `Atenção a ${textoBase}${camera}.`;
    if (/e-?mail|enviad/.test(baixo) || String(item.origem || "").toLowerCase().includes("email")) {
      fala = /disparo|tiro|arma/.test(baixo)
        ? `Enviei um alerta para o seu e-mail sobre este disparo${camera}.`
        : `Enviei um alerta para o seu e-mail${camera}: ${textoBase}`;
    } else if (/disparo|tiro/.test(baixo)) {
      fala = `Atenção a disparo${camera}. ${textoBase}`;
    }
    if (enfileirarFalaStive(`inf:${item.quando}|${textoBase}`, "Informe", fala, { classe: "risco" })) return;
  }

  for (const item of (dados.app || []).slice(0, 3)) {
    const titulo = String(item.titulo || "Ocorrência").trim();
    if (enfileirarFalaStive(
      `app:${item.quando}|${titulo}|${item.lugar || ""}`,
      "Aplicativo",
      `Ocorrência nova lançada no app: ${titulo}${item.lugar ? ` em ${item.lugar}` : ""}.`,
      { classe: "info" },
    )) return;
  }

  for (const item of (dados.insights || []).slice(0, 3)) {
    const texto = String(item.descricao || item.nome || "").trim();
    if (!texto) continue;
    if (enfileirarFalaStive(`ins:${item.quando}|${texto}`, "Insight", texto, { classe: "info" })) return;
  }

  // Fluxo anormal de pessoas → Detector de risco.
  if (falarFluxoAnormalStive(dados)) return;

  // Match RF sobe na lâmina; voz só se não houver outro assunto pendente.
  falarVozStive(dados);
}

async function enviarReacaoStive(botao, nota) {
  const corpo = new URLSearchParams();
  corpo.set("csrf", csrfDoBalao());
  corpo.set("chave", botao.dataset.chave || "");
  corpo.set("titulo", botao.dataset.titulo || "");
  corpo.set("texto", botao.dataset.texto || "");
  corpo.set("tipo", botao.dataset.tipo || "");
  corpo.set("nota", String(nota));
  await fetch("/agente/stive/reacao", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: corpo,
  }).catch(() => ({}));
}

function fecharFalaStive() {
  const caixa = document.getElementById("fala-hq");
  if (caixa) {
    caixa.hidden = true;
    caixa.innerHTML = "";
    caixa.dataset.travado = "";
  }
  falandoStive = false;
  salvarFalaAtiva(null);
  try {
    sessionStorage.removeItem(chaveFalaVivo());
  } catch (erro) {}
  processarFilaFalaStive();
}

let ultimoMatchRfToast = "";
let timerRfToast = null;

function caixaAlertaRf() {
  let caixa = document.getElementById("alerta-rf-flutuante");
  if (caixa) {
    // Garante que fica no body (esquerda da tela), fora do balão do Stive.
    if (caixa.parentElement !== document.body) document.body.appendChild(caixa);
    return caixa;
  }
  caixa = document.createElement("div");
  caixa.id = "alerta-rf-flutuante";
  caixa.className = "alerta-rf-flutuante";
  caixa.hidden = true;
  document.body.appendChild(caixa);
  return caixa;
}

function atualizarAlertaRfFlutuante(dados) {
  const caixa = caixaAlertaRf();
  if (!caixa) return;
  const match = dados.match;
  if (!match || !match.id) return;
  const chave = `${match.id}|${Number(match.taxa || 0).toFixed(2)}|${match.risco ? 1 : 0}|${match.camera || ""}`;
  if (chave === ultimoMatchRfToast) return;
  window._rfToastPronto = true;
  ultimoMatchRfToast = chave;
  const risco = !!match.risco;
  const t = Date.now();
  if (timerRfToast) clearTimeout(timerRfToast);
  caixa.hidden = false;
  caixa.classList.remove("fechando", "descendo", "risco", "info");
  void caixa.offsetWidth;
  caixa.className = `alerta-rf-flutuante${risco ? " risco" : " info"}`;
  caixa.innerHTML = `
    <strong>${risco ? "Alerta RF / LPR" : "Presença informativa"}</strong>
    <div class="rf-fotos">
      <figure><img alt="Referência" src="/img/match-ref.jpg?t=${t}" onerror="this.style.opacity=.35"><figcaption>Referência</figcaption></figure>
      <figure><img alt="Detectada" src="/img/match-agora.jpg?t=${t}" onerror="this.style.opacity=.35"><figcaption>Detectada</figcaption></figure>
    </div>
    <p class="rf-meta"><b>${escapar(match.nome || "Sem nome")}</b> · código ${escapar(match.id || "")}<br>
    Similaridade ${Number(match.taxa || 0).toFixed(2)} · ${escapar(match.camera || "")}</p>
    <span class="rf-link">Abrir Alertas de RF e LPR →</span>`;
  caixa.onclick = () => { window.location.href = "/painel/3"; };
  timerRfToast = setTimeout(() => {
    caixa.classList.add("fechando");
    setTimeout(() => {
      if (!caixa.classList.contains("fechando")) return;
      caixa.hidden = true;
      caixa.classList.remove("fechando");
      caixa.innerHTML = "";
      caixa.onclick = null;
    }, 650);
  }, 9000);
}

function iniciarFalaStive() {
  if (document.body.dataset.falaPronta) return;
  document.body.dataset.falaPronta = "1";
  const caixa = document.getElementById("fala-hq");
  if (!caixa) return;
  restaurarFalaStive();
  caixa.addEventListener("click", async (evento) => {
    const linkNav = evento.target.closest("a[data-stive-link], a[data-stive-vivo]");
    if (linkNav) {
      // Não fecha agora: persiste o balão e só libera após visualizar a tela destino.
      const destino = linkNav.getAttribute("data-stive-destino") || linkNav.getAttribute("href") || "/painel/cameras";
      try { sessionStorage.setItem(chaveFalaVivo(), destino); } catch (erro) {}
      salvarFalaAtiva(lerFalaAtiva() || falaAtivaStive);
      return;
    }
    const confirmar = evento.target.closest("button[data-resp]");
    if (confirmar) {
      const dados = await confirmarPendencia(confirmar);
      const chat = document.getElementById("chat-balao") || document.getElementById("chat-stive");
      if (chat) acrescentarBolhaChat(chat, "stive", dados.fala || "Confirmação registrada.");
      fecharFalaStive();
      return;
    }
    const reacao = evento.target.closest("button[data-reacao]");
    if (reacao) {
      await enviarReacaoStive(reacao, reacao.dataset.reacao || "0");
      fecharFalaStive();
      return;
    }
    const fechar = evento.target.closest("button[data-fechar]");
    if (fechar) {
      // Fechar sem like/dislike não treina o modelo (nota 0).
      await enviarReacaoStive(fechar, 0);
      fecharFalaStive();
    }
  });
}

function usuarioStive() {
  return (document.body.dataset.usuario || "").trim().toLowerCase() || "anon";
}

function chaveChatStive() {
  return `stive-chat:${usuarioStive()}`;
}

function chaveVisualStive() {
  return `stive-visual:${usuarioStive()}`;
}

function lerChatStive() {
  try {
    sessionStorage.removeItem("stive-chat");
    const bruto = JSON.parse(sessionStorage.getItem(chaveChatStive()) || "[]");
    return Array.isArray(bruto) ? bruto.filter((item) => item && item.papel && item.texto).slice(-80) : [];
  } catch (erro) {
    return [];
  }
}

function gravarChatStive(lista) {
  try {
    sessionStorage.setItem(chaveChatStive(), JSON.stringify((lista || []).slice(-80)));
  } catch (erro) {}
}

function acrescentarBolhaChat(chat, papel, texto, gravar) {
  if (!chat) return;
  const p = document.createElement("p");
  p.className = `bolha ${papel}`;
  p.textContent = texto;
  chat.appendChild(p);
  chat.scrollTop = chat.scrollHeight;
  if (gravar === false) return;
  const lista = lerChatStive();
  lista.push({ papel, texto: String(texto || "").slice(0, 4000) });
  gravarChatStive(lista);
}

function restaurarChatStive(chat) {
  if (!chat || chat.dataset.restaurado) return;
  chat.dataset.restaurado = "1";
  const lista = lerChatStive();
  if (!lista.length) return;
  chat.innerHTML = "";
  lista.forEach((item) => acrescentarBolhaChat(chat, item.papel, item.texto, false));
  requestAnimationFrame(() => { chat.scrollTop = chat.scrollHeight; });
}

function iniciarBalao() {
  iniciarFalaStive();
  const balao = document.getElementById("balao-stive");
  if (!balao || balao.dataset.pronto) return;
  balao.dataset.pronto = "1";
  try {
    const pos = JSON.parse(localStorage.getItem("stive-pos") || "null");
    if (pos && Number.isFinite(pos.left) && Number.isFinite(pos.top)) {
      balao.style.left = `${pos.left}px`;
      balao.style.top = `${pos.top}px`;
      balao.style.right = "auto";
      balao.style.bottom = "auto";
    }
  } catch (erro) {}
  const puxador = document.getElementById("abrir-stive");
  let arrastando = false;
  let moveu = false;
  let dx = 0;
  let dy = 0;
  let origemX = 0;
  let origemY = 0;
  puxador.addEventListener("pointerdown", (evento) => {
    arrastando = true;
    moveu = false;
    origemX = evento.clientX;
    origemY = evento.clientY;
    const rect = balao.getBoundingClientRect();
    dx = evento.clientX - rect.left;
    dy = evento.clientY - rect.top;
    puxador.setPointerCapture(evento.pointerId);
  });
  puxador.addEventListener("pointermove", (evento) => {
    if (!arrastando) return;
    if (Math.hypot(evento.clientX - origemX, evento.clientY - origemY) > 5) moveu = true;
    if (!moveu) return;
    balao.style.left = `${Math.max(8, evento.clientX - dx)}px`;
    balao.style.top = `${Math.max(8, evento.clientY - dy)}px`;
    balao.style.right = "auto";
    balao.style.bottom = "auto";
  });
  puxador.addEventListener("pointerup", () => {
    if (!arrastando) return;
    arrastando = false;
    if (moveu) {
      const rect = balao.getBoundingClientRect();
      localStorage.setItem("stive-pos", JSON.stringify({ left: Math.round(rect.left), top: Math.round(rect.top) }));
      return;
    }
    balao.classList.toggle("fechado");
  });
  const form = document.getElementById("form-balao");
  const chat = document.getElementById("chat-balao");
  restaurarChatStive(chat);
  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const campo = form.querySelector("[name=pergunta]");
    const texto = campo.value.trim();
    if (!texto) return;
    acrescentarBolhaChat(chat, "eu", texto);
    campo.value = "";
    const corpo = new URLSearchParams(new FormData(form));
    corpo.set("pergunta", texto);
    const resposta = await fetch("/agente/stive", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: corpo,
    });
    const dados = await resposta.json().catch(() => ({}));
    const visual = dados.visual || {};
    const grafico = visual.tipo === "barras" || visual.tipo === "linha" || visual.tipo === "rosca";
    if (grafico || visual.itens) {
      try {
        sessionStorage.removeItem("stive-visual");
        sessionStorage.setItem(chaveVisualStive(), JSON.stringify(visual));
      } catch (erro) {}
    }
    const fala = `${dados.fala || "Não consegui consultar a base agora."}${grafico ? " Para ver o gráfico, abra a página do Agente Stive." : ""}`;
    acrescentarBolhaChat(chat, "stive", fala);
  });
}
iniciarFalaStive();
iniciarBalao();
