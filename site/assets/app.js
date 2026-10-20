"use strict";

/* ============ utilidades ============ */
const COR = {
  ambar: "#f0b429", verde: "#3fb950", vermelho: "#f85149", azul: "#388bfd", ciano: "#39c5cf",
  roxo: "#a371f7", cinza: "#8b949e", texto: "#c9d1d9", borda: "#263040", grade: "#1b2430",
};
const PALETA_DATAS = ["#f0b429", "#39c5cf", "#a371f7", "#3fb950", "#8b949e", "#db61a2"];
const cache = {};
const graficos = [];
const app = document.getElementById("app");

async function dados(caminho) {
  if (!cache[caminho]) {
    cache[caminho] = fetch(caminho, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${caminho}: HTTP ${r.status}`);
      return r.json();
    });
  }
  return cache[caminho];
}

const num = (v, casas = 1) =>
  v == null || !isFinite(v) ? "—" : v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

function reais(v, casas = 1) {
  if (v == null || !isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return `R$ ${num(v / 1e12, casas)} tri`;
  if (a >= 1e9) return `R$ ${num(v / 1e9, casas)} bi`;
  if (a >= 1e6) return `R$ ${num(v / 1e6, casas)} mi`;
  if (a >= 1e3) return `R$ ${num(v / 1e3, casas)} mil`;
  return `R$ ${num(v, 2)}`;
}
const pct = (v, casas = 1) => (v == null || !isFinite(v) ? "—" : `${num(v * 100, casas)}%`);
const pctPronto = (v, casas = 2) => (v == null || !isFinite(v) ? "—" : `${num(v, casas)}%`);
const vezes = (v) => (v == null || !isFinite(v) ? "—" : `${num(v, 2)}x`);
const classeSinal = (v) => (v == null ? "" : v >= 0 ? "pos" : "neg");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dataBR = (iso) => (iso ? iso.split("-").reverse().join("/") : "—");
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function rotuloPeriodo(iso, visao, mesFim = 12) {
  const [a, m] = iso.split("-").map(Number);
  if (visao === "anual") return mesFim === 12 ? String(a) : `${MESES[m - 1]}/${String(a).slice(2)}`;
  return `${MESES[m - 1]}/${String(a).slice(2)}`;
}

function limparGraficos() {
  while (graficos.length) graficos.pop().dispose();
}
window.addEventListener("resize", () => graficos.forEach((g) => g.resize()));

/* ============ gráficos ============ */
function eixoValor(tipo, posicao) {
  const fmt = {
    reais: (v) => (v === 0 ? "0" : reais(v, 0).replace("R$ ", "")),
    pct: (v) => `${num(v * 100, 0)}%`,
    pctPronto: (v) => `${num(v, 1)}%`,
    vezes: (v) => `${num(v, 1)}x`,
    preco: (v) => num(v, 2),
    numero: (v) => num(v, 2),
  }[tipo];
  return {
    type: "value", position: posicao,
    axisLabel: { color: COR.cinza, formatter: fmt, fontFamily: "JetBrains Mono" },
    splitLine: { show: posicao === "left", lineStyle: { color: COR.grade } },
    axisLine: { show: true, lineStyle: { color: COR.borda } }, scale: tipo !== "reais",
  };
}

function formatar(tipo, v) {
  return { reais: reais, pct: pct, pctPronto: pctPronto, vezes: vezes, preco: (x) => num(x, 2), numero: (x) => num(x, 2) }[tipo](v);
}

/**
 * series: [{nome, valores, tipo:"bar"|"line", eixo:"esq"|"dir", cor}]
 * eixoEsq/eixoDir: "reais" | "pct" | "pctPronto" | "vezes" | "preco"
 */
function grafico(el, { rotulos, series, eixoEsq = "reais", eixoDir = null, xTempo = false, xNome = null, degrau = false,
  janela = 24, inicioTempo = null, deslizante = false }) {
  const g = echarts.init(el, null, { renderer: "canvas" });
  graficos.push(g);
  const eixosY = [eixoValor(eixoEsq, "left")];
  if (eixoDir) eixosY.push(eixoValor(eixoDir, "right"));
  g.setOption({
    backgroundColor: "transparent",
    textStyle: { fontFamily: "JetBrains Mono" },
    grid: { left: 64, right: eixoDir ? 64 : 24, top: 36, bottom: deslizante ? 70 : 48 },
    legend: { top: 0, type: "scroll", textStyle: { color: COR.texto, fontSize: 11 }, itemHeight: 8, itemGap: 14, pageTextStyle: { color: COR.cinza } },
    tooltip: {
      trigger: "axis", backgroundColor: "#151c25", borderColor: COR.borda, textStyle: { color: COR.texto, fontSize: 12 },
      valueFormatter: undefined,
      formatter: (itens) => {
        const cab = xTempo ? dataBR(new Date(itens[0].axisValue).toISOString().slice(0, 10)) : itens[0].axisValueLabel;
        return [cab, ...itens.map((i) => {
          const s = series[i.seriesIndex];
          const v = Array.isArray(i.value) ? i.value[1] : i.value;
          return `${i.marker} ${s.nome}: <b>${formatar(s.eixo === "dir" ? eixoDir : eixoEsq, v)}</b>`;
        })].join("<br>");
      },
    },
    xAxis: xTempo
      ? { type: "time", axisLabel: { color: COR.cinza }, axisLine: { lineStyle: { color: COR.borda } }, splitLine: { show: false } }
      : xNome
        ? { type: "value", name: xNome, nameLocation: "middle", nameGap: 28, nameTextStyle: { color: COR.cinza }, axisLabel: { color: COR.cinza }, axisLine: { lineStyle: { color: COR.borda } }, splitLine: { show: false }, scale: true }
        : { type: "category", data: rotulos, axisLabel: { color: COR.cinza, hideOverlap: true }, axisLine: { lineStyle: { color: COR.borda } } },
    yAxis: eixosY,
    dataZoom: xTempo
      ? (inicioTempo ? [{ type: "inside", startValue: inicioTempo },
        ...(deslizante ? [{ type: "slider", startValue: inicioTempo, height: 16, bottom: 30, borderColor: COR.borda, textStyle: { color: COR.cinza },
          fillerColor: "rgba(240,180,41,.15)", dataBackground: { lineStyle: { color: COR.cinza }, areaStyle: { color: "#1b2430" } } }] : [])] : [])
      : rotulos && rotulos.length > janela && !xNome ? [{ type: "inside", start: Math.max(0, 100 - (janela / rotulos.length) * 100), end: 100 }] : [],
    series: series.map((s) => ({
      name: s.nome, type: s.tipo || "bar", data: s.valores, yAxisIndex: s.eixo === "dir" ? 1 : 0,
      itemStyle: { color: s.cor }, lineStyle: { color: s.cor, width: 2, type: s.tracejado ? "dashed" : "solid" },
      symbol: s.tipo === "line" && !xTempo && s.valores.length < 40 ? "circle" : "none", symbolSize: 4,
      connectNulls: true, barMaxWidth: 28, step: degrau && s.tipo === "line" ? "end" : false, smooth: false, stack: s.pilha,
    })),
  });
  return g;
}

/* ============ ferramentas dos painéis: explicativo, download e tela cheia ============ */
// Todo painel com gráfico ganha os botões ⤓ (CSV) e ⛶ (tela cheia); com data-info, também o ⓘ
function decorarPaineis(raiz = app) {
  raiz.querySelectorAll(".painel").forEach((p) => {
    if (p.dataset.decorado) return;
    const titulo = p.querySelector("h2");
    const temGrafico = p.querySelector(".grafico");
    const temInfo = p.dataset.info && window.EXPLICATIVOS && window.EXPLICATIVOS[p.dataset.info];
    if (!titulo || (!temGrafico && !temInfo)) return;
    p.dataset.decorado = "1";
    const botoes = [];
    if (temInfo) botoes.push(`<button data-acao="info" title="O que é e como é calculado">ⓘ</button>`);
    if (temGrafico) botoes.push(`<button data-acao="csv" title="Baixar a série histórica completa (CSV, abre no Excel)">⤓</button>`,
      `<button data-acao="tela" title="Tela cheia (Esc para sair)">⛶</button>`);
    titulo.insertAdjacentHTML("beforeend", `<span class="ferramentas">${botoes.join("")}</span>`);
  });
}

// Painel que fica sozinho na sua linha (numa grade de 2 colunas) ocupa a largura toda
function ajustarGrades(raiz = app) {
  raiz.querySelectorAll(".grade").forEach((g) => {
    if (g.matches(".grade-3, .grade-empilhada, .grade-noticias")) return;
    const itens = [...g.children].filter((el) => el.classList.contains("painel") && getComputedStyle(el).display !== "none");
    let aberto = null;  // painel na 1ª coluna esperando par
    itens.forEach((el) => {
      el.classList.remove("sozinho");
      if (el.classList.contains("largo")) { if (aberto) aberto.classList.add("sozinho"); aberto = null; return; }
      aberto = aberto ? null : el;
    });
    if (aberto) aberto.classList.add("sozinho");
  });
}

function redimensionar(painel) {
  requestAnimationFrame(() => painel.querySelectorAll(".grafico").forEach((el) => { const g = echarts.getInstanceByDom(el); if (g) g.resize(); }));
}

function alternarTelaCheia(painel) {
  const ativo = painel.classList.toggle("tela-cheia");
  document.body.classList.toggle("sem-rolagem", ativo);
  const b = painel.querySelector('[data-acao="tela"]');
  if (b) b.textContent = ativo ? "✕" : "⛶";
  redimensionar(painel);
}

function fecharTelaCheia() {
  document.querySelectorAll(".painel.tela-cheia").forEach(alternarTelaCheia);
}

function nomeArquivo(texto) {
  return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^\w]+/g, "_").replace(/^_|_$/g, "").toLowerCase() || "serie";
}

// Exporta todas as séries do gráfico (histórico completo, não só a janela visível), separador ";" e vírgula decimal
function baixarCsv(painel) {
  const titulo = ((painel.querySelector("h2") || {}).firstChild || {}).textContent || "serie";
  const blocos = [];
  painel.querySelectorAll(".grafico").forEach((el) => {
    const g = echarts.getInstanceByDom(el);
    if (!g) return;
    const op = g.getOption(), eixo = op.xAxis[0];
    const series = op.series.filter((s) => s.data && s.data.length);
    const nomeX = eixo.type === "time" ? "Data" : eixo.type === "value" ? eixo.name || "x" : "Período";
    const linhas = new Map();
    series.forEach((s, j) => s.data.forEach((ponto, i) => {
      const par = Array.isArray(ponto) ? ponto : [eixo.data ? eixo.data[i] : i, ponto && typeof ponto === "object" ? ponto.value : ponto];
      if (!linhas.has(par[0])) linhas.set(par[0], []);
      linhas.get(par[0])[j] = par[1];
    }));
    const chaves = [...linhas.keys()];
    if (eixo.type !== "category") chaves.sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
    const fmt = (v) => (v == null || v === "" || !isFinite(v) ? "" : String(v).replace(".", ","));
    blocos.push([[nomeX, ...series.map((s) => s.name)].join(";"),
      ...chaves.map((x) => [typeof x === "number" ? fmt(x) : x, ...series.map((_, j) => fmt(linhas.get(x)[j]))].join(";"))].join("\r\n"));
  });
  if (!blocos.length) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["\ufeff" + blocos.join("\r\n\r\n")], { type: "text/csv;charset=utf-8" }));
  a.download = `${nomeArquivo(titulo.trim())}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

function abrirExplicativo(chave) {
  const e = (window.EXPLICATIVOS || {})[chave];
  if (!e) return;
  const m = document.getElementById("modal");
  m.innerHTML = `<div class="modal-caixa" role="dialog" aria-modal="true" aria-label="${esc(e.titulo)}">
    <div class="modal-topo"><h2>${esc(e.titulo)}</h2><button data-fechar title="Fechar (Esc)">✕</button></div>
    <div class="resumo">${e.html}</div></div>`;
  m.hidden = false;
}
function fecharModal() { document.getElementById("modal").hidden = true; }

app.addEventListener("click", (ev) => {
  const b = ev.target.closest(".ferramentas button");
  if (!b) return;
  ev.stopPropagation();
  const painel = b.closest(".painel");
  if (b.dataset.acao === "info") abrirExplicativo(painel.dataset.info);
  else if (b.dataset.acao === "csv") baixarCsv(painel);
  else if (b.dataset.acao === "tela") alternarTelaCheia(painel);
});
document.getElementById("modal").addEventListener("click", (ev) => {
  if (ev.target.id === "modal" || ev.target.closest("[data-fechar]")) fecharModal();
});
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") { fecharModal(); fecharTelaCheia(); } });

/* ============ busca / comando ============ */
let INDICE = [];
async function iniciarBusca() {
  INDICE = await dados("dados/empresas.json").catch(() => []);
  const entrada = document.getElementById("comando");
  const caixa = document.getElementById("sugestoes");
  let sel = 0, achados = [];
  const normal = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase();
  function mostrar() {
    const q = normal(entrada.value.trim());
    if (!q) { caixa.classList.remove("aberta"); return; }
    const nota = (e) => (e.tickers.some((t) => t === q) ? 0 : e.tickers.some((t) => t.startsWith(q)) ? 1 : normal(e.nome).startsWith(q) ? 2 : 3);
    achados = INDICE.filter((e) => e.tickers.some((t) => t.startsWith(q)) || normal(e.nome).includes(q))
      .sort((a, b) => nota(a) - nota(b) || a.nome.localeCompare(b.nome)).slice(0, 12);
    sel = 0;
    caixa.innerHTML = achados.map((e, i) =>
      `<div data-id="${esc(e.id)}" class="${i === 0 ? "sel" : ""}"><span>${esc(e.tickers.join(" / "))}</span><small>${esc(e.nome)}</small></div>`).join("");
    caixa.classList.toggle("aberta", achados.length > 0);
  }
  function ir(id) { entrada.value = ""; caixa.classList.remove("aberta"); location.hash = `#/on/empresa/${id}`; }
  entrada.addEventListener("input", mostrar);
  entrada.addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
      ev.preventDefault();
      sel = (sel + (ev.key === "ArrowDown" ? 1 : -1) + achados.length) % Math.max(achados.length, 1);
      [...caixa.children].forEach((d, i) => d.classList.toggle("sel", i === sel));
    } else if (ev.key === "Enter" && achados[sel]) ir(achados[sel].id);
    else if (ev.key === "Escape") caixa.classList.remove("aberta");
  });
  caixa.addEventListener("mousedown", (ev) => { const d = ev.target.closest("[data-id]"); if (d) ir(d.dataset.id); });
  entrada.addEventListener("blur", () => setTimeout(() => caixa.classList.remove("aberta"), 150));
}

/* ============ roteamento ============ */
// Mesmas seções, na mesma ordem, nos dois lados: #/on/<seção>/<detalhe> e #/off/<seção>/<detalhe>
const SECOES = [["", "Início"], ["noticias", "Notícias e agenda"], ["macro", "Macro"], ["juros", "Juros"], ["empresas", "Empresas"], ["downloads", "Downloads"]];
const ROTAS = {
  on: { banco: (p) => paginaBanco(p), "": paginaInicio, noticias: (p) => (p === "eleicoes" ? paginaEleicoes() : paginaNoticias("on")), macro: paginaMacro, juros: paginaJuros, empresas: paginaEmpresas, empresa: paginaEmpresa, downloads: paginaDownloads },
  off: Object.fromEntries(SECOES.map(([k]) => [k, (p) => paginaOffshore(k, p)])),
};
const SECOES_CONS = [["", "Juros"], ["inflacao", "Inflação"], ["atividade", "Atividade e emprego"], ["noticias", "Notícias e agenda"]];
ROTAS.cons = Object.fromEntries(SECOES_CONS.map(([k]) => [k, () => (k === "noticias" ? paginaNoticias("cons") : paginaConsolidado(k))]));
ROTAS.off.noticias = () => paginaNoticias("off");
const ROTAS_ANTIGAS = { agenda: "noticias" };  // endereços de antes da divisão Onshore/Offshore

function desenharNav(lado, secao) {
  document.querySelectorAll("#lados a").forEach((a) => a.classList.toggle("ativo", a.dataset.lado === lado));
  document.getElementById("nav").innerHTML = (lado === "cons" ? SECOES_CONS : SECOES).map(([k, nome]) =>
    `<a href="#/${lado || "on"}${k ? `/${k}` : ""}" class="${lado && k === secao ? "ativo" : ""}">${nome}</a>`).join("");
  document.body.dataset.lado = lado || "";
}

