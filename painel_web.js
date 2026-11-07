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
const COR_LED = { branco: "#f4f7fb", amarelo: "#ffb020", vermelho: "#ff3b3b", preto: "#05070c" };

function ler(dados, caminho) {
  return String(caminho).split(".").reduce((acc, chave) => (acc == null ? undefined : acc[chave]), dados);
}

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function cartao(icone, rotulo, caminho) {
  return `<article class="cartao"><span>${SVG[icone] || ""}${rotulo}</span><strong data-num="${caminho}">0</strong></article>`;
}

function animar(dados) {
  document.querySelectorAll("[data-num]").forEach((el) => {
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
    cor: CORES[nome],
    valores: lerValor(nome),
  }));
}

function linha(canvas, series, rotulos, eixoX) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 640;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  const esquerda = 48;
  const topo = 28;
  const direita = 12;
  const baixo = 42;
  const w = Math.max(10, largura - esquerda - direita);
  const h = Math.max(10, altura - topo - baixo);
  const base = series.filter((serie) => !serie.teto);
  const pico = Math.max(1, ...base.flatMap((serie) => serie.valores || [0]));
  ctx.font = "12px Segoe UI";
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
  });
  ctx.fillText(eixoX || "", esquerda, altura - 6);
  const xDe = (indice, total) => esquerda + (total <= 1 ? w / 2 : (indice / (total - 1)) * w);
  series.forEach((serie) => {
    const valores = serie.valores || [];
    const pontos = valores.map((valor, indice) => ({
      x: xDe(indice, valores.length),
      y: topo + h - ((serie.teto ? (valor ? 1 : 0) : valor / pico) * h),
      valor,
    }));
    ctx.beginPath();
    ctx.strokeStyle = serie.cor;
    ctx.lineWidth = 2;
    pontos.forEach((ponto, indice) => (indice === 0 ? ctx.moveTo(ponto.x, ponto.y) : ctx.lineTo(ponto.x, ponto.y)));
    ctx.stroke();
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
    });
  });
  let lx = esquerda;
  series.forEach((serie) => {
    ctx.fillStyle = serie.cor;
    ctx.fillRect(lx, 6, 10, 10);
    ctx.fillStyle = "#f4f7fb";
    ctx.fillText(serie.nome, lx + 14, 15);
    lx += ctx.measureText(serie.nome).width + 28;
  });
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

function barrasEmpilhadas(canvas, dias) {
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
  const esquerda = 42;
  const topo = 16;
  const baixo = 46;
  const h = Math.max(10, altura - topo - baixo);
  const grupos = Math.max(dias.length, 1);
  const barrasPorGrupo = CLASSES.length;
  const larguraGrupo = (largura - esquerda - 8) / grupos;
  const larguraBarra = Math.max(6, Math.min(18, (larguraGrupo - 16) / barrasPorGrupo));
  let pico = 1;
  dias.forEach((dia) => CLASSES.forEach((classe) => {
    const total = cameras.reduce((soma, camera) => soma + Number((dia.cameras?.[camera] || {})[classe] || 0), 0);
    pico = Math.max(pico, total);
  }));
  ctx.font = "11px Segoe UI";
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
  dias.forEach((dia, indiceDia) => {
    const x0 = esquerda + indiceDia * larguraGrupo + 8;
    CLASSES.forEach((classe, indiceClasse) => {
      const x = x0 + indiceClasse * (larguraBarra + 3);
      let y = topo + h;
      let total = 0;
      cameras.forEach((camera, indiceCamera) => {
        const valor = Number((dia.cameras?.[camera] || {})[classe] || 0);
        if (!valor) return;
        const alturaBarra = (valor / pico) * h;
        y -= alturaBarra;
        total += valor;
        ctx.fillStyle = corCamera(camera, indiceCamera);
        ctx.fillRect(x, y, larguraBarra, alturaBarra);
        if (alturaBarra >= 14) {
          ctx.fillStyle = "#041018";
          ctx.fillText(String(valor), x + 1, y + 12);
        }
      });
      if (total) {
        ctx.fillStyle = "#f4f7fb";
        ctx.fillText(String(total), x, y - 3);
      }
      ctx.fillStyle = CORES[classe];
      ctx.fillText(NOME_CLASSE[classe].slice(0, 3), x, topo + h + 14);
    });
    ctx.fillStyle = "#93a0b8";
    ctx.fillText(dia.rotulo || "", x0, altura - 8);
  });
  ctx.fillStyle = "#93a0b8";
  ctx.fillText("contagens", 2, 12);
  return cameras;
}

