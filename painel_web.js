const SVG = {
  pessoa: "<svg viewBox='0 0 24 24'><circle cx='12' cy='8' r='3'/><path d='M5 19c1.5-3 3.8-4.5 7-4.5S17.5 16 19 19'/></svg>",
  animal: "<svg viewBox='0 0 24 24'><path d='M5 16c.2-3.2 2.4-6 5-6 .8 0 1.4-.6 2.2-1.6.7.3 1.6 1 2.2 1.6 1.4.2 3.6 1.6 3.6 4.2V18H5z'/><path d='M8 9.2 6.5 6M11 9.2 12 6'/></svg>",
  veiculo: "<svg viewBox='0 0 24 24'><path d='M4 15h16v3H4z'/><path d='M6 15 8.2 9h7.6L18 15'/><circle cx='7.5' cy='18.2' r='1.4'/><circle cx='16.5' cy='18.2' r='1.4'/></svg>",
  camera: "<svg viewBox='0 0 24 24'><path d='M4 7h4l2-2h4l2 2h4v12H4z'/><circle cx='12' cy='13' r='3'/></svg>",
  alerta: "<svg viewBox='0 0 24 24'><path d='M12 3 3 19h18z'/><path d='M12 9v5M12 17h.01'/></svg>",
};

const CORES = { Pessoa: "#ffb020", Veiculo: "#3ee0ff", Animal: "#3ddc97", Objeto: "#4c8dff" };

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