async function rotear() {
  limparGraficos();
  fecharTelaCheia();
  fecharModal();
  const partes = location.hash.replace(/^#\/?/, "").split("/");
  if (partes[0] === "status") { desenharNav(null, null); return executar(paginaStatus); }
  if (!["on", "off", "cons"].includes(partes[0])) {
    partes[0] = ROTAS_ANTIGAS[partes[0]] || partes[0];
    location.replace(`#/on/${partes.join("/")}`.replace(/\/+$/, ""));
    return;
  }
  const [lado, secao = "", parametro] = partes;
  desenharNav(lado, secao === "empresa" || secao === "banco" ? "empresas" : secao);
  await executar(ROTAS[lado][secao] || ROTAS[lado][""], parametro ? decodeURIComponent(parametro) : undefined);
}

async function executar(pagina, parametro) {
  app.innerHTML = `<p class="carregando">Carregando…</p>`;
  window.scrollTo(0, 0);
  try {
    await pagina(parametro);
    decorarPaineis();
  } catch (e) {
    console.error(e);
    app.innerHTML = `<p class="erro">Não foi possível carregar esta página (${esc(e.message)}).</p>`;
  }
}
window.addEventListener("hashchange", rotear);
// Painéis redesenhados depois (troca de aba, de visão etc.) também ganham os botões
new MutationObserver(() => { decorarPaineis(); ajustarGrades(); }).observe(app, { childList: true, subtree: true });

/* ============ Início ============ */
function ultimo(serie) {
  if (!serie) return { data: null, valor: null };
  const n = serie.valores.length;
  return { data: serie.datas[n - 1], valor: serie.valores[n - 1] };
}
function cartao(rotulo, valor, det = "") {
  return `<div class="cartao"><div class="rotulo">${rotulo}</div><div class="valor">${valor}</div><div class="det">${det}</div></div>`;
}

async function paginaInicio() {
  const [macro, tesouro, di, agenda, noticias] = await Promise.all([
    dados("dados/macro.json").catch(() => null), dados("dados/tesouro.json").catch(() => null),
    dados("dados/curva_di.json").catch(() => null), dados("dados/agenda.json").catch(() => null),
    dados("dados/noticias.json").catch(() => null),
  ]);
  const s = macro ? macro.series : {};
  const selic = ultimo(s.selic_meta), ipca = ultimo(s.ipca_12m), cdi = ultimo(s.cdi), usd = ultimo(s.usd), real = ultimo(s.juro_real);
  const ipcaLongo = tesouro ? tesouro.curvas.hoje.ipca.slice(-1)[0] : null;
  const mercado = ((noticias && noticias.itens) || []).filter((n) => n.tipo === "mercado");

  app.innerHTML = `
    <div class="cabecalho"><div><h1>Onshore · painel</h1><div class="sub">Agenda, indicadores e notícias do Brasil</div></div></div>
    <div class="painel secao-topo"><h2>Agenda — próximos 14 dias</h2>${tabelaAgenda(agenda, 14)}
      <div class="nota"><a href="#/on/noticias">Ver agenda completa</a></div></div>
    <div class="grade-cartoes">
      ${cartao("Selic meta", pctPronto(selic.valor), dataBR(selic.data))}
      ${cartao("IPCA 12 meses", pctPronto(ipca.valor), ipca.data ? ipca.data.slice(0, 7) : "")}
      ${cartao("CDI", pctPronto(cdi.valor), dataBR(cdi.data))}
      ${cartao("Juro real ex-post", pctPronto(real.valor), "Selic ÷ IPCA 12m")}
      ${cartao("Dólar PTAX", usd.valor ? `R$ ${num(usd.valor, 4)}` : "—", dataBR(usd.data))}
      ${cartao("IPCA+ mais longo", ipcaLongo ? pctPronto(ipcaLongo.taxa) : "—", ipcaLongo ? `oficial de ${dataBR(tesouro.data_base)} · venc. ${ipcaLongo.vencimento.slice(0, 4)}` : "")}
    </div>
    <div class="grade">
      <div class="painel" data-info="curva_di"><h2>Curva DI x Pré — hoje vs. 1 ano</h2><div class="grafico" id="g-di"></div></div>
      <div class="painel" data-info="selic"><h2>Selic meta e IPCA 12m</h2><div class="grafico" id="g-juros"></div></div>
    </div>
    <div class="painel secao"><h2>Notícias de mercado</h2>${listaNoticias(mercado, 40)}
      <div class="nota">Manchetes de Valor Econômico, Folha, Estadão, Brazil Journal e InfoMoney, com link para o jornal. <a href="#/on/noticias">Ver todas</a></div></div>`;

  if (di && di.curvas.hoje) {
    const serieCurva = (c) => c.pre.filter((p) => p.anos <= 10).map((p) => [p.anos, p.taxa]);
    grafico(document.getElementById("g-di"), {
      xNome: "anos", eixoEsq: "pctPronto",
      series: [
        { nome: `Hoje (${dataBR(di.curvas.hoje.data)})`, valores: serieCurva(di.curvas.hoje), tipo: "line", cor: COR.ambar },
        ...(di.curvas["1 ano"] ? [{ nome: `1 ano (${dataBR(di.curvas["1 ano"].data)})`, valores: serieCurva(di.curvas["1 ano"]), tipo: "line", cor: COR.cinza, tracejado: true }] : []),
      ],
    });
  }
  if (macro) {
    const desde5 = `${new Date().getFullYear() - 5}-01-01`;
    const pares = (serie) => serie.datas.map((d, i) => [d, serie.valores[i]]).filter((p) => p[0] >= desde5);
    grafico(document.getElementById("g-juros"), {
      xTempo: true, eixoEsq: "pctPronto", degrau: true,
      series: [
        { nome: "Selic meta", valores: pares(s.selic_meta), tipo: "line", cor: COR.ambar },
        { nome: "IPCA 12m", valores: pares(s.ipca_12m), tipo: "line", cor: COR.vermelho },
      ],
    });
  }
}

/* ============ Empresas (lista) ============ */
// Duas abas: notícias e eventos das empresas (padrão) e a tabela com todas as empresas
const ABAS_EMPRESAS = [["noticias", "Informações"], ["tabela", "Empresas"], ["financeiras", "Instituições financeiras"]];

async function paginaEmpresas(aba) {
  if (!ABAS_EMPRESAS.some(([k]) => k === aba)) aba = "noticias";
  const [mercado, fatos, noticias, cal] = await Promise.all([dados("dados/mercado.json").catch(() => ({ empresas: [] })),
    dados("dados/eventos_recentes.json").catch(() => null), dados("dados/noticias.json").catch(() => null),
    dados("dados/calendario_resultados.json").catch(() => null)]);
  const citadas = ((noticias && noticias.itens) || []).filter((n) => (n.empresas || []).length);
  const recentes = [...INDICE].filter((e) => e.ultimo_periodo).sort((a, b) => b.ultimo_periodo.localeCompare(a.ultimo_periodo) || a.nome.localeCompare(b.nome)).slice(0, 15);
  const proximos = mercado.empresas.flatMap((e) => (e.proximos_proventos || []).map((p) => ({ ...p, id: e.id })));
  const hojeIso = new Date().toISOString().slice(0, 10);
  const chave = (p) => (p.data_com >= hojeIso ? p.data_com : p.pagamento || "");
  proximos.sort((a, b) => chave(a).localeCompare(chave(b)));
  const mapa = Object.fromEntries(mercado.empresas.map((m) => [m.id, m]));
  const linhas = INDICE.map((e) => {
    const m = mapa[e.id] || {};
    const mc = m.market_cap;
    return { ...e, mc, pl: mc && e.lucro_ltm > 0 ? mc / e.lucro_ltm : null, dy: m.dy_12m };
  });
  const abas = `<div class="abas">${ABAS_EMPRESAS.map(([k, n]) => `<a href="#/on/empresas/${k}" class="${k === aba ? "ativo" : ""}">${n}</a>`).join("")}</div>`;
  const cab = `<div class="cabecalho"><div><h1>Empresas</h1><div class="sub">${INDICE.length} empresas da lista · clique numa empresa para abrir a página dela</div></div></div>`;
  if (aba === "financeiras") return abaFinanceiras(cab, abas);
  if (aba === "noticias") {
    app.innerHTML = `${cab}${abas}
    <div class="grade">
      <div class="painel largo" data-info="calendario_resultados"><h2>Calendário de resultados — próximo ITR/DFP de cada empresa</h2>${tabelaCalendario(cal)}
        <div class="nota">"est." = estimativa pelo histórico: a data em que a empresa entregou o mesmo trimestre no ano anterior, limitada ao prazo legal.
          Não é a data oficial anunciada pela empresa. Fonte: CVM (datas de entrega de ITR/DFP).</div></div>
      <div class="painel"><h2>Notícias das empresas</h2>${listaNoticias(citadas, 80)}
        <div class="nota">Manchetes de jornais e fontes oficiais que citam o ticker ou o nome de pregão de uma empresa da lista (etiqueta = empresa).
          Fontes: Valor Econômico, Folha, Estadão, Brazil Journal, InfoMoney, Banco Central, IBGE, CVM e Agência Brasil.</div></div>
      <div class="painel"><h2>Fatos relevantes recentes</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Data</th><th>Papel</th><th style="text-align:left">Assunto</th></tr>
        ${fatos && fatos.eventos.length ? fatos.eventos.slice(0, 60).map((e) => `<tr><td>${dataBR(e.data)}</td>
          <td><a href="#/on/empresa/${esc(e.id)}">${esc(e.id)}</a></td>
          <td style="white-space:normal;text-align:left">${e.link ? `<a href="${esc(e.link)}" target="_blank" rel="noopener">${esc(e.assunto)}</a>` : esc(e.assunto)}</td></tr>`).join("")
          : `<tr><td colspan="3" class="sub">Sem fatos relevantes recentes.</td></tr>`}
      </table></div><div class="nota">Fonte: CVM (documentos IPE), com link para o documento oficial.</div></div>
      <div class="painel"><h2>Últimas divulgações de resultado</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Empresa</th><th>Período</th><th>Receita</th><th>Var. a/a</th><th>Lucro</th><th>Var. a/a</th></tr>
        ${recentes.map((e) => `<tr class="clicavel" onclick="location.hash='#/on/empresa/${esc(e.id)}'">
          <td>${esc(e.tickers[0])} <span class="sub">${esc(e.nome.slice(0, 22))}</span></td><td>${dataBR(e.ultimo_periodo)}</td>
          <td>${reais(e.receita_tri)}</td><td class="${classeSinal(e.cresc_receita_tri)}">${pct(e.cresc_receita_tri)}</td>
          <td>${reais(e.lucro_tri)}</td><td class="${classeSinal(e.cresc_lucro_tri)}">${pct(e.cresc_lucro_tri)}</td></tr>`).join("")}
      </table></div><div class="nota">Último trimestre entregue à CVM (ITR/DFP); variação contra o mesmo trimestre do ano anterior.</div></div>
      <div class="painel"><h2>Próximos proventos (data-com ou pagamento futuros)</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Papel</th><th>Tipo</th><th>Data-com</th><th>Pagamento</th><th>R$/ação</th></tr>
        ${proximos.length ? proximos.slice(0, 40).map((p) => `<tr class="clicavel" onclick="location.hash='#/on/empresa/${esc(p.id)}'">
          <td>${esc(p.id)} <span class="sub">${esc(p.classe)}</span></td><td>${esc(p.tipo)}</td><td>${dataBR(p.data_com)}</td>
          <td>${dataBR(p.pagamento)}</td><td>${num(p.valor, 4)}</td></tr>`).join("") : `<tr><td colspan="5" class="sub">Nenhum provento com data-com ou pagamento futuro anunciado.</td></tr>`}
      </table></div><div class="nota">Fonte: B3 (proventos em dinheiro anunciados).</div></div>
    </div>`;
    return;
  }
  app.innerHTML = `${cab}${abas}
    <div class="cabecalho"><h2 style="margin:0">Todas as empresas</h2><input class="filtro" id="filtro" placeholder="filtrar por nome, ticker ou setor"></div>
    <div class="painel"><div class="rolagem"><table class="tabela" id="tab">
      <thead><tr><th>Papel</th><th>Empresa</th><th>Setor</th><th>Market cap</th><th>Receita LTM</th><th>Lucro LTM</th>
      <th>Margem líq.</th><th>ROE</th><th>DL/EBITDA</th><th>DL/EBITDA c/ IFRS16</th><th>P/L</th><th>DY 12m</th></tr></thead><tbody></tbody></table></div></div>`;
  const corpo = app.querySelector("tbody");
  function desenhar(f = "") {
    const q = f.trim().toUpperCase();
    corpo.innerHTML = linhas.filter((e) => !q || e.nome.toUpperCase().includes(q) || e.tickers.some((t) => t.includes(q)) || (e.setor || "").toUpperCase().includes(q))
      .map((e) => `<tr class="clicavel" onclick="location.hash='#/on/empresa/${esc(e.id)}'">
        <td>${esc(e.tickers.join(" / "))}</td><td>${esc(e.nome.slice(0, 38))}</td><td class="sub">${esc((e.setor || "").slice(0, 30))}</td>
        <td>${reais(e.mc)}</td><td>${reais(e.receita_ltm)}</td><td class="${classeSinal(e.lucro_ltm)}">${reais(e.lucro_ltm)}</td>
        <td>${pct(e.m_liquida_ltm)}</td><td>${pct(e.roe)}</td><td>${vezes(e.dl_ebitda)}</td><td>${vezes(e.dl_ebitda_ifrs16)}</td><td>${vezes(e.pl)}</td><td>${pct(e.dy, 2)}</td></tr>`).join("");
  }
  desenhar();
  document.getElementById("filtro").addEventListener("input", (ev) => desenhar(ev.target.value));
}

/* ============ Empresa ============ */
let VISAO = "trimestral";
let FC_SEL = "todos";
let DIV_IFRS16 = false;
let ABA_EMPRESA = "negocio";
let NOTICIAS_CACHE = null;
const ABAS_EMPRESA = [["negocio", "Negócio"], ["eventos", "Eventos e notícias"], ["resultados", "Resultados"], ["indicadores", "Indicadores"], ["dividendos", "Dividendos"]];
const INFO_EMPRESA = {
  "Receita líquida": "receita", "Lucro bruto e margem bruta": "lucro_bruto", "EBITDA e margem EBITDA": "ebitda",
  "EBIT e margem EBIT": "ebit", "Lucro líquido e margem líquida": "lucro_liquido", "Resultado financeiro": "resultado_financeiro",
  "Retorno (LTM)": "retorno",
};
const OPCOES_FC = [["todos", "Todos"], ["fco", "FCO"], ["fci", "FCI"], ["fcfin", "FCFi"], ["soma", "Soma"]];

const INDICADORES_LTM = [
  ["Receita líquida", "receita", reais], ["EBITDA", "ebitda", reais], ["EBIT", "ebit", reais], ["Lucro líquido", "lucro_liquido", reais],
  ["FCO", "fco", reais], ["Capex", "capex", reais], ["FCF", "fcf", reais],
  ["Crescimento da receita", "cresc_receita", pct], ["Margem bruta", "m_bruta", pct], ["Margem EBITDA", "m_ebitda", pct],
  ["Margem EBIT", "m_ebit", pct], ["Margem líquida", "m_liquida", pct], ["Margem FCF", "m_fcf", pct],
  ["Alíquota efetiva de IR", "aliquota_efetiva", pct], ["Caixa + aplicações", null, reais],
  ["Dívida bruta (sem IFRS 16)", "divida_bruta", reais], ["Arrendamentos (IFRS 16)", "arrendamentos", reais],
  ["Dívida bruta (com IFRS 16)", "divida_bruta_ifrs16", reais],
  ["Dívida líquida (sem IFRS 16)", "divida_liquida", reais], ["Dívida líquida (com IFRS 16)", "divida_liquida_ifrs16", reais],
  ["Dív. líquida / EBITDA (sem IFRS 16)", "dl_ebitda", vezes], ["Dív. líquida / EBITDA (com IFRS 16)", "dl_ebitda_ifrs16", vezes],
  ["Dív. líquida / PL (sem IFRS 16)", "dl_pl", vezes], ["Dív. líquida / PL (com IFRS 16)", "dl_pl_ifrs16", vezes],
  ["Cobertura de juros (EBIT/desp. fin.)", "cobertura_juros", vezes], ["Liquidez corrente", "liquidez_corrente", vezes],
  ["ROE", "roe", pct], ["ROA", "roa", pct], ["ROIC (IR 34%)", "roic", pct],
  ["Conversão de caixa (FCO/EBITDA)", "conv_caixa", pct], ["Conversão de lucro (FCF/LL)", "conv_lucro", pct],
  ["Capex / receita", "capex_receita", pct], ["Capex / D&A", "capex_da", vezes], ["Dividendos + JCP pagos", "div_pagos", reais], ["Payout", "payout", pct],
];

async function paginaEmpresa(id) {
  ULTIMO_DIV = null;
  const calendario = await dados("dados/calendario_resultados.json").catch(() => null);
  const proxResultado = calendario ? calendario.empresas.find((l) => l.id === id) : null;
  const [emp, mercado, prov, ficha, eventos, negocio, resumo] = await Promise.all([
    dados(`dados/empresas/${id}.json`), dados("dados/mercado.json").catch(() => ({ empresas: [] })),
    dados(`dados/proventos/${id}.json`).catch(() => null), dados(`dados/fichas/${id}.json`).catch(() => null),
    dados(`dados/eventos/${id}.json`).catch(() => null), dados(`dados/negocio/${id}.json`).catch(() => null),
    dados(`dados/resumos/${id}.json`).catch(() => null),
  ]);
  const m = mercado.empresas.find((x) => x.id === id) || {};
  const ltm = emp.ltm, n = ltm.periodos.length - 1;
  const L = (k) => (n >= 0 ? ltm.series[k][n] : null);
  const mc = m.market_cap, dl = L("divida_liquida"), ev = mc != null && dl != null ? mc + dl : null;
  const ref = m.papel_referencia, cot = ref && m.cotacoes ? m.cotacoes[ref] : null;
  const pos = (v) => (v != null && v > 0 ? v : null);

  app.innerHTML = `
    <div class="cabecalho">
      <div><h1>${esc(emp.tickers.join(" / "))} · ${esc(emp.nome)}</h1>
        <div class="sub">${esc(emp.setor || "")} · CNPJ ${esc(emp.cnpj)}${m.segmento ? ` · ${esc(m.segmento)}` : ""} · último período ${dataBR(emp.trimestral.periodos.slice(-1)[0])}</div></div>
      <a class="botao" href="downloads/${encodeURIComponent(id)}.xlsx" download>Baixar Excel</a>
    </div>
    <div class="grade-cartoes">
      ${cartao(`Preço ${esc(ref || "")}`, cot ? `R$ ${num(cot.preco, 2)}` : "—", cot ? `<span class="${classeSinal(cot.variacao_dia)}">${num(cot.variacao_dia, 2)}%</span> · ${dataBR(cot.data)}` : "")}
      ${cartao("Market cap", reais(mc), "ações ON/PN B3 × preço")}
      ${cartao("EV", reais(ev), "market cap + dív. líquida")}
      ${cartao("P/L", vezes(mc && pos(L("lucro_liquido")) ? mc / L("lucro_liquido") : null), "LTM")}
      ${cartao("P/VP", vezes(mc && pos(L("pl")) ? mc / L("pl") : null), "")}
      ${cartao("EV/EBITDA", vezes(ev && pos(L("ebitda")) ? ev / L("ebitda") : null), "LTM")}
      ${cartao("EV/EBIT", vezes(ev && pos(L("ebit")) ? ev / L("ebit") : null), "LTM")}
      ${cartao("FCF yield", pct(mc && L("fcf") != null ? L("fcf") / mc : null), "FCF LTM ÷ market cap")}
      ${cartao("DY 12m", pct(m.dy_12m, 2), "proventos B3 (data-com 12m) ÷ preço atual")}
      ${cartao("ROE / ROIC", `${pct(L("roe"))} / ${pct(L("roic"))}`, "LTM")}
      ${proxResultado ? cartao("Próximo resultado", proxResultado.atrasado ? "atrasado" : proxResultado.data_estimada ? dataBR(proxResultado.data_estimada) : `até ${dataBR(proxResultado.prazo_legal)}`,
        `${proxResultado.documento} · ${proxResultado.data_estimada ? "estimado pelo ano anterior" : "prazo legal"}`) : ""}
    </div>
    <div class="abas" id="abas-empresa">${ABAS_EMPRESA.map(([k, r]) => `<button data-k="${k}" class="${k === ABA_EMPRESA ? "ativo" : ""}">${r}</button>`).join("")}</div>
    <div id="aba-empresa"></div>`;

  const nt = emp.notas || {};
  const ABAS = {
    resultados: () => {
      document.getElementById("aba-empresa").innerHTML = `
        <div class="cabecalho"><h2 style="margin:0">Resultados</h2>
          <div class="seletor" id="visao">${["trimestral", "semestral", "anual"].map((v) => `<button data-v="${v}" class="${v === VISAO ? "ativo" : ""}">${v[0].toUpperCase() + v.slice(1)}</button>`).join("")}</div></div>
        <div class="grade" id="graficos-empresa"></div>
        <div class="secao painel nota" id="notas">
          <b>Notas.</b> Valores em reais, da CVM (consolidado; individual quando não há consolidado). Semestres e anos só aparecem fechados.
          A visão anual usa o número oficial da DFP. Múltiplos e retornos usam sempre o LTM da mesma data.
          D&amp;A, capex e dividendos pagos não são contas padronizadas da CVM e foram somados pela descrição:<br>
          D&amp;A: ${esc((nt.da || []).join("; ") || "nenhuma linha encontrada (EBITDA = EBIT)")}<br>
          Capex: ${esc((nt.capex || []).join("; ") || "nenhuma linha encontrada")}<br>
          Dividendos pagos: ${esc((nt.dividendos || []).join("; ") || "nenhuma linha encontrada")}<br>
          Dívida bruta sem IFRS 16 = empréstimos, financiamentos e debêntures (CP + LP); com IFRS 16 = soma também os passivos de arrendamento, identificados pela descrição no balanço.</div>`;
      document.getElementById("visao").addEventListener("click", (ev) => {
        const b = ev.target.closest("button"); if (!b) return;
        VISAO = b.dataset.v;
        document.querySelectorAll("#visao button").forEach((x) => x.classList.toggle("ativo", x === b));
        desenharGraficosEmpresa(emp);
      });
      desenharGraficosEmpresa(emp);
    },
    indicadores: () => {
      document.getElementById("aba-empresa").innerHTML = `<div class="painel"><h2>Indicadores — anuais e último LTM</h2><div class="rolagem" id="tab-ind"></div></div>`;
      desenharIndicadores(emp);
    },
    dividendos: () => {
      document.getElementById("aba-empresa").innerHTML = `<div class="grade" id="dividendos"></div>`;
      desenharDividendos(emp, prov, m);
    },
    negocio: () => {
      document.getElementById("aba-empresa").innerHTML = `<div id="resumo-aprofundado"></div>
        <div class="grade grade-empilhada"><div class="painel" id="ficha"></div><div class="painel" id="negocio"></div></div>`;
      desenharFicha(ficha);
      desenharNegocio(negocio, resumo);
    },
    eventos: () => {
      const doEmp = ((NOTICIAS_CACHE && NOTICIAS_CACHE.itens) || []).filter((n) => (n.empresas || []).includes(id));
      const diasHist = (NOTICIAS_CACHE && NOTICIAS_CACHE.dias) || 7;
      document.getElementById("aba-empresa").innerHTML = `<div class="grade grade-empilhada">
        <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Eventos (CVM)</h2>
          <div class="seletor" id="sel-ev">${OPCOES_EVENTOS.map(([k, r]) => `<button data-k="${k}" class="${k === "todos" ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
          <div class="rolagem rolagem-y" id="lista-eventos"></div>
          <div class="nota">Fatos relevantes, comunicados ao mercado e avisos aos acionistas dos últimos 3 anos, com link para o documento oficial na CVM.</div></div>
        <div class="painel"><h2>Notícias que citam a empresa</h2>${listaNoticias(doEmp, 300)}
          <div class="nota">Manchetes que citam o ticker ou o nome de pregão, da mais recente para a mais antiga, nas mesmas fontes da seção
            Notícias e agenda (jornais, sites de mercado e fontes oficiais), guardadas por até ${diasHist} dias. Só a manchete, com link para a matéria.</div></div></div>`;
      desenharEventos(eventos, "todos");
      document.getElementById("sel-ev").addEventListener("click", (ev) => {
        const b = ev.target.closest("button"); if (!b) return;
        document.querySelectorAll("#sel-ev button").forEach((x) => x.classList.toggle("ativo", x === b));
        desenharEventos(eventos, b.dataset.k);
      });
    },
  };
  const mostrar = (k) => {
    limparGraficos();
    ABA_EMPRESA = ABAS[k] ? k : ABAS_EMPRESA[0][0];
    document.querySelectorAll("#abas-empresa button").forEach((x) => x.classList.toggle("ativo", x.dataset.k === ABA_EMPRESA));
    ABAS[ABA_EMPRESA]();
  };
  document.getElementById("abas-empresa").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (b) mostrar(b.dataset.k);
  });
  NOTICIAS_CACHE = await dados("dados/noticias_empresas.json").catch(() => dados("dados/noticias.json").catch(() => null));
  mostrar(ABA_EMPRESA);
}

const OPCOES_EVENTOS = [["todos", "Todos"], ["fato", "Fatos relevantes"], ["comunicado", "Comunicados"], ["aviso", "Avisos"]];
const NOME_CATEGORIA = { fato: "Fato relevante", comunicado: "Comunicado", aviso: "Aviso aos acionistas" };

function desenharEventos(eventos, filtro) {
  const lista = ((eventos && eventos.eventos) || []).filter((e) => filtro === "todos" || e.categoria === filtro);
  document.getElementById("lista-eventos").innerHTML = lista.length ? `<table class="tabela">
    <tr><th>Data</th><th style="text-align:left">Tipo</th><th style="text-align:left">Assunto</th></tr>
    ${lista.slice(0, 150).map((e) => `<tr><td>${dataBR(e.data)}</td><td style="text-align:left" class="${e.categoria === "fato" ? "" : "sub"}">${NOME_CATEGORIA[e.categoria]}</td>
      <td style="white-space:normal;text-align:left">${e.link ? `<a href="${esc(e.link)}" target="_blank" rel="noopener">${esc(e.assunto)}</a>` : esc(e.assunto)}</td></tr>`).join("")}</table>`
    : `<p class="sub">Nenhum documento desse tipo nos últimos 3 anos.</p>`;
}

function desenharNegocio(neg, resumo) {
  const r = document.getElementById("resumo-aprofundado");
  r.innerHTML = resumo && resumo.html ? `<div class="painel secao resumo" style="margin-bottom:14px">
      <h2>${esc(resumo.titulo || "Resumo aprofundado")}</h2>
      ${resumo.html}
      <div class="nota">Resumo aprofundado${resumo.atualizado ? ` · atualizado em ${dataBR(resumo.atualizado)}` : ""} · elaborado a partir do Formulário de Referência e de documentos da empresa.</div>
    </div>` : "";
  const area = document.getElementById("negocio");
  if (!neg || !neg.secoes || !neg.secoes.length) { area.innerHTML = `<h2>Negócio</h2><p class="sub">Trechos do Formulário de Referência indisponíveis.</p>`; return; }
  const paragrafos = (t) => t.split(/\n\n+/).map((p) => `<p style="margin:0 0 8px;line-height:1.65">${esc(p)}</p>`).join("");
  area.innerHTML = `<h2>Negócio — trechos do Formulário de Referência</h2>
    ${neg.secoes.map((s, i) => `<details ${i === 0 ? "open" : ""} style="margin:6px 0">
      <summary style="cursor:pointer;color:var(--ambar)">${esc(s.titulo)}</summary>
      <div style="margin-top:8px">${paragrafos(s.texto)}${s.cortado ? `<p class="sub">… trecho. <a href="${esc(neg.link)}" target="_blank" rel="noopener">Leia a seção completa no formulário</a>.</p>` : ""}</div>
    </details>`).join("")}
    <div class="nota">Texto da própria empresa, extraído do ${esc(neg.fonte)} entregue à CVM, sem edição.</div>`;
}

function desenharFicha(f) {
  const area = document.getElementById("ficha");
  if (!f) { area.innerHTML = `<h2>Sobre a empresa</h2><p class="sub">Ficha indisponível.</p>`; return; }
  const n0 = (v) => (v == null ? "—" : v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }));
  const acionistas = (f.acionistas || []).slice(0, 8);
  const porOrgao = {};
  (f.administracao || []).forEach((a) => (porOrgao[a.orgao || "Outros"] = porOrgao[a.orgao || "Outros"] || []).push(a));
  const ordem = ["Conselho de Administração", "Diretoria e Conselho de Administração", "Diretoria", "Conselho Fiscal"];
  const orgaos = Object.keys(porOrgao).sort((a, b) => (ordem.indexOf(a) + 9) % 9 - (ordem.indexOf(b) + 9) % 9);
  area.innerHTML = `
    <h2>Sobre a empresa</h2>
    ${f.descricao ? `<p style="margin:0 0 8px;line-height:1.6">${esc(f.descricao)}</p>` : ""}
    <div class="nota">${[f.segmento, f.site ? `<a href="${esc(/^https?:/i.test(f.site) ? f.site : "https://" + f.site)}" target="_blank" rel="noopener">${esc(f.site)}</a>` : null,
      f.fre ? `<a href="${esc(f.fre.link)}" target="_blank" rel="noopener">Formulário de Referência ${esc(f.fre.referencia.slice(0, 4))} (v${esc(f.fre.versao)})</a>` : null].filter(Boolean).join(" · ")}</div>
    <div class="grade-cartoes" style="margin-top:10px">
      ${cartao("Free float", f.free_float != null ? `${num(f.free_float, 1)}%` : "—", "ações em circulação")}
      ${cartao("Acionistas", f.base_acionistas ? n0((f.base_acionistas.pf || 0) + (f.base_acionistas.pj || 0) + (f.base_acionistas.institucionais || 0)) : "—",
        f.base_acionistas ? `PF ${n0(f.base_acionistas.pf)} · PJ ${n0(f.base_acionistas.pj)} · inst. ${n0(f.base_acionistas.institucionais)}` : "")}
      ${cartao("Empregados", n0(f.empregados), "")}
      ${cartao("Remuneração da administração", f.remuneracao ? reais(f.remuneracao.total) : "—", f.remuneracao ? `total pago em ${f.remuneracao.exercicio}` : "")}
    </div>
    <div class="sub" style="margin:8px 0 4px;color:var(--ambar)">Principais acionistas</div>
    <table class="tabela"><tr><th>Acionista</th><th>% total</th><th>% ON</th><th>% PN</th></tr>
      ${acionistas.map((a) => `<tr><td style="white-space:normal">${esc(a.nome)}${a.controlador ? ' <span class="sub">(controlador)</span>' : ""}</td>
        <td>${num(a.pct_total, 2)}%</td><td>${num(a.pct_on, 2)}%</td><td>${num(a.pct_pn, 2)}%</td></tr>`).join("")}</table>
    <details style="margin-top:8px"><summary class="sub" style="cursor:pointer">Administração (${(f.administracao || []).length}) e auditor</summary>
      ${orgaos.map((o) => `<div class="sub" style="margin:8px 0 2px;color:var(--ambar)">${esc(o)}</div>
        ${porOrgao[o].map((a) => `<div style="padding:2px 0">${esc(a.nome)} <span class="sub">— ${esc(a.cargo || "")}</span></div>`).join("")}`).join("")}
      ${f.auditor ? `<div class="sub" style="margin-top:8px">Auditor: ${esc(f.auditor.nome)}${f.auditor.desde ? ` (desde ${dataBR(f.auditor.desde)})` : ""}</div>` : ""}
    </details>
    <div class="nota" style="margin-top:6px">Fonte: Formulário de Referência e Formulário Cadastral (CVM).</div>`;
}

function desenharGraficosEmpresa(emp) {
  const area = document.getElementById("graficos-empresa");
  graficos.splice(0).forEach((g) => g.dispose());
  const v = emp[VISAO], S = v.series;
  const rot = v.periodos.map((p) => rotuloPeriodo(p, VISAO, emp.mes_fim_exercicio || 12));
  const neg = (arr) => arr.map((x) => (x == null ? null : -x));
  const soma = (a, b) => a.map((x, i) => (x == null && b[i] == null ? null : (x || 0) + (b[i] || 0)));
  const defs = [
    ["Receita líquida", { series: [{ nome: "Receita", valores: S.receita, cor: COR.azul }, { nome: "Crescimento a/a", valores: S.cresc_receita, tipo: "line", eixo: "dir", cor: COR.ambar }], eixoDir: "pct" }],
    ["Lucro bruto e margem bruta", { series: [{ nome: "Lucro bruto", valores: S.lucro_bruto, cor: COR.azul }, { nome: "Margem bruta", valores: S.m_bruta, tipo: "line", eixo: "dir", cor: COR.ambar }], eixoDir: "pct" }],
    ["EBITDA e margem EBITDA", { series: [{ nome: "EBITDA", valores: S.ebitda, cor: COR.azul }, { nome: "Margem EBITDA", valores: S.m_ebitda, tipo: "line", eixo: "dir", cor: COR.ambar }], eixoDir: "pct" }],
    ["EBIT e margem EBIT", { series: [{ nome: "EBIT", valores: S.ebit, cor: COR.azul }, { nome: "Margem EBIT", valores: S.m_ebit, tipo: "line", eixo: "dir", cor: COR.ambar }], eixoDir: "pct" }],
    ["Lucro líquido e margem líquida", { series: [{ nome: "Lucro líquido", valores: S.lucro_liquido, cor: COR.verde }, { nome: "Margem líquida", valores: S.m_liquida, tipo: "line", eixo: "dir", cor: COR.ambar }], eixoDir: "pct" }],
    ["Resultado financeiro", { series: [{ nome: "Receitas financeiras", valores: S.rec_fin, cor: COR.verde, pilha: "fin" }, { nome: "Despesas financeiras", valores: S.desp_fin, cor: COR.vermelho, pilha: "fin" }, { nome: "Resultado financeiro", valores: S.res_fin, tipo: "line", cor: COR.ambar }] }],
    ["Retorno (LTM)", { series: [{ nome: "ROE", valores: S.roe, tipo: "line", cor: COR.ambar }, { nome: "ROIC", valores: S.roic, tipo: "line", cor: COR.ciano }], eixoEsq: "pct" }],
  ];
  area.innerHTML = defs.map((d, i) => `<div class="painel" data-info="${INFO_EMPRESA[d[0]] || ""}"><h2>${d[0]}</h2><div class="grafico" id="ge-${i}"></div></div>`).join("")
    + `<div class="painel" data-info="fluxo_caixa"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Fluxo de caixa (DFC)</h2>
        <div class="seletor" id="sel-fc">${OPCOES_FC.map(([k, r]) => `<button data-k="${k}" class="${k === FC_SEL ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
        <div class="grafico" id="ge-fc"></div>
        <div class="nota">FCO = operacional · FCI = investimento · FCFi = financiamento · Soma = FCO + FCI + FCFi (variação do caixa, antes da variação cambial).</div></div>
      <div class="painel" data-info="endividamento"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Endividamento</h2>
        <div class="seletor" id="sel-div"><button data-k="sem" class="${DIV_IFRS16 ? "" : "ativo"}">Sem IFRS 16</button><button data-k="com" class="${DIV_IFRS16 ? "ativo" : ""}">+ Arrendamentos (IFRS 16)</button></div></div>
        <div class="grafico" id="ge-div"></div>
        <div class="nota">Sem IFRS 16: empréstimos, financiamentos e debêntures. Com IFRS 16: soma os passivos de arrendamento (aluguéis, frota, aeronaves) identificados no balanço. Dív. líq./EBITDA usa o EBITDA dos últimos 12 meses.</div></div>`;
  defs.forEach((d, i) => grafico(document.getElementById(`ge-${i}`), { rotulos: rot, ...d[1] }));
  const vazio = S.receita.map(() => null);
  const fco = S.fco || vazio, fci = S.fci || vazio, fcfin = S.fcfin || vazio;
  const somaFc = fco.map((x, i) => (x == null && fci[i] == null && fcfin[i] == null ? null : (x || 0) + (fci[i] || 0) + (fcfin[i] || 0)));
  const seriesFc = {
    fco: { nome: "FCO", valores: fco, cor: COR.azul }, fci: { nome: "FCI", valores: fci, cor: COR.vermelho },
    fcfin: { nome: "FCFi", valores: fcfin, cor: COR.roxo }, soma: { nome: "Soma (FCO+FCI+FCFi)", valores: somaFc, cor: COR.verde },
  };
  let gFc = null;
  const desenharFc = () => {
    if (gFc) { gFc.dispose(); graficos.splice(graficos.indexOf(gFc), 1); }
    const escolhidas = FC_SEL === "todos" ? [seriesFc.fco, seriesFc.fci, seriesFc.fcfin] : [seriesFc[FC_SEL]];
    gFc = grafico(document.getElementById("ge-fc"), { rotulos: rot, series: escolhidas, janela: 12 });
  };
  document.getElementById("sel-fc").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    FC_SEL = b.dataset.k;
    document.querySelectorAll("#sel-fc button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharFc();
  });
  desenharFc();

  let gDiv = null;
  const caixaTotal = soma(S.caixa, S.aplicacoes);
  const desenharDiv = () => {
    if (gDiv) { gDiv.dispose(); graficos.splice(graficos.indexOf(gDiv), 1); }
    const com = DIV_IFRS16 && S.divida_bruta_ifrs16;
    gDiv = grafico(document.getElementById("ge-div"), { rotulos: rot, eixoDir: "vezes", janela: 16, series: [
      { nome: "Dívida bruta (empréstimos)", valores: S.divida_bruta, cor: COR.vermelho, pilha: "divida" },
      ...(com ? [{ nome: "Arrendamentos (IFRS 16)", valores: S.arrendamentos, cor: COR.roxo, pilha: "divida" }] : []),
      { nome: "Caixa + aplicações", valores: caixaTotal, cor: COR.verde },
      { nome: com ? "Dívida líquida c/ arrend." : "Dívida líquida", valores: com ? S.divida_liquida_ifrs16 : S.divida_liquida, cor: COR.azul },
      { nome: com ? "Dív. líq./EBITDA c/ arrend." : "Dív. líq./EBITDA", valores: com ? S.dl_ebitda_ifrs16 : S.dl_ebitda, tipo: "line", eixo: "dir", cor: COR.ambar }] });
  };
  document.getElementById("sel-div").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    DIV_IFRS16 = b.dataset.k === "com";
    document.querySelectorAll("#sel-div button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharDiv();
  });
  desenharDiv();
  redesenharDividendos();
}

function desenharIndicadores(emp) {
  // Últimos 8 anos fechados (ou o máximo disponível) + o último LTM
  const anual = emp.anual, ltm = emp.ltm, mesFim = emp.mes_fim_exercicio || 12;
  const cols = anual.periodos.map((p, i) => ({ visao: anual, i, titulo: rotuloPeriodo(p, "anual", mesFim) })).slice(-8);
  const nl = ltm.periodos.length - 1;
  if (nl >= 0 && ltm.periodos[nl] !== anual.periodos[anual.periodos.length - 1]) cols.push({ visao: ltm, i: nl, titulo: `LTM ${dataBR(ltm.periodos[nl])}` });
  const valor = (v, k, i) => (k ? (v.series[k] || [])[i] : ((v.series.caixa || [])[i] || 0) + ((v.series.aplicacoes || [])[i] || 0));
  document.getElementById("tab-ind").innerHTML = cols.length === 0 ? `<p class="sub">Sem anos fechados nem LTM disponíveis.</p>` : `
    <table class="tabela"><tr><th>Indicador</th>${cols.map((c) => `<th>${c.titulo}</th>`).join("")}</tr>
    ${INDICADORES_LTM.map(([nome, k, f]) => `<tr><td>${nome}</td>${cols.map((c) => `<td>${f(valor(c.visao, k, c.i))}</td>`).join("")}</tr>`).join("")}</table>
    <div class="nota">Colunas anuais: exercício fechado (DFP). Última coluna: últimos 12 meses (LTM). Retornos e múltiplos de endividamento usam o LTM da data.</div>`;
}

let ULTIMO_DIV = null;
function desenharDividendos(emp, prov, m) { ULTIMO_DIV = { emp, prov, m }; redesenharDividendos(true); }

function redesenharDividendos(primeira = false) {
  if (!ULTIMO_DIV) return;
  const { emp, prov, m } = ULTIMO_DIV;
  const area = document.getElementById("dividendos");
  if (!area) return;
  const anual = emp.anual, A = anual.series;
  const rot = anual.periodos.map((p) => rotuloPeriodo(p, "anual", emp.mes_fim_exercicio || 12));
  const porAno = (prov && prov.proventos_por_acao_ano) || {};
  const anos = Object.keys(porAno).sort();
  const cot = prov && prov.cotacao_semanal && prov.cotacao_semanal.datas ? prov.cotacao_semanal : null;
  const precoMedio = (ano) => {
    if (!cot) return null;
    const v = cot.datas.map((d, i) => (d.startsWith(ano) ? cot.fechamento[i] : null)).filter((x) => x != null);
    return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
  };
  const b3 = (prov && prov.proventos_b3) || [];
  if (primeira || !document.getElementById("gd-dfc")) {
    area.innerHTML = `
      <div class="painel" data-info="dividendos_dfc"><h2>Dividendos + JCP pagos (DFC) e payout</h2><div class="grafico" id="gd-dfc"></div></div>
      <div class="painel" data-info="proventos_acao"><h2>Proventos por ação ${esc(prov && prov.papel_referencia ? "· " + prov.papel_referencia : "")} e DY</h2><div class="grafico" id="gd-acao"></div>
        <div class="nota">${prov && prov.fonte_por_acao === "B3"
          ? "Proventos anunciados (dividendos + JCP) por ação, somados pelo ano da data-com — fonte B3. DY do ano = soma, provento a provento, de valor ÷ preço de fechamento na data-com (também da B3)."
          : "Proventos por ação somados pelo ano da data ex — fonte Yahoo Finance (não oficial). DY do ano = proventos ÷ preço médio semanal do ano (Yahoo)."}
          Não é o valor pago na DFC: esse está no gráfico ao lado, pelo caixa efetivamente pago no ano.</div></div>
      <div class="painel"><h2>Proventos anunciados (B3) — últimos 3 anos</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Tipo</th><th>Classe</th><th>Data-com</th><th>Pagamento</th><th>R$/ação</th><th>Preço data-com</th><th>Aprovado</th></tr>
        ${b3.length ? b3.map((p) => `<tr><td>${esc(p.tipo)}</td><td>${esc(p.classe)}</td><td>${dataBR(p.data_com)}</td><td>${dataBR(p.pagamento)}</td><td>${num(p.valor, 6)}</td><td>${p.preco_data_com ? num(p.preco_data_com, 2) : "—"}</td><td class="sub">${dataBR(p.aprovado)}</td></tr>`).join("")
          : `<tr><td colspan="7" class="sub">A B3 não informou proventos.</td></tr>`}
      </table></div><div class="nota">Proventos 12m (${esc(prov && prov.classe_referencia || "classe de referência")}): R$ ${num(m.proventos_12m_por_acao, 4)} por ação, data-com nos últimos 12 meses.
        A data de pagamento só é informada pela B3 para cerca dos últimos 12 meses.</div></div>
      <div class="painel" data-info="cotacao"><h2>Cotação semanal ${esc(prov && prov.papel_referencia ? "· " + prov.papel_referencia : "")}</h2><div class="grafico" id="gd-cot"></div>
        <div class="nota">Fechamento semanal dos últimos 10 anos, sem ajuste por proventos — fonte Yahoo Finance (não oficial).</div></div>`;
  }
  grafico(document.getElementById("gd-dfc"), { rotulos: rot, eixoDir: "pct", series: [
    { nome: "Dividendos + JCP pagos", valores: A.div_pagos, cor: COR.verde },
    { nome: "Payout", valores: A.payout, tipo: "line", eixo: "dir", cor: COR.ambar }] });
  const dyAno = (prov && prov.dy_ano) || {};
  grafico(document.getElementById("gd-acao"), { rotulos: anos, eixoEsq: "preco", eixoDir: "pct", janela: 12, series: [
    { nome: "R$ por ação", valores: anos.map((a) => porAno[a]), cor: COR.verde },
    { nome: "DY", valores: anos.map((a) => { if (dyAno[a] != null) return dyAno[a]; const p = precoMedio(a); return p ? porAno[a] / p : null; }), tipo: "line", eixo: "dir", cor: COR.ambar }] });
  if (cot) grafico(document.getElementById("gd-cot"), { xTempo: true, eixoEsq: "preco", series: [
    { nome: "Fechamento", valores: cot.datas.map((d, i) => [d, cot.fechamento[i]]), tipo: "line", cor: COR.ambar }] });
  else document.getElementById("gd-cot").innerHTML = `<p class="sub">Cotação histórica indisponível.</p>`;
}

/* ============ Macro ============ */
let JANELA_MACRO = 10;
const SUBS_MACRO = [["atividade", "Atividade"], ["inflacao", "Inflação"], ["monetaria", "Política monetária"], ["expectativas", "Expectativas (Focus)"], ["cambio", "Câmbio"]];
const NOMES_FOCUS = { selic: "Selic fim de ano (% a.a.)", ipca: "IPCA (%)", pib: "PIB (%)", cambio: "Câmbio fim de ano (R$/US$)" };
const ESCOLHA_GRAFICO = {};  // opção escolhida em cada gráfico com botões (fica ao trocar de janela)
const NUCLEOS = [["nucleo_ex0", "EX0", COR.azul], ["nucleo_ex2", "EX2", COR.cinza], ["nucleo_ex3", "EX3", COR.roxo],
  ["nucleo_ms", "MS", COR.ciano], ["nucleo_dp", "DP", COR.verde], ["nucleo_p55", "P55", "#db61a2"]];

async function paginaMacro(sub) {
  if (!SUBS_MACRO.some(([k]) => k === sub)) sub = SUBS_MACRO[0][0];
  const macro = await dados("dados/macro.json");
  const S = macro.series, F = macro.focus;
  const u = (k) => ultimo(S[k]);
  const mes = (k) => (u(k).data ? `${MESES[Number(u(k).data.slice(5, 7)) - 1]}/${u(k).data.slice(2, 4)}` : "");
  const focusAno = (k) => { const a = String(new Date().getFullYear()); const f = F[k] && F[k][a]; return f ? f.valores[f.valores.length - 1] : null; };
  const cartoes = {
    inflacao: [cartao("IPCA no mês", pctPronto(u("ipca").valor), mes("ipca")), cartao("IPCA 12 meses", pctPronto(u("ipca_12m").valor), mes("ipca_12m")),
      cartao("IPCA 3m anualizado", pctPronto(u("ipca_mm3").valor), "sem ajuste sazonal"),
      cartao("Média dos núcleos 12m", pctPronto(u("nucleos_media_12m").valor), "EX0, EX3, MS, DP, P55"),
      cartao("IGP-M 12 meses", pctPronto(u("igpm_12m").valor), mes("igpm_12m")), cartao("INCC 12 meses", pctPronto(u("incc_12m").valor), mes("incc_12m"))],
    atividade: [cartao("PIB tri/tri (dessaz.)", pctPronto(u("pib_tri").valor), u("pib_tri").data ? `${Math.ceil(Number(u("pib_tri").data.slice(5, 7)) / 3)}º tri/${u("pib_tri").data.slice(0, 4)}` : ""),
      cartao("PIB 4 trimestres", pctPronto(u("pib_12m").valor), "acumulado"), cartao("PIB anual", pctPronto(u("pib_anual").valor), u("pib_anual").data ? u("pib_anual").data.slice(0, 4) : ""),
      cartao("IBC-Br m/m (dessaz.)", pctPronto(u("ibcbr_mensal").valor), mes("ibcbr_mensal")), cartao("IBC-Br 12 meses", pctPronto(u("ibcbr_12m").valor), mes("ibcbr_12m")),
      cartao("Desemprego", pctPronto(u("desemprego").valor, 1), u("desemprego").data ? `trimestre até ${mes("desemprego")}` : "")],
    monetaria: [cartao("Selic meta", pctPronto(u("selic_meta").valor), dataBR(u("selic_meta").data)), cartao("CDI", pctPronto(u("cdi").valor), dataBR(u("cdi").data)),
      cartao("Juro real ex-post", pctPronto(u("juro_real").valor), "Selic ÷ IPCA 12m")],
    cambio: [cartao("Dólar PTAX", `R$ ${num(u("usd").valor, 4)}`, dataBR(u("usd").data)), cartao("Euro PTAX", `R$ ${num(u("eur").valor, 4)}`, dataBR(u("eur").data))],
    expectativas: [cartao(`IPCA ${new Date().getFullYear()}`, pctPronto(focusAno("ipca")), "mediana Focus"), cartao(`Selic fim de ${new Date().getFullYear()}`, pctPronto(focusAno("selic")), "mediana Focus"),
      cartao(`Câmbio fim de ${new Date().getFullYear()}`, focusAno("cambio") ? `R$ ${num(focusAno("cambio"), 2)}` : "—", "mediana Focus"), cartao(`PIB ${new Date().getFullYear()}`, pctPronto(focusAno("pib")), "mediana Focus")],
  }[sub];
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Macro</h1><div class="sub">Banco Central (SGS), IBGE, FGV e boletim Focus · atualizado em ${dataBR(macro.gerado_em)} · botões = janela inicial; use a roda do mouse ou a barra para ver mais</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        ${sub === "expectativas" ? "" : `<div class="seletor" id="janela">${[[1, "1A"], [5, "5A"], [10, "10A"], [99, "Máx"]].map(([a, r]) => `<button data-a="${a}" class="${a === JANELA_MACRO ? "ativo" : ""}">${r}</button>`).join("")}</div>`}
        <a class="botao" href="downloads/macro.xlsx" download>Baixar planilha de Macro</a></div></div>
    <div class="abas">${SUBS_MACRO.map(([k, n]) => `<a href="#/on/macro/${k}" class="${k === sub ? "ativo" : ""}">${n}</a>`).join("")}</div>
    <div class="grade-cartoes">${cartoes.join("")}</div>
    <div class="grade" id="graficos-macro"></div>`;
  const janela = document.getElementById("janela");
  if (janela) janela.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    JANELA_MACRO = Number(b.dataset.a);
    document.querySelectorAll("#janela button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharMacro(S, F, sub);
  });
  desenharMacro(S, F, sub);
}

function desenharMacro(S, F, sub) {
  limparGraficos();
  // Histórico completo em todos os gráficos; os botões de janela só escolhem o início (dá para dar zoom para trás)
  const inicio = (anos) => { if (anos >= 99) return null; const d = new Date(); d.setFullYear(d.getFullYear() - anos); return d.toISOString().slice(0, 10); };
  const corte = inicio(JANELA_MACRO);
  const P = (s) => (s ? s.datas.map((d, i) => [d, s.valores[i]]) : []);
  const ACUM = { "12 meses": "12m", "3 meses anualizado": "mm3" };
  const rotuloAcum = { "12m": "12 meses", mm3: "3 meses anualizado" };
  // um índice: barras com a variação do mês e linha com o acumulado escolhido no botão
  const indice = (k) => Object.fromEntries(Object.entries(ACUM).map(([rot, suf]) => [rot, { eixoEsq: "pctPronto", eixoDir: "pctPronto", series: [
    { nome: "Mensal", valores: P(S[k]), cor: COR.azul },
    { nome: rot, valores: P(S[`${k}_${suf}`]), tipo: "line", eixo: "dir", cor: suf === "12m" ? COR.vermelho : COR.ambar }] }]));
  const comparativo = Object.fromEntries(Object.entries(ACUM).map(([rot, suf]) => [rot, { eixoEsq: "pctPronto", series: [
    { nome: `IPCA ${rotuloAcum[suf]}`, valores: P(S[`ipca_${suf}`]), tipo: "line", cor: COR.vermelho },
    { nome: `IGP-M ${rotuloAcum[suf]}`, valores: P(S[`igpm_${suf}`]), tipo: "line", cor: COR.azul },
    { nome: `INCC-DI ${rotuloAcum[suf]}`, valores: P(S[`incc_${suf}`]), tipo: "line", cor: COR.verde }] }]));
  const nucleos = Object.fromEntries(Object.entries(ACUM).map(([rot, suf]) => [rot, { eixoEsq: "pctPronto", series: [
    { nome: "Média dos 5 núcleos", valores: P(S[`nucleos_media_${suf}`]), tipo: "line", cor: COR.ambar },
    ...NUCLEOS.map(([k, n, c]) => ({ nome: n, valores: P(S[`${k}_${suf}`]), tipo: "line", cor: c })),
    { nome: "IPCA cheio", valores: P(S[`ipca_${suf}`]), tipo: "line", cor: COR.vermelho, tracejado: true }] }]));
  const anos = S.pib_anual ? S.pib_anual.datas.map((d) => d.slice(0, 4)) : [];
  const nominal = S.pib_nominal ? Object.fromEntries(S.pib_nominal.datas.map((d, i) => [d.slice(0, 4), S.pib_nominal.valores[i]])) : {};
  // cada item: { t: título, info, op: opções do gráfico | alt: { rótulo do botão: opções }, largo, focus }
  const defs = {
    inflacao: [
      { t: "Inflação: IPCA, IGP-M e INCC", info: "ipca", alt: comparativo, largo: true },
      { t: "IPCA", info: "ipca", alt: indice("ipca") },
      { t: "Núcleos do IPCA", info: "nucleos", alt: nucleos },
      { t: "IGP-M", info: "igpm", alt: indice("igpm") },
      { t: "INCC-DI (custo da construção)", info: "incc", alt: indice("incc") },
    ],
    atividade: [
      { t: "IBC-Br (prévia mensal do PIB)", info: "ibcbr", op: { series: [{ nome: "Mensal (dessaz., m/m)", valores: P(S.ibcbr_mensal), cor: COR.azul }, { nome: "Acumulado em 12 meses", valores: P(S.ibcbr_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto", inicio: inicio(Math.min(JANELA_MACRO, 3)) } },
      { t: "PIB trimestral", info: "pib_tri", op: { series: [{ nome: "Trimestral (dessaz., tri/tri)", valores: P(S.pib_tri), cor: COR.azul }, { nome: "Acumulado em 4 trimestres", valores: P(S.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto" } },
      { t: "PIB anual (anos fechados)", info: "pib_anual", op: { xTempo: false, rotulos: anos, eixoEsq: "reais", eixoDir: "pctPronto", janela: 30, series: [
        { nome: "PIB nominal (R$ correntes)", valores: anos.map((a) => nominal[a] ?? null), cor: COR.azul },
        { nome: "Crescimento real", valores: S.pib_anual ? S.pib_anual.valores : [], tipo: "line", eixo: "dir", cor: COR.ambar }] } },
      { t: "Desemprego (PNAD Contínua, trimestre móvel)", info: "desemprego_br", op: { eixoEsq: "pctPronto", series: [
        { nome: "Taxa de desocupação", valores: P(S.desemprego), tipo: "line", cor: COR.vermelho }] } },
    ],
    monetaria: [
      { t: "Selic meta, CDI e IPCA 12 meses", info: "selic", largo: true, op: { series: [{ nome: "Selic meta", valores: P(S.selic_meta), tipo: "line", cor: COR.ambar }, { nome: "CDI", valores: P(S.cdi), tipo: "line", cor: COR.ciano }, { nome: "IPCA 12m", valores: P(S.ipca_12m), tipo: "line", cor: COR.vermelho }, { nome: "Média dos núcleos 12m", valores: P(S.nucleos_media_12m), tipo: "line", cor: COR.roxo, tracejado: true }], eixoEsq: "pctPronto", degrau: true } },
      { t: "Juro real ex-post (Selic ÷ IPCA 12m)", info: "juro_real", largo: true, op: { series: [{ nome: "Juro real", valores: P(S.juro_real), tipo: "line", cor: COR.verde }], eixoEsq: "pctPronto" } },
    ],
    cambio: [
      { t: "Câmbio PTAX", info: "cambio", largo: true, op: { series: [{ nome: "Dólar", valores: P(S.usd), tipo: "line", cor: COR.verde }, { nome: "Euro", valores: P(S.eur), tipo: "line", cor: COR.roxo }], eixoEsq: "preco" } },
    ],
    expectativas: Object.keys(NOMES_FOCUS).map((k) => ({ t: NOMES_FOCUS[k], info: "focus", focus: k })),
  }[sub];
  const area = document.getElementById("graficos-macro");
  area.innerHTML = defs.map((d, i) => {
    const titulo = d.alt
      ? `<div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">${d.t}</h2><div class="seletor" data-alt="${i}">
          ${Object.keys(d.alt).map((k) => `<button data-k="${k}" class="${k === (ESCOLHA_GRAFICO[d.t] || Object.keys(d.alt)[0]) ? "ativo" : ""}">${k}</button>`).join("")}</div></div>`
      : `<h2>${d.t}</h2>`;
    return `<div class="painel${d.largo ? " largo" : ""}" data-info="${d.info}">${titulo}<div class="grafico" id="gm-${i}"></div></div>`;
  }).join("");
  const desenhar = (i) => {
    const d = defs[i], el = document.getElementById(`gm-${i}`);
    const antigo = echarts.getInstanceByDom(el);
    if (antigo) { graficos.splice(graficos.indexOf(antigo), 1); antigo.dispose(); }
    if (d.focus) {
      const anosF = Object.keys(F[d.focus] || {}).sort();
      grafico(el, { xTempo: true, eixoEsq: d.focus === "cambio" ? "preco" : "pctPronto",
        series: anosF.map((a, j) => ({ nome: a, valores: F[d.focus][a].datas.map((x, n) => [x, F[d.focus][a].valores[n]]), tipo: "line", cor: PALETA_DATAS[j % PALETA_DATAS.length] })) });
      return;
    }
    const opcoes = d.alt ? d.alt[ESCOLHA_GRAFICO[d.t] || Object.keys(d.alt)[0]] : d.op;
    const { inicio: ini, xTempo = true, ...resto } = opcoes;
    grafico(el, xTempo ? { xTempo: true, inicioTempo: (ini !== undefined ? ini : corte) || "1990-01-01", deslizante: true, ...resto } : resto);
  };
  defs.forEach((_, i) => desenhar(i));
  area.querySelectorAll("[data-alt]").forEach((sel) => sel.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    const i = Number(sel.dataset.alt);
    ESCOLHA_GRAFICO[defs[i].t] = b.dataset.k;
    sel.querySelectorAll("button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenhar(i);
  }));
}

/* ============ Juros ============ */
const GRUPOS_TESOURO = [
  ["Tesouro Prefixado", "Prefixado (LTN)"], ["Tesouro Prefixado com Juros Semestrais", "Prefixado com juros semestrais (NTN-F)"],
  ["Tesouro IPCA+", "IPCA+ (NTN-B Principal)"], ["Tesouro IPCA+ com Juros Semestrais", "IPCA+ com juros semestrais (NTN-B)"],
  ["Tesouro Selic", "Selic (LFT)"], ["Tesouro Renda+ Aposentadoria Extra", "Renda+"], ["Tesouro Educa+", "Educa+"],
  ["Tesouro IGPM+ com Juros Semestrais", "IGP-M+ com juros semestrais (NTN-C)"],
];

function variacaoSemana(tes, t) {
  const c = tes.curvas["1 semana"];
  if (!c) return null;
  const ponto = [...c.prefixado, ...c.ipca].find((p) => p.vencimento === t.vencimento && p.titulo === t.tipo);
  return ponto ? t.taxa_compra - ponto.taxa : null;
}

function interpolar(pontos, anos) {
  if (!pontos || !pontos.length || anos < pontos[0].anos || anos > pontos[pontos.length - 1].anos) return null;
  const k = pontos.findIndex((p) => p.anos >= anos);
  if (pontos[k].anos === anos || k === 0) return pontos[k].taxa;
  const a = pontos[k - 1], b = pontos[k];
  return a.taxa + ((anos - a.anos) / (b.anos - a.anos)) * (b.taxa - a.taxa);
}
let REF_TITULOS = "oficial";

// Tabela de títulos: mesma estrutura nas duas referências (oficial = data base do Tesouro Transparente; tempo real = não oficial)
function tabelaTitulos(tes, modo) {
  const tr = tes.tempo_real;
  const oficial = Object.fromEntries(tes.titulos.map((t) => [`${t.tipo}|${t.vencimento}`, t]));
  const lista = modo === "agora" && tr ? tr.titulos : tes.titulos;
  return GRUPOS_TESOURO.filter(([tipo]) => lista.some((t) => t.tipo === tipo)).map(([tipo, nome]) => `
    <div><div class="sub" style="margin:4px 0 6px;color:var(--ambar)">${esc(nome)}</div><table class="tabela">
      <tr><th>Vencimento</th><th>Taxa compra</th><th>${modo === "agora" ? "vs. oficial" : "Var. 1 sem."}</th><th>PU compra</th>${modo === "agora" ? "<th>Hora</th>" : ""}</tr>
      ${lista.filter((t) => t.tipo === tipo).map((t) => {
        const o = oficial[`${t.tipo}|${t.vencimento}`];
        const v = modo === "agora" ? (o ? t.taxa_compra - o.taxa_compra : null) : variacaoSemana(tes, t);
        return `<tr class="clicavel" data-id="${esc(t.id)}"><td>${dataBR(t.vencimento)}</td><td>${num(t.taxa_compra, 2)}%</td>
          <td class="${v == null ? "" : v > 0 ? "neg" : "pos"}">${v == null ? "—" : `${v > 0 ? "+" : ""}${num(v * 100, 0)} bp`}</td><td>R$ ${num(t.pu_compra, 2)}</td>
          ${modo === "agora" ? `<td class="sub">${esc((t.precificado_em || "").slice(11, 16))}</td>` : ""}</tr>`; }).join("")}
    </table></div>`).join("");
}

function notaTitulos(tes, modo) {
  const tr = tes.tempo_real;
  return modo === "agora" && tr
    ? `<b>Tempo real · não oficial:</b> taxas que o site do Tesouro Direto pratica agora (preços de ${dataBR(tr.precificado_em.slice(0, 10))} às ${tr.precificado_em.slice(11, 16)}),
       lidas de um endereço interno do site, sem documentação nem garantia, e conferidas contra a última taxa oficial antes de publicar.
       "vs. oficial" compara com a data base de ${dataBR(tes.data_base)}. Atualizado 3 vezes por dia útil.`
    : `<b>Oficial:</b> taxa e preço de compra da manhã de ${dataBR(tes.data_base)} nos dados abertos do Tesouro Nacional (Tesouro Transparente),
       publicados com 1 a 2 dias úteis de atraso. Variação em pontos-base contra a curva de 1 semana antes.`;
}

async function paginaJuros() {
  const [di, tes] = await Promise.all([dados("dados/curva_di.json").catch(() => null), dados("dados/tesouro.json")]);
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Juros</h1><div class="sub">Curvas DI (B3, fim do dia) e Tesouro Direto · taxas em % a.a. ·
      Tesouro oficial com <b>referência ${dataBR(tes.data_base)}</b> (o Tesouro Transparente publica com 1–2 dias úteis de atraso)</div></div>
      <a class="botao" href="downloads/juros.xlsx" download>Baixar planilha de Juros</a></div>
    <div class="grade">
      <div data-info="curva_di" class="painel"><h2>Curva DI x Pré (B3)</h2><div class="grafico alto" id="gj-di"></div></div>
      <div data-info="di_ipca" class="painel"><h2>Curva DI x IPCA, juro real (B3) · a partir de 3 meses</h2><div class="grafico alto" id="gj-dic"></div></div>
      <div data-info="tesouro_ipca" class="painel largo"><h2>Tesouro IPCA+ (juro real) — oficial · ref. ${dataBR(tes.data_base)}</h2><div class="grafico alto" id="gj-ipca"></div></div>
      <div data-info="tesouro_pre" class="painel largo"><h2>Tesouro prefixado — oficial · ref. ${dataBR(tes.data_base)}</h2><div class="grafico alto" id="gj-pre"></div></div>
      <div data-info="inflacao_implicita" class="painel largo"><h2>Inflação implícita (prefixado × IPCA+) — oficial · ref. ${dataBR(tes.data_base)}</h2><div class="grafico alto" id="gj-impl"></div></div>
      <div data-info="vertices" class="painel largo"><h2>Taxas DI por prazo (B3)</h2><div class="rolagem" id="tab-vertices"></div>
        <div class="nota">Interpolação linear da curva DI nos prazos (anos de 252 dias úteis). DI x IPCA = juro real.</div></div>
      <div data-info="titulos" class="painel largo"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Títulos do Tesouro Direto</h2>
        <div class="seletor" id="ref-titulos"><button data-k="oficial">Oficial · data base ${dataBR(tes.data_base)}</button>
          <button data-k="agora" ${tes.tempo_real ? "" : "disabled title=\"Sem preço do momento mais novo que a data base\""}>Tempo real · não oficial${tes.tempo_real ? ` · ${tes.tempo_real.precificado_em.slice(11, 16)}` : ""}</button></div></div>
        <div class="grade" id="tab-tit"></div>
        <div class="nota" id="nota-tit"></div>
        <div class="nota">Clique num título para ver o histórico oficial de taxa e preço.</div></div>
      <div class="painel largo" id="painel-titulo" style="display:none"><h2 id="titulo-hist"></h2><div class="grafico alto" id="gj-hist"></div></div>
    </div>
    <div class="nota secao">A curva DI vem do arquivo "Taxas de Mercado para Swaps" da B3 (fim de dia). As curvas do Tesouro usam a taxa de compra
      do Tesouro Direto: título sem cupom e, nos prazos onde ele não existe, o título com juros semestrais. A inflação implícita interpola a curva
      prefixada nos vencimentos do IPCA+, sem extrapolar.</div>`;

  const rotulos = Object.keys(tes.curvas);
  const porData = (fonte, campo, maxAnos, minAnos = 0) => rotulos
    .filter((r) => fonte[r] && fonte[r][campo] && fonte[r][campo].length)
    .map((r, i) => ({ nome: fonte === tes.curvas && r === "hoje" ? "último oficial" : r, valores: fonte[r][campo].filter((p) => p.anos <= maxAnos && p.anos >= minAnos).map((p) => [p.anos, p.taxa]),
      tipo: "line", cor: PALETA_DATAS[i], tracejado: i > 0 }));
  const datas = (fonte) => rotulos.filter((r) => fonte[r]).map((r) => `${fonte === tes.curvas && r === "hoje" ? "último oficial" : r}: ${dataBR(fonte[r].data)}`).join(" · ");
  const notaDatas = (id, fonte) => document.getElementById(id).insertAdjacentHTML("afterend", `<div class="nota">${datas(fonte)}</div>`);
  if (di) {
    grafico(document.getElementById("gj-di"), { xNome: "anos (dias úteis/252)", eixoEsq: "pctPronto", series: porData(di.curvas, "pre", 10) });
    grafico(document.getElementById("gj-dic"), { xNome: "anos (dias úteis/252)", eixoEsq: "pctPronto", series: porData(di.curvas, "ipca", 10, 0.25) });
    notaDatas("gj-di", di.curvas); notaDatas("gj-dic", di.curvas);
  } else {
    document.getElementById("gj-di").innerHTML = document.getElementById("gj-dic").innerHTML = `<p class="sub">Curva DI indisponível.</p>`;
  }
  grafico(document.getElementById("gj-pre"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: porData(tes.curvas, "prefixado", 99) });
  grafico(document.getElementById("gj-ipca"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: porData(tes.curvas, "ipca", 99) });
  grafico(document.getElementById("gj-impl"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: porData(tes.curvas, "inflacao_implicita", 99) });
  ["gj-pre", "gj-ipca", "gj-impl"].forEach((id) => notaDatas(id, tes.curvas));

  if (di) {
    const datasDi = Object.keys(di.curvas);
    const prazos = [[0.5, "6 meses"], [1, "1 ano"], [2, "2 anos"], [3, "3 anos"], [5, "5 anos"], [10, "10 anos"]];
    const linhas = (campo) => prazos.map(([a, r]) => `<tr><td>${r}</td>${datasDi.map((d) => `<td>${pctPronto(interpolar(di.curvas[d][campo], a))}</td>`).join("")}</tr>`).join("");
    document.getElementById("tab-vertices").innerHTML = `<table class="tabela">
      <tr><th>DI x Pré</th>${datasDi.map((d) => `<th>${d}<br><span class="sub">${dataBR(di.curvas[d].data)}</span></th>`).join("")}</tr>${linhas("pre")}
      <tr><th>DI x IPCA</th>${datasDi.map(() => "<th></th>").join("")}</tr>${linhas("ipca")}</table>`;
  }

  const mostrarTitulos = (modo) => {
    REF_TITULOS = modo === "agora" && tes.tempo_real ? "agora" : "oficial";
    document.querySelectorAll("#ref-titulos button").forEach((x) => x.classList.toggle("ativo", x.dataset.k === REF_TITULOS));
    document.getElementById("tab-tit").innerHTML = tabelaTitulos(tes, REF_TITULOS);
    document.getElementById("nota-tit").innerHTML = notaTitulos(tes, REF_TITULOS);
  };
  document.getElementById("ref-titulos").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (b && !b.disabled) mostrarTitulos(b.dataset.k);
  });
  mostrarTitulos(REF_TITULOS);

  let gHist = null;
  document.getElementById("tab-tit").addEventListener("click", async (ev) => {
    const tr = ev.target.closest("[data-id]"); if (!tr) return;
    const t = await dados(`dados/tesouro/${tr.dataset.id}.json`);
    const painel = document.getElementById("painel-titulo");
    painel.style.display = "block";
    document.getElementById("titulo-hist").textContent = `${t.tipo} ${dataBR(t.vencimento)} — taxa de compra e preço (PU)`;
    if (gHist) { gHist.dispose(); graficos.splice(graficos.indexOf(gHist), 1); }
    gHist = grafico(document.getElementById("gj-hist"), { xTempo: true, eixoEsq: "preco", eixoDir: "pctPronto", series: [
      { nome: "PU compra", valores: t.datas.map((d, i) => [d, t.pu_compra[i] || null]), tipo: "line", cor: COR.azul },
      { nome: "Taxa compra", valores: t.datas.map((d, i) => [d, t.taxa_compra[i] || null]), tipo: "line", eixo: "dir", cor: COR.ambar }] });
    painel.scrollIntoView({ behavior: "smooth", block: "center" });
  });
}

/* ============ Agenda ============ */
const CATEGORIAS_AGENDA = {
  copom: ["Copom", COR.ambar], inflacao: ["Inflação", COR.vermelho], atividade: ["Atividade", COR.azul],
  trabalho: ["Emprego", COR.verde], bc: ["Banco Central", COR.ciano],
};
const DIAS_SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

function linhaAgenda(e) {
  const [nome, cor] = CATEGORIAS_AGENDA[e.categoria] || CATEGORIAS_OFF[e.categoria] || [e.categoria, COR.cinza];
  const d = new Date(`${e.data}T12:00:00`);
  return `<tr><td>${dataBR(e.data)} <span class="sub">${DIAS_SEMANA[d.getDay()]}</span></td>
    <td style="text-align:left"><span style="color:${cor}">●</span> ${esc(nome)}</td>
    <td style="text-align:left;white-space:normal">${esc(e.evento)}${e.detalhe ? `<div class="sub" style="font-size:11px">${esc(e.detalhe)}</div>` : ""}</td>
    <td class="sub">${esc(e.fonte)}</td></tr>`;
}

function tabelaAgenda(agenda, dias, filtro = "todos") {
  if (!agenda || !agenda.eventos) return `<p class="sub">Agenda indisponível.</p>`;
  const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
  const limite = new Date(hoje); limite.setDate(limite.getDate() + dias);
  const lista = agenda.eventos.filter((e) => {
    const d = new Date(`${e.data}T12:00:00`);
    return d >= hoje && d <= limite && (filtro === "todos" || e.categoria === filtro);
  });
  if (!lista.length) return `<p class="sub">Nenhum evento no período.</p>`;
  return `<div class="rolagem rolagem-y"><table class="tabela"><tr><th>Data</th><th style="text-align:left">Tipo</th>
    <th style="text-align:left">Evento</th><th>Fonte</th></tr>${lista.map(linhaAgenda).join("")}</table></div>`;
}

const dataHoraBR = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)} ${iso.slice(11, 16)}` : "—");

function listaNoticias(itens, maximo = 300) {
  if (!itens.length) return `<p class="sub">Nenhuma manchete no período.</p>`;
  return `<div class="rolagem rolagem-y"><table class="tabela">
    ${itens.slice(0, maximo).map((n) => `<tr><td class="sub">${dataHoraBR(n.data)}</td>
      <td style="text-align:left;white-space:normal"><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.titulo)}</a>
        ${(n.empresas || []).map((id) => `<a class="etiqueta" href="#/on/empresa/${esc(id)}">${esc(id)}</a>`).join("")}</td>
      <td class="sub">${esc(n.fonte)}${n.tipo === "mercado" ? "" : ' <span class="etiqueta">oficial</span>'}</td></tr>`).join("")}</table></div>`;
}

// lado: "on" (Brasil), "off" (exterior) ou "cons" (os dois)
async function paginaNoticias(lado = "on") {
  const quer = (l) => lado === "cons" || lado === l;
  const [nOn, aOn, nOff, aOff] = await Promise.all([
    quer("on") ? dados("dados/noticias.json").catch(() => null) : null, quer("on") ? dados("dados/agenda.json").catch(() => null) : null,
    quer("off") ? dados("dados/noticias_offshore.json").catch(() => null) : null, quer("off") ? dados("dados/agenda_offshore.json").catch(() => null) : null,
  ]);
  const marcar = (n, origem) => ((n && n.itens) || []).map((i) => ({ ...i, origem, tipo: i.tipo || "oficial" }));
  const itens = [...marcar(nOn, "Brasil"), ...marcar(nOff, "Exterior")].sort((a, b) => b.data.localeCompare(a.data));
  const agenda = { eventos: [...((aOn && aOn.eventos) || []), ...((aOff && aOff.eventos) || [])].sort((a, b) => a.data.localeCompare(b.data)) };
  const categorias = { ...(quer("on") ? CATEGORIAS_AGENDA : {}), ...(quer("off") ? CATEGORIAS_OFF : {}) };
  const fontes = (tipo) => [...new Set(itens.filter((n) => n.tipo === tipo).map((n) => n.fonte))].sort();
  const filtros = [["todas", "Todas"], ...(lado === "cons" ? [["origem:Brasil", "Brasil"], ["origem:Exterior", "Exterior"]] : []),
    ["tipo:mercado", "Mercado"], ["tipo:oficial", "Oficiais"]];
  let filtro = "tipo:mercado", janela = 30, categoria = "todos", editoria = "todas";
  const EDITORIAS = [["todas", "Todas"], ["politica", "Política"], ["economia", "Economia e finanças"], ["empresas", "Empresas"]];
  const comEditoria = lado !== "off";
  const titulo = { on: "Notícias e agenda", off: "Offshore · Notícias e agenda", cons: "Consolidado · Notícias e agenda" }[lado];
  const jornais = { on: "Valor Econômico, Folha, Estadão, Brazil Journal e InfoMoney", off: "WSJ, Financial Times, CNBC, MarketWatch, The Guardian e BBC",
    cons: "jornais do Brasil e do exterior" }[lado];
  const oficiais = { on: "Banco Central, IBGE, CVM e Agência Brasil", off: "Federal Reserve e BCE", cons: "Banco Central, IBGE, CVM, Agência Brasil, Fed e BCE" }[lado];
  // Onshore: agenda em cima e notícias embaixo, cada uma na largura toda e mais alta; Offshore e Consolidado: lado a lado
  const painelNoticias = `
      <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Notícias</h2>
        ${comEditoria ? `<div class="seletor seletor-editoria" id="filtro-editoria">${EDITORIAS.map(([k, r]) => `<button data-k="${k}" class="${k === editoria ? "ativo" : ""}">${r}</button>`).join("")}</div>` : ""}</div>
        <div class="seletor" id="filtro-fonte" style="margin-bottom:8px">${filtros.map(([k, r]) => `<button data-k="${k}" class="${k === filtro ? "ativo" : ""}">${r}</button>`).join("")}
          ${[...fontes("mercado"), ...fontes("oficial")].map((f) => `<button data-k="fonte:${esc(f)}">${esc(f)}</button>`).join("")}</div>
        <div id="lista-noticias"></div>
        <div class="nota">Mercado: últimos 7 dias. Oficiais: últimas semanas. Sempre da mais recente para a mais antiga. O texto completo fica no site de cada
          fonte (alguns jornais exigem assinatura). Editoria: a seção do jornal de onde veio a manchete; manchete de economia que cita uma empresa
          da lista vai para Empresas. Etiquetas: empresas da lista citadas na manchete.</div></div>`;
  const painelAgenda = `
      <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Agenda</h2>
        <div class="seletor" id="janela-ag">${[[14, "2 sem."], [30, "1 mês"], [90, "3 meses"], [400, "Tudo"]].map(([d, r]) => `<button data-d="${d}" class="${d === janela ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
        <div class="seletor" id="filtro-ag" style="margin-bottom:8px">
          <button data-k="todos" class="ativo">Todos</button>
          ${Object.entries(categorias).map(([k, [n, c]]) => `<button data-k="${k}"><span style="color:${c}">●</span> ${n}</button>`).join("")}
        </div>
        <div id="tab-agenda"></div>
        <div class="nota">Datas oficiais${quer("on") ? " do Banco Central, IBGE e FGV" : ""}${lado === "cons" ? " e" : ""}${quer("off") ? " das páginas do Fed e do BCE" : ""}; podem mudar.</div></div>`;
  app.innerHTML = `
    <div class="cabecalho"><div><h1>${titulo}</h1><div class="sub">Notícias de mercado (${jornais}) e oficiais (${oficiais}) · só a manchete, com link para a fonte</div></div></div>
    ${lado === "on" ? abasNoticiasOn("", await eleicoesAtivas()) : ""}
    ${lado === "on" ? `<div class="grade grade-empilhada">${painelAgenda}${painelNoticias}</div>` : `<div class="grade grade-noticias">${painelNoticias}${painelAgenda}</div>`}`;
  const passa = (n) => {
    if (comEditoria && editoria !== "todas" && (n.categoria || "economia") !== editoria) return false;
    if (filtro === "todas") return true;
    const [campo, valor] = filtro.split(":");
    return n[campo] === valor;
  };
  const desenharNoticias = () => (document.getElementById("lista-noticias").innerHTML = listaNoticias(itens.filter(passa)));
  const desenharAgenda = () => (document.getElementById("tab-agenda").innerHTML = tabelaAgenda(agenda, janela, categoria));
  const seletor = (id, aoEscolher) => document.getElementById(id).addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    document.querySelectorAll(`#${id} button`).forEach((x) => x.classList.toggle("ativo", x === b));
    aoEscolher(b);
  });
  seletor("filtro-fonte", (b) => { filtro = b.dataset.k; desenharNoticias(); });
  if (comEditoria) seletor("filtro-editoria", (b) => { editoria = b.dataset.k; desenharNoticias(); });
  seletor("filtro-ag", (b) => { categoria = b.dataset.k; desenharAgenda(); });
  seletor("janela-ag", (b) => { janela = Number(b.dataset.d); desenharAgenda(); });
  desenharNoticias();
  desenharAgenda();
}