function legendaCameras(cameras) {
  if (!cameras.length) return "";
  return `<div class="legenda-linha">${cameras.map((nome, indice) => `<span><b style="background:${corCamera(nome, indice)}"></b>${escapar(nome)}</span>`).join("")}</div>`;
}

function rosca(canvas, riscos) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 320;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  const ordem = ["Informativo", "Atencao", "Prioritario", "Critico"];
  const valores = ordem.map((nome) => Number(riscos[nome] || 0));
  const total = valores.reduce((soma, valor) => soma + valor, 0);
  const cx = largura * 0.42;
  const cy = altura * 0.48;
  const raio = Math.min(largura, altura) * 0.30;
  let angulo = -Math.PI / 2;
  ordem.forEach((nome, indice) => {
    const fatia = total ? (valores[indice] / total) * Math.PI * 2 : 0;
    if (fatia <= 0) return;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.fillStyle = CORES_RISCO[nome];
    ctx.arc(cx, cy, raio, angulo, angulo + fatia);
    ctx.closePath();
    ctx.fill();
    const meio = angulo + fatia / 2;
    const pct = total ? Math.round((1000 * valores[indice]) / total) / 10 : 0;
    ctx.fillStyle = CORES_RISCO[nome];
    ctx.font = "13px Segoe UI";
    ctx.fillText(`${NOME_RISCO[nome]} ${pct}%`, cx + Math.cos(meio) * (raio + 8), cy + Math.sin(meio) * (raio + 8));
    angulo += fatia;
  });
  ctx.beginPath();
  ctx.fillStyle = "#12182a";
  ctx.arc(cx, cy, raio * 0.58, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#f4f7fb";
  ctx.font = "22px Segoe UI";
  ctx.textAlign = "center";
  ctx.fillText(String(total), cx, cy + 6);
  ctx.textAlign = "left";
  if (!total) {
    ctx.fillStyle = "#93a0b8";
    ctx.font = "14px Segoe UI";
    ctx.fillText("Sem prioridade hoje", 16, 24);
  }
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

const pulso = { canvas: null, pontos: [], opcoes: null };
const cacheTile = {};
let ocorrenciaRedraw = null;

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

function inicio(tela, dados) {
  if (!tela.dataset.pronto) {
    const blocos = [
      ["pessoa", "Pessoas hoje", "periodos.dia.Pessoa"],
      ["pessoa", "Pessoas no mês", "periodos.mes.Pessoa"],
      ["pessoa", "Pessoas acumulado", "periodos.total.Pessoa"],
      ["veiculo", "Veículos hoje", "periodos.dia.Veiculo"],
      ["veiculo", "Veículos no mês", "periodos.mes.Veiculo"],
      ["veiculo", "Veículos acumulado", "periodos.total.Veiculo"],
      ["animal", "Animais hoje", "periodos.dia.Animal"],
      ["animal", "Animais no mês", "periodos.mes.Animal"],
      ["animal", "Animais acumulado", "periodos.total.Animal"],
      ["alerta", "Comportamentos hoje", "periodos.dia.Comportamento"],
      ["pessoa", "Match de pessoa hoje", "periodos.dia.MatchFace"],
      ["veiculo", "Match de placa hoje", "periodos.dia.MatchPlaca"],
    ];
    tela.innerHTML = `<section class="cartoes">${blocos.map((item) => cartao(item[0], item[1], item[2])).join("")}</section>
      <section class="cartao"><h2>Movimento do dia</h2><canvas class="grafico" id="movimento"></canvas></section>`;
    tela.dataset.pronto = "1";
  }
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
    <article class="cartao"><h2>Mapa das câmeras</h2><canvas class="mapa" id="mapa-contagens"></canvas><div id="legenda-contagens"></div></article>
    <section class="grade">
      <article class="cartao"><h2>Últimos dias</h2><canvas class="grafico" id="dias"></canvas><div id="legenda-dias"></div></article>
      <article class="cartao"><h2>Histórico do dia</h2><canvas class="grafico" id="horas"></canvas></article>
    </section>`;
    tela.dataset.pronto = "1";
  }
  const pontos = pontosGeo(dados, "itens");
  observarMapa(document.getElementById("mapa-contagens"), pontos, null);
  document.getElementById("legenda-contagens").innerHTML = legendaCameras(pontos.map((ponto) => ponto.nome));
  const cameras = barrasEmpilhadas(document.getElementById("dias"), dados.dias_empilhados || []);
  document.getElementById("legenda-dias").innerHTML = legendaCameras(cameras || []);
  const horas = dados.horas || {};
  linha(document.getElementById("horas"), seriesClasse(horas, (nome) => horas[nome] || []), horasDoDia(), "horas");
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
      <article class="cartao"><h2>Prioridade</h2><canvas class="grafico" id="rosca"></canvas><div id="legenda-risco"></div></article>
    </section>
    <article class="cartao"><h2>Prioridade ao longo das horas</h2><canvas class="grafico" id="horas-prioridade"></canvas></article>
    <section class="grade">
      <article class="cartao"><h2>Mapa dos comportamentos</h2><canvas class="mapa" id="mapa-comp"></canvas></article>
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
  );
  const pontos = pontosGeo(dados, "comportamento");
  observarMapa(document.getElementById("mapa-comp"), pontos, { pisca: true });
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
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<section class="coluna"><div>
      <article class="cartao" id="comparacao"></article>
      <article class="cartao"><h2>Últimos alertas</h2><div id="historico"></div></article>
      <section class="grade">
        <article class="cartao"><h2>Reconhecimento por câmera</h2><canvas class="mapa" id="mapa-face"></canvas></article>
        <article class="cartao"><h2>Pessoa na área</h2><div id="frase-face" class="leitura"></div></article>
      </section>
      <section class="grade">
        <article class="cartao"><h2>Memórias de rua</h2><div id="memorias"></div></article>
        <article class="cartao"><h2>Últimos informes</h2><p id="relatorio"></p><div id="informes"></div></article>
      </section>
      <section class="grade tres">
        <article class="cartao"><h2>Resumo</h2><p id="resumo" class="leitura"></p></article>
        <article class="cartao"><h2>Assessoramento</h2><p id="assessoramento" class="leitura"></p></article>
        <article class="cartao"><h2>Aprendizado</h2><p id="aprendizado" class="leitura"></p></article>
      </section>
    </div>
    <aside class="cartao"><h2>Quem mais passa</h2><div id="faces"></div></aside></section>`;
    tela.dataset.pronto = "1";
  }
  const match = dados.match || null;
  const chaveMatch = match ? `${match.id}|${match.taxa}|${match.passagens}|${match.risco}|${match.narracao_ia || match.narracao || ""}` : "";
  const comparacao = document.getElementById("comparacao");
  if (comparacao.dataset.chave !== chaveMatch) {
    const avisoRisco = match && match.tipo === "FACE" ? `<p><span class="luz-alerta"></span> Atenção, Pessoa de risco na área!</p>` : "";
    if (match) {
      comparacao.className = `cartao${match.risco ? " sobe" : ""}`;
      comparacao.innerHTML = `${avisoRisco}<h2>${escapar(match.nome || match.id)} · ${escapar(match.id)}</h2>
        <p>Similaridade ${Number(match.taxa || 0).toFixed(2)} · reapareceu ${match.passagens || 0} vezes · ${escapar(match.camera || "")}</p>
        ${fotos(`/img/match-ref.jpg?t=${Date.now()}`, `/img/match-agora.jpg?t=${Date.now()}`)}
        <p>${escapar(match.narracao_ia || match.narracao || "")}</p>`;
    } else {
      comparacao.className = "cartao";
      comparacao.innerHTML = "<h2>Comparação</h2><p>Nenhuma pessoa de interesse na câmera neste momento.</p>";
    }
    comparacao.dataset.chave = chaveMatch;
  }
  const historico = dados.historico || [];
  const chaveHist = historico.map((item) => `${item.quando}|${item.id}|${item.taxa}`).join(";");
  const caixaHist = document.getElementById("historico");
  if (caixaHist.dataset.chave !== chaveHist) {
    caixaHist.innerHTML = historico.map((item) => `<div class="alerta-linha">
      <div><strong class="titulo-alerta">${escapar(item.tipo)} ${escapar(item.id)}</strong><span class="nome-alerta">${escapar(item.nome || "")}</span>
      <p>${escapar(item.quando)} · ${escapar(item.rotulo || "SIM")} ${Number(item.taxa || 0).toFixed(2)} · ${escapar(item.nome)} · ${escapar(item.camera)}</p></div>
      ${fotos(`${item.ref}?t=${encodeURIComponent(item.quando)}`, `${item.agora}?t=${encodeURIComponent(item.quando)}`)}
    </div>`).join("") || "<p>Nenhum alerta de rosto ou placa ainda.</p>";
    caixaHist.dataset.chave = chaveHist;
  }
  const pontos = pontosGeo(dados, "alertas").map((ponto) => ({
    ...ponto,
    risco: match && match.camera === ponto.nome ? (dados.led || ponto.risco) : (ponto.risco || "branco"),
  }));
  observarMapa(document.getElementById("mapa-face"), pontos, { pisca: true });
  const texto = match
    ? `Pessoa de interesse na área. ${match.narracao_ia || match.narracao || "O movimento aparece quando o rosto é acompanhado."}`
    : "Nenhuma pessoa de interesse na área agora.";
  document.getElementById("frase-face").textContent = texto;
  document.getElementById("memorias").innerHTML = (dados.memorias || []).map((item) => `<p><strong>${escapar(item.quando)}</strong><br>${escapar(item.texto)}</p>`).join("") || "<p>Sem memória registrada.</p>";
  document.getElementById("relatorio").textContent = dados.relatorio || "";
  document.getElementById("informes").innerHTML = (dados.informes || []).map((item) => `<p><strong>${escapar(item.quando)}</strong><br>O que: ${escapar(item.descricao || item.tipo)}</p>`).join("") || "<p>Nenhum informe enviado.</p>";
  document.getElementById("resumo").textContent = dados.resumo || "O relatório do dia ainda não tem resumo. O agente grava este texto no fechamento do dia.";
  document.getElementById("assessoramento").textContent = dados.assessoramento || "O assessoramento entra no relatório, com a conclusão de risco e a orientação do período.";
  document.getElementById("aprendizado").textContent = dados.aprendizado || "O aprendizado da rua entra quando o relatório fecha o dia.";
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
  const assinatura = cameras.map((camera) => camera.nome).join("|");
  if (tela.dataset.pronto !== assinatura) {
    tela.innerHTML = `<article class="cartao"><p id="voz" class="voz branco"></p></article>
    <div id="odometros">${cameras.map((camera) => fileiraFluxo(camera)).join("") || "<p>Nenhuma câmera em análise.</p>"}</div>
    <article class="cartao"><h2>Mapa de risco</h2><canvas class="mapa" id="mapa-risco"></canvas></article>
    <article class="cartao"><h2>Telemetria</h2><canvas class="grafico" id="esteira"></canvas></article>
    <article class="cartao"><h2>Últimos informes</h2><div id="informes-risco"></div></article>
    <article class="cartao" id="subida"></article>`;
    tela.dataset.pronto = assinatura;
  }
  const voz = document.getElementById("voz");
  if (voz) {
    voz.textContent = dados.voz || "A área está em observação.";
    voz.className = "voz " + (dados.led || "branco");
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
    const altura = { branco: "18%", amarelo: "46%", vermelho: "74%", preto: "100%" }[camera.risco] || "18%";
    const cor = COR_LED[camera.risco] || "#f4f7fb";
    if (termo) {
      termo.style.height = altura;
      termo.style.background = cor;
    }
  });
  observarMapa(document.getElementById("mapa-risco"), pontosGeo(dados, "itens").map((ponto) => ({ ...ponto, valor: 1 })), { pisca: true, fixo: true });
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
  linha(document.getElementById("esteira"), series, rotulos, "tempo");
  const caixaInforme = document.getElementById("informes-risco");
  if (caixaInforme) {
    caixaInforme.innerHTML = (dados.informes || []).map((item) => {
      const texto = `${item.descricao || item.tipo || ""}`;
      const baixo = texto.toLowerCase();
      let cor = "branco";
      if (dados.led === "preto" || /disparo|arma/.test(baixo)) cor = "preto";
      else if (/briga|queda|interesse|risco|alerta/.test(baixo)) cor = "vermelho";
      else if (/deitad|intera|suspeito|áudio|audio/.test(baixo)) cor = "amarelo";
      return `<p class="informe ${cor}"><strong>${escapar(item.quando)}</strong><br>${escapar(texto)}</p>`;
    }).join("") || "<p>Nenhum informe enviado.</p>";
  }
  const subida = document.getElementById("subida");
  const match = dados.match;
  const chaveSubida = match && match.risco ? `${match.id}|${match.taxa}|${match.passagens}|${match.narracao_ia || match.narracao || ""}` : "";
  if (subida && subida.dataset.chave !== chaveSubida) {
    if (match && match.risco) {
      subida.className = "cartao sobe";
      subida.innerHTML = `<p><span class="luz-alerta"></span> Pessoa de risco detectada</p>
        <h2>${escapar(match.nome || match.id)}</h2>
        <p>Similaridade ${Number(match.taxa || 0).toFixed(2)} · reapareceu ${match.passagens || 0} vezes</p>
        <div class="rostos"><figure><img alt="" src="/img/match-agora.jpg?t=${Date.now()}"></figure></div>
        <p>${escapar(match.narracao_ia || match.narracao || "")}</p>`;
    } else {
      subida.className = "cartao";
      subida.innerHTML = "<h2>Match</h2><p>O cartão sobe quando uma pessoa de risco cadastrada reaparece.</p>";
    }
    subida.dataset.chave = chaveSubida;
  }
}

