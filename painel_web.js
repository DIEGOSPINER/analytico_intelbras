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
    cor: CORES[nome],
    valores: lerValor(nome),
  }));
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
        if (!muitos && alturaBarra >= 16 && larguraBarra >= 16) {
          ctx.fillStyle = "#041018";
          ctx.font = "10px Segoe UI";
          ctx.fillText(String(valor), x + 1, y + 12);
          ctx.font = `${fonte}px Segoe UI`;
        }
      });
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
    }
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
  if (!itens.length) {
    ctx.fillStyle = "#93a0b8";
    ctx.fillText("Sem ocorrência neste período.", 16, 36);
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
    ctx.fillStyle = item.cor || "#4c8dff";
    ctx.fillRect(x, y, Math.max(8, passo - 16), alturaBarra);
    ctx.fillStyle = "#f4f7fb";
    ctx.fillText(String(item.total), x, Math.max(14, y - 4));
    ctx.fillStyle = "#93a0b8";
    ctx.save();
    ctx.translate(x, topo + h + 8);
    ctx.rotate(itens.length > 8 ? -0.7 : 0);
    ctx.fillText(String(item.rotulo).slice(0, 18), 0, 12);
    ctx.restore();
  });
}

function roscaLivre(canvas, fatias) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 320;
  const altura = canvas.clientHeight || 280;
  const dpr = 2;
  canvas.width = largura * dpr;
  canvas.height = altura * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  const total = fatias.reduce((soma, item) => soma + item.total, 0);
  const cx = largura * 0.34;
  const cy = altura * 0.52;
  const raio = Math.min(largura, altura) * 0.32;
  let angulo = -Math.PI / 2;
  fatias.forEach((item) => {
    const fatia = total ? (item.total / total) * Math.PI * 2 : 0;
    if (fatia <= 0) return;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.fillStyle = item.cor;
    ctx.arc(cx, cy, raio, angulo, angulo + fatia);
    ctx.closePath();
    ctx.fill();
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
  ctx.font = "14px Segoe UI";
  fatias.slice(0, 8).forEach((item, indice) => {
    const pct = total ? Math.round((1000 * item.total) / total) / 10 : 0;
    const y = 28 + indice * 22;
    ctx.fillStyle = item.cor;
    ctx.fillRect(largura * 0.62, y - 10, 10, 10);
    ctx.fillStyle = "#f4f7fb";
    ctx.fillText(`${item.nome || item.rotulo || ""}  ${pct}%  (${item.total})`, largura * 0.62 + 16, y);
  });
  if (!total) {
    ctx.fillStyle = "#93a0b8";
    ctx.fillText("Sem ocorrência neste período.", 16, 28);
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
      <article class="cartao"><h2>Prioridade</h2><canvas class="grafico" id="rosca"></canvas><div id="legenda-risco"></div></article>
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
  const assinatura = `risco-v2|${cameras.map((camera) => camera.nome).join("|")}`;
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
    rotulo, total, cor: CORES_CAMERA[indice % CORES_CAMERA.length],
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
        <article class="cartao"><h2>Por natureza</h2><canvas class="grafico" id="rosca-app"></canvas><div id="legenda-natureza"></div></article>
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
    nome, rotulo: nome, total, cor: CORES_CAMERA[indice % CORES_CAMERA.length],
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
    "legenda-natureza": naturezasGrafico.map((item) => ({
      ...item,
      rotulo: `${item.rotulo} · ${item.total}`,
    })),
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

const render = { inicio, contagens, comportamento, alertas, mapas, risco, vivo, audio };

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
  const selo = document.getElementById("selo-stive");
  if (selo) {
    const total = (dados.pendencias || []).length;
    selo.hidden = !total;
    selo.textContent = total ? String(total) : "";
  }
  const seloAlertas = document.getElementById("selo-alertas");
  if (seloAlertas) {
    const total = (dados.match ? 1 : 0) + ((dados.historico || []).length);
    seloAlertas.hidden = !total;
    seloAlertas.textContent = total ? String(total) : "";
  }
  const seloAudio = document.getElementById("selo-audio");
  if (seloAudio) {
    const total = Number((dados.audio || {}).risco_aberto || 0) || ((dados.audio || {}).alertas || []).length;
    seloAudio.hidden = !total;
    seloAudio.textContent = total ? String(total) : "";
  }
  const seloRisco = document.getElementById("selo-risco");
  if (seloRisco) {
    const aceso = ["amarelo", "vermelho", "preto"].includes(dados.led);
    seloRisco.hidden = !aceso;
    seloRisco.textContent = aceso ? "!" : "";
  }
  if (window.atualizarStive) window.atualizarStive(dados);
  atualizarFalaStive(dados);
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

function piscarStive() {
  const avatar = document.querySelector("#abrir-stive");
  if (!avatar) return;
  avatar.classList.remove("falando");
  void avatar.offsetWidth;
  avatar.classList.add("falando");
  setTimeout(() => avatar.classList.remove("falando"), 1200);
}

function acoesFalaHtml(item) {
  const extra = item.html || "";
  return `${extra}<div class="acoes-fala">
    <button type="button" data-reacao="1" data-chave="${escapar(item.chave || "")}" data-titulo="${escapar(item.titulo || "")}" data-texto="${escapar(item.texto || "")}" data-tipo="${escapar(item.tipo || "")}">Legal</button>
    <button type="button" data-reacao="-1" data-chave="${escapar(item.chave || "")}" data-titulo="${escapar(item.titulo || "")}" data-texto="${escapar(item.texto || "")}" data-tipo="${escapar(item.tipo || "")}">Não legal</button>
    <button type="button" data-fechar="1" data-chave="${escapar(item.chave || "")}" data-titulo="${escapar(item.titulo || "")}" data-texto="${escapar(item.texto || "")}" data-tipo="${escapar(item.tipo || "")}">Fechar</button>
  </div>`;
}

function mostrarFalaHq(item) {
  const caixa = document.getElementById("fala-hq");
  if (!caixa) return;
  const classe = item.classe || "";
  caixa.hidden = false;
  caixa.dataset.travado = "1";
  caixa.className = `fala-hq sobe${classe ? ` ${classe}` : ""}`;
  caixa.innerHTML = `<strong>${escapar(item.titulo || "Stive")}</strong><p>${escapar(item.texto || "")}</p>${acoesFalaHtml(item)}`;
  piscarStive();
}

function enfileirarFalaStive(chave, titulo, texto, opcoes) {
  if (!chave || !texto || falasVistas.has(chave)) return;
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
  });
  processarFilaFalaStive();
}

function processarFilaFalaStive() {
  if (falandoStive) return;
  const caixa = document.getElementById("fala-hq");
  if (!caixa) return;
  const item = filaFalaStive.shift();
  if (!item) {
    caixa.hidden = true;
    caixa.innerHTML = "";
    caixa.dataset.travado = "";
    return;
  }
  falandoStive = true;
  mostrarFalaHq(item);
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
  return chaves;
}

let ultimaVozBaixaEm = 0;

function vozDeBaixoRisco(dados, voz) {
  const led = dados.led || "branco";
  if (led === "amarelo" || led === "vermelho" || led === "preto") return false;
  const baixo = String(voz || "").toLowerCase();
  return /observação|observacao|nenhum risco|sem comportamento de risco|área está|area esta|tranquila|ronda/.test(baixo) || !baixo;
}

function falarVozStive(dados) {
  const voz = String(dados.voz || "").trim();
  if (!voz) return;
  const classe = dados.led === "verde" ? "info" : (dados.led === "branco" ? "" : "risco");
  if (vozDeBaixoRisco(dados, voz)) {
    const agora = Date.now();
    if (agora - ultimaVozBaixaEm < 10 * 60 * 1000) return;
    ultimaVozBaixaEm = agora;
    enfileirarFalaStive(`voz:baixa:${Math.floor(agora / 600000)}`, "Detector de risco", voz, { classe });
    return;
  }
  enfileirarFalaStive(`voz:${voz}`, "Detector de risco", voz, { classe });
}

function atualizarFalaStive(dados) {
  if (!document.getElementById("fala-hq")) return;
  if (!window._stiveBasePronto) {
    chavesFalaBase(dados).forEach((chave) => falasVistas.add(chave));
    window._stiveBasePronto = true;
    falarVozStive(dados);
    return;
  }
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
        html: `<div class="pendencia"><span>
          <button type="button" data-id="${escapar(item.id)}" data-resp="sim" data-tipo="${escapar(item.tipo || "")}" data-camera="${escapar(item.camera || "")}" data-texto="${escapar(item.texto || "")}">Sim</button>
          <button type="button" data-id="${escapar(item.id)}" data-resp="nao" data-tipo="${escapar(item.tipo || "")}" data-camera="${escapar(item.camera || "")}" data-texto="${escapar(item.texto || "")}">Não</button>
        </span></div>`,
      },
    );
  }
  const match = dados.match;
  if (match) {
    const risco = !!match.risco;
    enfileirarFalaStive(
      `match:${match.id}|${match.taxa}|${match.risco}`,
      risco ? "Match RF/LPR" : "Presença informativa",
      risco
        ? `${match.nome || match.id} na ${match.camera || "câmera"}. ${match.narracao_ia || match.narracao || "Pessoa de risco na área."}`
        : `${match.nome || match.id} na ${match.camera || "câmera"}. Morador ou pessoa sem classificação de risco.`,
      { classe: risco ? "risco" : "info" },
    );
  }
  falarVozStive(dados);
  ((dados.audio || {}).alertas || []).slice(0, 4).forEach((item) => {
    const trecho = String(item.texto || item.detalhe || item.categoria || "").trim();
    if (!trecho) return;
    const nivel = Number(item.nivel || 0);
    if (nivel < 2 && !item.risco) return;
    enfileirarFalaStive(
      `audio:${item.quando}|${item.camera}|${trecho}`,
      "Áudio de risco",
      `Escutei na ${item.camera || "câmera"}: ${trecho}`,
      { classe: nivel >= 3 ? "risco" : "info", tipo: "audio" },
    );
  });
  (dados.informes || []).slice(0, 4).forEach((item) => {
    const textoBase = String(item.descricao || item.tipo || "").trim();
    if (!textoBase) return;
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
    enfileirarFalaStive(`inf:${item.quando}|${textoBase}`, "Informe", fala, { classe: "risco" });
  });
  (dados.app || []).slice(0, 3).forEach((item) => {
    const titulo = String(item.titulo || "Ocorrência").trim();
    enfileirarFalaStive(
      `app:${item.quando}|${titulo}|${item.lugar || ""}`,
      "Aplicativo",
      `Ocorrência nova lançada no app: ${titulo}${item.lugar ? ` em ${item.lugar}` : ""}.`,
      { classe: "info" },
    );
  });
  (dados.insights || []).slice(0, 3).forEach((item) => {
    const texto = String(item.descricao || item.nome || "").trim();
    if (!texto) return;
    enfileirarFalaStive(`ins:${item.quando}|${texto}`, "Insight", texto, { classe: "info" });
  });
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
  processarFilaFalaStive();
}