/* ============ Downloads ============ */
async function paginaDownloads() {
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Downloads</h1><div class="sub">Planilhas atualizadas todo dia, com o histórico completo</div></div></div>
    <div class="grade" style="margin-bottom:14px">
      <div class="painel"><h2>Macro</h2><p class="sub" style="line-height:1.6">Uma aba por grupo de gráficos: inflação (IPCA, IGP-M, INCC, médias de 3 meses anualizadas),
        núcleos do IPCA, PIB trimestral e anual, IBC-Br, Selic e juro real, CDI e câmbio diários e expectativas do Focus.</p>
        <a class="botao" href="downloads/macro.xlsx" download>Baixar macro.xlsx</a></div>
      <div class="painel"><h2>Juros</h2><p class="sub" style="line-height:1.6">Curva DI x Pré e DI x IPCA (B3) nas datas de comparação, curvas do Tesouro,
        títulos à venda e o histórico diário de taxa e preço de cada título do Tesouro Direto.</p>
        <a class="botao" href="downloads/juros.xlsx" download>Baixar juros.xlsx</a></div>
    </div>
    <div class="nota" style="margin-bottom:14px">Cada gráfico do site também tem o botão ⤓, que baixa a série daquele gráfico em CSV (abre direto no Excel).</div>
    <div class="cabecalho"><div><h2 style="margin:0">Empresas</h2><div class="sub">Excel padrão de cada empresa: Cadastro, Demonstrações, Indicadores (LTM) e Dividendos, com histórico completo desde 2011</div></div>
      <input class="filtro" id="filtro" placeholder="buscar por nome ou ticker"></div>
    <div class="painel"><div class="rolagem"><table class="tabela"><thead><tr><th>Papel</th><th>Empresa</th><th>Último período</th><th></th></tr></thead><tbody></tbody></table></div></div>`;
  const corpo = app.querySelector("tbody");
  const desenhar = (f = "") => {
    const q = f.trim().toUpperCase();
    corpo.innerHTML = INDICE.filter((e) => !q || e.nome.toUpperCase().includes(q) || e.tickers.some((t) => t.includes(q)))
      .map((e) => `<tr><td>${esc(e.tickers.join(" / "))}</td><td>${esc(e.nome)}</td><td>${dataBR(e.ultimo_periodo)}</td>
        <td><a class="botao" href="downloads/${encodeURIComponent(e.id)}.xlsx" download>Baixar Excel</a></td></tr>`).join("");
  };
  desenhar();
  document.getElementById("filtro").addEventListener("input", (ev) => desenhar(ev.target.value));
}

/* ============ Offshore ============ */
const PLANO_OFFSHORE = {
  empresas: ["Empresas", "Empresas estrangeiras para comparação setorial.", [
    ["Comparáveis estrangeiras", "Receita, margens, endividamento e retorno de empresas listadas nos EUA.", "SEC EDGAR (balanços XBRL, API oficial)"]]],
  china: ["China", "", [["China", "PIB, inflação e produção industrial.", "DBnomics (dados do NBS)"]]],
  global: ["Global", "", [["Global", "PIB e projeções por país.", "FMI (World Economic Outlook), Banco Mundial, OCDE"]]],
  mercados: ["Mercados", "", [["Mercados", "Índices de ações (S&P 500, Nasdaq, Stoxx), petróleo, minério, ouro e dólar global.",
    "FRED e EIA (precisam de chave gratuita), Banco Mundial (Pink Sheet, mensal)"]]],
};
const CATEGORIAS_OFF = { fed: ["Fed", COR.verde], bce: ["BCE", COR.roxo] };
const SUBS_MACRO_OFF = [["eua", "Estados Unidos"], ["euro", "Zona do Euro"], ["china", "China"], ["global", "Global"], ["mercados", "Mercados"]];

function emConstrucao(itens) {
  return `<div class="aviso">Em construção: a estrutura está pronta e os dados entram nas próximas etapas.</div>
    <div class="grade">${itens.map(([nome, conteudo, fonte]) => `<div class="painel em-construcao"><h2>${nome}</h2>
      <p style="margin:0 0 8px;line-height:1.6">${conteudo}</p><div class="nota">Fonte prevista: ${fonte}</div></div>`).join("")}</div>`;
}

const Pares = (s) => (s ? s.datas.map((d, i) => [d, s.valores[i]]) : []);
const curvaPts = (c) => (c ? c.pontos.map((p) => [p.anos, p.taxa]) : []);
// Taxa básica guardada só nas mudanças: repete o valor mês a mês até hoje, para a linha não sumir
// quando a última mudança fica antes da janela do gráfico
const ateHoje = (s) => {
  const p = Pares(s);
  if (!p.length) return p;
  const saida = [], fim = new Date().toISOString().slice(0, 10), d = new Date(`${p[0][0].slice(0, 7)}-01T12:00:00`);
  let i = 0, atual = p[0][1];
  for (let iso = p[0][0]; iso <= fim; d.setMonth(d.getMonth() + 1), iso = d.toISOString().slice(0, 10)) {
    while (i < p.length && p[i][0] <= iso) { saida.push(p[i]); atual = p[i][1]; i++; }
    if (saida.length && saida[saida.length - 1][0] < iso) saida.push([iso, atual]);
  }
  while (i < p.length) { saida.push(p[i]); atual = p[i][1]; i++; }
  saida.push([fim, atual]);
  return saida;
};
const desde = (anos) => { const d = new Date(); d.setFullYear(d.getFullYear() - anos); return d.toISOString().slice(0, 10); };

function painelG(id, titulo, info, extra = "", classe = "") {
  return `<div class="painel ${classe}" data-info="${info}"><h2>${titulo}</h2><div class="grafico${classe.includes("largo") ? " alto" : ""}" id="${id}"></div>${extra}</div>`;
}

function curvasPorData(curvas) {
  return Object.keys(curvas || {}).map((r, i) => ({ nome: `${r} (${dataBR(curvas[r].data)})`, valores: curvaPts(curvas[r]), tipo: "line",
    cor: PALETA_DATAS[i % PALETA_DATAS.length], tracejado: i > 0 }));
}

async function paginaOffshore(secao, parametro) {
  const off = await dados("dados/offshore.json").catch(() => null);
  if (secao === "empresas") {
    const [t, sub, itens] = PLANO_OFFSHORE.empresas;
    app.innerHTML = `<div class="cabecalho"><div><h1>Offshore · ${t}</h1><div class="sub">${sub}</div></div></div>${emConstrucao(itens)}`;
    return;
  }
  if (!off) { app.innerHTML = `<p class="erro">Dados do exterior indisponíveis.</p>`; return; }
  const cab = (titulo, sub, extra = "") => `<div class="cabecalho"><div><h1>${titulo}</h1><div class="sub">${sub} · atualizado em ${dataHoraBR(off.gerado_em)}</div></div>${extra}</div>`;
  const T = off.treasuries || {}, F = off.fed || {}, B = off.bls || {}, E = off.bce || {}, Z = off.eurostat || {};
  const u = (s) => ultimo(s);
  const mes = (s) => (u(s).data ? `${MESES[Number(u(s).data.slice(5, 7)) - 1]}/${u(s).data.slice(2, 4)}` : "");
  const ust10 = T.historico ? u(T.historico["10 anos"]) : {};

  if (secao === "macro") {
    const sub = SUBS_MACRO_OFF.some(([k]) => k === parametro) ? parametro : "eua";
    const abas = `<div class="abas">${SUBS_MACRO_OFF.map(([k, n]) => `<a href="#/off/macro/${k}" class="${k === sub ? "ativo" : ""}">${n}</a>`).join("")}</div>`;
    if (PLANO_OFFSHORE[sub]) { app.innerHTML = `${cab("Offshore · Macro", "Atividade, inflação e emprego no exterior")}${abas}${emConstrucao(PLANO_OFFSHORE[sub][2])}`; return; }
    if (sub === "eua") {
      app.innerHTML = `${cab("Offshore · Macro", "Estados Unidos: BLS (API oficial)")}${abas}
        <div class="grade-cartoes">
          ${cartao("CPI 12 meses", pctPronto(u(B.cpi_12m).valor), mes(B.cpi_12m))}${cartao("Núcleo do CPI 12m", pctPronto(u(B.cpi_nucleo_12m).valor), mes(B.cpi_nucleo_12m))}
          ${cartao("CPI no mês (dessaz.)", pctPronto(u(B.cpi_mensal).valor), mes(B.cpi_mensal))}${cartao("Desemprego", pctPronto(u(B.desemprego).valor, 1), mes(B.desemprego))}
          ${cartao("Payroll (vagas no mês)", u(B.payroll_var).valor != null ? `${num(u(B.payroll_var).valor, 0)} mil` : "—", mes(B.payroll_var))}</div>
        <div class="grade">${painelG("go-cpi", "Inflação ao consumidor (CPI)", "cpi_eua")}${painelG("go-cpin", "CPI — núcleo (sem alimentos e energia)", "cpi_eua")}
          ${painelG("go-trab", "Mercado de trabalho: payroll e desemprego", "emprego_eua")}</div>`;
      grafico(document.getElementById("go-cpi"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", eixoDir: "pctPronto", series: [
        { nome: "Mensal (dessaz.)", valores: Pares(B.cpi_mensal), cor: COR.azul }, { nome: "12 meses", valores: Pares(B.cpi_12m), tipo: "line", eixo: "dir", cor: COR.vermelho },
        { nome: "Núcleo 12 meses", valores: Pares(B.cpi_nucleo_12m), tipo: "line", eixo: "dir", cor: COR.ambar, tracejado: true }] });
      grafico(document.getElementById("go-cpin"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", eixoDir: "pctPronto", series: [
        { nome: "Núcleo mensal (dessaz.)", valores: Pares(B.cpi_nucleo_mensal), cor: COR.azul }, { nome: "Núcleo 12 meses", valores: Pares(B.cpi_nucleo_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] });
      grafico(document.getElementById("go-trab"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "numero", eixoDir: "pctPronto", series: [
        { nome: "Payroll (mil vagas no mês)", valores: Pares(B.payroll_var), cor: COR.verde }, { nome: "Desemprego", valores: Pares(B.desemprego), tipo: "line", eixo: "dir", cor: COR.vermelho }] });
      return;
    }
    app.innerHTML = `${cab("Offshore · Macro", "Zona do Euro: Eurostat (API oficial)")}${abas}
      <div class="grade-cartoes">
        ${cartao("HICP 12 meses", pctPronto(u(Z.hicp_12m).valor, 1), mes(Z.hicp_12m))}${cartao("Núcleo 12m", pctPronto(u(Z.hicp_nucleo_12m).valor, 1), "sem energia, alimentos, álcool e fumo")}
        ${cartao("Serviços 12m", pctPronto(u(Z.hicp_servicos_12m).valor, 1), mes(Z.hicp_servicos_12m))}${cartao("Desemprego", pctPronto(u(Z.desemprego).valor, 1), mes(Z.desemprego))}
        ${cartao("PIB tri/tri", pctPronto(u(Z.pib_tri).valor, 1), u(Z.pib_tri).data ? `${Math.ceil(Number(u(Z.pib_tri).data.slice(5, 7)) / 3)}º tri/${u(Z.pib_tri).data.slice(0, 4)}` : "")}</div>
      <div class="grade">${painelG("go-hicp", "Inflação (HICP) — 12 meses", "hicp")}${painelG("go-des", "Desemprego", "desemprego_euro")}${painelG("go-pib", "PIB", "pib_euro")}</div>`;
    grafico(document.getElementById("go-hicp"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", series: [
      { nome: "Cheio", valores: Pares(Z.hicp_12m), tipo: "line", cor: COR.vermelho }, { nome: "Núcleo", valores: Pares(Z.hicp_nucleo_12m), tipo: "line", cor: COR.ambar },
      { nome: "Serviços", valores: Pares(Z.hicp_servicos_12m), tipo: "line", cor: COR.ciano, tracejado: true }] });
    grafico(document.getElementById("go-des"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", series: [
      { nome: "Desemprego (dessaz.)", valores: Pares(Z.desemprego), tipo: "line", cor: COR.vermelho }] });
    grafico(document.getElementById("go-pib"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", eixoDir: "pctPronto", series: [
      { nome: "Tri/tri (dessaz.)", valores: Pares(Z.pib_tri), cor: COR.azul }, { nome: "Contra o mesmo tri do ano anterior", valores: Pares(Z.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] });
    return;
  }

  if (secao === "juros") {
    app.innerHTML = `${cab("Offshore · Juros", "Tesouro dos EUA, Fed de Nova York e BCE (fontes oficiais) · taxas em % a.a.",
      `<a class="botao" href="downloads/offshore.xlsx" download>Baixar planilha Offshore</a>`)}
      <div class="grade">
        ${painelG("gq-ust", "Treasuries — curva nominal", "ust_curva")}${painelG("gq-tips", "Treasuries — curva real (TIPS)", "ust_real")}
        ${painelG("gq-hist", "Treasuries de 2, 10 e 30 anos", "ust_hist")}${painelG("gq-incl", "Inclinação da curva: 10 anos − 2 anos", "ust_hist")}
        ${painelG("gq-fed", "Fed Funds: meta, taxa efetiva e SOFR", "fed_funds")}${painelG("gq-bce", "BCE: taxa de depósito e €STR", "bce_juros")}
        ${painelG("gq-eur", "Zona do Euro — curva de juros (títulos AAA)", "curva_euro")}${painelG("gq-eur10", "Juro de 10 anos: Treasury x Zona do Euro AAA", "curva_euro")}
      </div>`;
    grafico(document.getElementById("gq-ust"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: curvasPorData(T.nominal) });
    grafico(document.getElementById("gq-tips"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: curvasPorData(T.real) });
    const H = T.historico || {};
    grafico(document.getElementById("gq-hist"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", series: [
      { nome: "2 anos", valores: Pares(H["2 anos"]), tipo: "line", cor: COR.ciano }, { nome: "10 anos", valores: Pares(H["10 anos"]), tipo: "line", cor: COR.ambar },
      { nome: "30 anos", valores: Pares(H["30 anos"]), tipo: "line", cor: COR.roxo }, { nome: "10 anos real (TIPS)", valores: Pares(H["10 anos real (TIPS)"]), tipo: "line", cor: COR.verde, tracejado: true }] });
    grafico(document.getElementById("gq-incl"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", series: [
      { nome: "10a − 2a (pontos percentuais)", valores: Pares(H["inclinação 10a − 2a"]), tipo: "line", cor: COR.ambar }] });
    grafico(document.getElementById("gq-fed"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", degrau: true, series: [
      { nome: "Meta — limite superior", valores: ateHoje(F.meta_max), tipo: "line", cor: COR.ambar }, { nome: "Meta — limite inferior", valores: ateHoje(F.meta_min), tipo: "line", cor: COR.ambar, tracejado: true },
      { nome: "Efetiva (EFFR)", valores: Pares(F.effr), tipo: "line", cor: COR.ciano }, { nome: "SOFR", valores: Pares(F.sofr), tipo: "line", cor: COR.roxo }] });
    grafico(document.getElementById("gq-bce"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", degrau: true, series: [
      { nome: "Taxa de depósito", valores: ateHoje(E.deposito), tipo: "line", cor: COR.ambar }, { nome: "€STR", valores: Pares(E.estr), tipo: "line", cor: COR.ciano }] });
    grafico(document.getElementById("gq-eur"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: curvasPorData(E.curva) });
    grafico(document.getElementById("gq-eur10"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", series: [
      { nome: "Treasury 10 anos", valores: Pares(H["10 anos"]), tipo: "line", cor: COR.ambar }, { nome: "Zona do Euro AAA 10 anos", valores: Pares(E.aaa_10a), tipo: "line", cor: COR.roxo }] });
    return;
  }

  if (secao === "downloads") {
    app.innerHTML = `${cab("Offshore · Downloads", "Planilha com as séries do exterior, atualizada todo dia")}
      <div class="grade"><div class="painel"><h2>Offshore</h2><p class="sub" style="line-height:1.6">Treasuries (curvas nas datas de comparação e histórico de 2, 10 e 30 anos),
        Fed Funds, SOFR, BCE (depósito, €STR e curva AAA), inflação e emprego dos EUA (BLS) e inflação, desemprego e PIB da Zona do Euro (Eurostat).</p>
        <a class="botao" href="downloads/offshore.xlsx" download>Baixar offshore.xlsx</a></div></div>
      <div class="nota secao">Cada gráfico do site também tem o botão ⤓ para baixar a série daquele gráfico em CSV.</div>`;
    return;
  }

  // Início do Offshore
  const [agenda, noticias] = await Promise.all([dados("dados/agenda_offshore.json").catch(() => null), dados("dados/noticias_offshore.json").catch(() => null)]);
  const mMin = u(F.meta_min), mMax = u(F.meta_max);
  const mercadoOff = ((noticias && noticias.itens) || []).filter((n) => n.tipo === "mercado");
  app.innerHTML = `${cab("Offshore · painel", "Agenda, indicadores e notícias dos EUA e da Zona do Euro")}
    <div class="painel secao-topo"><h2>Próximas decisões de juros</h2>${tabelaAgenda(agenda, 120)}<div class="nota"><a href="#/off/noticias">Ver agenda e notícias</a></div></div>
    <div class="grade-cartoes">
      ${cartao("Fed Funds (meta)", mMin.valor != null ? `${num(mMin.valor, 2)}–${num(mMax.valor, 2)}%` : "—", `efetiva ${pctPronto(u(F.effr).valor)}`)}
      ${cartao("Treasury 10 anos", pctPronto(ust10.valor), dataBR(ust10.data))}
      ${cartao("CPI EUA 12m", pctPronto(u(B.cpi_12m).valor, 1), `núcleo ${pctPronto(u(B.cpi_nucleo_12m).valor, 1)} · ${mes(B.cpi_12m)}`)}
      ${cartao("Desemprego EUA", pctPronto(u(B.desemprego).valor, 1), mes(B.desemprego))}
      ${cartao("BCE (depósito)", pctPronto(u(E.deposito).valor), `€STR ${pctPronto(u(E.estr).valor)}`)}
      ${cartao("HICP 12m", pctPronto(u(Z.hicp_12m).valor, 1), `núcleo ${pctPronto(u(Z.hicp_nucleo_12m).valor, 1)} · ${mes(Z.hicp_12m)}`)}
    </div>
    <div class="grade">
      ${painelG("gi-ust", "Curva de Treasuries — hoje vs. 1 ano", "ust_curva")}
      ${painelG("gi-juros", "Juros básicos: Fed Funds x BCE (depósito)", "fed_funds")}
    </div>
    <div class="painel secao"><h2>Notícias de mercado</h2>${listaNoticias(mercadoOff, 40)}
      <div class="nota">Manchetes de WSJ, Financial Times, CNBC, MarketWatch, The Guardian e BBC, com link para o jornal. <a href="#/off/noticias">Ver todas</a></div></div>
    ${off.falhas && off.falhas.length ? `<div class="nota secao">Fontes com falha na última atualização (mostrando a versão anterior): ${esc(off.falhas.join("; "))}</div>` : ""}`;
  const N = T.nominal || {};
  grafico(document.getElementById("gi-ust"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: curvasPorData(
    Object.fromEntries(["hoje", "1 ano"].filter((k) => N[k]).map((k) => [k, N[k]]))) });
  grafico(document.getElementById("gi-juros"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", degrau: true, series: [
    { nome: "Fed Funds (limite superior)", valores: ateHoje(F.meta_max), tipo: "line", cor: COR.verde }, { nome: "BCE (depósito)", valores: ateHoje(E.deposito), tipo: "line", cor: COR.roxo }] });
}

/* ============ Consolidado: Brasil, EUA e Zona do Euro nos mesmos gráficos ============ */
const PAISES = { br: ["Brasil", COR.verde], eua: ["EUA", COR.azul], euro: ["Zona do Euro", COR.roxo] };

// valor de uma série "em degraus" (taxa básica) vigente em cada data
function vigente(serie, datas) {
  const pares = Pares(serie);
  let k = 0, atual = null;
  return datas.map((d) => { while (k < pares.length && pares[k][0] <= d) atual = pares[k++][1]; return atual; });
}

// juro real ex-post mensal: (1 + taxa básica vigente no mês) ÷ (1 + inflação 12 meses) − 1
function juroReal(taxa, inflacao12m) {
  const fimDoMes = inflacao12m.datas.map((d) => { const x = new Date(`${d}T12:00:00`); x.setMonth(x.getMonth() + 1, 0); return x.toISOString().slice(0, 10); });
  const t = vigente(taxa, fimDoMes);
  return inflacao12m.datas.map((d, i) => [d, t[i] == null ? null : ((1 + t[i] / 100) / (1 + inflacao12m.valores[i] / 100) - 1) * 100]).filter((p) => p[1] != null);
}

async function paginaConsolidado(secao) {
  const [macro, off] = await Promise.all([dados("dados/macro.json"), dados("dados/offshore.json").catch(() => null)]);
  const S = macro.series, T = (off && off.treasuries) || {}, F = (off && off.fed) || {}, B = (off && off.bls) || {}, E = (off && off.bce) || {}, Z = (off && off.eurostat) || {};
  const u = (s) => ultimo(s);
  const mes = (s) => (u(s).data ? `${MESES[Number(u(s).data.slice(5, 7)) - 1]}/${u(s).data.slice(2, 4)}` : "");
  const titulos = { "": "Juros", inflacao: "Inflação", atividade: "Atividade e emprego" };
  const cab = `<div class="cabecalho"><div><h1>Consolidado · ${titulos[secao] || "Juros"}</h1>
    <div class="sub">Brasil, Estados Unidos e Zona do Euro nos mesmos gráficos · mesmas fontes oficiais das seções Onshore e Offshore
      <span style="color:${PAISES.br[1]}">●</span> Brasil <span style="color:${PAISES.eua[1]}">●</span> EUA <span style="color:${PAISES.euro[1]}">●</span> Zona do Euro</div></div></div>`;
  const linha = (pais, nome, valores, extra = {}) => ({ nome, valores, tipo: "line", cor: PAISES[pais][1], ...extra });
  const tempo = (anos = 10) => ({ xTempo: true, inicioTempo: desde(anos), deslizante: true, eixoEsq: "pctPronto" });

  if (secao === "inflacao") {
    app.innerHTML = `${cab}
      <div class="grade-cartoes">
        ${cartao("IPCA 12m", pctPronto(u(S.ipca_12m).valor, 1), `meta 3% · ${mes(S.ipca_12m)}`)}
        ${cartao("CPI EUA 12m", pctPronto(u(B.cpi_12m).valor, 1), `objetivo do Fed 2% (PCE) · ${mes(B.cpi_12m)}`)}
        ${cartao("HICP 12m", pctPronto(u(Z.hicp_12m).valor, 1), `meta do BCE 2% · ${mes(Z.hicp_12m)}`)}
        ${cartao("Núcleos Brasil 12m", pctPronto(u(S.nucleos_media_12m).valor, 1), "média dos 5 núcleos")}
        ${cartao("Núcleo CPI 12m", pctPronto(u(B.cpi_nucleo_12m).valor, 1), "sem alimentos e energia")}
        ${cartao("Núcleo HICP 12m", pctPronto(u(Z.hicp_nucleo_12m).valor, 1), "sem energia, alimentos, álcool e fumo")}
      </div>
      <div class="grade">
        ${painelG("gc-inf", "Inflação em 12 meses: IPCA, CPI e HICP", "inflacao_mundo")}
        ${painelG("gc-nuc", "Núcleos em 12 meses", "inflacao_mundo")}
        ${painelG("gc-inf-meta", "Distância da meta (inflação 12m − meta)", "inflacao_mundo")}
      </div>`;
    grafico(document.getElementById("gc-inf"), { ...tempo(), series: [
      linha("br", "IPCA (Brasil)", Pares(S.ipca_12m)), linha("eua", "CPI (EUA)", Pares(B.cpi_12m)), linha("euro", "HICP (Zona do Euro)", Pares(Z.hicp_12m))] });
    grafico(document.getElementById("gc-nuc"), { ...tempo(), series: [
      linha("br", "Média dos núcleos do IPCA", Pares(S.nucleos_media_12m)), linha("eua", "Núcleo do CPI", Pares(B.cpi_nucleo_12m)),
      linha("euro", "Núcleo do HICP", Pares(Z.hicp_nucleo_12m))] });
    const menos = (s, meta) => Pares(s).map(([d, v]) => [d, v - meta]);
    grafico(document.getElementById("gc-inf-meta"), { ...tempo(), series: [
      linha("br", "IPCA − 3%", menos(S.ipca_12m, 3)), linha("eua", "CPI − 2%", menos(B.cpi_12m, 2)), linha("euro", "HICP − 2%", menos(Z.hicp_12m, 2))] });
    return;
  }

  if (secao === "atividade") {
    app.innerHTML = `${cab}
      <div class="grade-cartoes">
        ${cartao("PIB Brasil 4 tri", pctPronto(u(S.pib_12m).valor, 1), "acumulado em 4 trimestres")}
        ${cartao("PIB Zona do Euro", pctPronto(u(Z.pib_12m).valor, 1), "contra o mesmo tri do ano anterior")}
        ${cartao("Desemprego EUA", pctPronto(u(B.desemprego).valor, 1), mes(B.desemprego))}
        ${cartao("Desemprego Zona do Euro", pctPronto(u(Z.desemprego).valor, 1), mes(Z.desemprego))}
      </div>
      <div class="grade">
        ${painelG("gc-pib", "PIB: crescimento contra um ano antes", "pib_mundo")}
        ${painelG("gc-des", "Desemprego", "desemprego_mundo")}
      </div>
      <div class="nota secao">Em seguida: PIB dos EUA (precisa da chave gratuita do FRED) e desemprego do Brasil (PNAD Contínua, IBGE).</div>`;
    grafico(document.getElementById("gc-pib"), { ...tempo(), series: [
      linha("br", "Brasil (4 trimestres)", Pares(S.pib_12m)), linha("euro", "Zona do Euro (ano contra ano)", Pares(Z.pib_12m))] });
    grafico(document.getElementById("gc-des"), { ...tempo(), series: [
      linha("eua", "EUA", Pares(B.desemprego)), linha("euro", "Zona do Euro", Pares(Z.desemprego))] });
    return;
  }

  // Juros
  const fed = u(F.meta_max), bce = u(E.deposito);
  app.innerHTML = `${cab}
    <div class="grade-cartoes">
      ${cartao("Selic meta", pctPronto(u(S.selic_meta).valor), dataBR(u(S.selic_meta).data))}
      ${cartao("Fed Funds (teto)", pctPronto(fed.valor), `banda ${pctPronto(u(F.meta_min).valor)}–${pctPronto(fed.valor)}`)}
      ${cartao("BCE (depósito)", pctPronto(bce.valor), "")}
      ${cartao("Juro real Brasil", pctPronto(u(S.juro_real).valor, 1), "Selic ÷ IPCA 12m")}
      ${cartao("Treasury 10 anos", pctPronto(u(T.historico && T.historico["10 anos"]).valor), dataBR(u(T.historico && T.historico["10 anos"]).data))}
      ${cartao("Euro AAA 10 anos", pctPronto(u(E.aaa_10a).valor), dataBR(u(E.aaa_10a).data))}
    </div>
    <div class="grade">
      ${painelG("gc-basicos", "Juros básicos: Selic, Fed Funds e BCE", "juros_mundo")}
      ${painelG("gc-real", "Juro real ex-post: taxa básica ÷ inflação 12 meses", "juro_real_mundo")}
      ${painelG("gc-inf-j", "Inflação em 12 meses: IPCA, CPI e HICP", "inflacao_mundo", "", "largo")}
    </div>`;
  grafico(document.getElementById("gc-basicos"), { ...tempo(), degrau: true, series: [
    linha("br", "Selic meta", ateHoje(S.selic_meta)), linha("eua", "Fed Funds (teto da banda)", ateHoje(F.meta_max)), linha("euro", "BCE (depósito)", ateHoje(E.deposito))] });
  grafico(document.getElementById("gc-real"), { ...tempo(), series: [
    linha("br", "Brasil", Pares(S.juro_real)), linha("eua", "EUA (Fed Funds ÷ CPI)", B.cpi_12m ? juroReal(F.meta_max, B.cpi_12m) : []),
    linha("euro", "Zona do Euro (depósito ÷ HICP)", Z.hicp_12m ? juroReal(E.deposito, Z.hicp_12m) : [])] });
  // Inflação dos três logo abaixo dos juros, na última linha inteira
  grafico(document.getElementById("gc-inf-j"), { ...tempo(), series: [
    linha("br", "IPCA (Brasil)", Pares(S.ipca_12m)), linha("eua", "CPI (EUA)", Pares(B.cpi_12m)), linha("euro", "HICP (Zona do Euro)", Pares(Z.hicp_12m))] });
}

/* ============ Eleições 2026 (Onshore · Notícias e agenda) ============ */
// A aba só existe em ano eleitoral (o pipeline marca "ativo" pelo calendário do TSE); depois das eleições some sozinha
let ELEICOES_ATIVAS = null;
async function eleicoesAtivas() {
  if (ELEICOES_ATIVAS === null) ELEICOES_ATIVAS = await dados("dados/eleicoes.json").then((e) => (e.ativo ? e : false)).catch(() => false);
  return ELEICOES_ATIVAS;
}
const abasNoticiasOn = (ativa, el) => (el ? `<div class="abas">${[["", "Notícias e agenda"], ["eleicoes", `Eleições ${el.ano}`]]
  .map(([k, n]) => `<a href="#/on/noticias${k ? `/${k}` : ""}" class="${k === ativa ? "ativo" : ""}">${n}</a>`).join("")}</div>` : "");

async function paginaEleicoes() {
  const el = await eleicoesAtivas();
  if (!el) { location.replace("#/on/noticias"); return; }
  const [t1, t2] = el.turnos;
  if (!t1.candidatos.length) {  // ano eleitoral, antes da votação: só as datas
    app.innerHTML = `<div class="cabecalho"><div><h1>Eleições ${el.ano} · Presidente</h1></div></div>${abasNoticiasOn("eleicoes", el)}
      <div class="painel" data-info="eleicoes"><h2>Aguardando a votação</h2><p>1º turno em <b>${dataBR(t1.data)}</b>${t2 ? ` · 2º turno (se houver) em <b>${dataBR(t2.data)}</b>` : ""}.
        Os resultados oficiais do TSE aparecem aqui assim que a apuração começar.</p><div class="nota">Fonte: TSE — Divulgação de Resultados.</div></div>`;
    return;
  }
  const t2apurado = Boolean(t2 && t2.apurado_pct > 0 && t2.candidatos.length);
  const atual = t2apurado ? t2 : t1;
  const cores = [COR.azul, COR.vermelho, COR.verde, COR.roxo, COR.ciano, COR.ambar, COR.cinza];
  const corDe = {};
  t1.candidatos.forEach((c, i) => (corDe[c.nome] = cores[i] || COR.cinza));
  const tabela = (t) => `<table class="tabela"><tr><th>Candidato</th><th style="text-align:left">Partido / coligação</th><th>Votos</th><th>% válidos</th><th>Situação</th></tr>
    ${t.candidatos.map((c) => `<tr><td><span style="color:${corDe[c.nome] || COR.cinza}">●</span> ${esc(c.nome)} <span class="sub">${esc(c.numero)}</span></td>
      <td style="text-align:left;white-space:normal">${esc(c.partido)}${c.coligacao ? ` <span class="sub">· ${esc(c.coligacao)}</span>` : ""}</td>
      <td>${c.votos.toLocaleString("pt-BR")}</td><td><b>${num(c.pct, 2)}%</b></td><td class="sub">${esc(c.situacao)}</td></tr>`).join("")}</table>`;
  const ufs = Object.entries(atual.por_uf || {});
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Eleições ${el.ano} · Presidente</h1><div class="sub">Resultado oficial do TSE · 1º turno em ${dataBR(t1.data)}${t2 ? ` · 2º turno em ${dataBR(t2.data)}` : ""}
      · atualizado pelo TSE em ${esc(atual.atualizado_tse || "—")} · esta aba fica até ${dataBR(el.ate)}</div></div></div>
    ${abasNoticiasOn("eleicoes", el)}
    <div class="grade-cartoes">
      ${cartao(t2apurado ? "2º turno apurado" : "1º turno apurado", `${num(atual.apurado_pct, 2)}%`, `${atual.turno}º turno · ${dataBR(atual.data)}`)}
      ${cartao("Comparecimento", `${num(atual.comparecimento_pct, 2)}%`, `${atual.eleitores.toLocaleString("pt-BR")} eleitores`)}
      ${cartao("Abstenção", `${num(atual.abstencao_pct, 2)}%`, "")}
      ${cartao("Brancos / nulos", `${num(atual.brancos_pct, 2)}% / ${num(atual.nulos_pct, 2)}%`, "do total de votos")}
      ${t2 && !t2apurado ? cartao("2º turno", dataBR(t2.data), t2.candidatos.map((c) => c.nome).join(" x ")) : ""}
    </div>
    <div class="grade">
      ${t2apurado ? `<div class="painel" data-info="eleicoes"><h2>2º turno — votos válidos</h2><div class="grafico" id="ge-t2"></div></div>` : ""}
      <div class="painel" data-info="eleicoes"><h2>1º turno — votos válidos</h2><div class="grafico" id="ge-t1"></div></div>
      <div class="painel" data-info="eleicoes"><h2>${t2apurado ? "2º turno" : "1º turno"} — candidatos</h2><div class="rolagem">${tabela(atual)}</div></div>
      ${t2apurado ? `<div class="painel" data-info="eleicoes"><h2>1º turno — candidatos</h2><div class="rolagem">${tabela(t1)}</div></div>` : ""}
      <div class="painel largo" data-info="eleicoes"><h2>Resultado por estado — ${atual.turno}º turno</h2><div class="rolagem"><table class="tabela">
        <tr><th>UF</th><th style="text-align:left">Mais votado</th><th>%</th><th style="text-align:left">Segundo</th><th>%</th><th>Diferença</th></tr>
        ${ufs.map(([uf, [a, b]]) => `<tr><td>${uf}</td><td style="text-align:left"><span style="color:${corDe[a.nome] || COR.cinza}">●</span> ${esc(a.nome)}</td><td>${num(a.pct, 2)}%</td>
          <td style="text-align:left" class="sub">${b ? esc(b.nome) : "—"}</td><td class="sub">${b ? `${num(b.pct, 2)}%` : "—"}</td><td>${b ? `${num(a.pct - b.pct, 2)} p.p.` : "—"}</td></tr>`).join("")}
      </table></div></div>
    </div>
    <div class="nota secao">Fonte: TSE — Divulgação de Resultados (arquivos públicos de resultados.tse.jus.br). Percentuais sobre os votos válidos
      (sem brancos e nulos). No dia do 2º turno a atualização diária traz o resultado na manhã seguinte.</div>`;
  const barras = (id, t) => grafico(document.getElementById(id), { rotulos: t.candidatos.map((c) => c.nome), eixoEsq: "pctPronto", janela: 20,
    series: [{ nome: "% dos votos válidos", valores: t.candidatos.map((c) => c.pct), cor: COR.ambar }] });
  barras("ge-t1", t1);
  if (t2apurado) barras("ge-t2", t2);
}