function vivo(_tela, dados) {
  (dados.cameras_vivo || []).forEach((camera) => {
    const figura = document.querySelector(`[data-camera="${CSS.escape(camera.nome)}"] .placar-camera`);
    if (!figura) return;
    const agora = camera.agora || {};
    const acumulado = camera.acumulado || {};
    const linhas = [
      ["pessoa", "Pessoas", agora.Pessoa || 0, acumulado.Pessoa || 0],
      ["veiculo", "Veículos", agora.Veiculo || 0, acumulado.Veiculo || 0],
      ["camera", "Objetos", agora.Objeto || 0, acumulado.Objeto || 0],
      ["animal", "Animais", agora.Animal || 0, acumulado.Animal || 0],
    ];
    const comportamentoAtual = (camera.comportamentos || []).map((item) => `${item.nome} ${item.agora}`).join(" · ") || "sem comportamento agora";
    figura.innerHTML = `<div class="placar"><div><span>Agora</span></div><div><span>Acumulado</span></div>
      ${linhas.map((item) => `<div><span>${SVG[item[0]]} ${item[1]}</span><strong>${item[2]}</strong></div><div><strong>${item[3]}</strong></div>`).join("")}
    </div><p>${escapar(comportamentoAtual)}</p>`;
  });
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

function mapas(tela, dados) {
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<article class="cartao"><canvas id="mapa"></canvas><div id="legenda"></div></article>`;
    tela.dataset.pronto = "1";
    document.querySelectorAll("button[data-periodo],button[data-desenho]").forEach((botao) => {
      botao.addEventListener("click", () => {
        document.querySelectorAll(`button[data-${botao.dataset.periodo ? "periodo" : "desenho"}]`).forEach((item) => item.classList.remove("ativo"));
        botao.classList.add("ativo");
        const corpo = new URLSearchParams();
        if (botao.dataset.periodo) corpo.set("periodo", botao.dataset.periodo);
        if (botao.dataset.desenho) corpo.set("desenho", botao.dataset.desenho);
        fetch("/comando", { method: "POST", body: corpo, headers: { "Content-Type": "application/x-www-form-urlencoded" } });
      });
    });
    const mes = document.querySelector('button[data-periodo="mes"]');
    const pontos = document.querySelector('button[data-desenho="pontos"]');
    if (mes) mes.classList.add("ativo");
    if (pontos) pontos.classList.add("ativo");
  }
  const canvas = document.getElementById("mapa");
  const lista = pontosDo(dados);
  const ctx = canvas.getContext("2d");
  canvas.width = (canvas.clientWidth || 800) * 2;
  canvas.height = 1040;
  ctx.fillStyle = "#101624";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!lista.length) {
    ctx.fillStyle = "#93a0b8";
    ctx.font = "32px Segoe UI";
    ctx.fillText("Sem latitude e longitude neste período.", 40, 80);
    document.getElementById("legenda").textContent = "";
    return;
  }
  ocorrenciaRedraw = () => {
    const alvo = document.getElementById("tela");
    if (alvo && alvo.dataset.tela === "mapas") mapas(alvo, dados);
  };
  const projetor = projetarRuas(ctx, canvas.width, canvas.height, lista);
  const modo = desenhoAtual();
  const tipos = {};
  lista.forEach((ponto, indice) => {
    const [x, y] = projetor(indice);
    const cor = `hsl(${(Array.from(ponto.tipo || "").reduce((s, c) => s + c.charCodeAt(0), 0) * 17) % 360} 80% 60%)`;
    tipos[ponto.tipo] = (tipos[ponto.tipo] || 0) + 1;
    if (modo === "pontos") {
      ctx.beginPath();
      ctx.fillStyle = cor;
      ctx.arc(x, y, 12, 0, Math.PI * 2);
      ctx.fill();
    } else {
      const raio = modo === "mancha" ? 90 : 54;
      const tinta = ctx.createRadialGradient(x, y, 4, x, y, raio);
      tinta.addColorStop(0, cor);
      tinta.addColorStop(1, "transparent");
      ctx.fillStyle = tinta;
      ctx.beginPath();
      ctx.arc(x, y, raio, 0, Math.PI * 2);
      ctx.fill();
    }
  });
  document.getElementById("legenda").textContent = Object.entries(tipos).map(([tipo, total]) => `${tipo}: ${total}`).join(" · ")
    + (lista.some((ponto) => ponto.aproximado) ? " · ponto sem coordenada usa a câmera citada" : "");
}

const render = { inicio, contagens, comportamento, alertas, mapas, risco, vivo };

function pulsar() {
  if (pulso.opcoes && pulso.opcoes.pisca && pulso.canvas && document.body.contains(pulso.canvas)) {
    mapaCameras(pulso.canvas, pulso.pontos, pulso.opcoes);
  }
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
  const led = document.getElementById("led");
  if (led) led.className = "led " + (dados.led || "branco");
  const tela = document.getElementById("tela");
  if (tela && render[tela.dataset.tela]) render[tela.dataset.tela](tela, dados);
  animar(dados);
  if (tela && tela.dataset.tela === "vivo" && !document.querySelector(".video")) {
    setTimeout(() => location.reload(), 2000);
  }
}

ciclo();
setInterval(ciclo, 1000);