function iniciarFalaStive() {
  if (document.body.dataset.falaPronta) return;
  document.body.dataset.falaPronta = "1";
  const caixa = document.getElementById("fala-hq");
  if (!caixa) return;
  caixa.addEventListener("click", async (evento) => {
    const confirmar = evento.target.closest("button[data-resp]");
    if (confirmar) {
      const dados = await confirmarPendencia(confirmar);
      const chat = document.getElementById("chat-balao") || document.getElementById("chat-stive");
      if (chat) {
        const dele = document.createElement("p");
        dele.className = "bolha stive";
        dele.textContent = dados.fala || "Confirmação registrada.";
        chat.appendChild(dele);
        chat.scrollTop = chat.scrollHeight;
      }
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
      await enviarReacaoStive(fechar, 0);
      fecharFalaStive();
    }
  });
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
  form.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const campo = form.querySelector("[name=pergunta]");
    const texto = campo.value.trim();
    if (!texto) return;
    const eu = document.createElement("p");
    eu.className = "bolha eu";
    eu.textContent = texto;
    chat.appendChild(eu);
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
    if (grafico) {
      try { sessionStorage.setItem("stive-visual", JSON.stringify(visual)); } catch (erro) {}
    }
    const dele = document.createElement("p");
    dele.className = "bolha stive";
    dele.textContent = `${dados.fala || "Não consegui consultar a base agora."}${grafico ? " Para ver o gráfico, abra a página do Agente Stive." : ""}`;
    chat.appendChild(dele);
    chat.scrollTop = chat.scrollHeight;
  });
}
iniciarFalaStive();
iniciarBalao();