/* ============ Calendário de resultados (Empresas · Informações) ============ */
function tabelaCalendario(cal, maximo = 400) {
  if (!cal || !cal.empresas) return `<p class="sub">Calendário indisponível.</p>`;
  const tri = (iso) => { const m = Number(iso.slice(5, 7)); return `${Math.ceil(m / 3)}º tri/${iso.slice(2, 4)}`; };
  return `<div class="rolagem rolagem-y"><table class="tabela"><tr><th>Data</th><th>Empresa</th><th>Período</th><th>Doc.</th>
    <th>Ano anterior</th><th>Prazo legal</th></tr>
    ${cal.empresas.slice(0, maximo).map((l) => `<tr class="clicavel" onclick="location.hash='#/on/empresa/${esc(l.id)}'">
      <td>${l.atrasado ? `<span class="neg">atrasado</span>` : l.data_estimada ? `${dataBR(l.data_estimada)} <span class="sub">est.</span>` : `<span class="sub">até ${dataBR(l.prazo_legal)}</span>`}</td>
      <td>${esc(l.id)} <span class="sub">${esc(l.nome.slice(0, 26))}</span></td><td>${tri(l.proximo_periodo)}</td><td class="sub">${l.documento}</td>
      <td class="sub">${l.base_ano_anterior ? dataBR(l.base_ano_anterior) : "—"}</td><td class="sub">${dataBR(l.prazo_legal)}</td></tr>`).join("")}</table></div>`;
}