function linha(canvas, series) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const largura = canvas.clientWidth || 640;
  const altura = canvas.clientHeight || 220;
  canvas.width = largura * 2;
  canvas.height = altura * 2;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const valores = series.flatMap((serie) => serie.valores);
  const pico = Math.max(1, ...valores);
  ctx.lineWidth = 4;
  series.forEach((serie) => {
    ctx.beginPath();
    ctx.strokeStyle = serie.cor;
    serie.valores.forEach((valor, indice) => {
      const x = (indice / Math.max(serie.valores.length - 1, 1)) * (canvas.width - 24) + 12;
      const y = canvas.height - 20 - (valor / pico) * (canvas.height - 48);
      if (indice === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
}

function barras(itens) {
  const pico = Math.max(1, ...itens.map((item) => item.total));
  if (!itens.length) return "<p>Ainda sem contagem neste período.</p>";
  return itens.map((item) => {
    const foto = item.id ? `<img class="mini" alt="" src="/rosto/${encodeURIComponent(item.id)}.jpg">` : (SVG[item.icone] || "");
    const nome = item.nome ? `${escapar(item.nome)} · ` : "";
    return `<div class="linha-face"><span>${foto}${nome}${escapar(item.rotulo)}</span><strong>${item.total}</strong></div>
      <div class="barra"><i style="width:${Math.round(100 * item.total / pico)}%"></i></div>`;
  }).join("");
}

function periodos(dados) {
  return dados.periodos || { dia: {}, mes: {}, total: {} };
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
      <section class="cartao"><h2>Movimento do dia</h2><canvas class="grafico" id="horas"></canvas></section>
      <section class="grade">
        <a class="atalho cartao" href="/painel/1">${SVG.pessoa}Contagens</a>
        <a class="atalho cartao" href="/painel/2">${SVG.alerta}Comportamento</a>
        <a class="atalho cartao" href="/painel/3">${SVG.pessoa}Alertas de RF e LPR</a>
        <a class="atalho cartao" href="/painel/4">${SVG.camera}Mapas</a>
        <a class="atalho cartao" href="/painel/risco">${SVG.alerta}Detector de risco</a>
        <a class="atalho cartao" href="/painel/cameras">${SVG.camera}Ao vivo</a>
      </section>`;
    tela.dataset.pronto = "1";
  }
  const horas = dados.horas || {};
  linha(document.getElementById("horas"), ["Pessoa", "Veiculo", "Animal"].map((nome) => ({
    cor: CORES[nome],
    valores: horas[nome] || [],
  })));
}

function contagens(tela, dados) {
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<section class="cartoes">
      ${cartao("pessoa", "Pessoas hoje", "periodos.dia.Pessoa")}
      ${cartao("veiculo", "Veículos hoje", "periodos.dia.Veiculo")}
      ${cartao("animal", "Animais hoje", "periodos.dia.Animal")}
      ${cartao("camera", "Objetos hoje", "periodos.dia.Objeto")}
    </section>
    <section class="grade">
      <article class="cartao"><h2>Últimos dias</h2><div id="dias"></div></article>
      <article class="cartao"><h2>Horas de hoje</h2><canvas class="grafico" id="horas"></canvas></article>
    </section>`;
    tela.dataset.pronto = "1";
  }
  const dias = dados.serie_dias || [];
  document.getElementById("dias").innerHTML = barras(dias.map((dia) => ({
    rotulo: dia.rotulo,
    total: (dia.Pessoa || 0) + (dia.Veiculo || 0) + (dia.Animal || 0),
    icone: "pessoa",
  })));
  const horas = dados.horas || {};
  linha(document.getElementById("horas"), ["Pessoa", "Veiculo", "Animal"].map((nome) => ({
    cor: CORES[nome],
    valores: horas[nome] || [],
  })));
}

function comportamento(tela, dados) {
  if (!tela.dataset.pronto) {
    tela.innerHTML = `<section class="cartoes">
      ${cartao("alerta", "Comportamentos hoje", "periodos.dia.Comportamento")}
      ${cartao("alerta", "No mês", "periodos.mes.Comportamento")}
      ${cartao("alerta", "Acumulado", "periodos.total.Comportamento")}
    </section>
    <section class="grade">
      <article class="cartao"><h2>Classes</h2><div id="classes"></div></article>
      <article class="cartao"><h2>Prioridade</h2><div id="rosca"></div></article>
    </section>`;
    tela.dataset.pronto = "1";
  }
  document.getElementById("classes").innerHTML = barras((dados.classes || []).map((item) => ({
    rotulo: item.nome,
    total: item.total,
    icone: "pessoa",
  })));
  const riscos = dados.riscos || {};
  const ordem = ["Informativo", "Atencao", "Prioritario", "Critico"];
  const cores = ["#93a0b8", "#ffb020", "#ff7a18", "#ff3b3b"];
  const total = ordem.reduce((soma, nome) => soma + Number(riscos[nome] || 0), 0) || 1;
  let angulo = 0;
  const fatias = ordem.map((nome, indice) => {
    const fim = angulo + (Number(riscos[nome] || 0) / total) * 100;
    const parte = `${cores[indice]} ${angulo}% ${fim}%`;
    angulo = fim;
    return parte;
  }).join(", ");
  document.getElementById("rosca").innerHTML = `<div class="odo" style="background:conic-gradient(${fatias})"><span>${total}</span></div>
    <p>${ordem.map((nome) => `${nome} ${riscos[nome] || 0}`).join(" · ")}</p>`;
}

function alertas(tela, dados) {
  const match = dados.match || null;
  const chave = match ? `${match.id}:${match.taxa}:${match.passagens}` : "";
  if (tela.dataset.chave !== chave || !tela.dataset.pronto) {
    const avisoRisco = match && match.tipo === "FACE" ? `<p><span class="luz-alerta"></span> Atenção, Pessoa de risco na área!</p>` : "";
    const comparacao = match ? `<article class="cartao ${match.risco ? "sobe" : ""}" id="match">
      ${avisoRisco}
      <h2>${escapar(match.nome || match.id)} · ${escapar(match.id)}</h2>
      <p>Similaridade ${Number(match.taxa || 0).toFixed(2)} · reapareceu ${match.passagens || 0} vezes · ${escapar(match.camera || "")}</p>
      <div class="rostos">
        <figure><img alt="Referência" src="/img/match-ref.jpg?t=${Date.now()}"><figcaption>Referência</figcaption></figure>
        <figure><img alt="Agora" src="/img/match-agora.jpg?t=${Date.now()}"><figcaption>Agora</figcaption></figure>
      </div>
      <p>${escapar(match.narracao_ia || match.narracao || dados.narracao_ia || dados.narracao || "")}</p>
    </article>` : `<article class="cartao"><h2>Comparação</h2><p>Nenhuma pessoa de interesse na câmera neste momento.</p></article>`;
    tela.innerHTML = `<section class="coluna"><div>${comparacao}<article class="cartao"><h2>Leitura do agente</h2><p id="narracao">${escapar((dados.narracao_ia || dados.narracao || "A leitura aparece quando uma pessoa de interesse entra na cena."))}</p></article></div>
      <aside class="cartao"><h2>Quem mais passa</h2><div id="faces"></div></aside></section>`;
    tela.dataset.pronto = "1";
    tela.dataset.chave = chave;
  }
  const narracao = document.getElementById("narracao");
  if (narracao) narracao.textContent = dados.narracao_ia || dados.narracao || narracao.textContent;
  document.getElementById("faces").innerHTML = barras((dados.passagens || []).map((item) => ({
    id: item.id,
    nome: item.nome,
    rotulo: item.id,
    total: item.total,
  })));
}

function faixaFluxo(minuto) {
  if (minuto > 10) return "vermelho";
  if (minuto >= 4) return "amarelo";
  return "verde";
}

function relogio(rotulo, valor, topo, cor) {
  const giro = Math.max(0, Math.min(100, (valor / topo) * 100));
  return `<div><div class="odo ${cor}" style="--giro:${giro}%"><span>${valor}</span></div><p>${rotulo}</p></div>`;
}

function risco(tela, dados) {
  const match = dados.match;
  const aviso = dados.led === "vermelho" || dados.led === "preto" ? `<p class="aviso">Alerta ${escapar(dados.led)} na área.</p>` : "";
  tela.innerHTML = `${aviso}<section class="cartoes">
    <article class="cartao"><span>Branco</span><p>Apenas informes.</p></article>
    <article class="cartao"><span>Amarelo</span><p>Pessoa deitada, interação ou áudio suspeito.</p></article>
    <article class="cartao"><span>Vermelho</span><p>Pessoa ou veículo de interesse, queda ou interação suspeita.</p></article>
    <article class="cartao"><span>Preto</span><p>Deitada, interação e som de risco ao mesmo tempo. Chamar apoio.</p></article>
  </section>
  <section id="odometros" class="grade"></section>
  <article class="cartao"><h2>Telemetria</h2><canvas class="grafico" id="esteira"></canvas></article>
  <article class="cartao ${match && match.risco ? "sobe" : ""}" id="subida"></article>`;
  const caixa = document.getElementById("odometros");
  caixa.innerHTML = (dados.cameras_vivo || []).map((camera) => {
    const fluxo = camera.fluxo || {};
    const cor = faixaFluxo(Number(fluxo.minuto || 0));
    const lampada = camera.risco === "vermelho" || camera.risco === "preto" ? `<span class="luz-alerta"></span>` : "";
    const cena = camera.cena ? `<img alt="Cena" src="${camera.cena}?t=${Date.now()}">` : "";
    return `<article class="cartao"><h2>${lampada} ${escapar(camera.nome)}</h2>
      <div class="grade">
        ${relogio("por segundo", fluxo.segundo || 0, 10 / 60, cor)}
        ${relogio("por minuto", fluxo.minuto || 0, 10, cor)}
        ${relogio("por hora", fluxo.hora || 0, 600, cor)}
      </div>
      ${cena}
    </article>`;
  }).join("") || "<p>Nenhuma câmera em análise.</p>";
  linha(document.getElementById("esteira"), ["Pessoa", "Veiculo", "Animal"].map((nome) => ({
    cor: CORES[nome],
    valores: (dados.serie || []).map((ponto) => ponto[nome] || 0),
  })));
  const subida = document.getElementById("subida");
  if (match && match.risco) {
    subida.innerHTML = `<p><span class="luz-alerta"></span> Pessoa de risco detectada</p>
      <h2>${escapar(match.nome || match.id)}</h2>
      <p>Similaridade ${Number(match.taxa || 0).toFixed(2)} · reapareceu ${match.passagens || 0} vezes</p>
      <div class="rostos"><figure><img alt="" src="/img/match-agora.jpg?t=${Date.now()}"></figure></div>
      <p>${escapar(match.narracao_ia || match.narracao || "")}</p>`;
  } else {
    subida.innerHTML = "<h2>Match</h2><p>O cartão sobe quando uma pessoa de risco cadastrada reaparece.</p>";
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
    const comportamento = (camera.comportamentos || []).map((item) => `${item.nome} ${item.agora}`).join(" · ") || "sem comportamento agora";
    figura.innerHTML = `<div class="placar"><div><span>Agora</span></div><div><span>Acumulado</span></div>
      ${linhas.map((item) => `<div><span>${SVG[item[0]]} ${item[1]}</span><strong>${item[2]}</strong></div><div><strong>${item[3]}</strong></div>`).join("")}
    </div><p>${escapar(comportamento)}</p>`;
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
  const lats = lista.map((ponto) => ponto.lat);
  const lons = lista.map((ponto) => ponto.lon);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const folgaLat = Math.max(0.002, (maxLat - minLat) * 0.25);
  const folgaLon = Math.max(0.002, (maxLon - minLon) * 0.25);
  const px = (ponto) => [
    ((ponto.lon - (minLon - folgaLon)) / ((maxLon + folgaLon) - (minLon - folgaLon))) * (canvas.width - 40) + 20,
    (1 - (ponto.lat - (minLat - folgaLat)) / ((maxLat + folgaLat) - (minLat - folgaLat))) * (canvas.height - 40) + 20,
  ];
  const modo = desenhoAtual();
  const tipos = {};
  lista.forEach((ponto, indice) => {
    const [x, y] = px(ponto);
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
    if (ponto.aproximado && indice === 0) {
      ctx.fillStyle = "#93a0b8";
    }
  });
  document.getElementById("legenda").textContent = Object.entries(tipos).map(([tipo, total]) => `${tipo}: ${total}`).join(" · ")
    + (lista.some((ponto) => ponto.aproximado) ? " · ponto sem coordenada usa a câmera citada" : "");
}

const render = { inicio, contagens, comportamento, alertas, mapas, risco, vivo };

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
