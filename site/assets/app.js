"use strict";

/* ============ utilidades ============ */
const COR = {
  ambar: "#f0b429", verde: "#3fb950", vermelho: "#f85149", azul: "#388bfd", ciano: "#39c5cf",
  roxo: "#a371f7", cinza: "#8b949e", texto: "#c9d1d9", borda: "#263040", grade: "#1b2430",
};
const PALETA_DATAS = ["#f0b429", "#39c5cf", "#a371f7", "#3fb950", "#8b949e"];
const cache = {};
const graficos = [];

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
  function ir(id) { entrada.value = ""; caixa.classList.remove("aberta"); location.hash = `#/empresa/${id}`; }
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
const app = document.getElementById("app");
const ROTAS = { "": paginaInicio, empresas: paginaEmpresas, empresa: paginaEmpresa, macro: paginaMacro, juros: paginaJuros, downloads: paginaDownloads };

async function rotear() {
  limparGraficos();
  const [, rota = "", parametro] = location.hash.replace(/^#/, "").split("/");
  document.querySelectorAll("#nav a").forEach((a) => {
    const r = a.dataset.rota;
    a.classList.toggle("ativo", (r === "inicio" && rota === "") || r === rota || (r === "empresas" && rota === "empresa"));
  });
  app.innerHTML = `<p class="carregando">Carregando…</p>`;
  window.scrollTo(0, 0);
  try {
    await (ROTAS[rota] || paginaInicio)(parametro ? decodeURIComponent(parametro) : undefined);
  } catch (e) {
    console.error(e);
    app.innerHTML = `<p class="erro">Não foi possível carregar esta página (${esc(e.message)}).</p>`;
  }
}
window.addEventListener("hashchange", rotear);

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
  const [macro, tesouro, di, mercado] = await Promise.all([
    dados("dados/macro.json").catch(() => null), dados("dados/tesouro.json").catch(() => null),
    dados("dados/curva_di.json").catch(() => null), dados("dados/mercado.json").catch(() => null),
  ]);
  const s = macro ? macro.series : {};
  const selic = ultimo(s.selic_meta), ipca = ultimo(s.ipca_12m), cdi = ultimo(s.cdi), usd = ultimo(s.usd), real = ultimo(s.juro_real);
  const ipcaLongo = tesouro ? tesouro.curvas.hoje.ipca.slice(-1)[0] : null;

  const recentes = [...INDICE].filter((e) => e.ultimo_periodo).sort((a, b) => b.ultimo_periodo.localeCompare(a.ultimo_periodo) || a.nome.localeCompare(b.nome)).slice(0, 15);
  const proximos = mercado ? mercado.empresas.flatMap((e) => (e.proximos_proventos || []).map((p) => ({ ...p, id: e.id }))) : [];
  const hojeIso = new Date().toISOString().slice(0, 10);
  const chave = (p) => (p.data_com >= hojeIso ? p.data_com : p.pagamento || "");
  proximos.sort((a, b) => chave(a).localeCompare(chave(b)));

  app.innerHTML = `
    <div class="cabecalho"><div><h1>Painel</h1><div class="sub">Macro, juros e empresas da lista selecionada</div></div></div>
    <div class="grade-cartoes">
      ${cartao("Selic meta", pctPronto(selic.valor), dataBR(selic.data))}
      ${cartao("IPCA 12 meses", pctPronto(ipca.valor), ipca.data ? ipca.data.slice(0, 7) : "")}
      ${cartao("CDI", pctPronto(cdi.valor), dataBR(cdi.data))}
      ${cartao("Juro real ex-post", pctPronto(real.valor), "Selic ÷ IPCA 12m")}
      ${cartao("Dólar PTAX", usd.valor ? `R$ ${num(usd.valor, 4)}` : "—", dataBR(usd.data))}
      ${cartao("IPCA+ mais longo", ipcaLongo ? pctPronto(ipcaLongo.taxa) : "—", ipcaLongo ? `venc. ${dataBR(ipcaLongo.vencimento)}` : "")}
    </div>
    <div class="grade">
      <div class="painel"><h2>Curva DI x Pré — hoje vs. 1 ano</h2><div class="grafico" id="g-di"></div></div>
      <div class="painel"><h2>Selic meta e IPCA 12m</h2><div class="grafico" id="g-juros"></div></div>
      <div class="painel"><h2>Últimas divulgações</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Empresa</th><th>Período</th><th>Receita</th><th>Var. a/a</th><th>Lucro</th><th>Var. a/a</th></tr>
        ${recentes.map((e) => `<tr class="clicavel" onclick="location.hash='#/empresa/${esc(e.id)}'">
          <td>${esc(e.tickers[0])} <span class="sub">${esc(e.nome.slice(0, 22))}</span></td><td>${dataBR(e.ultimo_periodo)}</td>
          <td>${reais(e.receita_tri)}</td><td class="${classeSinal(e.cresc_receita_tri)}">${pct(e.cresc_receita_tri)}</td>
          <td>${reais(e.lucro_tri)}</td><td class="${classeSinal(e.cresc_lucro_tri)}">${pct(e.cresc_lucro_tri)}</td></tr>`).join("")}
      </table></div></div>
      <div class="painel"><h2>Próximos proventos (data-com ou pagamento futuros)</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Papel</th><th>Tipo</th><th>Data-com</th><th>Pagamento</th><th>R$/ação</th></tr>
        ${proximos.length ? proximos.slice(0, 40).map((p) => `<tr class="clicavel" onclick="location.hash='#/empresa/${esc(p.id)}'">
          <td>${esc(p.id)} <span class="sub">${esc(p.classe)}</span></td><td>${esc(p.tipo)}</td><td>${dataBR(p.data_com)}</td>
          <td>${dataBR(p.pagamento)}</td><td>${num(p.valor, 4)}</td></tr>`).join("") : `<tr><td colspan="5" class="sub">Nenhum provento com data-com ou pagamento futuro anunciado.</td></tr>`}
      </table></div></div>
    </div>`;

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
    const desde = `${new Date().getFullYear() - 5}-01-01`;
    const pares = (serie) => serie.datas.map((d, i) => [d, serie.valores[i]]).filter((p) => p[0] >= desde);
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
async function paginaEmpresas() {
  const mercado = await dados("dados/mercado.json").catch(() => ({ empresas: [] }));
  const mapa = Object.fromEntries(mercado.empresas.map((m) => [m.id, m]));
  const linhas = INDICE.map((e) => {
    const m = mapa[e.id] || {};
    const mc = m.market_cap;
    return { ...e, mc, pl: mc && e.lucro_ltm > 0 ? mc / e.lucro_ltm : null, dy: m.dy_12m };
  });
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Empresas</h1><div class="sub">${INDICE.length} empresas · clique para abrir</div></div>
      <input class="filtro" id="filtro" placeholder="filtrar por nome, ticker ou setor"></div>
    <div class="painel"><div class="rolagem"><table class="tabela" id="tab">
      <thead><tr><th>Papel</th><th>Empresa</th><th>Setor</th><th>Market cap</th><th>Receita LTM</th><th>Lucro LTM</th>
      <th>Margem líq.</th><th>ROE</th><th>DL/EBITDA</th><th>DL/EBITDA c/ IFRS16</th><th>P/L</th><th>DY 12m</th></tr></thead><tbody></tbody></table></div></div>`;
  const corpo = app.querySelector("tbody");
  function desenhar(f = "") {
    const q = f.trim().toUpperCase();
    corpo.innerHTML = linhas.filter((e) => !q || e.nome.toUpperCase().includes(q) || e.tickers.some((t) => t.includes(q)) || (e.setor || "").toUpperCase().includes(q))
      .map((e) => `<tr class="clicavel" onclick="location.hash='#/empresa/${esc(e.id)}'">
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
  const [emp, mercado, prov] = await Promise.all([
    dados(`dados/empresas/${id}.json`), dados("dados/mercado.json").catch(() => ({ empresas: [] })),
    dados(`dados/proventos/${id}.json`).catch(() => null),
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
    </div>
    <div class="cabecalho"><h2 style="margin:0">Resultados</h2>
      <div class="seletor" id="visao">${["trimestral", "semestral", "anual"].map((v) => `<button data-v="${v}" class="${v === VISAO ? "ativo" : ""}">${v[0].toUpperCase() + v.slice(1)}</button>`).join("")}</div></div>
    <div class="grade" id="graficos-empresa"></div>
    <div class="secao painel"><h2>Indicadores — anuais e último LTM</h2><div class="rolagem" id="tab-ind"></div></div>
    <div class="secao"><h2>Dividendos</h2><div class="grade" id="dividendos"></div></div>
    <div class="secao painel nota" id="notas"></div>`;

  document.getElementById("visao").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    VISAO = b.dataset.v;
    document.querySelectorAll("#visao button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharGraficosEmpresa(emp);
  });
  desenharGraficosEmpresa(emp);
  desenharIndicadores(emp);
  desenharDividendos(emp, prov, m);
  const nt = emp.notas || {};
  document.getElementById("notas").innerHTML = `
    <b>Notas.</b> Valores em reais, da CVM (consolidado; individual quando não há consolidado). Semestres e anos só aparecem fechados.
    A visão anual usa o número oficial da DFP. Múltiplos e retornos usam sempre o LTM da mesma data.
    D&amp;A, capex e dividendos pagos não são contas padronizadas da CVM e foram somados pela descrição:<br>
    D&amp;A: ${esc((nt.da || []).join("; ") || "nenhuma linha encontrada (EBITDA = EBIT)")}<br>
    Capex: ${esc((nt.capex || []).join("; ") || "nenhuma linha encontrada")}<br>
    Dividendos pagos: ${esc((nt.dividendos || []).join("; ") || "nenhuma linha encontrada")}<br>
    Dívida bruta sem IFRS 16 = empréstimos, financiamentos e debêntures (CP + LP); com IFRS 16 = soma também os passivos de arrendamento, identificados pela descrição no balanço.`;
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
  area.innerHTML = defs.map((d, i) => `<div class="painel"><h2>${d[0]}</h2><div class="grafico" id="ge-${i}"></div></div>`).join("")
    + `<div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Fluxo de caixa (DFC)</h2>
        <div class="seletor" id="sel-fc">${OPCOES_FC.map(([k, r]) => `<button data-k="${k}" class="${k === FC_SEL ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
        <div class="grafico" id="ge-fc"></div>
        <div class="nota">FCO = operacional · FCI = investimento · FCFi = financiamento · Soma = FCO + FCI + FCFi (variação do caixa, antes da variação cambial).</div></div>
      <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Endividamento</h2>
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
      <div class="painel"><h2>Dividendos + JCP pagos (DFC) e payout</h2><div class="grafico" id="gd-dfc"></div></div>
      <div class="painel"><h2>Proventos por ação ${esc(prov && prov.papel_referencia ? "· " + prov.papel_referencia : "")} e DY</h2><div class="grafico" id="gd-acao"></div>
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
      <div class="painel"><h2>Cotação semanal ${esc(prov && prov.papel_referencia ? "· " + prov.papel_referencia : "")}</h2><div class="grafico" id="gd-cot"></div>
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
async function paginaMacro() {
  const macro = await dados("dados/macro.json");
  const S = macro.series, F = macro.focus;
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Macro</h1><div class="sub">Banco Central (SGS) e boletim Focus · atualizado em ${dataBR(macro.gerado_em)} · botões = janela inicial; use a roda do mouse ou a barra para ver mais</div></div>
      <div class="seletor" id="janela">${[[1, "1A"], [5, "5A"], [10, "10A"], [99, "Máx"]].map(([a, r]) => `<button data-a="${a}" class="${a === JANELA_MACRO ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
    <div class="grade-cartoes">
      ${cartao("IPCA mensal", pctPronto(ultimo(S.ipca).valor), ultimo(S.ipca).data?.slice(0, 7))}
      ${cartao("IPCA 12m", pctPronto(ultimo(S.ipca_12m).valor), "")}
      ${cartao("IGP-M 12m", pctPronto(ultimo(S.igpm_12m).valor), "")}
      ${cartao("Selic meta", pctPronto(ultimo(S.selic_meta).valor), "")}
      ${cartao("Dólar", `R$ ${num(ultimo(S.usd).valor, 4)}`, dataBR(ultimo(S.usd).data))}
      ${cartao("PIB (tri, dessaz.)", pctPronto(ultimo(S.pib_tri).valor), ultimo(S.pib_tri).data?.slice(0, 7))}
    </div>
    <div class="grade" id="graficos-macro"></div>
    <div class="secao"><h2>Expectativas — boletim Focus (mediana)</h2><div class="grade" id="graficos-focus"></div></div>`;
  document.getElementById("janela").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    JANELA_MACRO = Number(b.dataset.a);
    document.querySelectorAll("#janela button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharMacro(S, F);
  });
  desenharMacro(S, F);
}

function desenharMacro(S, F) {
  graficos.splice(0).forEach((g) => g.dispose());
  // Histórico completo em todos os gráficos; os botões só escolhem a janela inicial (dá para dar zoom para trás)
  const inicio = (anos) => { if (anos >= 99) return null; const d = new Date(); d.setFullYear(d.getFullYear() - anos); return d.toISOString().slice(0, 10); };
  const corte = inicio(JANELA_MACRO);
  const P = (s) => (s ? s.datas.map((d, i) => [d, s.valores[i]]) : []);
  const defs = [
    ["IPCA", { series: [{ nome: "Mensal", valores: P(S.ipca), cor: COR.azul }, { nome: "12 meses", valores: P(S.ipca_12m), tipo: "line", eixo: "dir", cor: COR.vermelho }], eixoEsq: "pctPronto", eixoDir: "pctPronto" }],
    ["IGP-M", { series: [{ nome: "Mensal", valores: P(S.igpm), cor: COR.azul }, { nome: "12 meses", valores: P(S.igpm_12m), tipo: "line", eixo: "dir", cor: COR.vermelho }], eixoEsq: "pctPronto", eixoDir: "pctPronto" }],
    ["Selic meta e CDI", { series: [{ nome: "Selic meta", valores: P(S.selic_meta), tipo: "line", cor: COR.ambar }, { nome: "CDI", valores: P(S.cdi), tipo: "line", cor: COR.ciano }], eixoEsq: "pctPronto", degrau: true }],
    ["Juro real ex-post (Selic ÷ IPCA 12m)", { series: [{ nome: "Juro real", valores: P(S.juro_real), tipo: "line", cor: COR.verde }], eixoEsq: "pctPronto" }],
    ["Câmbio PTAX", { series: [{ nome: "Dólar", valores: P(S.usd), tipo: "line", cor: COR.verde }, { nome: "Euro", valores: P(S.eur), tipo: "line", cor: COR.roxo }], eixoEsq: "preco" }],
    ["PIB", { series: [{ nome: "Trimestral (dessaz., tri/tri)", valores: P(S.pib_tri), cor: COR.azul }, { nome: "Acumulado em 12 meses", valores: P(S.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto" }],
    ["IBC-Br (prévia mensal do PIB)", { series: [{ nome: "Mensal (dessaz., m/m)", valores: P(S.ibcbr_mensal), cor: COR.azul }, { nome: "Acumulado em 12 meses", valores: P(S.ibcbr_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto", inicio: inicio(Math.min(JANELA_MACRO, 3)) }],
  ];
  const area = document.getElementById("graficos-macro");
  area.innerHTML = defs.map((d, i) => `<div class="painel"><h2>${d[0]}</h2><div class="grafico" id="gm-${i}"></div></div>`).join("");
  defs.forEach((d, i) => {
    const { inicio: ini, ...opcoes } = d[1];
    grafico(document.getElementById(`gm-${i}`), { xTempo: true, inicioTempo: (ini !== undefined ? ini : corte) || "1990-01-01", deslizante: true, ...opcoes });
  });

  const nomes = { ipca: "IPCA (%)", selic: "Selic fim de ano (% a.a.)", cambio: "Câmbio fim de ano (R$/US$)", pib: "PIB (%)" };
  const fa = document.getElementById("graficos-focus");
  fa.innerHTML = Object.keys(nomes).map((k) => `<div class="painel"><h2>${nomes[k]}</h2><div class="grafico" id="gf-${k}"></div></div>`).join("");
  Object.keys(nomes).forEach((k) => {
    const anos = Object.keys(F[k] || {}).sort();
    grafico(document.getElementById(`gf-${k}`), { xTempo: true, eixoEsq: k === "cambio" ? "preco" : "pctPronto",
      series: anos.map((a, i) => ({ nome: a, valores: F[k][a].datas.map((d, j) => [d, F[k][a].valores[j]]), tipo: "line", cor: PALETA_DATAS[i % PALETA_DATAS.length] })) });
  });
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
async function paginaJuros() {
  const [di, tes] = await Promise.all([dados("dados/curva_di.json").catch(() => null), dados("dados/tesouro.json")]);
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Juros</h1><div class="sub">Curvas DI (B3) e Tesouro Direto · taxas em % a.a.</div></div></div>
    <div class="grade">
      <div class="painel"><h2>Curva DI x Pré (B3)</h2><div class="grafico alto" id="gj-di"></div></div>
      <div class="painel"><h2>Curva DI x IPCA, juro real (B3) · a partir de 3 meses</h2><div class="grafico alto" id="gj-dic"></div></div>
      <div class="painel"><h2>Tesouro prefixado</h2><div class="grafico alto" id="gj-pre"></div></div>
      <div class="painel"><h2>Tesouro IPCA+ (juro real)</h2><div class="grafico alto" id="gj-ipca"></div></div>
      <div class="painel"><h2>Inflação implícita (prefixado × IPCA+)</h2><div class="grafico alto" id="gj-impl"></div></div>
      <div class="painel"><h2>Taxas DI por prazo (B3)</h2><div class="rolagem" id="tab-vertices"></div>
        <div class="nota">Interpolação linear da curva DI nos prazos (anos de 252 dias úteis). DI x IPCA = juro real.</div></div>
      <div class="painel largo"><h2>Títulos à venda — Tesouro Direto (${dataBR(tes.data_base)})</h2><div class="grade" id="tab-tit">
        ${GRUPOS_TESOURO.filter(([tipo]) => tes.titulos.some((t) => t.tipo === tipo)).map(([tipo, nome]) => `
          <div><div class="sub" style="margin:4px 0 6px;color:var(--ambar)">${esc(nome)}</div><table class="tabela">
            <tr><th>Vencimento</th><th>Taxa compra</th><th>Var. 1 sem.</th><th>PU compra</th></tr>
            ${tes.titulos.filter((t) => t.tipo === tipo).map((t) => { const v = variacaoSemana(tes, t);
              return `<tr class="clicavel" data-id="${esc(t.id)}"><td>${dataBR(t.vencimento)}</td><td>${num(t.taxa_compra, 2)}%</td>
                <td class="${v == null ? "" : v > 0 ? "neg" : "pos"}">${v == null ? "—" : `${v > 0 ? "+" : ""}${num(v * 100, 0)} bp`}</td><td>R$ ${num(t.pu_compra, 2)}</td></tr>`; }).join("")}
          </table></div>`).join("")}
      </div><div class="nota">Clique num título para ver o histórico de taxa e preço. Variação em pontos-base (bp) contra a curva de 1 semana atrás (quando o título está nela).</div></div>
      <div class="painel largo" id="painel-titulo" style="display:none"><h2 id="titulo-hist"></h2><div class="grafico alto" id="gj-hist"></div></div>
    </div>
    <div class="nota secao">A curva DI vem do arquivo "Taxas de Mercado para Swaps" da B3 (fim de dia). As curvas do Tesouro usam a taxa de compra
      do Tesouro Direto: título sem cupom e, nos prazos onde ele não existe, o título com juros semestrais. A inflação implícita interpola a curva
      prefixada nos vencimentos do IPCA+, sem extrapolar.</div>`;

  const rotulos = Object.keys(tes.curvas);
  const porData = (fonte, campo, maxAnos, minAnos = 0) => rotulos
    .filter((r) => fonte[r] && fonte[r][campo] && fonte[r][campo].length)
    .map((r, i) => ({ nome: r, valores: fonte[r][campo].filter((p) => p.anos <= maxAnos && p.anos >= minAnos).map((p) => [p.anos, p.taxa]),
      tipo: "line", cor: PALETA_DATAS[i], tracejado: i > 0 }));
  const datas = (fonte) => rotulos.filter((r) => fonte[r]).map((r) => `${r}: ${dataBR(fonte[r].data)}`).join(" · ");
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

/* ============ Downloads ============ */
async function paginaDownloads() {
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Downloads</h1><div class="sub">Excel padrão de cada empresa: Cadastro, Demonstrações, Indicadores (LTM) e Dividendos, com histórico completo desde 2011</div></div>
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

/* ============ início ============ */
iniciarBusca().then(rotear);