/* ============ Instituições financeiras (IF.data do Banco Central) ============ */
const SEGMENTOS = {
  S1: "S1 — porte igual ou maior que 10% do PIB ou atuação internacional relevante",
  S2: "S2 — porte entre 1% e 10% do PIB", S3: "S3 — porte entre 0,1% e 1% do PIB", S4: "S4 — porte menor que 0,1% do PIB",
  S5: "S5 — perfil de risco simplificado", "": "Sem segmento prudencial informado",
};
const TIPOS_IF = { bancos: ["B1", "B2", "B4"], cooperativas: ["B3S", "B3C"], nao_bancarias: ["N1", "N2"], pagamento: ["N4"] };
const TIPO_CURTO = { B1: "Banco comercial/múltiplo", B2: "Banco múltiplo/investimento", B4: "Banco de desenvolvimento",
  N1: "Não bancária de crédito", N2: "Mercado de capitais", N4: "Instituição de pagamento", B3S: "Cooperativa de crédito", B3C: "Central de cooperativas" };
const triIF = (iso) => `${Math.ceil(Number(iso.slice(5, 7)) / 3)}T${iso.slice(2, 4)}`;

async function abaFinanceiras(cab, abas) {
  const b = await dados("dados/bancos.json").catch(() => null);
  if (!b) { app.innerHTML = `${cab}${abas}<p class="erro">Dados do IF.data indisponíveis.</p>`; return; }
  let tipo = "bancos", busca = "";
  app.innerHTML = `${cab}${abas}
    <div class="cabecalho"><div class="sub">${b.instituicoes.length} instituições do IF.data · data-base ${dataBR(b.data_base)} · por segmento prudencial (S1 a S5)
      e, dentro de cada um, do maior para o menor ativo · clique para abrir</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <div class="seletor" id="tipo-if">${[["bancos", "Bancos"], ["cooperativas", "Cooperativas"], ["nao_bancarias", "Não bancárias"], ["pagamento", "Pagamento"], ["todas", "Todas"]]
          .map(([k, r]) => `<button data-k="${k}" class="${k === tipo ? "ativo" : ""}">${r}</button>`).join("")}</div>
        <input class="filtro" id="busca-if" placeholder="buscar instituição ou ticker" style="max-width:240px"></div></div>
    <div class="painel aviso-4966" data-info="ifdata_4966" style="margin-bottom:10px"><h2>Mudança no IF.data em 2025 (Resolução CMN 4.966)</h2>
      <p class="sub" style="margin:0">O detalhe das demonstrações e das carteiras começa no 1º tri de 2025, quando entraram as novas regras contábeis dos bancos.
        Clique em ⓘ para entender o que mudou.</p></div>
    <div class="painel" data-info="ifdata"><h2>Instituições financeiras</h2><div class="rolagem" id="tab-if"></div>
      <div class="nota">Fonte: Banco Central — IF.data (conglomerado prudencial ou instituição independente). ROE = lucro dos últimos 12 meses ÷ PL;
        inadimplência = carteira inadimplente ÷ carteira total.</div></div>`;
  const desenhar = () => {
    const q = busca.trim().toUpperCase();
    const lista = b.instituicoes.filter((i) => (tipo === "todas" || TIPOS_IF[tipo].includes(i.tipo_cod))
      && (!q || i.nome.toUpperCase().includes(q) || (i.ticker || "").includes(q)));
    let seg = null;
    const linhas = lista.map((i) => {
      const cab = i.segmento !== seg ? `<tr><th colspan="11" style="text-align:left;color:var(--ambar);padding-top:12px">${esc(SEGMENTOS[(seg = i.segmento) || ""] || i.segmento)}</th></tr>` : "";
      return `${cab}<tr class="clicavel" onclick="location.hash='#/on/banco/${esc(i.id)}'">
        <td>${esc(i.nome.replace(/ - PRUDENCIAL$/, ""))}${i.ticker ? `<span class="etiqueta">${esc(i.ticker)}</span>` : ""}${i.fonte === "CVM" ? `<span class="etiqueta" title="Fora do IF.data: dados da CVM">CVM</span>` : ""}</td>
        <td class="sub">${esc(TIPO_CURTO[i.tipo_cod] || i.tipo_cod || "")}${i.segmento_calculado ? ' <span class="etiqueta" title="Segmento em branco no cadastro do BC: calculado pelo site pela regra da Res. 4.553">seg. calculado</span>' : ""}</td><td class="sub">${esc(i.controle || "")}</td><td class="sub">${esc(i.uf || "")}</td>
        <td>${reais(i.ativo)}</td><td>${reais(i.carteira)}</td><td>${reais(i.pl)}</td><td class="${classeSinal(i.lucro_12m)}">${reais(i.lucro_12m)}</td>
        <td>${pct(i.roe)}</td><td>${pct(i.basileia)}</td><td>${pct(i.inadimplencia, 2)}</td></tr>`;
    }).join("");
    document.getElementById("tab-if").innerHTML = `<table class="tabela"><thead><tr><th>Instituição</th><th style="text-align:left">Tipo</th><th style="text-align:left">Controle</th>
      <th>UF</th><th>Ativo total</th><th>Carteira</th><th>PL</th><th>Lucro 12m</th><th>ROE</th><th>Basileia</th><th>Inadimplência</th></tr></thead>
      <tbody>${linhas || `<tr><td colspan="11" class="sub">Nenhuma instituição.</td></tr>`}</tbody></table>`;
  };
  document.getElementById("tipo-if").addEventListener("click", (ev) => {
    const x = ev.target.closest("button"); if (!x) return;
    tipo = x.dataset.k;
    document.querySelectorAll("#tipo-if button").forEach((y) => y.classList.toggle("ativo", y === x));
    desenhar();
  });
  document.getElementById("busca-if").addEventListener("input", (ev) => { busca = ev.target.value; desenhar(); });
  desenhar();
}

// ---------- página de um banco ----------
const ABAS_BANCO = [["perfil", "Perfil"], ["dfs", "DFs"], ["carteira_resumo", "Carteira — resumo"], ["carteira_total", "Carteira — total"]];
let ABA_BANCO = "perfil";
let PERIODO_DF = { tipo: "trimestre", fim: null };

// períodos disponíveis de cada tipo: [{rotulo, idx: índices dos trimestres que compõem o período}]
function periodosDF(trimestres, tipo) {
  const n = trimestres.length, saida = [];
  const mes = (i) => Number(trimestres[i].slice(5, 7)), ano = (i) => trimestres[i].slice(0, 4);
  for (let i = 0; i < n; i++) {
    if (tipo === "trimestre") saida.push({ rotulo: triIF(trimestres[i]), idx: [i] });
    else if (tipo === "semestre" && (mes(i) === 6 || mes(i) === 12) && i >= 1 && ano(i - 1) === ano(i)) saida.push({ rotulo: `${mes(i) === 6 ? 1 : 2}S${ano(i).slice(2)}`, idx: [i - 1, i] });
    else if (tipo === "anual" && mes(i) === 12 && i >= 3 && ano(i - 3) === ano(i)) saida.push({ rotulo: ano(i), idx: [i - 3, i - 2, i - 1, i] });
    else if (tipo === "ltm" && i >= 3) saida.push({ rotulo: `LTM ${triIF(trimestres[i])}`, idx: [i - 3, i - 2, i - 1, i] });
  }
  return saida;
}

function tabelaDF(linhas, periodos, fluxo, baseK, escala) {
  // fluxo (DRE): soma dos trimestres; estoque (balanço): saldo do último trimestre do período
  const valor = (l, p) => {
    if (!fluxo) return l.v[p.idx[p.idx.length - 1]];
    const xs = p.idx.map((i) => l.v[i]);
    return xs.some((x) => x == null) ? null : xs.reduce((a, b) => a + b, 0);
  };
  const base = linhas.find((l) => l.k === baseK);
  const fmt = (v) => (v == null ? "—" : num(v / escala, 0));
  return `<table class="tabela tabela-df"><tr><th></th>${periodos.map((p) => `<th>${p.rotulo}</th><th class="sub">(%)</th>`).join("")}<th>∆P (%)</th></tr>
    ${linhas.map((l) => {
      const vs = periodos.map((p) => valor(l, p)), bs = periodos.map((p) => (base ? valor(base, p) : null));
      const ini = vs[0], fim = vs[vs.length - 1];
      const delta = ini != null && fim != null && ini !== 0 && periodos.length > 1 ? (fim - ini) / Math.abs(ini) : null;
      const estilo = l.n < 0 ? "font-weight:700;color:var(--texto-forte)" : "";
      return `<tr><td style="text-align:left;padding-left:${8 + Math.max(l.n, 0) * 14}px;${estilo}">${esc(l.r)}</td>
        ${vs.map((v, j) => `<td style="${estilo}">${fmt(v)}</td><td class="sub">${l.k === baseK || v == null || !bs[j] ? "" : pct(v / bs[j])}</td>`).join("")}
        <td class="${delta == null ? "" : classeSinal(delta)}">${delta == null ? "—" : pct(delta)}</td></tr>`;
    }).join("")}</table>`;
}

async function paginaBanco(id) {
  const bk = await dados(`dados/bancos/${id}.json`);
  const tk = bk.ticker;
  const [ficha, negocio, resumoAp, eventos, mercado] = tk ? await Promise.all([
    dados(`dados/fichas/${tk}.json`).catch(() => null), dados(`dados/negocio/${tk}.json`).catch(() => null),
    dados(`dados/resumos/${tk}.json`).catch(() => null), dados(`dados/eventos/${tk}.json`).catch(() => null),
    dados("dados/mercado.json").catch(() => null)]) : [null, null, null, null, null];
  const mk = mercado ? mercado.empresas.find((x) => x.id === tk) || {} : {};
  const cot = mk.papel_referencia && mk.cotacoes ? mk.cotacoes[mk.papel_referencia] : null;
  const soCvm = bk.fonte === "CVM";
  const lista = await dados("dados/bancos.json").catch(() => null);
  const temExcel = Boolean(lista && (lista.instituicoes.find((i) => i.id === id) || {}).excel);
  const T = bk.trimestres, n = T.length - 1;
  const R = bk.resumo;
  const ultimoR = (k) => (R[k] || [])[n];
  const l4 = (R["Lucro Líquido"] || []).slice(-4);
  const lucro12 = l4.length === 4 && l4.every((x) => x != null) ? l4.reduce((a, b) => a + b, 0) : null;
  const cap = (k) => (bk.capital.find((l) => l.k === k) || { v: [] }).v[n];
  const abasBanco = [...ABAS_BANCO.filter(([k]) => !(soCvm && k.startsWith("carteira"))), ...(tk ? [["eventos", "Eventos e notícias"]] : [])];
  if (!abasBanco.some(([k]) => k === ABA_BANCO)) ABA_BANCO = "perfil";
  const tg = (bk.carteiras["Total Geral"] || [])[n], inad = (bk.carteiras["Inadimplência"] || [])[n];
  app.innerHTML = `
    <div class="cabecalho"><div><h1>${esc(bk.nome.replace(/ - PRUDENCIAL$/, ""))}${bk.ticker ? ` · ${esc(bk.ticker)}` : ""}</h1>
      <div class="sub">${esc(bk.tipo || "")} · ${esc(SEGMENTOS[bk.segmento || ""] || "")}${bk.segmento_calculado ? " (calculado pelo site: em branco no cadastro do BC)" : ""} · ${esc(bk.controle || "")} · ${esc(bk.municipio || "")}/${esc(bk.uf || "")}
        · data-base ${dataBR(T[n])} · fonte: ${soCvm ? "CVM (ITR/DFP)" : "Banco Central (IF.data)"}</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">${temExcel ? `<a class="botao" href="downloads/bancos/${esc(bk.id)}.xlsx" download>Baixar Excel (DFs)</a>` : ""}
        <a class="botao" href="#/on/empresas/financeiras">Voltar à lista</a></div></div>
    ${soCvm ? `<div class="aviso">Esta instituição não aparece no IF.data do Banco Central: os números vêm das demonstrações entregues à CVM (ITR/DFP),
      no plano de contas da CVM, e não há dados de capital (Basileia) nem de carteira de crédito.</div>` : ""}
    <div class="grade-cartoes">
      ${cot ? cartao(`Preço ${esc(mk.papel_referencia)}`, `R$ ${num(cot.preco, 2)}`, `<span class="${classeSinal(cot.variacao_dia)}">${num(cot.variacao_dia, 2)}%</span> · ${dataBR(cot.data)}`) : ""}
      ${mk.market_cap ? cartao("Market cap", reais(mk.market_cap), "ações B3 × preço") : ""}
      ${mk.market_cap && ultimoR("Patrimônio Líquido") > 0 ? cartao("P/VP", vezes(mk.market_cap / ultimoR("Patrimônio Líquido")), "market cap ÷ PL") : ""}
      ${mk.market_cap && lucro12 > 0 ? cartao("P/L", vezes(mk.market_cap / lucro12), "market cap ÷ lucro 12m") : ""}
      ${mk.dy_12m != null ? cartao("DY 12m", pct(mk.dy_12m, 2), "proventos B3 ÷ preço") : ""}
      ${cartao("Ativo total", reais(ultimoR("Ativo Total")), triIF(T[n]))}
      ${soCvm ? "" : cartao("Carteira de crédito", reais(ultimoR("Carteira de Crédito")), "")}
      ${soCvm ? "" : cartao("Captações", reais(ultimoR("Captações")), "")}
      ${cartao("Patrimônio líquido", reais(ultimoR("Patrimônio Líquido")), "")}
      ${cartao("Lucro 12 meses", reais(lucro12), "soma dos 4 trimestres")}
      ${cartao("ROE", pct(lucro12 != null && ultimoR("Patrimônio Líquido") > 0 ? lucro12 / ultimoR("Patrimônio Líquido") : null), "lucro 12m ÷ PL")}
      ${soCvm ? "" : cartao("Índice de Basileia", pct(cap("n")), `capital principal ${pct(cap("l"))}`)}
      ${soCvm ? "" : cartao("Inadimplência", pct(tg ? inad / tg : null, 2), "carteira inadimplente ÷ total")}
    </div>
    <div class="abas" id="abas-banco">${abasBanco.map(([k, r]) => `<button data-k="${k}" class="${k === ABA_BANCO ? "ativo" : ""}">${r}</button>`).join("")}</div>
    <div id="aba-banco"></div>`;
  const area = () => document.getElementById("aba-banco");
  const ultimos5 = T.map((_, i) => i).slice(-5);
  const P = (s, datas) => datas.map((d, i) => [d, s[i]]);

  const ABAS = {
    perfil: () => {
      const tabelaInfo = (titulo, linhas, fmt) => `<table class="tabela"><tr><th style="text-align:left">${titulo}</th>${ultimos5.map((i) => `<th>${triIF(T[i])}</th>`).join("")}<th>∆P (%)</th></tr>
        ${linhas.map(([rotulo, vals, indice]) => { const ini = vals[ultimos5[0]], fim = vals[ultimos5[ultimos5.length - 1]];
          const d = ini != null && fim != null && ini !== 0 ? (fim - ini) / Math.abs(ini) : null;
          return `<tr><td style="text-align:left">${rotulo}</td>${ultimos5.map((i) => `<td>${indice ? pct(vals[i]) : fmt(vals[i])}</td>`).join("")}
            <td class="${d == null ? "" : classeSinal(d)}">${d == null ? "—" : pct(d)}</td></tr>`; }).join("")}</table>`;
      const mil = (v) => (v == null ? "—" : num(v / 1e3, 0));
      const gerais = soCvm ? [["Ativo Total", R["Ativo Total"]], ["Patrimônio Líquido", R["Patrimônio Líquido"]], ["Lucro Líquido (trimestre)", R["Lucro Líquido"]]]
        : [["Quantidade de clientes com operações ativas", bk.clientes["Quantidade de clientes com operações ativas"] || []],
        ["Quantidade de operações ativas", bk.clientes["Quantidade de operações ativas"] || []],
        ["Ativo Total", R["Ativo Total"]], ["Carteira de Crédito", R["Carteira de Crédito"]], ["Títulos e Valores Mobiliários", R["Títulos e Valores Mobiliários"]],
        ["Passivo Exigível", R["Passivo Exigível"]], ["Captações", R["Captações"]], ["Patrimônio Líquido", R["Patrimônio Líquido"]],
        ["Lucro Líquido (trimestre)", R["Lucro Líquido"]]];
      const cad = [["Instituição", bk.nome], ["Tipo", bk.tipo], ["Segmento prudencial", SEGMENTOS[bk.segmento || ""]], ["Controle", bk.controle],
        ["Atividade", bk.atividade], ["Sede", `${bk.municipio || "—"}/${bk.uf || "—"}`], ["Início das atividades", bk.inicio_atividade ? String(bk.inicio_atividade).replace(/(\d{4})(\d{2})/, "$2/$1") : "—"],
        ["Código no IF.data", bk.cod || "não está no IF.data"], ["CNPJ da instituição líder", bk.cnpj_lider || "—"], ["Ticker na B3", bk.ticker || "não listada"]];
      const H = bk.historico;
      const perfilCvm = tk ? `<div id="resumo-aprofundado"></div><div class="grade" style="margin-bottom:10px"><div class="painel" id="ficha"></div><div class="painel" id="negocio"></div></div>` : "";
      area().innerHTML = `${perfilCvm}<div class="grade">
        <div class="painel" data-info="ifdata"><h2>Cadastro</h2><table class="tabela">${cad.map(([k, v]) => `<tr><td style="text-align:left" class="sub">${k}</td><td style="text-align:left">${esc(v || "—")}</td></tr>`).join("")}</table>
          <div class="nota">Fonte: ${soCvm ? "CVM" : "Banco Central — IF.data (cadastro)"}.</div></div>
        <div class="painel" data-info="ifdata"><h2>Dados gerais (valores em R$ mil)</h2><div class="rolagem">${tabelaInfo("Dados gerais", gerais.map(([r, v]) => [r, v]),
          (v) => (v == null ? "—" : r_mil(v)))}</div></div>
        ${soCvm ? "" : `<div class="painel largo" data-info="capital_banco"><h2>Dados patrimoniais e capital (valores em R$ mil)</h2><div class="rolagem">${tabelaInfo("Capital",
          bk.capital.map((l) => [l.r, l.v, l.indice]), mil)}</div></div>`}
        ${painelG("gb-ativo", soCvm ? "Ativo total" : "Ativo total e carteira de crédito (desde 2015)", "historico_banco")}
        ${painelG("gb-lucro", soCvm ? "Lucro trimestral e patrimônio líquido" : "Lucro trimestral e patrimônio líquido (desde 2015)", "historico_banco")}
        ${soCvm ? "" : painelG("gb-basileia", "Índice de Basileia (desde 2015)", "capital_banco", "", "largo")}
      </div>`;
      if (tk) { desenharFicha(ficha); desenharNegocio(negocio, resumoAp); }
      grafico(document.getElementById("gb-ativo"), { xTempo: true, eixoEsq: "reais", series: [
        { nome: "Ativo total", valores: P(H.ativo, H.datas), tipo: "line", cor: COR.azul },
        ...(H.carteira ? [{ nome: "Carteira de crédito", valores: P(H.carteira, H.datas), tipo: "line", cor: COR.ambar }] : []),
        ...(H.captacoes ? [{ nome: "Captações", valores: P(H.captacoes, H.datas), tipo: "line", cor: COR.cinza, tracejado: true }] : [])] });
      grafico(document.getElementById("gb-lucro"), { xTempo: true, eixoEsq: "reais", eixoDir: "reais", series: [
        { nome: "Lucro trimestral", valores: P(H.lucro_tri, H.datas), cor: COR.verde }, { nome: "Patrimônio líquido", valores: P(H.pl, H.datas), tipo: "line", eixo: "dir", cor: COR.ambar }] });
      if (!soCvm) grafico(document.getElementById("gb-basileia"), { xTempo: true, eixoEsq: "pct", series: [
        { nome: "Índice de Basileia", valores: P(H.basileia, H.datas), tipo: "line", cor: COR.ambar },
        { nome: "Mínimo regulatório (11%)", valores: H.datas.map((d) => [d, 0.105]), tipo: "line", cor: COR.vermelho, tracejado: true }] });
    },
    dfs: () => {
      const tipos = [["trimestre", "Trimestre"], ["semestre", "Semestre"], ["anual", "Anual"], ["ltm", "LTM"]];
      const desenhar = () => {
        const todos = periodosDF(T, PERIODO_DF.tipo);
        if (!todos.length) { document.getElementById("df-corpo").innerHTML = `<p class="sub">Ainda não há período completo desse tipo no layout novo (desde 1T25).</p>`; return; }
        let fim = todos.findIndex((p) => p.rotulo === PERIODO_DF.fim);
        if (fim < 0) fim = todos.length - 1;
        document.getElementById("df-fim").innerHTML = todos.map((p, i) => `<option value="${esc(p.rotulo)}" ${i === fim ? "selected" : ""}>${esc(p.rotulo)}</option>`).join("");
        const sel = todos.slice(Math.max(0, fim - 4), fim + 1);
        document.getElementById("df-corpo").innerHTML = `
          <div class="painel largo" data-info="dfs_banco"><h2>Ativo (R$ mil)</h2><div class="rolagem">${tabelaDF(bk.ativo, sel, false, soCvm ? "1" : "k", 1e3)}</div></div>
          <div class="painel largo" data-info="dfs_banco"><h2>Passivo (R$ mil)</h2><div class="rolagem">${tabelaDF(bk.passivo, sel, false, soCvm ? "2" : "k", 1e3)}</div></div>
          <div class="painel largo" data-info="dfs_banco"><h2>DRE (R$ mil) — ${{ trimestre: "trimestre", semestre: "semestre", anual: "ano", ltm: "últimos 12 meses" }[PERIODO_DF.tipo]}</h2>
            <div class="rolagem">${tabelaDF(bk.dre, sel, true, soCvm ? (bk.dre[0] || {}).k : "=receitas", 1e3)}</div>
            <div class="nota">(%) da DRE = sobre as receitas da intermediação financeira; (%) do balanço = sobre o total. ∆P = variação entre a primeira e a última coluna.</div></div>`;
      };
      area().innerHTML = `<div class="cabecalho" style="margin-bottom:8px"><div class="seletor" id="df-tipo">${tipos.map(([k, r]) => `<button data-k="${k}" class="${k === PERIODO_DF.tipo ? "ativo" : ""}">${r}</button>`).join("")}</div>
        <label class="sub">Até: <select id="df-fim" class="filtro" style="width:auto;display:inline-block"></select></label></div>
        ${soCvm ? "" : `<div class="painel aviso-4966" data-info="ifdata_4966"><h2>Mudança no IF.data em 2025 (Resolução CMN 4.966)</h2>
          <p class="sub" style="margin:0">Desde o 1º tri de 2025 os bancos seguem novas regras contábeis, alinhadas ao IFRS 9, e o Banco Central mudou os
            relatórios: provisão por perda esperada, carteiras C1 a C5, "ativos problemáticos" e outro plano de contas. Por isso as DFs começam em 1T25.
            Clique em ⓘ para o resumo das mudanças.</p></div>`}
        <div class="grade" id="df-corpo"></div>
        <div class="nota secao">${soCvm ? "Demonstrações entregues à CVM (ITR/DFP), contas até o 3º nível; o 4º trimestre é o ano (DFP) menos os 9 meses."
          : "Layout do IF.data desde 1T25 (Resolução CMN 4.966)."} Semestre e anual somam os trimestres; LTM soma os últimos 4 trimestres.
          O balanço mostra o saldo no fim de cada período.</div>`;
      document.getElementById("df-tipo").addEventListener("click", (ev) => {
        const x = ev.target.closest("button"); if (!x) return;
        PERIODO_DF = { tipo: x.dataset.k, fim: null };
        document.querySelectorAll("#df-tipo button").forEach((y) => y.classList.toggle("ativo", y === x));
        desenhar();
      });
      document.getElementById("df-fim").addEventListener("change", (ev) => { PERIODO_DF.fim = ev.target.value; desenhar(); });
      desenhar();
    },
    carteira_resumo: () => {
      const rot = T.map(triIF);
      const empilhado = (obj, chaves, total) => chaves.filter((k) => obj[k] && obj[k].some((x) => x)).map((k, i) => ({
        nome: k.split("|").pop(), valores: obj[k].map((x, j) => (x == null || !total[j] ? null : x / total[j])), cor: PALETA_GRAF[i % PALETA_GRAF.length], pilha: "a" }));
      // prazo consolidado = soma das modalidades PF e PJ por faixa
      const porFaixa = PRAZOS_IF.map((f) => T.map((_, j) => [bk.pf, bk.pj].reduce((s, g) => s + Object.entries(g)
        .filter(([k]) => k.split("|")[1].toLowerCase() === f.toLowerCase()).reduce((a, [, v]) => a + (v[j] || 0), 0), 0)));
      const totalFaixas = T.map((_, j) => porFaixa.reduce((a, s) => a + s[j], 0));
      const C = bk.carteiras, tot = C["Total Geral"] || T.map(() => null);
      area().innerHTML = `<div class="grade">
        ${painelG("gr-prazo", "Carteira por prazo (% do total)", "carteira_banco")}
        ${painelG("gr-c", "Carteira por classificação C1 a C5 (% do total)", "carteira_banco")}
        ${painelG("gr-inad", "Inadimplência e ativos problemáticos (% da carteira)", "carteira_banco")}
        ${painelG("gr-tam", "Carteira total, clientes e operações", "carteira_banco")}
        ${painelG("gr-idx", "Carteira por indexador (% do total)", "carteira_banco")}
        ${painelG("gr-reg", "Carteira por região (% do total)", "carteira_banco")}
        ${painelG("gr-porte", "Carteira PJ por porte do tomador (% da carteira PJ)", "carteira_banco", "", "largo")}
      </div><div class="nota secao">Concentração nos maiores devedores: não é divulgada no IF.data desde 2025.</div>`;
      grafico(document.getElementById("gr-prazo"), { rotulos: rot, eixoEsq: "pct", series: PRAZOS_IF.map((f, i) => ({ nome: f.replace("A Vencer ", "").replace("Entre ", ""),
        valores: porFaixa[i].map((x, j) => (totalFaixas[j] ? x / totalFaixas[j] : null)), cor: PALETA_GRAF[i], pilha: "a" })) });
      grafico(document.getElementById("gr-c"), { rotulos: rot, eixoEsq: "pct", series: empilhado(C, ["C1", "C2", "C3", "C4", "C5", "Carteira não Informada ou não se Aplica", "Total não Individualizado", "Total Exterior"], tot) });
      grafico(document.getElementById("gr-inad"), { rotulos: rot, eixoEsq: "pct", series: [
        { nome: "Inadimplência", valores: (C["Inadimplência"] || []).map((x, j) => (x == null || !tot[j] ? null : x / tot[j])), tipo: "line", cor: COR.vermelho },
        { nome: "Ativos problemáticos", valores: (C["Ativos problemáticos"] || []).map((x, j) => (x == null || !tot[j] ? null : x / tot[j])), tipo: "line", cor: COR.ambar }] });
      grafico(document.getElementById("gr-tam"), { rotulos: rot, eixoEsq: "reais", eixoDir: "numero", series: [
        { nome: "Carteira total", valores: tot, cor: COR.azul },
        { nome: "Clientes", valores: bk.clientes["Quantidade de clientes com operações ativas"] || [], tipo: "line", eixo: "dir", cor: COR.ambar },
        { nome: "Operações", valores: bk.clientes["Quantidade de operações ativas"] || [], tipo: "line", eixo: "dir", cor: COR.cinza, tracejado: true }] });
      const idx = Object.keys(bk.indexador).filter((k) => !/^Total/.test(k));
      const totIdx = bk.indexador["Total Geral"] || tot;
      grafico(document.getElementById("gr-idx"), { rotulos: rot, eixoEsq: "pct", series: empilhado(bk.indexador, idx, totIdx) });
      const reg = Object.keys(bk.regiao).filter((k) => k !== "Total Geral");
      grafico(document.getElementById("gr-reg"), { rotulos: rot, eixoEsq: "pct", series: empilhado(bk.regiao, reg, bk.regiao["Total Geral"] || tot) });
      const portes = ["Micro", "Pequena", "Média", "Grande", "Indisponível", "Total Exterior Pessoa Jurídica", "Total não Individualizado Pessoa Jurídica"];
      grafico(document.getElementById("gr-porte"), { rotulos: rot, eixoEsq: "pct", series: empilhado(bk.porte, portes, bk.porte["Total da Carteira de Pessoa Jurídica"] || tot) });
    },
    eventos: async () => {
      const not = await dados("dados/noticias.json").catch(() => null);
      const doBanco = ((not && not.itens) || []).filter((x) => (x.empresas || []).includes(tk));
      area().innerHTML = `<div class="grade">
        <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Eventos (CVM)</h2>
          <div class="seletor" id="sel-ev">${OPCOES_EVENTOS.map(([k, r]) => `<button data-k="${k}" class="${k === "todos" ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
          <div class="rolagem rolagem-y" id="lista-eventos"></div>
          <div class="nota">Fatos relevantes, comunicados ao mercado e avisos aos acionistas dos últimos 3 anos, com link para o documento oficial na CVM.</div></div>
        <div class="painel"><h2>Notícias que citam o banco</h2>${listaNoticias(doBanco, 60)}
          <div class="nota">Manchetes dos últimos dias que citam o ticker ou o nome de pregão.</div></div></div>`;
      desenharEventos(eventos, "todos");
      document.getElementById("sel-ev").addEventListener("click", (ev) => {
        const x = ev.target.closest("button"); if (!x) return;
        document.querySelectorAll("#sel-ev button").forEach((y) => y.classList.toggle("ativo", y === x));
        desenharEventos(eventos, x.dataset.k);
      });
    },
    carteira_total: () => {
      const rot = T.map(triIF);
      const modalidades = (g) => [...new Set(Object.keys(g).filter((k) => k.endsWith("|Total") && k.split("|")[0]).map((k) => k.split("|")[0]))];
      const pfM = modalidades(bk.pf), pjM = modalidades(bk.pj);
      const serieM = (g, m) => g[`${m}|Total`] || [];
      const totPF = bk.pf["|Total da Carteira de Pessoa Física"] || [], totPJ = bk.pj["|Total da Carteira de Pessoa Jurídica"] || [];
      const faixasUlt = (g, m) => PRAZOS_IF.map((f) => { const k = Object.keys(g).find((x) => x.split("|")[0] === m && x.split("|")[1].toLowerCase() === f.toLowerCase()); return k ? g[k][n] : null; });
      area().innerHTML = `<div class="grade">
        ${painelG("gt-pf", "Carteira PF por modalidade (R$)", "carteira_banco")}
        ${painelG("gt-pj", "Carteira PJ por modalidade (R$)", "carteira_banco")}
        ${painelG("gt-pf-prazo", `Carteira PF por modalidade e prazo — ${triIF(T[n])}`, "carteira_banco")}
        ${painelG("gt-pj-prazo", `Carteira PJ por modalidade e prazo — ${triIF(T[n])}`, "carteira_banco")}
        ${painelG("gt-pfpj", "Carteira PF x PJ (R$)", "carteira_banco", "", "largo")}
      </div>`;
      grafico(document.getElementById("gt-pf"), { rotulos: rot, eixoEsq: "reais", series: pfM.map((m, i) => ({ nome: m, valores: serieM(bk.pf, m), cor: PALETA_GRAF[i % PALETA_GRAF.length], pilha: "a" })) });
      grafico(document.getElementById("gt-pj"), { rotulos: rot, eixoEsq: "reais", series: pjM.map((m, i) => ({ nome: m.slice(0, 40), valores: serieM(bk.pj, m), cor: PALETA_GRAF[i % PALETA_GRAF.length], pilha: "a" })) });
      const porPrazo = (g, ms) => PRAZOS_IF.map((f, i) => ({ nome: f.replace("A Vencer ", "").replace("Entre ", ""), valores: ms.map((m) => faixasUlt(g, m)[i]), cor: PALETA_GRAF[i], pilha: "a" }));
      grafico(document.getElementById("gt-pf-prazo"), { rotulos: pfM.map((m) => m.slice(0, 18)), eixoEsq: "reais", series: porPrazo(bk.pf, pfM) });
      grafico(document.getElementById("gt-pj-prazo"), { rotulos: pjM.map((m) => m.slice(0, 18)), eixoEsq: "reais", series: porPrazo(bk.pj, pjM) });
      grafico(document.getElementById("gt-pfpj"), { rotulos: rot, eixoEsq: "reais", series: [
        { nome: "Pessoa física", valores: totPF, cor: COR.verde, pilha: "a" }, { nome: "Pessoa jurídica", valores: totPJ, cor: COR.azul, pilha: "a" }] });
    },
  };
  const mostrar = (k) => {
    limparGraficos();
    ABA_BANCO = ABAS[k] ? k : "perfil";
    document.querySelectorAll("#abas-banco button").forEach((x) => x.classList.toggle("ativo", x.dataset.k === ABA_BANCO));
    ABAS[ABA_BANCO]();
  };
  document.getElementById("abas-banco").addEventListener("click", (ev) => { const x = ev.target.closest("button"); if (x) mostrar(x.dataset.k); });
  mostrar(ABA_BANCO);
}
const r_mil = (v) => (v == null ? "—" : Math.abs(v) >= 1e4 ? num(v / 1e3, 0) : num(v, 0));
const PRAZOS_IF = ["Vencido a Partir de 15 Dias", "A Vencer em até 90 Dias", "A Vencer Entre 91 a 360 Dias", "A Vencer Entre 361 a 1080 Dias",
  "A Vencer Entre 1081 a 1800 Dias", "A Vencer Entre 1801 a 5400 Dias", "A Vencer Acima de 5400 Dias"];
const PALETA_GRAF = ["#388bfd", "#f0b429", "#3fb950", "#a371f7", "#39c5cf", "#f85149", "#8b949e", "#db61a2", "#d29922", "#56d364", "#79c0ff", "#ff7b72"];

/* ============ Status dos dados ============ */
const NOMES_ETAPAS = {
  macro: "Macro (Banco Central, IBGE, FGV)", agenda: "Agenda (Banco Central, IBGE, FGV)", tesouro: "Tesouro Direto", curva_di: "Curva DI (B3)",
  mercado: "Cotações e proventos (B3)", noticias: "Notícias", planilhas: "Planilhas de Macro e Juros", eventos: "Eventos (CVM)",
  ficha: "Ficha da empresa (FRE/FCA)", fre_textos: "Trechos do Formulário de Referência", resumos: "Resumos aprofundados",
  cvm_base: "Base de demonstrações (CVM)", empresas: "Empresas (JSON e Excel)", indice: "Índice de empresas",
  offshore: "Offshore (Tesouro dos EUA, Fed, BLS, BCE, Eurostat)", bancos: "Instituições financeiras (IF.data)", eleicoes: "Eleições 2026 (TSE)", calendario_resultados: "Calendário de resultados (CVM)", tesouro_intradia: "Tesouro Direto — tempo real (3x ao dia)",
};

async function paginaStatus() {
  const [st, saude, agenda, obs] = await Promise.all([dados("dados/status.json").catch(() => null), dados("dados/saude.json").catch(() => null),
    dados("dados/agenda.json").catch(() => null), dados("dados/observacoes.json").catch(() => null)]);
  const marca = (ok) => `<span class="${ok ? "pos" : "neg"}">${ok ? "✔" : "✖"}</span>`;
  const quando = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Status dos dados</h1><div class="sub">Resultado da última atualização automática e das checagens do monitor de fontes</div></div>
      <a class="botao" href="https://github.com/fredperin/screeening-cvm/actions" target="_blank" rel="noopener">Execuções no GitHub</a></div>
    <div class="painel" style="margin-bottom:10px"><h2>Observações em aberto</h2>${(() => {
      const ab = (obs && obs.abertas) || [];
      return ab.length ? `<table class="tabela"><tr><th>Fonte</th><th style="text-align:left">Problema</th><th>Desde</th></tr>
        ${ab.map((o) => `<tr><td>${esc(o.fonte)}</td><td style="white-space:normal;text-align:left" class="neg">${esc(o.detalhe)}</td><td>${quando(o.desde)}</td></tr>`).join("")}</table>`
        : `<p class="pos" style="margin:0">Nenhuma — todas as fontes passaram na última verificação.</p>`;
    })()}</div>
    <div class="grade">
      <div class="painel"><h2>Atualização — ${st ? quando(st.atualizado_em) : "—"}</h2>${st ? `<table class="tabela">
        <tr><th>Etapa</th><th></th><th>Tempo / erro</th></tr>
        ${Object.entries(st.etapas).map(([k, e]) => `<tr><td>${esc(NOMES_ETAPAS[k] || k)}</td><td>${marca(e.ok)}</td>
          <td style="white-space:normal" class="${e.ok ? "sub" : "neg"}">${e.ok ? `${e.segundos} s` : esc(e.erro || "")}</td></tr>`).join("")}</table>
        ${st.cvm_reprocessados && st.cvm_reprocessados.length ? `<div class="nota">Arquivos da CVM reprocessados: ${esc(st.cvm_reprocessados.join(", "))}</div>` : ""}`
        : `<p class="sub">status.json indisponível.</p>`}</div>
      <div class="painel"><h2>Fontes — verificado em ${saude ? quando(saude.verificado_em) : "—"}</h2>${saude ? `<table class="tabela">
        <tr><th>Fonte</th><th></th><th style="text-align:left">Detalhe</th></tr>
        ${Object.entries(saude.fontes).map(([k, f]) => `<tr><td>${esc(k)}</td><td>${marca(f.ok)}</td>
          <td style="white-space:normal;text-align:left" class="${f.ok ? "sub" : "neg"}">${esc(f.detalhe)}</td></tr>`).join("")}</table>`
        : `<p class="sub">saude.json indisponível.</p>`}</div>
      <div class="painel"><h2>Divulgações dos próximos 7 dias</h2>${tabelaAgenda(agenda, 7)}
        <div class="nota">O que deve aparecer no site depois de cada divulgação (a atualização roda todo dia às 06:30).</div></div>
    </div>
    <div class="nota secao">A atualização roda todo dia às 06:30 (Brasília) no GitHub Actions; o monitor confere cada fonte logo depois e abre um alerta
      no GitHub se algo falhar. Para uma verificação detalhada, peça ao Claude: "rode o auditor de atualização".</div>`;
}

/* ============ Observações: problemas de dados em aberto ============ */
// Vêm do monitor (atualização diária) e do Tesouro em tempo real (3x ao dia); cada item some quando o problema é resolvido
async function carregarObservacoes() {
  const [obs, tes] = await Promise.all([dados("dados/observacoes.json").catch(() => null), dados("dados/tesouro.json").catch(() => null)]);
  const itens = ((obs && obs.abertas) || []).map((o) => ({ fonte: o.fonte, detalhe: o.detalhe, desde: o.desde }));
  if (tes && tes.falha_tempo_real) itens.push({ fonte: "Tesouro Direto — tempo real (não oficial)", detalhe: tes.falha_tempo_real, desde: tes.gerado_em });
  const area = document.getElementById("observacoes");
  if (!itens.length) { area.hidden = true; return; }
  const quando = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");
  area.innerHTML = `<details><summary>⚠ Observações sobre os dados (${itens.length}) — o site segue com os últimos dados bons dessas fontes</summary>
    <ul>${itens.map((o) => `<li><b>${esc(o.fonte)}</b> <span class="sub">· desde ${quando(o.desde)}</span><br><span class="sub">${esc(o.detalhe.slice(0, 260))}</span></li>`).join("")}</ul>
    <div class="sub">Cada observação sai daqui sozinha quando a fonte volta ao normal. Detalhes em <a href="#/status">Status dos dados</a>
      ${obs ? `· última verificação ${quando(obs.verificado_em)}` : ""}.</div></details>`;
  area.hidden = false;
}

/* ============ início ============ */
iniciarBusca().then(rotear);
carregarObservacoes();
