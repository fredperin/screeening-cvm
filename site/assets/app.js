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

const ARQUIVOS_PAGINA = new Set();  // arquivos de dados usados pela tela aberta (para o ⓘ dizer de onde vem cada gráfico)
async function dados(caminho) {
  if (caminho !== "dados/atualizacoes.json") ARQUIVOS_PAGINA.add(caminho);
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

let MOEDA = "R$";  // as páginas das empresas do Mundo trocam para US$ (volta a R$ a cada navegação)
function reais(v, casas = 1) {
  if (v == null || !isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return `${MOEDA} ${num(v / 1e12, casas)} tri`;
  if (a >= 1e9) return `${MOEDA} ${num(v / 1e9, casas)} bi`;
  if (a >= 1e6) return `${MOEDA} ${num(v / 1e6, casas)} mi`;
  if (a >= 1e3) return `${MOEDA} ${num(v / 1e3, casas)} mil`;
  return `${MOEDA} ${num(v, 2)}`;
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
    reais: (v) => (v === 0 ? "0" : reais(v, 0).replace(`${MOEDA} `, "")),
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
  janela = 24, inicioTempo = null, deslizante = false, limitesEsq = null }) {
  const g = echarts.init(el, null, { renderer: "canvas" });
  graficos.push(g);
  const eixosY = [{ ...eixoValor(eixoEsq, "left"), ...(limitesEsq ? { min: limitesEsq[0], max: limitesEsq[1], scale: false } : {}) }];
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
        // do maior para o menor valor; sem valor no ponto, no fim
        const valorDe = (i) => { const v = Array.isArray(i.value) ? i.value[1] : i.value; return v == null || !isFinite(v) ? -Infinity : Number(v); };
        itens = [...itens].sort((a, b) => valorDe(b) - valorDe(a));
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
      ...(s.area ? { areaStyle: { color: s.cor, opacity: 0.85 }, lineStyle: { width: 0 } } : {}),
    })),
  });
  if (series.length >= MUITAS_SERIES) botaoTodasSeries(el);
  return g;
}

// Gráficos com muitas séries: botão ☑ para desmarcar todas (e escolher na legenda) ou marcar todas de novo
const MUITAS_SERIES = 6;
function botaoTodasSeries(el) {
  const painel = el.closest(".painel"), titulo = painel && painel.querySelector("h2");
  if (!titulo || painel.querySelector('[data-acao="todas"]')) return;
  let caixa = titulo.querySelector(".ferramentas");
  if (!caixa) { titulo.insertAdjacentHTML("beforeend", '<span class="ferramentas"></span>'); caixa = titulo.querySelector(".ferramentas"); }
  caixa.insertAdjacentHTML("afterbegin", '<button data-acao="todas" title="Desmarcar todas as séries (depois escolha na legenda) ou marcar todas de novo">☑</button>');
}
function alternarTodasSeries(painel) {
  painel.querySelectorAll(".grafico").forEach((el) => {
    const g = echarts.getInstanceByDom(el); if (!g) return;
    const op = g.getOption(), marcadas = (op.legend && op.legend[0] && op.legend[0].selected) || {};
    const todas = op.series.every((s) => marcadas[s.name] !== false);
    g.dispatchAction({ type: todas ? "legendInverseSelect" : "legendAllSelect" });
  });
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
    const caixa = titulo.querySelector(".ferramentas");
    if (caixa) caixa.insertAdjacentHTML("beforeend", botoes.join(""));
    else titulo.insertAdjacentHTML("beforeend", `<span class="ferramentas">${botoes.join("")}</span>`);
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

// Data mais recente com valor nos gráficos do painel (eixo de tempo); `mensal`/`trimestral` pelo espaçamento das datas
function dadoMaisRecente(painel) {
  let max = null;
  const datas = new Set(), pontos = [];
  painel.querySelectorAll(".grafico").forEach((el) => {
    const g = echarts.getInstanceByDom(el);
    if (!g) return;
    const op = g.getOption();
    const eixo = op.xAxis && op.xAxis[0];
    // eixo de tempo ([data, valor]) ou de categorias que são datas (rótulos AAAA-MM-DD)
    const rotulosData = eixo && eixo.type === "category" && (eixo.data || []).length && /^\d{4}-\d{2}-\d{2}/.test(String(eixo.data[eixo.data.length - 1]));
    if (!eixo || (eixo.type !== "time" && !rotulosData)) return;
    op.series.forEach((s) => (s.data || []).forEach((p0, i) => {
      const p = rotulosData ? [eixo.data[i], p0 && typeof p0 === "object" && !Array.isArray(p0) ? p0.value : p0] : p0;
      if (!Array.isArray(p) || p[1] == null || p[0] == null) return;
      const d = typeof p[0] === "number" ? new Date(p[0]).toISOString().slice(0, 10) : String(p[0]).slice(0, 10);
      datas.add(d);
      pontos.push([d, p[1]]);
      if (!max || d > max) max = d;
    }));
  });
  if (!max) return null;
  const valores = pontos.filter((p) => p[0] === max).map((p) => p[1]);
  const todas = [...datas];
  const dia1 = todas.length > 2 && todas.every((d) => d.slice(8, 10) === "01");
  const tri = dia1 && todas.every((d) => ["01", "04", "07", "10"].includes(d.slice(5, 7)));
  const mes = Number(max.slice(5, 7));
  const rotulo = tri ? `${Math.floor((mes - 1) / 3) + 1}º tri/${max.slice(0, 4)}` : dia1 ? `${MESES[mes - 1]}/${max.slice(0, 4)}` : dataBR(max);
  return { data: max, rotulo, valores };
}

// Se o arquivo tem uma série que termina na data `d` com um dos `valores` do gráfico (para saber de qual arquivo
// veio o gráfico quando dois arquivos da tela terminam na mesma data)
function contemSerie(obj, d, valores, nivel = 0) {
  if (!obj || typeof obj !== "object" || nivel > 6) return false;
  if (!Array.isArray(obj)) {
    const eixo = ["datas", "periodos"].find((e) => Array.isArray(obj[e]) && obj[e].length);
    if (eixo && String(obj[eixo][obj[eixo].length - 1]).slice(0, 10) === d) {
      const n = obj[eixo].length;
      const listas = Object.values(obj).flatMap((v) => (Array.isArray(v) ? [v] : v && typeof v === "object" ? Object.values(v).filter(Array.isArray) : []));
      // o gráfico pode mostrar o valor em outra escala (ex.: US$ milhões do arquivo × 1 milhão no gráfico)
      const igual = (a, x) => [1, 1e3, 1e6, 1e9, 100, 0.01].some((k) => Math.abs(a * k - x) <= 1e-6 * Math.max(1, Math.abs(x)));
      if (listas.some((l) => l.length === n && typeof l[n - 1] === "number" && valores.some((x) => igual(l[n - 1], x)))) return true;
    }
  }
  return Object.values(obj).some((v) => v && typeof v === "object" && contemSerie(v, d, valores, nivel + 1));
}

const ARQUIVO_POR_PREFIXO = [["externo_", "setor_externo.json"], ["credito_", "credito.json"], ["fiscal_", "macro.json"]];

// Gráficos sem eixo de datas (curvas de juros por prazo): arquivo de origem e data de referência da curva
const FONTE_CURVAS = { curva_di: "curva_di.json", di_ipca: "curva_di.json", tesouro_ipca: "tesouro.json", tesouro_pre: "tesouro.json",
  inflacao_implicita: "tesouro.json", ust_curva: "offshore.json", ust_real: "offshore.json", curva_euro: "offshore.json",
  fiscal_dpf_vencimentos: "fiscal.json" };
function referenciaDaCurva(j, chave) {
  if (!j) return null;
  if (chave === "fiscal_dpf_vencimentos") return (j.vencimentos_dpf || {}).data || null;
  if (j.data_base) return j.data_base;
  if (j.curvas && j.curvas.hoje) return j.curvas.hoje.data;
  const T = j.treasuries || {}, C = (j.bce || {}).curva || {};
  if (chave.startsWith("ust")) return ((T[chave === "ust_real" ? "real" : "nominal"] || {}).hoje || {}).data || null;
  return (C.hoje || {}).data || C.data || null;
}

// Data e hora no horário de Brasília (o pipeline grava em UTC ou com fuso; só a data quando não há hora)
function dataHoraCompleta(iso) {
  if (!iso) return "—";
  if (iso.length <= 10) return dataBR(iso);
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit" }).format(d).replace(",", " às");
}
// Etapa da atualização que gera cada arquivo (status.json registra se ela consultou a fonte com sucesso)
const etapaDoArquivo = (a) => (a.startsWith("tesouro") ? "tesouro" : a.startsWith("proventos/") ? "mercado"
  : a.startsWith("mundo_empresas") ? "empresas_mundo" : a.replace(/\.json$/, ""));

// Bloco "Atualização" do ⓘ: dado mais recente do gráfico, quando chegou ao site e quando a fonte foi verificada.
// Fora: demonstrativos e formulários (empresas e bancos), que mudam poucas vezes por ano.
async function blocoAtualizacao(painel) {
  if (!painel) return "";
  const naEmpresa = /^#\/(on|off)\/(empresa|banco)\//.test(location.hash);
  if (naEmpresa && !/cotac|provento/.test(painel.dataset.info || "")) return "";
  let ult = dadoMaisRecente(painel), arq = null, achado = null;
  const reg = await dados("dados/atualizacoes.json").catch(() => null);
  if (!ult) {
    const fonte = FONTE_CURVAS[painel.dataset.info];
    if (!fonte) return "";
    const ref = referenciaDaCurva(await dados(`dados/${fonte}`).catch(() => null), painel.dataset.info);
    ult = { data: ref, rotulo: ref ? dataBR(ref) : "—" };
    arq = fonte;
  } else {
    const usados = [...ARQUIVOS_PAGINA].map((c) => c.replace(/^dados\//, "")).filter((c) => reg && reg.chegadas[c]);
    const candidatos = usados.filter((a) => ult.data in reg.chegadas[a]);
    for (const a of candidatos) {
      if (candidatos.length === 1 || contemSerie(await dados(`dados/${a}`).catch(() => null), ult.data, ult.valores)) { achado = a; break; }
    }
    if (!achado && candidatos.length) {
      // gráfico com valores calculados (somas, acumulados): o arquivo sai do nome do explicativo; na dúvida, sem "chegou"
      const pref = (ARQUIVO_POR_PREFIXO.find(([p]) => (painel.dataset.info || "").startsWith(p)) || [])[1];
      achado = candidatos.includes(pref) ? pref : null;
    }
    arq = achado || (usados.length === 1 ? usados[0] : null);
  }
  let verificacao = "";
  if (arq) {
    const st = await dados("dados/status.json").catch(() => null);
    const etapa = etapaDoArquivo(arq);
    const info = st && st.etapas ? st.etapas[etapa] : null;
    const intradia = st && st.etapas ? st.etapas[`${etapa}_intradia`] : null;  // Tesouro e notícias: 3x por dia útil
    let quando = info && info.ok ? st.atualizado_em : null;
    if (intradia && intradia.ok && (!quando || new Date(intradia.em) > new Date(quando))) quando = intradia.em;
    if (quando) verificacao = `<li>Última verificação na fonte: <b>${dataHoraCompleta(quando)}</b></li>`;
    else if (info) verificacao = `<li>A fonte não respondeu na última atualização (${dataHoraCompleta(st.atualizado_em)}): o gráfico mostra o último dado recebido</li>`;
  }
  const chegou = achado && reg ? reg.chegadas[achado][ult.data] : undefined;
  const linhas = [`<li>Dado mais recente: <b>${ult.rotulo}</b></li>`];
  if (chegou !== undefined) linhas.push(`<li>Chegou ao site: <b>${chegou ? dataHoraCompleta(chegou) : `antes de ${dataBR(reg.desde.slice(0, 10))}`}</b></li>`);
  if (verificacao) linhas.push(verificacao);
  return `<h3>Atualização</h3><ul>${linhas.join("")}</ul>`;
}

async function abrirExplicativo(chave, painel = null) {
  const e = (window.EXPLICATIVOS || {})[chave];
  if (!e) return;
  const m = document.getElementById("modal");
  m.innerHTML = `<div class="modal-caixa" role="dialog" aria-modal="true" aria-label="${esc(e.titulo)}">
    <div class="modal-topo"><h2>${esc(e.titulo)}</h2><button data-fechar title="Fechar (Esc)">✕</button></div>
    <div class="resumo">${e.html}<div class="atualizacao"></div></div></div>`;
  m.hidden = false;
  const alvo = m.querySelector(".atualizacao");
  try { alvo.innerHTML = await blocoAtualizacao(painel); } catch (_) { /* sem o bloco, o explicativo continua */ }
}
function fecharModal() { document.getElementById("modal").hidden = true; }

app.addEventListener("click", (ev) => {
  const b = ev.target.closest(".ferramentas button");
  if (!b) return;
  ev.stopPropagation();
  const painel = b.closest(".painel");
  if (b.dataset.acao === "info") abrirExplicativo(painel.dataset.info, painel);
  else if (b.dataset.acao === "csv") baixarCsv(painel);
  else if (b.dataset.acao === "tela") alternarTelaCheia(painel);
  else if (b.dataset.acao === "todas") alternarTodasSeries(painel);
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
// Brasil e Mundo abrem em Notícias e agenda (a antiga página Início repetia o que vem nas seções); "noticias" fica como endereço
const SECOES = [["", "Notícias e agenda"], ["macro", "Macro"], ["juros", "Juros"], ["empresas", "Empresas"], ["downloads", "Downloads"]];
const ROTAS = {
  on: { banco: (p) => paginaBanco(p), "": () => paginaNoticias("on"), noticias: (p) => (p === "eleicoes" ? paginaEleicoes() : paginaNoticias("on")), macro: paginaMacro, juros: paginaJuros, empresas: paginaEmpresas, empresa: paginaEmpresa, downloads: paginaDownloads },
  off: Object.fromEntries(SECOES.map(([k]) => [k, (p) => paginaOffshore(k, p)])),
};
// Consolidado abre em Notícias e agenda; "noticias" fica como endereço antigo
// Consolidado: Notícias e agenda + Gráficos (PIB, inflação, juros e desemprego); endereços antigos abrem os Gráficos
const SECOES_CONS = [["", "Notícias e agenda"], ["graficos", "Gráficos"]];
ROTAS.cons = { "": () => paginaNoticias("cons"), noticias: () => paginaNoticias("cons"), graficos: paginaConsolidado,
  atividade: paginaConsolidado, inflacao: paginaConsolidado, juros: paginaConsolidado };
ROTAS.off.noticias = () => paginaNoticias("off");
ROTAS.off[""] = () => paginaNoticias("off");
ROTAS.off.empresas = () => paginaEmpresasMundo();
ROTAS.off.empresa = (p) => paginaEmpresaMundo(p);
const ROTAS_ANTIGAS = { agenda: "noticias" };  // endereços de antes da divisão Onshore/Offshore

function desenharNav(lado, secao) {
  document.querySelectorAll("#lados a").forEach((a) => a.classList.toggle("ativo", a.dataset.lado === lado));
  document.getElementById("nav").innerHTML = (lado === "cons" ? SECOES_CONS : SECOES).map(([k, nome]) =>
    `<a href="#/${lado || "on"}${k ? `/${k}` : ""}" class="${lado && k === (secao === "noticias" ? "" : secao) ? "ativo" : ""}">${nome}</a>`).join("");
  document.body.dataset.lado = lado || "";
}

async function rotear() {
  MOEDA = "R$";
  ARQUIVOS_PAGINA.clear();
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
    <div class="cabecalho"><div><h1>Brasil · painel</h1><div class="sub">Agenda, indicadores e notícias do Brasil</div></div></div>
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
// Abas: informações (calendário, divulgações, proventos), notícias e fatos relevantes, tabela das empresas e instituições financeiras
const ABAS_EMPRESAS = [["noticias", "Informações"], ["fatos", "Notícias e fatos relevantes"], ["tabela", "Empresas não financeiras"], ["financeiras", "Instituições financeiras"]];

async function paginaEmpresas(aba) {
  if (!ABAS_EMPRESAS.some(([k]) => k === aba)) aba = "noticias";
  const [mercado, fatos, noticias, cal] = await Promise.all([dados("dados/mercado.json").catch(() => ({ empresas: [] })),
    dados("dados/eventos_recentes.json").catch(() => null),
    dados("dados/noticias_empresas.json").catch(() => dados("dados/noticias.json").catch(() => null)),
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
  if (aba === "fatos") {
    // fatos relevantes na 1ª linha e notícias na 2ª, cada um na largura toda
    app.innerHTML = `${cab}${abas}
    <div class="grade grade-empilhada">
      <div class="painel"><h2>Fatos relevantes recentes</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Data</th><th>Papel</th><th style="text-align:left">Assunto</th></tr>
        ${fatos && fatos.eventos.length ? fatos.eventos.slice(0, 200).map((e) => `<tr><td>${dataBR(e.data)}</td>
          <td><a href="#/on/empresa/${esc(e.id)}">${esc(e.id)}</a></td>
          <td style="white-space:normal;text-align:left">${e.link ? `<a href="${esc(e.link)}" target="_blank" rel="noopener">${esc(e.assunto)}</a>` : esc(e.assunto)}</td></tr>`).join("")
          : `<tr><td colspan="3" class="sub">Sem fatos relevantes recentes.</td></tr>`}
      </table></div><div class="nota">Fonte: CVM (documentos IPE), com link para o documento oficial.</div></div>
      <div class="painel"><h2>Notícias das empresas</h2>${listaNoticias(citadas, 400)}
        <div class="nota">Manchetes de jornais e fontes oficiais que citam o ticker ou o nome de pregão de uma empresa da lista (etiqueta = empresa),
          da mais recente para a mais antiga, guardadas por até ${(noticias && noticias.dias) || 7} dias. Mesmas fontes da seção Notícias e agenda.</div></div>
    </div>`;
    return;
  }
  if (aba === "noticias") {
    app.innerHTML = `${cab}${abas}
    <div class="grade">
      <div class="painel largo" data-info="calendario_resultados"><h2>Calendário de resultados — próximo ITR/DFP de cada empresa</h2>${tabelaCalendario(cal)}
        <div class="nota">"est." = estimativa pelo histórico: a data em que a empresa entregou o mesmo trimestre no ano anterior, limitada ao prazo legal.
          Não é a data oficial anunciada pela empresa. Fonte: CVM (datas de entrega de ITR/DFP).</div></div>
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
    <div class="cabecalho"><h2 style="margin:0">Empresas não financeiras</h2><input class="filtro" id="filtro" placeholder="filtrar por nome, ticker ou setor"></div>
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
const ABAS_EMPRESA = [["negocio", "Negócio"], ["eventos", "Eventos e notícias"], ["cotacao", "Cotação"], ["resultados", "Resultados"], ["graficos", "Gráficos"], ["dividendos", "Dividendos"]];
let JANELA_COTACAO = 5;
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
        <div class="sub">${esc(emp.setor || "")} · CNPJ ${esc(emp.cnpj)}${m.segmento ? ` · ${esc(m.segmento)}` : ""} · último período ${dataBR(emp.trimestral.periodos.slice(-1)[0])}
          ${seloResultado(proxResultado)}</div></div>
      <a class="botao" href="downloads/${encodeURIComponent(id)}.xlsx" download>Baixar Excel</a>
    </div>
    <div class="grade-cartoes">
      ${cartao(`Preço ${esc(ref || "")}`, cot ? `R$ ${num(cot.preco, 2)}` : "—", cot ? `<span class="${classeSinal(cot.variacao_dia)}">${num(cot.variacao_dia, 2)}%</span> · ${dataBR(cot.data)}` : "")}
      ${cartao("Market cap", reais(mc), "ações ON/PN B3 × preço")}
      ${cartao("EV", reais(ev), "market cap + dív. líquida")}
      ${cartao("P/L", vezes(mc && pos(L("lucro_liquido")) ? mc / L("lucro_liquido") : null), "LTM")}
      ${cartao("P/VP", vezes(mc && pos(L("pl")) ? mc / L("pl") : null), "")}
      ${cartao("EV/EBITDA", vezes(ev && pos(L("ebitda")) ? ev / L("ebitda") : null), "LTM")}
      ${cartao("FCF yield", pct(mc && L("fcf") != null ? L("fcf") / mc : null), "FCF LTM ÷ market cap")}
      ${cartao("DY 12m", pct(m.dy_12m, 2), "proventos B3 (data-com 12m) ÷ preço atual")}
      ${cartao("ROE / ROIC", `${pct(L("roe"))} / ${pct(L("roic"))}`, "LTM")}
    </div>
    <div class="abas" id="abas-empresa">${ABAS_EMPRESA.map(([k, r]) => `<button data-k="${k}" class="${k === ABA_EMPRESA ? "ativo" : ""}">${r}</button>`).join("")}</div>
    <div id="aba-empresa"></div>`;

  const nt = emp.notas || {};
  const ABAS = {
    graficos: () => {
      document.getElementById("aba-empresa").innerHTML = `
        <div class="cabecalho"><h2 style="margin:0">Gráficos</h2>
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
    resultados: () => {
      // Espaço do painel de indicadores (em montagem) em cima; DRE e balanço resumidos com análise vertical embaixo
      document.getElementById("aba-empresa").innerHTML = `<div class="grade grade-empilhada">
        <div class="painel" id="painel-indicadores"><h2>Painel de indicadores</h2>
          <p class="sub">Espaço reservado para o painel de indicadores (em montagem).</p>
          <details><summary class="sub" style="cursor:pointer">Tabela de indicadores atual (anos fechados e LTM)</summary><div class="rolagem" id="tab-ind"></div></details></div>
        <div class="painel" data-info="dre_resumida"><h2>DRE · R$ milhões e análise vertical (% da receita)</h2><div class="rolagem" id="tab-dre"></div></div>
        <div class="painel" data-info="balanco_resumido"><h2>Balanço patrimonial · R$ milhões e análise vertical (% do ativo total)</h2><div class="rolagem" id="tab-bp"></div></div></div>`;
      desenharIndicadores(emp);
      desenharDreBalanco(emp);
    },
    cotacao: () => {
      document.getElementById("aba-empresa").innerHTML = `<div id="cotacao-empresa"></div>`;
      desenharCotacao(prov, m);
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
      <div class="painel largo"><h2>Proventos anunciados (B3) — últimos 3 anos</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Tipo</th><th>Classe</th><th>Data-com</th><th>Pagamento</th><th>R$/ação</th><th>Preço data-com</th><th>Aprovado</th></tr>
        ${b3.length ? b3.map((p) => `<tr><td>${esc(p.tipo)}</td><td>${esc(p.classe)}</td><td>${dataBR(p.data_com)}</td><td>${dataBR(p.pagamento)}</td><td>${num(p.valor, 6)}</td><td>${p.preco_data_com ? num(p.preco_data_com, 2) : "—"}</td><td class="sub">${dataBR(p.aprovado)}</td></tr>`).join("")
          : `<tr><td colspan="7" class="sub">A B3 não informou proventos.</td></tr>`}
      </table></div><div class="nota">Proventos 12m (${esc(prov && prov.classe_referencia || "classe de referência")}): R$ ${num(m.proventos_12m_por_acao, 4)} por ação, data-com nos últimos 12 meses.
        A data de pagamento só é informada pela B3 para cerca dos últimos 12 meses.</div></div>`;
  }
  grafico(document.getElementById("gd-dfc"), { rotulos: rot, eixoDir: "pct", series: [
    { nome: "Dividendos + JCP pagos", valores: A.div_pagos, cor: COR.verde },
    { nome: "Payout", valores: A.payout, tipo: "line", eixo: "dir", cor: COR.ambar }] });
  const dyAno = (prov && prov.dy_ano) || {};
  grafico(document.getElementById("gd-acao"), { rotulos: anos, eixoEsq: "preco", eixoDir: "pct", janela: 12, series: [
    { nome: "R$ por ação", valores: anos.map((a) => porAno[a]), cor: COR.verde },
    { nome: "DY", valores: anos.map((a) => { if (dyAno[a] != null) return dyAno[a]; const p = precoMedio(a); return p ? porAno[a] / p : null; }), tipo: "line", eixo: "dir", cor: COR.ambar }] });
}

// Selo ao lado de "último período": resultados em dia ou atrasados (calendário de resultados da CVM)
function seloResultado(p) {
  if (!p) return "";
  const periodo = p.proximo_periodo ? rotuloTrimestre(p.proximo_periodo) : "";
  if (p.atrasado) return `<span class="selo-resultado atraso" title="${esc(p.documento)} ${periodo}: prazo legal ${dataBR(p.prazo_legal)} já passou e a CVM ainda não recebeu">
    Resultado atrasado · ${esc(p.documento)} ${periodo} (prazo ${dataBR(p.prazo_legal)})</span>`;
  const quando = p.data_estimada ? `previsto ${dataBR(p.data_estimada)}` : `até ${dataBR(p.prazo_legal)}`;
  return `<span class="selo-resultado ok" title="Próxima divulgação: ${esc(p.documento)} ${periodo} — ${p.data_estimada ? "data estimada pela divulgação do ano anterior" : "prazo legal"}; prazo legal ${dataBR(p.prazo_legal)}">
    Em dia · próximo ${esc(p.documento)} ${periodo} ${quando}</span>`;
}
const rotuloTrimestre = (iso) => `${Math.ceil(Number(iso.slice(5, 7)) / 3)}T${iso.slice(2, 4)}`;

// Aba Cotação: cotação semanal (Yahoo, não oficial) com janela escolhida e variações no período
function desenharCotacao(prov, m) {
  const area = document.getElementById("cotacao-empresa");
  const cot = prov && prov.cotacao_semanal && prov.cotacao_semanal.datas && prov.cotacao_semanal.datas.length ? prov.cotacao_semanal : null;
  const ref = prov && prov.papel_referencia;
  const atual = ref && m.cotacoes ? m.cotacoes[ref] : null;
  if (!cot) { area.innerHTML = `<div class="painel"><h2>Cotação</h2><p class="sub">Cotação histórica indisponível.</p></div>`; return; }
  const pares = cot.datas.map((d, i) => [d, cot.fechamento[i]]).filter((p) => p[1] != null);
  const ultimo = atual && atual.preco ? { d: atual.data, v: atual.preco } : { d: pares[pares.length - 1][0], v: pares[pares.length - 1][1] };
  const antes = (dias) => { const lim = new Date(`${ultimo.d}T12:00:00`); lim.setDate(lim.getDate() - dias); const iso = lim.toISOString().slice(0, 10);
    const p = [...pares].reverse().find(([d]) => d <= iso); return p ? p[1] : null; };
  const inicioAno = (() => { const p = [...pares].reverse().find(([d]) => d < `${ultimo.d.slice(0, 4)}-01-01`); return p ? p[1] : null; })();
  const varia = (base) => (base ? ultimo.v / base - 1 : null);
  const ult52 = pares.filter(([d]) => d >= new Date(new Date(`${ultimo.d}T12:00:00`).getTime() - 365 * 864e5).toISOString().slice(0, 10)).map((p) => p[1]);
  const vcart = (rot, v, sub) => cartao(rot, v == null ? "—" : `<span class="${classeSinal(v)}">${num(v * 100, 1)}%</span>`, sub);
  area.innerHTML = `
    <div class="grade-cartoes">
      ${cartao(`Preço ${esc(ref || "")}`, `R$ ${num(ultimo.v, 2)}`, atual ? `B3 · ${dataBR(atual.data)}` : `fechamento semanal · ${dataBR(ultimo.d)}`)}
      ${vcart("1 mês", varia(antes(30)), "variação")}
      ${vcart("No ano", varia(inicioAno), `desde o fechamento de ${Number(ultimo.d.slice(0, 4)) - 1}`)}
      ${vcart("12 meses", varia(antes(365)), "variação")}
      ${vcart("5 anos", varia(antes(5 * 365)), "variação")}
      ${cartao("Mín. / máx. 52 semanas", ult52.length ? `R$ ${num(Math.min(...ult52), 2)} / ${num(Math.max(...ult52), 2)}` : "—", "fechamentos semanais")}
    </div>
    <div class="grade"><div class="painel largo" data-info="cotacao"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Cotação semanal${ref ? ` · ${esc(ref)}` : ""}</h2>
      <div class="seletor" id="janela-cot">${[[1, "1A"], [3, "3A"], [5, "5A"], [10, "10A"]].map(([a, r]) => `<button data-a="${a}" class="${a === JANELA_COTACAO ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
      <div class="grafico alto" id="gc-cotacao"></div>
      <div class="nota">Fechamento semanal dos últimos 10 anos, sem ajuste por proventos — fonte Yahoo Finance (não oficial). Preço atual e variação do dia: B3.
        Variações calculadas sobre os fechamentos semanais, sem somar proventos.</div></div></div>`;
  const desenhar = () => {
    limparGraficos();
    grafico(document.getElementById("gc-cotacao"), { xTempo: true, eixoEsq: "preco", inicioTempo: desde(JANELA_COTACAO), deslizante: true, series: [
      { nome: "Fechamento (R$)", valores: pares, tipo: "line", cor: COR.ambar }] });
  };
  document.getElementById("janela-cot").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    JANELA_COTACAO = Number(b.dataset.a);
    document.querySelectorAll("#janela-cot button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenhar();
  });
  desenhar();
}

// Aba Resultados: DRE e balanço com as contas do Excel (CVM), últimos 4 anos fechados + LTM, análise vertical ao lado.
// Enquanto a empresa não foi reprocessada com essas contas, mostra a versão resumida (desenharDreBalancoResumido).
function desenharDreBalanco(emp) {
  const dm = emp.demonstracoes;
  if (!dm || !dm.dre || !dm.dre.length) return desenharDreBalancoResumido(emp);
  const mesFim = emp.mes_fim_exercicio || 12;
  const cols = dm.colunas.map((c) => (c.ltm ? `LTM ${rotuloPeriodo(c.data, "trimestral")}` : rotuloPeriodo(c.data, "anual", mesFim)));
  const mi = (x) => (x == null ? "—" : num(x / 1e6, 0));
  const av = (x, b) => (x == null || !b ? "—" : `${num((x / b) * 100, 1)}%`);
  const nivel = (c) => c.split(".").length - 1;
  const estilo = (c, tot) => (c === tot || nivel(c) === 0 ? "total" : nivel(c) === 1 ? "subtotal" : "");
  const tabela = (linhas, base, extra = []) => `<table class="tabela tabela-av">
    <tr><th style="text-align:left">R$ milhões</th>${cols.map((t) => `<th>${t}</th><th class="sub">AV</th>`).join("")}</tr>
    ${[...linhas, ...extra].map((l) => `<tr class="${l.estilo != null ? l.estilo : estilo(l.c, "")}"><td style="text-align:left;padding-left:${6 + Math.max(0, nivel(l.c || "x") - 1) * 14}px">${esc(l.r)}</td>
      ${l.v.map((x, i) => `<td>${mi(x)}</td><td class="sub">${av(x, base[i])}</td>`).join("")}</tr>`).join("")}</table>`;
  const linha = (ls, c) => (ls.find((l) => l.c === c) || { v: [] }).v;
  // DRE simples: só as linhas principais (sem abrir despesas, sem D&A/EBITDA — a D&A está embutida em custos e despesas)
  const PRINCIPAIS = ["3.01", "3.02", "3.03", "3.04", "3.05", "3.06", "3.07", "3.08", "3.11"];
  const simples = PRINCIPAIS.map((c) => dm.dre.find((l) => l.c === c)).filter(Boolean)
    .map((l) => ({ ...l, estilo: ["3.01", "3.11"].includes(l.c) ? "total" : ["3.03", "3.05", "3.07"].includes(l.c) ? "subtotal" : "" }));
  const receita = linha(dm.dre, "3.01");
  document.getElementById("tab-dre").innerHTML = tabela(simples, receita) + `<div class="nota">Linhas principais da DRE da CVM (as mesmas do Excel).
    Anos fechados: número oficial da DFP; LTM: soma dos últimos 4 trimestres. AV em % da receita líquida.
    Custos e despesas incluem a depreciação e amortização (a CVM não a separa); EBIT = resultado antes do resultado financeiro e dos tributos.</div>`;
  const ativo = linha(dm.bp, "1");
  document.getElementById("tab-bp").innerHTML = tabela(dm.bp, ativo) + `<div class="nota">Mesmas contas da aba Demonstrações do Excel (padrão da CVM),
    posição no fim de cada exercício e, na coluna LTM, no último trimestre. AV em % do ativo total (igual ao passivo total). Contas zeradas em todas as datas ficam de fora.</div>`;
}

function desenharDreBalancoResumido(emp) {
  const anual = emp.anual, ltm = emp.ltm, mesFim = emp.mes_fim_exercicio || 12;
  const cols = anual.periodos.map((p, i) => ({ v: anual, i, titulo: rotuloPeriodo(p, "anual", mesFim) })).slice(-4);
  const nl = ltm.periodos.length - 1;
  if (nl >= 0 && ltm.periodos[nl] !== anual.periodos[anual.periodos.length - 1]) cols.push({ v: ltm, i: nl, titulo: `LTM ${rotuloPeriodo(ltm.periodos[nl], "trimestral")}`, ltm: true });
  const g = (c, k) => { const x = (c.v.series[k] || [])[c.i]; return x == null || !isFinite(x) ? null : x; };
  const soma = (...xs) => (xs.some((x) => x == null) ? null : xs.reduce((a, b) => a + b, 0));
  const mi = (x) => (x == null ? "—" : num(x / 1e6, 0));
  const av = (x, base) => (x == null || !base ? "—" : `${num((x / base) * 100, 1)}%`);
  const tabela = (linhas, base, rotuloBase) => `<table class="tabela tabela-av">
    <tr><th style="text-align:left">R$ milhões</th>${cols.map((c) => `<th>${c.titulo}</th><th class="sub">AV</th>`).join("")}</tr>
    ${linhas.map(([nome, f, estilo]) => `<tr class="${estilo || ""}"><td style="text-align:left">${nome}</td>${cols.map((c) => { const x = f(c); return `<td>${mi(x)}</td><td class="sub">${av(x, base(c))}</td>`; }).join("")}</tr>`).join("")}
  </table>`;
  if (!cols.length) { ["tab-dre", "tab-bp"].forEach((id) => (document.getElementById(id).innerHTML = `<p class="sub">Sem anos fechados nem LTM disponíveis.</p>`)); return; }

  const receita = (c) => g(c, "receita"), lb = (c) => g(c, "lucro_bruto"), ebit = (c) => g(c, "ebit");
  document.getElementById("tab-dre").innerHTML = tabela([
    ["Receita líquida", receita, "total"],
    ["(−) Custos", (c) => soma(lb(c), receita(c) == null ? null : -receita(c))],
    ["Lucro bruto", lb, "subtotal"],
    ["(−) Despesas operacionais", (c) => soma(ebit(c), lb(c) == null ? null : -lb(c))],
    ["EBIT", ebit, "subtotal"],
    ["(+/−) Resultado financeiro", (c) => g(c, "res_fin")],
    ["Lucro antes do IR (LAIR)", (c) => g(c, "lair"), "subtotal"],
    ["(−) IR e CSLL", (c) => g(c, "ir")],
    ["Lucro líquido", (c) => g(c, "lucro_liquido"), "total"],
  ], receita) + `<div class="nota">Anos fechados (DFP) e últimos 12 meses (LTM). AV = análise vertical, em % da receita líquida do período.
    Custos e despesas incluem a depreciação e amortização (a CVM não a separa). Despesas operacionais incluem equivalência patrimonial e outras
    receitas/despesas operacionais. Lucro líquido consolidado, inclusive a parte dos minoritários.</div>`;

  const at = (c) => g(c, "ativo_total"), ac = (c) => g(c, "ativo_circ"), pc = (c) => g(c, "passivo_circ"), pl = (c) => g(c, "pl");
  const caixa = (c) => (g(c, "caixa") == null && g(c, "aplicacoes") == null ? null : (g(c, "caixa") || 0) + (g(c, "aplicacoes") || 0));
  const pnc = (c) => soma(at(c), pc(c) == null ? null : -pc(c), pl(c) == null ? null : -pl(c));
  document.getElementById("tab-bp").innerHTML = tabela([
    ["Caixa e aplicações financeiras", caixa],
    ["Outros ativos circulantes", (c) => soma(ac(c), caixa(c) == null ? null : -caixa(c))],
    ["Ativo circulante", ac, "subtotal"],
    ["Ativo não circulante", (c) => soma(at(c), ac(c) == null ? null : -ac(c)), "subtotal"],
    ["Ativo total", at, "total"],
    ["Empréstimos e financiamentos (CP)", (c) => g(c, "emprest_cp")],
    ["Outros passivos circulantes", (c) => soma(pc(c), g(c, "emprest_cp") == null ? null : -g(c, "emprest_cp"))],
    ["Passivo circulante", pc, "subtotal"],
    ["Empréstimos e financiamentos (LP)", (c) => g(c, "emprest_lp")],
    ["Outros passivos não circulantes", (c) => soma(pnc(c), g(c, "emprest_lp") == null ? null : -g(c, "emprest_lp"))],
    ["Passivo não circulante", pnc, "subtotal"],
    ["Patrimônio líquido", pl, "subtotal"],
    ["Passivo total + PL", at, "total"],
    ["Memória: arrendamentos (IFRS 16, CP + LP)", (c) => g(c, "arrendamentos"), "memoria"],
    ["Memória: dívida líquida (sem IFRS 16)", (c) => g(c, "divida_liquida"), "memoria"],
  ], at) + `<div class="nota">Posição no fim de cada exercício; na coluna LTM, o balanço do último trimestre. AV em % do ativo total.
    Empréstimos incluem debêntures. Os arrendamentos (IFRS 16) estão dentro dos "outros passivos" e aparecem também como memória.
    Passivo não circulante = ativo total − passivo circulante − PL (PL consolidado, com minoritários).</div>`;
}

/* ============ Macro ============ */
let JANELA_MACRO = 10;
const SUBS_MACRO = [["atividade", "Atividade"], ["inflacao", "Inflação"], ["expectativas", "Expectativas (Focus)"], ["monetaria", "Política monetária"], ["fiscal", "Política fiscal"], ["credito", "Crédito"], ["cambio", "Câmbio"], ["externo", "Setor externo"]];
const SUBS_CREDITO = [["total", "Total"], ["pj", "Pessoa jurídica"], ["pf", "Pessoa física"]];
let ABA_CREDITO = "total";
const SUBS_FISCAL = [["arrecadacao", "Arrecadação"], ["despesas", "Despesas"], ["endividamento", "Endividamento"]];
let ABA_FISCAL = "arrecadacao";
const SUBS_JUROS_OFF = [["mundo", "Mundo"], ["eua", "EUA"], ["euro", "Zona do Euro"], ["china", "China"]];
let ABA_JUROS_OFF = "mundo";
const GRUPOS_ATIVOS = { desenvolvidos: true, emergentes: true, mundo: true };  // Macro > Global
const GRUPOS_JUROS = { desenvolvidos: true, emergentes: true };  // Juros > Mundo  // botões liga/desliga Desenvolvidos / Em desenvolvimento
const NOMES_FOCUS = { selic: "Selic fim de ano (% a.a.)", ipca: "IPCA (%)", pib: "PIB (%)", cambio: "Câmbio fim de ano (R$/US$)" };
const ESCOLHA_GRAFICO = {};  // opção escolhida em cada gráfico com botões (fica ao trocar de janela)
const NUCLEOS = [["nucleo_ex0", "EX0", COR.azul], ["nucleo_ex2", "EX2", COR.cinza], ["nucleo_ex3", "EX3", COR.roxo],
  ["nucleo_ms", "MS", COR.ciano], ["nucleo_dp", "DP", COR.verde], ["nucleo_p55", "P55", "#db61a2"]];

async function paginaMacro(sub) {
  if (!SUBS_MACRO.some(([k]) => k === sub)) sub = SUBS_MACRO[0][0];
  const [macro, cred, ext, fis] = await Promise.all([dados("dados/macro.json"), sub === "credito" ? dados("dados/credito.json").catch(() => null) : null,
    sub === "externo" ? dados("dados/setor_externo.json").catch(() => null) : null,
    sub === "fiscal" ? dados("dados/fiscal.json").catch(() => null) : null]);
  // Setor externo: séries do BC e do Comex Stat entram no mesmo dicionário (prefixo cx_ para o Comex); valores em US$
  const S = { ...macro.series, ...((cred && cred.series) || {}), ...((fis && fis.series) || {}), ...((ext && ext.bc) || {}),
    ...(ext && ext.comex ? { cx_exportacoes: ext.comex.exportacoes, cx_importacoes: ext.comex.importacoes } : {}) }, F = macro.focus;
  if (sub === "externo") MOEDA = "US$";
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
    // Política fiscal: cartões da aba interna; no Endividamento, NFSP com sinal invertido (resultado: superávit positivo)
    fiscal: ABA_FISCAL !== "endividamento" ? cartoesFiscal(S, u, mes) : [cartao("Dívida bruta (DBGG)", pctPronto(u("dbgg").valor, 1), `% do PIB · ${mes("dbgg")}`),
      cartao("Dívida líquida (DLSP)", pctPronto(u("dlsp").valor, 1), `% do PIB · ${mes("dlsp")}`),
      cartao("Resultado primário 12m", pctPronto(u("nfsp_primario").valor == null ? null : -u("nfsp_primario").valor, 2), `% do PIB · setor público consolidado`),
      cartao("Juros nominais 12m", pctPronto(u("nfsp_juros").valor, 2), "% do PIB"),
      cartao("Resultado nominal 12m", pctPronto(u("nfsp_nominal").valor == null ? null : -u("nfsp_nominal").valor, 2), "% do PIB"),
      cartao("Dívida federal pós-fixada (Selic)", pctPronto(u("dmf_selic").valor, 1), `do estoque · ${mes("dmf_selic")}`),
      cartao("Dívida Pública Federal em mercado", u("dpf_total").valor != null ? reais(u("dpf_total").valor * 1e6) : "—", `Tesouro · ${mes("dpf_total")}`),
      cartao("DPF que vence em 12 meses", pctPronto(u("dpf_vence_12m").valor, 1), `do estoque · ${mes("dpf_vence_12m")}`)],
    credito: cred ? cartoesCredito(S, u, mes) : [],
    externo: ext ? cartoesExterno(S, u, mes) : [],
    expectativas: [cartao(`IPCA ${new Date().getFullYear()}`, pctPronto(focusAno("ipca")), "mediana Focus"), cartao(`Selic fim de ${new Date().getFullYear()}`, pctPronto(focusAno("selic")), "mediana Focus"),
      cartao(`Câmbio fim de ${new Date().getFullYear()}`, focusAno("cambio") ? `R$ ${num(focusAno("cambio"), 2)}` : "—", "mediana Focus"), cartao(`PIB ${new Date().getFullYear()}`, pctPronto(focusAno("pib")), "mediana Focus")],
  }[sub];
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Macro</h1><div class="sub">Banco Central (SGS, Estatísticas Fiscais, de Crédito e do Setor Externo), Tesouro Nacional (RTN, Dívida Pública, SICONFI), Receita Federal, IBGE, FGV, Comex Stat e boletim Focus · atualizado em ${dataBR(macro.gerado_em)} · botões = janela inicial; use a roda do mouse ou a barra para ver mais</div></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        ${sub === "expectativas" ? "" : `<div class="seletor" id="janela">${[[1, "1A"], [5, "5A"], [10, "10A"], [99, "Máx"]].map(([a, r]) => `<button data-a="${a}" class="${a === JANELA_MACRO ? "ativo" : ""}">${r}</button>`).join("")}</div>`}
        <a class="botao" href="downloads/macro.xlsx" download>Baixar planilha de Macro</a></div></div>
    <div class="abas">${SUBS_MACRO.map(([k, n]) => `<a href="#/on/macro/${k}" class="${k === sub ? "ativo" : ""}">${n}</a>`).join("")}</div>
    ${sub === "credito" ? `<div class="seletor seletor-editoria" id="sub-credito" style="margin:-4px 0 12px">${SUBS_CREDITO.map(([k, n]) => `<button data-k="${k}" class="${k === ABA_CREDITO ? "ativo" : ""}">${n}</button>`).join("")}</div>
      ${cred ? "" : `<p class="sub">Estatísticas de crédito indisponíveis no momento.</p>`}` : ""}
    ${sub === "fiscal" ? `<div class="seletor seletor-editoria" id="sub-fiscal" style="margin:-4px 0 12px">${SUBS_FISCAL.map(([k, n]) => `<button data-k="${k}" class="${k === ABA_FISCAL ? "ativo" : ""}">${n}</button>`).join("")}</div>
      ${fis || ABA_FISCAL === "endividamento" ? "" : `<p class="sub">Dados de arrecadação e despesas indisponíveis no momento.</p>`}` : ""}
    <div class="grade-cartoes">${cartoes.join("")}</div>
    <div class="grade" id="graficos-macro"></div>`;
  const subCred = document.getElementById("sub-credito");
  if (subCred) subCred.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    ABA_CREDITO = b.dataset.k;
    paginaMacro("credito");
  });
  const subFiscal = document.getElementById("sub-fiscal");
  if (subFiscal) subFiscal.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    ABA_FISCAL = b.dataset.k;
    paginaMacro("fiscal");
  });
  const janela = document.getElementById("janela");
  if (janela) janela.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    JANELA_MACRO = Number(b.dataset.a);
    document.querySelectorAll("#janela button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharMacro(S, F, sub, cred, ext, fis);
  });
  desenharMacro(S, F, sub, cred, ext, fis);
}

function desenharMacro(S, F, sub, cred = null, ext = null, fis = null) {
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
  // Setor externo: valores em US$ milhões (BC e Comex Stat); 12 meses = soma móvel dos últimos 12 meses
  const MU = (s) => P(s).map(([d, v]) => [d, v == null ? null : v * 1e6]);
  const soma12 = (s) => { const p = P(s); return p.map(([d], i) => [d, i >= 11 ? p.slice(i - 11, i + 1).reduce((a, x) => a + (x[1] || 0), 0) * 1e6 : null]).filter((x) => x[1] != null); };
  const defsExterno = () => {
    const C = ext.comex || {}, prod = C.produtos || {}, dest = C.destinos || {};
    const grupoProd = (cods) => ({ eixoEsq: "reais", series: cods.filter((c) => prod[c]).map((c, j) => ({ nome: prod[c].nome, valores: soma12(prod[c]), tipo: "line", cor: PALETA_GRAF[j] })) });
    const saldo = C.exportacoes && C.importacoes ? P(C.exportacoes).map(([d, v], i) => [d, (v - (C.importacoes.valores[i] || 0)) * 1e6]) : [];
    return [
      { t: "Transações correntes e investimento direto (12 meses, % do PIB)", info: "externo_tc", op: { eixoEsq: "pctPronto", series: [
        { nome: "Transações correntes", valores: P(S.tc_pib), tipo: "line", cor: COR.vermelho },
        { nome: "Investimento direto no país (IDP)", valores: P(S.idp_pib), tipo: "line", cor: COR.verde }] } },
      { t: "Balança comercial — mensal (Comex Stat)", info: "externo_balanca", op: { eixoEsq: "reais", inicio: inicio(Math.min(JANELA_MACRO, 5)), series: [
        { nome: "Exportações", valores: MU(C.exportacoes), cor: COR.verde }, { nome: "Importações", valores: MU(C.importacoes), cor: COR.vermelho },
        { nome: "Saldo", valores: saldo, tipo: "line", cor: COR.ambar }] } },
      { t: "Exportações por produto — acumulado em 12 meses", info: "externo_produtos", largo: true, alt: {
        "Minerais e energia": grupoProd(["2709", "2601", "2710", "7207"]), "Grãos": grupoProd(["1201", "2304", "1005", "5201"]),
        "Proteínas e alimentos": grupoProd(["0202", "0207", "1701", "0901"]), "Celulose e aviões": grupoProd(["4703", "8802"]) } },
      { t: "Exportações por destino — acumulado em 12 meses", info: "externo_destinos", op: { eixoEsq: "reais", series:
        ["China", "União Europeia", "Estados Unidos", "Argentina"].filter((p) => dest[p]).map((p, j) => ({ nome: p, valores: soma12(dest[p]), tipo: "line", cor: [COR.vermelho, COR.azul, COR.verde, COR.ciano][j] })) } },
      { t: "Investimento estrangeiro em carteira — acumulado em 12 meses", info: "externo_carteira", op: { eixoEsq: "reais", series: [
        { nome: "Ações", valores: soma12(S.carteira_acoes), cor: COR.azul, pilha: "c" },
        { nome: "Títulos de dívida", valores: soma12(S.carteira_titulos), cor: COR.roxo, pilha: "c" },
        { nome: "Total em carteira", valores: soma12(S.carteira_mensal), tipo: "line", cor: COR.ambar }] } },
      { t: "Investimento direto no país (IDP)", info: "externo_tc", op: { eixoEsq: "reais", eixoDir: "reais", series: [
        { nome: "No mês", valores: MU(S.idp_mensal), cor: COR.verde }, { nome: "12 meses (eixo direito)", valores: soma12(S.idp_mensal), tipo: "line", eixo: "dir", cor: COR.ambar }] } },
      { t: "Reservas internacionais (conceito liquidez)", info: "externo_reservas", op: { eixoEsq: "reais", series: [
        { nome: "Reservas no fim do mês", valores: MU(S.reservas), tipo: "line", cor: COR.verde }] } },
    ];
  };
  // Crédito (Banco Central): saldos e concessões vêm em R$ milhões
  const M = (s) => P(s).map(([d, v]) => [d, v == null ? null : v * 1e6]);
  // Selic meta vigente no fim de cada mês da série de referência (a Selic guarda só as datas de mudança)
  const selicNoMes = (ref) => {
    if (!ref || !S.selic_meta) return [];
    const mud = P(S.selic_meta);
    return ref.datas.map((d) => { const fim = `${d.slice(0, 7)}-31`; let v = null; for (const [x, y] of mud) { if (x <= fim) v = y; else break; } return [d, v]; });
  };
  // barras somadas: cada parte nas datas da série de referência (vazio onde a parte não tem dado), em R$
  const naRef = (ref, chave) => {
    if (!ref || !S[chave]) return [];
    const m = Object.fromEntries(P(S[chave]));
    return ref.datas.map((d) => [d, m[d] == null ? null : m[d] * 1e6]);
  };
  const defsCredito = (g) => {
    const x = g === "total" ? "" : `_${g}`;            // sufixo das chaves: saldo_pj, taxa_pf...
    const k = (base) => (g === "total" ? `${base}_total` : `${base}_${g}`);
    const quem = { total: "", pj: " · pessoa jurídica", pf: " · pessoa física" }[g];
    const refConc = S[`${k("conc")}_sa`];
    const lista = [
      { t: `Saldo da carteira de crédito${quem}`, info: "credito_saldo", op: { eixoEsq: "reais", eixoDir: "pctPronto", series: [
        { nome: "Recursos livres", valores: M(S[g === "total" ? "saldo_livres" : `saldo${x}_livres`]), cor: COR.azul, pilha: "saldo" },
        { nome: "Recursos direcionados", valores: M(S[g === "total" ? "saldo_dir" : `saldo${x}_dir`]), cor: COR.roxo, pilha: "saldo" },
        { nome: "Crescimento em 12 meses", valores: P(S[`${k("saldo")}_12m`]), tipo: "line", eixo: "dir", cor: COR.ambar }] } },
      { t: `Crédito em % do PIB${quem}`, info: "credito_pib", op: { eixoEsq: "pctPronto", series: [
        { nome: "Total", valores: P(S[k("pib")]), tipo: "line", cor: COR.ambar },
        { nome: "Recursos livres", valores: P(S[g === "total" ? "pib_livres" : `pib${x}_livres`]), tipo: "line", cor: COR.azul },
        { nome: "Recursos direcionados", valores: P(S[g === "total" ? "pib_dir" : `pib${x}_dir`]), tipo: "line", cor: COR.roxo }] } },
      { t: `Concessões (crédito novo no mês, dessazonalizado)${quem}`, info: "credito_concessoes", alt: {
        "Segmentado": { eixoEsq: "reais", series: [
          { nome: "Recursos livres", valores: naRef(refConc, g === "total" ? "conc_livres_sa" : `conc${x}_livres_sa`), cor: COR.azul, pilha: "conc" },
          { nome: "Recursos direcionados", valores: naRef(refConc, g === "total" ? "conc_dir_sa" : `conc${x}_dir_sa`), cor: COR.roxo, pilha: "conc" }] },
        "Total": { eixoEsq: "reais", series: [{ nome: "Total", valores: M(refConc), cor: COR.ambar }] } } },
      { t: `Juros, spread e custo do crédito${quem}`, info: "credito_juros", op: { eixoEsq: "pctPronto", series: [
        { nome: "Taxa média (crédito novo)", valores: P(S[k("taxa")]), tipo: "line", cor: COR.ambar },
        { nome: "Taxa — livres", valores: P(S[g === "total" ? "taxa_livres" : `taxa${x}_livres`]), tipo: "line", cor: COR.azul },
        { nome: "Taxa — direcionados", valores: P(S[g === "total" ? "taxa_dir" : `taxa${x}_dir`]), tipo: "line", cor: COR.roxo },
        { nome: "Spread (p.p.)", valores: P(S[k("spread")]), tipo: "line", cor: COR.vermelho },
        { nome: "ICC (custo da carteira)", valores: P(S[k("icc")]), tipo: "line", cor: COR.verde },
        { nome: "Selic meta (fim do mês)", valores: selicNoMes(S[k("taxa")]), tipo: "line", cor: COR.cinza, tracejado: true }] } },
      { t: `Inadimplência e atrasos${quem}`, info: "credito_inadimplencia", op: { eixoEsq: "pctPronto", series: [
        { nome: "Inadimplência (> 90 dias)", valores: P(S[k("inad")]), tipo: "line", cor: COR.vermelho },
        { nome: "Inadimplência — livres", valores: P(S[g === "total" ? "inad_livres" : `inad${x}_livres`]), tipo: "line", cor: COR.azul },
        { nome: "Inadimplência — direcionados", valores: P(S[g === "total" ? "inad_dir" : `inad${x}_dir`]), tipo: "line", cor: COR.roxo },
        { nome: "Atraso de 15 a 90 dias", valores: P(S[k("atraso")]), tipo: "line", cor: COR.ambar, tracejado: true }] } },
    ];
    if (g === "total") {
      lista.push({ t: "Pessoa física × pessoa jurídica: saldo", info: "credito_pfpj", op: { eixoEsq: "reais", series: [
        { nome: "Pessoa física", valores: naRef(S.saldo_total, "saldo_pf"), cor: COR.verde, pilha: "pfpj" },
        { nome: "Pessoa jurídica", valores: naRef(S.saldo_total, "saldo_pj"), cor: COR.azul, pilha: "pfpj" }] } });
      return lista;
    }
    lista.push({ t: `Prazo médio da carteira (meses)${quem}`, info: "credito_prazo", op: { eixoEsq: "numero", series: [
      { nome: "Total", valores: P(S[`prazo${x}`]), tipo: "line", cor: COR.ambar },
      { nome: "Recursos livres", valores: P(S[`prazo${x}_livres`]), tipo: "line", cor: COR.azul },
      { nome: "Recursos direcionados", valores: P(S[`prazo${x}_dir`]), tipo: "line", cor: COR.roxo }] } });
    if (g === "pf") {
      lista.push({ t: "Endividamento das famílias (% da renda de 12 meses)", info: "credito_familias", op: { eixoEsq: "pctPronto", series: [
        { nome: "Endividamento total", valores: P(S.endiv), tipo: "line", cor: COR.ambar },
        { nome: "Sem crédito habitacional", valores: P(S.endiv_sem_hab), tipo: "line", cor: COR.azul }] } });
      lista.push({ t: "Comprometimento de renda com dívidas (% da renda mensal, dessaz.)", info: "credito_familias", op: { eixoEsq: "pctPronto", series: [
        { nome: "Serviço da dívida (juros + amortização)", valores: P(S.compr), tipo: "line", cor: COR.ambar },
        { nome: "Juros", valores: P(S.compr_juros), cor: COR.vermelho, pilha: "c" },
        { nome: "Amortização", valores: P(S.compr_amort), cor: COR.azul, pilha: "c" }] } });
    }
    // Modalidades: um gráfico com botões; saldo em barras somadas (uma parte por modalidade), juros e inadimplência em linhas
    const mods = ((cred && cred.modalidades) || {})[g] || [];
    // nas barras somadas fica de fora o que já está dentro de outra modalidade (o rotativo faz parte do cartão total)
    const PARTE_DE_OUTRA = new Set(["cartao_rotativo"]);
    const porMod = (campo, conv) => ({ eixoEsq: campo === "saldo" ? "reais" : "pctPronto", series: mods.map((m, j) => [m, j]).filter(([m]) => campo !== "saldo" || !PARTE_DE_OUTRA.has(m.k)).map(([m, j]) => (campo === "saldo"
      ? { nome: m.nome, valores: naRef(S[k("saldo")], `mod_${g}_${m.k}_saldo`), cor: PALETA_GRAF[j % PALETA_GRAF.length], pilha: "mod" }
      : { nome: m.nome, valores: conv(S[`mod_${g}_${m.k}_${campo}`]), tipo: "line", cor: PALETA_GRAF[j % PALETA_GRAF.length] })) });
    lista.push({ t: `Modalidades${quem}`, info: "credito_modalidades", largo: true, alt: {
      "Saldo": porMod("saldo", M), "Taxa de juros": porMod("taxa", P), "Inadimplência": porMod("inad", P) } });
    return lista;
  };
  // contas públicas: NFSP com sinal invertido (resultado: superávit positivo) e soma de indexadores pequenos
  const neg = (s) => P(s).map(([d, v]) => [d, v == null ? null : -v]);
  // soma de séries nas datas de uma série de referência (empilhamento precisa das mesmas datas em todas)
  const alinhar = (ref, ks) => {
    if (!ref) return [];
    const mapas = ks.map((k) => Object.fromEntries(P(S[k])));
    return ref.datas.map((d) => [d, Math.round(mapas.reduce((a, m) => a + (m[d] || 0), 0) * 100) / 100]);
  };
  const soma = (ks) => {
    const base = S[ks[0]]; if (!base) return [];
    const mapas = ks.map((k) => Object.fromEntries(P(S[k])));
    return base.datas.map((d) => [d, Math.round(mapas.reduce((a, m) => a + (m[d] || 0), 0) * 100) / 100]);
  };
  // ---------- Política fiscal (Tesouro/RTN, Receita Federal, Tesouro Transparente, SICONFI) ----------
  // barras somadas em % (sem conversão de unidade), alinhadas às datas da série de referência
  const naRefPct = (ref, chave) => {
    if (!ref || !S[chave]) return [];
    const m = Object.fromEntries(P(S[chave]));
    return ref.datas.map((d) => [d, m[d] == null ? null : m[d]]);
  };
  const pilhaR = (ref, partes, pilha, suf = "") => partes.map(([k, nome], j) => ({ nome, valores: naRef(S[ref], `${k}${suf}`),
    cor: PALETA_GRAF[j % PALETA_GRAF.length], pilha }));
  const pilhaPct = (ref, partes, pilha, suf) => partes.map(([k, nome], j) => ({ nome, valores: naRefPct(S[ref], `${k}${suf}`),
    cor: PALETA_GRAF[j % PALETA_GRAF.length], pilha }));
  const TRIBUTOS_GR = [["arr_ir", "Imposto de Renda"], ["arr_previdencia", "Previdência (RGPS)"], ["arr_cofins", "Cofins"],
    ["arr_pis", "PIS/Pasep"], ["arr_csll", "CSLL"], ["arr_ipi", "IPI"], ["arr_comercio", "Importação e exportação"], ["arr_iof", "IOF"],
    ["arr_outros_orgaos", "Administradas por outros órgãos"], ["arr_outros", "Demais"]];
  const GRUPOS_DESPESA = [["rtn_previdencia", "Benefícios previdenciários"], ["rtn_pessoal", "Pessoal e encargos"],
    ["rtn_outras_obrig", "Outras obrigatórias"], ["rtn_controle_fluxo", "Obrigatórias com controle de fluxo"],
    ["rtn_discricionarias", "Discricionárias do Executivo"]];
  const defsFiscal = (aba) => {
    if (aba === "arrecadacao") return [
      // linha 1: arrecadação por tributo (um seletor: 12 meses, 12 meses a preços de hoje, mensal) | receita do Governo Central
      { t: "Arrecadação federal por tributo", info: "fiscal_arrecadacao", alt: {
        "12 meses": { eixoEsq: "reais", series: pilhaR("arr_total_12m", TRIBUTOS_GR, "arr", "_12m") },
        "12 meses a preços de hoje": { eixoEsq: "reais", series: pilhaR("arr_total_12m_real", TRIBUTOS_GR, "arr", "_12m_real") },
        "Mensal": { eixoEsq: "reais", inicio: inicio(Math.min(JANELA_MACRO, 3)), series: pilhaR("arr_total", TRIBUTOS_GR, "arrm") } } },
      { t: "Receita do Governo Central e transferências — 12 meses", info: "fiscal_receitas_rtn", alt: {
        "R$": { eixoEsq: "reais", series: pilhaR("rtn_receita_total_12m", [["rtn_receita_liquida", "Receita líquida do Governo Central"],
          ["rtn_transferencias", "Transferências a estados e municípios"]], "rec", "_12m") },
        "% do PIB": { eixoEsq: "pctPronto", series: [
          { nome: "Receita total", valores: P(S.rtn_receita_total_12m_pib), tipo: "line", cor: COR.ambar },
          { nome: "Receita líquida", valores: P(S.rtn_receita_liquida_12m_pib), tipo: "line", cor: COR.azul },
          { nome: "Transferências a estados e municípios", valores: P(S.rtn_transferencias_12m_pib), tipo: "line", cor: COR.roxo }] } } },
      // linha 2: receitas não administradas | dividendos de estatais
      { t: "Receitas não administradas — 12 meses", info: "fiscal_nao_administradas", op: { eixoEsq: "reais",
        series: pilhaR("rtn_receita_nao_adm_12m", [["rtn_concessoes", "Concessões e permissões"], ["rtn_dividendos", "Dividendos de estatais"],
          ["rtn_recursos_naturais", "Royalties e participações (recursos naturais)"], ["rtn_nao_adm_demais", "Demais"]], "na", "_12m") } },
      { t: "Dividendos de estatais pagos à União — 12 meses", info: "fiscal_dividendos", op: { eixoEsq: "reais",
        series: pilhaR("rtn_dividendos_12m", [["rtn_div_petrobras", "Petrobras"], ["rtn_div_bndes", "BNDES"], ["rtn_div_bb", "Banco do Brasil"],
          ["rtn_div_caixa", "Caixa"], ["rtn_div_eletrobras", "Eletrobras"], ["rtn_div_demais", "Demais empresas"]], "div", "_12m") } },
      { t: "Arrecadação federal: % do PIB e crescimento real (12 meses)", info: "fiscal_arrecadacao_pib", largo: true, op: { eixoEsq: "pctPronto", eixoDir: "pctPronto", series: [
        { nome: "% do PIB", valores: P(S.arr_total_12m_pib), tipo: "line", cor: COR.ambar },
        { nome: "Crescimento real em 12 meses (eixo direito)", valores: P(S.arr_total_cresc_real), tipo: "line", eixo: "dir", cor: COR.verde }] } },
    ];
    return [  // despesas
      { t: "Despesa total do Governo Central por grupo — 12 meses", info: "fiscal_despesa_grupos", largo: true, alt: {
        "R$": { eixoEsq: "reais", series: pilhaR("rtn_despesa_total_12m", GRUPOS_DESPESA, "desp", "_12m") },
        "% do PIB": { eixoEsq: "pctPronto", series: pilhaPct("rtn_despesa_total_12m_pib", GRUPOS_DESPESA, "desp", "_12m_pib") } } },
      { t: "Receita líquida, despesa e resultado primário do Governo Central — 12 meses (% do PIB)", info: "fiscal_resultado_central", op: {
        eixoEsq: "pctPronto", eixoDir: "pctPronto", series: [
          { nome: "Receita líquida", valores: P(S.rtn_receita_liquida_12m_pib), tipo: "line", cor: COR.azul },
          { nome: "Despesa total", valores: P(S.rtn_despesa_total_12m_pib), tipo: "line", cor: COR.vermelho },
          { nome: "Resultado primário (eixo direito)", valores: P(S.rtn_resultado_central_12m_pib), eixo: "dir", cor: COR.verde }] } },
      { t: "Resultado primário do Governo Central por órgão — 12 meses", info: "fiscal_resultado_orgaos", op: { eixoEsq: "reais", series: [
        ...pilhaR("rtn_resultado_central_12m", [["rtn_resultado_tesouro", "Tesouro Nacional"], ["rtn_resultado_previdencia", "Previdência Social"],
          ["rtn_resultado_bcb", "Banco Central"]], "res", "_12m"),
        { nome: "Total do Governo Central", valores: M(S.rtn_resultado_central_12m), tipo: "line", cor: COR.ambar }] } },
      { t: "Despesas discricionárias do Poder Executivo por área — 12 meses", info: "fiscal_discricionarias", op: { eixoEsq: "reais",
        series: pilhaR("rtn_discricionarias_12m", [["rtn_disc_saude", "Saúde"], ["rtn_disc_educacao", "Educação"], ["rtn_disc_defesa", "Defesa"],
          ["rtn_disc_transporte", "Transporte"], ["rtn_disc_administracao", "Administração"], ["rtn_disc_ciencia", "Ciência e tecnologia"],
          ["rtn_disc_seguranca", "Segurança pública"], ["rtn_disc_assistencia", "Assistência social"], ["rtn_disc_demais", "Demais"]], "disc", "_12m") } },
      { t: "Outras despesas obrigatórias — 12 meses", info: "fiscal_obrigatorias", op: { eixoEsq: "reais",
        series: pilhaR("rtn_outras_obrig_12m", [["rtn_obr_bpc", "BPC (LOAS/RMV)"], ["rtn_obr_abono", "Abono e seguro-desemprego"],
          ["rtn_obr_sentencas", "Sentenças judiciais e precatórios"], ["rtn_obr_fundeb", "Fundeb"], ["rtn_obr_subsidios", "Subsídios e subvenções"],
          ["rtn_obr_creditos", "Créditos extraordinários"], ["rtn_obr_compensacao", "Compensação da desoneração da folha"],
          ["rtn_obr_demais", "Demais"]], "obr", "_12m") } },
      { t: "Obrigatórias com controle de fluxo — 12 meses", info: "fiscal_controle_fluxo", op: { eixoEsq: "reais",
        series: pilhaR("rtn_controle_fluxo_12m", [["rtn_cf_bolsa", "Bolsa Família"], ["rtn_cf_saude", "Saúde"], ["rtn_cf_educacao", "Educação"],
          ["rtn_cf_demais", "Demais"]], "cf", "_12m") } },
      { t: "Investimento do governo federal — 12 meses", info: "fiscal_investimento", op: { eixoEsq: "reais", eixoDir: "pctPronto", series: [
        { nome: "Investimento (12 meses)", valores: M(S.rtn_investimento_12m), cor: COR.azul },
        { nome: "% do PIB (eixo direito)", valores: P(S.rtn_investimento_12m_pib), tipo: "line", eixo: "dir", cor: COR.ambar }] } },
    ];
  };
  // Endividamento: gráficos do Banco Central que já existiam + dívida por esfera, Dívida Pública Federal e Tesouro Direto
  const defsEndividamento = (bc) => {
    const [divida, resultado, esferas, prazo, dmf] = bc;
    const V = (fis && fis.vencimentos_dpf) || null;
    const IDX = [["dpf_selic", "Selic (LFT)"], ["dpf_pre", "Prefixado (LTN e NTN-F)"], ["dpf_ipca", "IPCA (NTN-B)"], ["dpf_igpm", "IGP-M (NTN-C)"],
      ["dpf_cambio", "Câmbio (dívida externa)"], ["dpf_demais", "Demais"]];
    const parteDpf = (k) => (S.dpf_total ? S.dpf_total.datas.map((d, i) => { const m = Object.fromEntries(P(S[k])); return [d, m[d] == null ? null : m[d] / S.dpf_total.valores[i] * 100]; }) : []);
    const estados = ((fis && fis.estados) || []).slice(0, 6);
    return [
      divida,
      { t: "Dívida líquida do setor público por esfera (% do PIB)", info: "fiscal_dlsp_esferas", op: { eixoEsq: "pctPronto", series: [
        ...[["dlsp_federal", "Governo Federal e Banco Central"], ["dlsp_estados", "Estados"], ["dlsp_municipios", "Municípios"], ["dlsp_estatais", "Estatais"]]
          .map(([k, nome], j) => ({ nome, valores: alinhar(S.dlsp, [k]), cor: [COR.azul, COR.roxo, COR.ciano, COR.cinza][j], pilha: "dlsp" })),
        { nome: "Total (DLSP)", valores: P(S.dlsp), tipo: "line", cor: COR.ambar }] } },
      resultado, esferas,
      ...(S.dpf_total ? [{ t: "Dívida Pública Federal em mercado por indexador (Tesouro)", info: "fiscal_dpf", largo: true, alt: {
        "R$": { eixoEsq: "reais", series: pilhaR("dpf_total", IDX, "dpf") },
        "% do estoque": { eixoEsq: "pctPronto", limitesEsq: [0, 100], series: IDX.map(([k, nome], j) => ({ nome, valores: parteDpf(k), cor: PALETA_GRAF[j], pilha: "dpfp" })) } } }] : []),
      ...(V ? [{ t: `Vencimentos da Dívida Pública Federal em mercado, por ano · posição de ${mesAno(V.data)}`, info: "fiscal_dpf_vencimentos", op: {
        xTempo: false, rotulos: [...V.anos, "Depois"], eixoEsq: "reais", janela: 30, series: [
          { nome: "A vencer", valores: [...V.valores, V.depois].map((v) => v * 1e6), cor: COR.azul }] } }] : []),
      ...(S.dpf_vence_12m ? [{ t: "Parcela da Dívida Pública Federal que vence em 12 meses", info: "fiscal_dpf_12m", op: { eixoEsq: "pctPronto", series: [
        { nome: "Vence em até 12 meses", valores: P(S.dpf_vence_12m), tipo: "line", cor: COR.vermelho }] } }] : []),
      // composição por indexador ao lado do prazo médio (composição primeiro)
      { ...dmf, largo: false }, prazo,
      ...(S.td_total ? [{ t: "Tesouro Direto — estoque por tipo de título", info: "fiscal_tesouro_direto", op: { eixoEsq: "reais", series: pilhaR("td_total",
        [["td_selic", "Tesouro Selic"], ["td_ipca", "Tesouro IPCA+"], ["td_prefixado", "Tesouro Prefixado"], ["td_renda", "Tesouro Renda+"],
          ["td_educa", "Tesouro Educa+"], ["td_igpm", "Tesouro IGP-M+"], ["td_outros", "Outros"]], "td") } }] : []),
      ...(estados.length ? [{ t: "Dívida consolidada líquida dos estados mais endividados (% da receita corrente líquida)", info: "fiscal_estados", largo: true, op: {
        eixoEsq: "pctPronto", series: estados.map((e, j) => ({ nome: e.nome, tipo: "line", cor: PALETA_GRAF[j],
          valores: e.historico.datas.map((d, i) => [d, e.historico.dcl_rcl[i]]) })) } }] : []),
    ];
  };
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
      // linha 1: PIB anual inteiro; linha 2: IBC-Br | PIB trimestral; linha 3: desemprego inteiro
      { t: "PIB anual (anos fechados)", info: "pib_anual", largo: true, op: { xTempo: false, rotulos: anos, eixoEsq: "reais", eixoDir: "pctPronto", janela: 30, series: [
        { nome: "PIB nominal (R$ correntes)", valores: anos.map((a) => nominal[a] ?? null), cor: COR.azul },
        { nome: "Crescimento real", valores: S.pib_anual ? S.pib_anual.valores : [], tipo: "line", eixo: "dir", cor: COR.ambar }] } },
      { t: "IBC-Br (prévia mensal do PIB)", info: "ibcbr", op: { series: [{ nome: "Mensal (dessaz., m/m)", valores: P(S.ibcbr_mensal), cor: COR.azul }, { nome: "Acumulado em 12 meses", valores: P(S.ibcbr_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto", inicio: inicio(Math.min(JANELA_MACRO, 3)) } },
      { t: "PIB trimestral", info: "pib_tri", op: { series: [{ nome: "Trimestral (dessaz., tri/tri)", valores: P(S.pib_tri), cor: COR.azul }, { nome: "Acumulado em 4 trimestres", valores: P(S.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto" } },
      { t: "Desemprego (PNAD Contínua, trimestre móvel)", info: "desemprego_br", largo: true, op: { eixoEsq: "pctPronto", series: [
        { nome: "Taxa de desocupação", valores: P(S.desemprego), tipo: "line", cor: COR.vermelho }] } },
    ],
    monetaria: [
      { t: "Selic meta, CDI e IPCA 12 meses", info: "selic", largo: true, op: { series: [{ nome: "Selic meta", valores: P(S.selic_meta), tipo: "line", cor: COR.ambar }, { nome: "CDI", valores: P(S.cdi), tipo: "line", cor: COR.ciano }, { nome: "IPCA 12m", valores: P(S.ipca_12m), tipo: "line", cor: COR.vermelho }, { nome: "Média dos núcleos 12m", valores: P(S.nucleos_media_12m), tipo: "line", cor: COR.roxo, tracejado: true }], eixoEsq: "pctPronto", degrau: true } },
      { t: "Juro real ex-post (Selic ÷ IPCA 12m)", info: "juro_real", largo: true, op: { series: [{ nome: "Juro real", valores: P(S.juro_real), tipo: "line", cor: COR.verde }], eixoEsq: "pctPronto" } },
    ],
    credito: cred ? defsCredito(ABA_CREDITO) : [],
    externo: ext ? defsExterno() : [],
    fiscal: ABA_FISCAL === "endividamento" ? defsEndividamento([
      { t: "Dívida pública (% do PIB): bruta e líquida", info: "fiscal_divida", op: { eixoEsq: "pctPronto", series: [
        { nome: "Dívida bruta do governo geral (DBGG)", valores: P(S.dbgg), tipo: "line", cor: COR.vermelho },
        { nome: "Dívida líquida do setor público (DLSP)", valores: P(S.dlsp), tipo: "line", cor: COR.azul }] } },
      { t: "Resultado do setor público em 12 meses (% do PIB)", info: "fiscal_resultado", op: { eixoEsq: "pctPronto", series: [
        { nome: "Resultado primário", valores: neg(S.nfsp_primario), cor: COR.verde },
        { nome: "Juros nominais", valores: neg(S.nfsp_juros), tipo: "line", cor: COR.ambar },
        { nome: "Resultado nominal", valores: neg(S.nfsp_nominal), tipo: "line", cor: COR.vermelho }] } },
      { t: "Resultado primário por esfera em 12 meses (% do PIB)", info: "fiscal_esferas", op: { eixoEsq: "pctPronto", series: [
        // barras empilhadas precisam das mesmas datas: todas alinhadas pelo total (desde nov/2002), com o sinal invertido
        { nome: "Governo Federal e Banco Central", valores: alinhar(S.nfsp_primario, ["nfsp_primario_central"]).map(([d, v]) => [d, -v]), cor: COR.azul, pilha: "esfera" },
        { nome: "Estados e municípios", valores: alinhar(S.nfsp_primario, ["nfsp_primario_regionais"]).map(([d, v]) => [d, -v]), cor: COR.roxo, pilha: "esfera" },
        { nome: "Empresas estatais", valores: alinhar(S.nfsp_primario, ["nfsp_primario_estatais"]).map(([d, v]) => [d, -v]), cor: COR.ciano, pilha: "esfera" },
        { nome: "Total (setor público consolidado)", valores: neg(S.nfsp_primario), tipo: "line", cor: COR.ambar }] } },
      { t: "Prazo médio da dívida mobiliária federal (meses)", info: "fiscal_prazo", op: { eixoEsq: "numero", series: [
        { nome: "Prazo médio dos títulos emitidos", valores: P(S.dmf_prazo), tipo: "line", cor: COR.ambar }] } },
      // áreas empilhadas alinhadas mês a mês (as quatro faixas somam 100%)
      { t: "Composição da dívida mobiliária federal por indexador (% do estoque)", info: "fiscal_dmf", largo: true, op: { eixoEsq: "pctPronto", limitesEsq: [0, 100], series: [
        { nome: "Selic (LFT)", valores: alinhar(S.dmf_ipca, ["dmf_selic"]), tipo: "line", area: true, cor: COR.azul, pilha: "dmf" },
        { nome: "Prefixado (LTN, NTN-F)", valores: alinhar(S.dmf_ipca, ["dmf_pre"]), tipo: "line", area: true, cor: COR.verde, pilha: "dmf" },
        { nome: "IPCA (NTN-B)", valores: alinhar(S.dmf_ipca, ["dmf_ipca"]), tipo: "line", area: true, cor: COR.vermelho, pilha: "dmf" },
        { nome: "Câmbio, IGP-M, TR e outros", valores: alinhar(S.dmf_ipca, ["dmf_cambio", "dmf_igpm", "dmf_igpdi", "dmf_tr", "dmf_tjlp", "dmf_outros"]), tipo: "line", area: true, cor: COR.cinza, pilha: "dmf" }] } },
    ]) : defsFiscal(ABA_FISCAL),
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
  if (sub === "fiscal" && fis) {  // tabelas da Política fiscal no fim da aba
    if (ABA_FISCAL === "arrecadacao") area.insertAdjacentHTML("beforeend", tabelaTributos(S));
    if (ABA_FISCAL === "endividamento") area.insertAdjacentHTML("beforeend",
      tabelaEntes(fis.estados, "Estados", "fiscal_estados", 200, 49) + tabelaEntes(fis.capitais, "Capitais", "fiscal_capitais", 120, 54));
  }
  if (sub === "externo" && ext && ext.comex && ext.comex.produtos) {  // tabela logo abaixo do gráfico de produtos
    const graf = document.getElementById(`gm-${defs.findIndex((d) => d.info === "externo_produtos")}`);
    (graf ? graf.closest(".painel") : area.lastElementChild).insertAdjacentHTML("afterend", tabelaProdutosExterno(ext.comex));
  }
  area.querySelectorAll("[data-alt]").forEach((sel) => sel.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    const i = Number(sel.dataset.alt);
    ESCOLHA_GRAFICO[defs[i].t] = b.dataset.k;
    sel.querySelectorAll("button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenhar(i);
  }));
}

// Política fiscal: cartões de Arrecadação e Despesas (valores do RTN e da Receita em R$ milhões)
function cartoesFiscal(S, u, mes) {
  const r = (k) => (u(k).valor != null ? reais(u(k).valor * 1e6) : "—");
  const parte = (a, b) => (u(a).valor != null && u(b).valor ? pct(u(a).valor / u(b).valor) : "—");
  if (ABA_FISCAL === "arrecadacao") return [
    cartao("Arrecadação federal 12m", r("arr_total_12m"), `Receita Federal · até ${mes("arr_total_12m")}`),
    cartao("Arrecadação em % do PIB", pctPronto(u("arr_total_12m_pib").valor, 1), `12 meses · ${mes("arr_total_12m_pib")}`),
    cartao("Crescimento real 12m", pctPronto(u("arr_total_cresc_real").valor, 1), "acima do IPCA, contra 12 meses antes"),
    cartao("Arrecadação no mês", r("arr_total"), mes("arr_total")),
    cartao("Imposto de Renda", parte("arr_ir_12m", "arr_total_12m"), "da arrecadação de 12 meses"),
    cartao("Dividendos de estatais 12m", r("rtn_dividendos_12m"), `pagos à União · ${mes("rtn_dividendos_12m")}`)];
  return [
    cartao("Despesa do Governo Central 12m", r("rtn_despesa_total_12m"), `Tesouro (RTN) · até ${mes("rtn_despesa_total_12m")}`),
    cartao("Despesa em % do PIB", pctPronto(u("rtn_despesa_total_12m_pib").valor, 1), `12 meses · ${mes("rtn_despesa_total_12m_pib")}`),
    cartao("Previdência", parte("rtn_previdencia_12m", "rtn_despesa_total_12m"), "da despesa de 12 meses"),
    cartao("Discricionárias 12m", r("rtn_discricionarias_12m"), "do Poder Executivo"),
    cartao("Resultado primário 12m", pctPronto(u("rtn_resultado_central_12m_pib").valor, 2), "% do PIB · Governo Central"),
    cartao("Investimento federal 12m", r("rtn_investimento_12m"), `${pctPronto(u("rtn_investimento_12m_pib").valor, 2)} do PIB`)];
}

function tabelaTributos(S) {
  const ult = (k) => (S[k] && S[k].valores.length ? S[k].valores[S[k].valores.length - 1] : null);
  const tot = ult("arr_total_12m");
  const linhas = [["arr_total", "Arrecadação federal total", true], ["arr_ir", "Imposto de Renda"], ["ir_irpf", "· IRPF (pessoa física)"],
    ["ir_irpj", "· IRPJ (empresas)"], ["ir_irrf_trabalho", "· IRRF — trabalho"], ["ir_irrf_capital", "· IRRF — capital"],
    ["ir_irrf_exterior", "· IRRF — remessas ao exterior"], ["ir_irrf_outros", "· IRRF — outros"], ["arr_previdencia", "Previdência (RGPS)"],
    ["arr_cofins", "Cofins"], ["arr_pis", "PIS/Pasep"], ["arr_csll", "CSLL"], ["arr_ipi", "IPI"], ["arr_comercio", "Importação e exportação"],
    ["arr_iof", "IOF"], ["arr_outros_orgaos", "Administradas por outros órgãos"], ["arr_outros", "Demais"]].filter(([k]) => S[k]);
  const bi = (v) => (v == null ? "—" : num(v / 1000, 1));
  const ref = S.arr_total ? S.arr_total.datas[S.arr_total.datas.length - 1] : null;
  return `<div class="painel largo" data-info="fiscal_tributos"><h2>Arrecadação federal por tributo — R$ bilhões · ${mesAno(ref)}</h2><div class="rolagem"><table class="tabela">
    <tr><th style="text-align:left">Tributo</th><th>No mês</th><th>12 meses</th><th>% do total</th><th>Crescimento real 12m</th></tr>
    ${linhas.map(([k, nome, negrito]) => { const c = ult(`${k}_cresc_real`); return `<tr${negrito ? ' style="font-weight:700"' : ""}><td style="text-align:left">${esc(nome)}</td>
      <td>${bi(ult(k))}</td><td>${bi(ult(`${k}_12m`))}</td><td>${tot ? pct(ult(`${k}_12m`) / tot) : "—"}</td>
      <td>${c == null ? "—" : `<span class="${classeSinal(c)}">${num(c, 1)}%</span>`}</td></tr>`; }).join("")}
  </table></div><div class="nota">Crescimento real: 12 meses a preços de hoje (corrigidos pelo IPCA) contra os 12 meses anteriores.
    Fonte: Receita Federal — Arrecadação das receitas federais (dados abertos); IPCA do IBGE pelo Banco Central.</div></div>`;
}

// Estados ou capitais: dívida consolidada líquida e despesa com pessoal do Poder Executivo (RGF, último quadrimestre publicado)
function tabelaEntes(lista, titulo, info, limiteDcl, limitePessoal) {
  if (!lista || !lista.length) return "";
  const bi = (v) => (v == null ? "—" : num(v / 1e9, 1));
  const alerta = (v, lim) => (v == null ? "" : v >= lim ? "neg" : v >= lim * 0.9 ? "atencao" : "");
  const per = (p) => (p ? `${p.slice(5, 6)}º quad./${p.slice(0, 4)}` : "—");
  return `<div class="painel largo" data-info="${info}"><h2>${titulo} — dívida e gasto com pessoal (Relatório de Gestão Fiscal)</h2><div class="rolagem"><table class="tabela">
    <tr><th style="text-align:left">${titulo === "Estados" ? "UF" : "Capital"}</th><th>Período</th><th>Dívida consolidada líquida (R$ bi)</th>
      <th>Receita corrente líquida (R$ bi)</th><th>DCL / RCL</th><th>Pessoal do Executivo / RCL</th></tr>
    ${lista.map((e) => `<tr><td style="text-align:left">${esc(e.nome)}</td><td class="sub">${per(e.periodo)}</td><td>${bi(e.dcl)}</td><td>${bi(e.rcl)}</td>
      <td><span class="${alerta(e.dcl_rcl, limiteDcl)}">${e.dcl_rcl == null ? "—" : `${num(e.dcl_rcl, 1)}%`}</span></td>
      <td><span class="${alerta(e.pessoal_rcl, limitePessoal)}">${e.pessoal_rcl == null ? "—" : `${num(e.pessoal_rcl, 1)}%`}</span></td></tr>`).join("")}
  </table></div><div class="nota">Limites da Lei de Responsabilidade Fiscal e do Senado: dívida consolidada líquida até ${limiteDcl}% da receita corrente líquida;
    pessoal do Poder Executivo até ${limitePessoal}% (em vermelho, acima do limite; em amarelo, a partir de 90% dele). DCL negativa = caixa maior que a dívida.
    Fonte: Tesouro Nacional — SICONFI, Relatório de Gestão Fiscal (anexos 1 e 2).</div></div>`;
}

// Setor externo: cartões e tabela de produtos (US$ milhões)
function cartoesExterno(S, u, mes) {
  const bi = (x) => (x == null ? "—" : `US$ ${num(x / 1000, 1)} bi`);
  const ult12 = (s) => (s && s.valores.length >= 12 ? s.valores.slice(-12).reduce((a, b) => a + b, 0) : null);
  const ant12 = (s) => (s && s.valores.length >= 24 ? s.valores.slice(-24, -12).reduce((a, b) => a + b, 0) : null);
  const e12 = ult12(S.cx_exportacoes), i12 = ult12(S.cx_importacoes), eAnt = ant12(S.cx_exportacoes);
  return [
    cartao("Transações correntes 12m", pctPronto(u("tc_pib").valor, 1), `do PIB · ${bi(u("tc_12m").valor)} · ${mes("tc_pib")}`),
    cartao("Investimento direto 12m", pctPronto(u("idp_pib").valor, 1), `do PIB · ${bi(u("idp_12m").valor)}`),
    cartao("Balança comercial 12m", bi(e12 != null && i12 != null ? e12 - i12 : null), `Comex Stat · até ${mes("cx_exportacoes")}`),
    cartao("Exportações 12m", bi(e12), eAnt ? `${num((e12 / eAnt - 1) * 100, 1)}% contra 12 meses antes` : ""),
    cartao("Reservas internacionais", bi(u("reservas").valor), "conceito liquidez"),
    cartao("Estrangeiros em ações 12m", bi(u("carteira_acoes_12m").valor), "investimento em carteira, líquido"),
  ];
}
function tabelaProdutosExterno(C) {
  const tot = C.exportacoes ? C.exportacoes.valores.slice(-12).reduce((a, b) => a + b, 0) : null;
  const linhas = Object.values(C.produtos).map((p) => {
    const v = p.valores, s12 = v.slice(-12).reduce((a, b) => a + b, 0), a12 = v.length >= 24 ? v.slice(-24, -12).reduce((a, b) => a + b, 0) : null;
    return { nome: p.nome, cod: p.codigo, mes: v[v.length - 1], data: p.datas[p.datas.length - 1], s12, var: a12 ? s12 / a12 - 1 : null, part: tot ? s12 / tot : null };
  }).sort((a, b) => b.s12 - a.s12);
  return `<div class="painel largo" data-info="externo_produtos"><h2>Principais produtos exportados — US$ milhões</h2><div class="rolagem"><table class="tabela">
    <tr><th style="text-align:left">Produto</th><th>SH</th><th>Último mês</th><th>12 meses</th><th>% das exportações</th><th>Var. 12m</th></tr>
    ${linhas.map((l) => `<tr><td style="text-align:left">${esc(l.nome)}</td><td class="sub">${l.cod}</td><td>${num(l.mes, 0)} <span class="sub">${mesAno(l.data)}</span></td>
      <td>${num(l.s12, 0)}</td><td>${pct(l.part)}</td><td>${l.var == null ? "—" : `<span class="${classeSinal(l.var)}">${num(l.var * 100, 1)}%</span>`}</td></tr>`).join("")}
  </table></div><div class="nota">Valor FOB das exportações, pela posição de 4 dígitos do Sistema Harmonizado (SH). Var. 12m = últimos 12 meses contra os 12 anteriores.
    Fonte: Comex Stat (Ministério do Desenvolvimento, Indústria, Comércio e Serviços).</div></div>`;
}

// Cartões da aba Crédito (saldo em R$ milhões no SGS)
function cartoesCredito(S, u, mes) {
  const g = ABA_CREDITO, k = (b) => (g === "total" ? `${b}_total` : `${b}_${g}`);
  const tri = (x) => (x == null ? "—" : reais(x * 1e6));
  const base = [
    cartao("Saldo da carteira", tri(u(k("saldo")).valor), `${mes(k("saldo"))} · ${pctPronto(u(`${k("saldo")}_12m`).valor, 1)} em 12 meses`),
    cartao("Crédito / PIB", pctPronto(u(k("pib")).valor, 1), mes(k("pib"))),
    cartao("Taxa média de juros", pctPronto(u(k("taxa")).valor, 1), "a.a. · crédito novo"),
    cartao("Spread", `${num(u(k("spread")).valor, 1)} p.p.`, "taxa − custo de captação"),
    cartao("Inadimplência", pctPronto(u(k("inad")).valor, 2), "atraso acima de 90 dias"),
  ];
  if (g === "pf") base.push(cartao("Endividamento das famílias", pctPronto(u("endiv").valor, 1), `% da renda · ${mes("endiv")}`),
    cartao("Comprometimento de renda", pctPronto(u("compr").valor, 1), "com o serviço da dívida"));
  else base.push(cartao("Concessões no mês", tri(u(`${k("conc")}_sa`).valor), "dessazonalizadas"));
  return base;
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
        <div class="nota">Clique num título para ver o histórico oficial de taxa e preço no gráfico abaixo.</div></div>
      <div data-info="titulos" class="painel largo" id="painel-titulo"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0" id="titulo-hist">Taxa × preço</h2>
        <label class="sub">Título: <select id="sel-titulo" class="filtro" style="width:auto;display:inline-block">
          ${GRUPOS_TESOURO.filter(([tipo]) => tes.titulos.some((t) => t.tipo === tipo)).map(([tipo, nome]) => `<optgroup label="${esc(nome)}">
            ${tes.titulos.filter((t) => t.tipo === tipo).map((t) => `<option value="${esc(t.id)}">${esc(t.tipo)} ${dataBR(t.vencimento)}</option>`).join("")}</optgroup>`).join("")}
        </select></label></div>
        <div class="grafico alto" id="gj-hist"></div>
        <div class="nota">Histórico oficial (Tesouro Transparente) da taxa de compra e do preço unitário (PU) de compra da manhã, desde o lançamento do título.
          Taxa e preço andam em sentidos opostos: taxa sobe, preço cai (e vice-versa).</div></div>
    </div>
    <div class="nota secao">A curva DI vem do arquivo "Taxas de Mercado para Swaps" da B3 (fim de dia). As curvas do Tesouro usam a taxa de compra
      do Tesouro Direto: título sem cupom e, nos prazos onde ele não existe, o título com juros semestrais. A inflação implícita é calculada nos
      vencimentos do IPCA+ e dos prefixados onde as duas curvas existem, interpolando a outra curva, sem extrapolar.</div>`;

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

  // Gráfico taxa × preço sempre visível; o título vem do seletor ou de um clique na tabela
  let gHist = null;
  const sel = document.getElementById("sel-titulo");
  const desenharTitulo = async (id, rolar = false) => {
    const t = await dados(`dados/tesouro/${id}.json`).catch(() => null);
    if (!t) { document.getElementById("gj-hist").innerHTML = `<p class="sub">Histórico indisponível para este título.</p>`; return; }
    sel.value = id;
    document.getElementById("titulo-hist").textContent = `Taxa × preço · ${t.tipo} ${dataBR(t.vencimento)} — oficial`;
    if (gHist) { gHist.dispose(); graficos.splice(graficos.indexOf(gHist), 1); }
    gHist = grafico(document.getElementById("gj-hist"), { xTempo: true, eixoEsq: "preco", eixoDir: "pctPronto", series: [
      { nome: "PU compra (R$)", valores: t.datas.map((d, i) => [d, t.pu_compra[i] || null]), tipo: "line", cor: COR.azul },
      { nome: "Taxa compra (% a.a.)", valores: t.datas.map((d, i) => [d, t.taxa_compra[i] || null]), tipo: "line", eixo: "dir", cor: COR.ambar }] });
    if (rolar) document.getElementById("painel-titulo").scrollIntoView({ behavior: "smooth", block: "center" });
  };
  sel.addEventListener("change", () => desenharTitulo(sel.value));
  document.getElementById("tab-tit").addEventListener("click", (ev) => {
    const tr = ev.target.closest("[data-id]"); if (tr) desenharTitulo(tr.dataset.id, true);
  });
  // começa no IPCA+ mais longo sem cupom (ou no primeiro da lista)
  const ipcaLongo = tes.titulos.filter((t) => t.tipo === "Tesouro IPCA+").slice(-1)[0];
  if (sel.options.length) desenharTitulo(ipcaLongo ? ipcaLongo.id : sel.options[0].value);
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
  const itens = [...marcar(nOn, "Brasil"), ...marcar(nOff, "Mundo")].sort((a, b) => b.data.localeCompare(a.data));
  const agenda = { eventos: [...((aOn && aOn.eventos) || []), ...((aOff && aOff.eventos) || [])].sort((a, b) => a.data.localeCompare(b.data)) };
  const categorias = { ...(quer("on") ? CATEGORIAS_AGENDA : {}), ...(quer("off") ? CATEGORIAS_OFF : {}) };
  const fontes = (tipo) => [...new Set(itens.filter((n) => n.tipo === tipo).map((n) => n.fonte))].sort();
  const filtros = [["todas", "Todas"], ["tipo:mercado", "Mercado"], ["tipo:oficial", "Oficiais"]];
  let filtro = "tipo:mercado", janela = 30, categoria = "todos", editoria = "todas", origem = "tudo";
  // Consolidado: botões para separar as notícias do Brasil e do Mundo
  const ORIGENS = [["tudo", "Tudo"], ["Brasil", "Brasil"], ["Mundo", "Mundo"]];
  const EDITORIAS = [["todas", "Todas"], ["politica", "Política"], ["economia", "Economia e finanças"], ["empresas", "Empresas"]];
  const comEditoria = lado !== "off";
  const titulo = { on: "Notícias e agenda", off: "Mundo · Notícias e agenda", cons: "Consolidado · Notícias e agenda" }[lado];
  const jornais = { on: "Valor Econômico, Folha, Estadão, Brazil Journal e InfoMoney", off: "WSJ, Financial Times, CNBC, MarketWatch, The Guardian e BBC",
    cons: "jornais do Brasil e do exterior" }[lado];
  const oficiais = { on: "Banco Central, IBGE, CVM e Agência Brasil", off: "Federal Reserve e BCE", cons: "Banco Central, IBGE, CVM, Agência Brasil, Fed e BCE" }[lado];
  // Agenda em cima e notícias embaixo, cada uma na largura toda e mais alta (Brasil, Mundo e Consolidado)
  const painelNoticias = `
      <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Notícias</h2>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${lado === "cons" ? `<div class="seletor seletor-editoria" id="filtro-origem">${ORIGENS.map(([k, r]) => `<button data-k="${k}" class="${k === origem ? "ativo" : ""}">${r}</button>`).join("")}</div>` : ""}
        ${comEditoria ? `<div class="seletor seletor-editoria" id="filtro-editoria">${EDITORIAS.map(([k, r]) => `<button data-k="${k}" class="${k === editoria ? "ativo" : ""}">${r}</button>`).join("")}</div>` : ""}</div></div>
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
        <div class="nota">Datas oficiais${quer("on") ? " do Banco Central, IBGE e FGV" : ""}${lado === "cons" ? " e" : ""}${quer("off") ? " do Fed, do BCE, do FRED (divulgações dos EUA) e do Eurostat" : ""}; podem mudar.
          Horários convertidos para Brasília.</div></div>`;
  app.innerHTML = `
    <div class="cabecalho"><div><h1>${titulo}</h1><div class="sub">Notícias de mercado (${jornais}) e oficiais (${oficiais}) · só a manchete, com link para a fonte</div></div></div>
    ${lado === "on" ? abasNoticiasOn("", await eleicoesAtivas()) : ""}
    <div class="grade grade-empilhada">${painelAgenda}${painelNoticias}</div>`;
  const passa = (n) => {
    if (lado === "cons" && origem !== "tudo" && n.origem !== origem) return false;
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
  if (lado === "cons") seletor("filtro-origem", (b) => { origem = b.dataset.k; desenharNoticias(); });
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
};
const CATEGORIAS_OFF = { fed: ["Fed", COR.verde], bce: ["BCE", COR.roxo], eua: ["EUA (dados)", COR.azul], europa: ["Europa (dados)", COR.ciano] };
const SUBS_MACRO_OFF = [["global", "Global"], ["mercados", "Mercados"], ["eua", "Estados Unidos"], ["euro", "Europa (Zona do Euro)"], ["china", "China"]];
// Abas internas de cada país (mesma organização da seção Brasil)
const ABAS_PAIS_OFF = [["atividade", "Atividade"], ["inflacao", "Inflação"], ["emprego", "Emprego"], ["monetaria", "Política monetária"]];
let ABA_PAIS_OFF = "atividade";

function desenharPaisOff(pais, off, cab, abas, mundo = null) {
  const B = off.bls || {}, R = off.fred || {}, F = off.fed || {}, E = off.bce || {}, Z = off.eurostat || {};
  const C = (mundo && mundo.china) || {};
  const u = (x) => ultimo(x);
  const mes = (x) => (u(x).data ? `${MESES[Number(u(x).data.slice(5, 7)) - 1]}/${u(x).data.slice(2, 4)}` : "");
  const tri = (x) => (u(x).data ? `${Math.ceil(Number(u(x).data.slice(5, 7)) / 3)}º tri/${u(x).data.slice(0, 4)}` : "");
  const t = (anos = 10, extra = {}) => ({ xTempo: true, inicioTempo: desde(anos), deslizante: true, eixoEsq: "pctPronto", ...extra });
  const meta = (x, v, nome) => ({ nome, valores: x && x.datas ? x.datas.map((d) => [d, v]) : [], tipo: "line", cor: COR.cinza, tracejado: true });
  const semFred = pais === "eua" && !off.fred;
  // cada aba: { fonte, cartoes, graficos: [{ id, t, info, largo, op }] }
  const D = pais === "china" ? {
    atividade: { fonte: "OCDE (dados do NBS)",
      cartoes: [cartao("PIB contra um ano antes", pctPronto(u(C.pib_12m).valor, 1), tri(C.pib_12m)), cartao("PIB tri/tri (dessaz.)", pctPronto(u(C.pib_tri).valor, 1), tri(C.pib_tri)),
        cartao("Exportações 12m", pctPronto(u(C.exportacoes_12m).valor, 1), `em dólares · ${mes(C.exportacoes_12m)}`), cartao("Importações 12m", pctPronto(u(C.importacoes_12m).valor, 1), mes(C.importacoes_12m)),
        cartao("Indicador antecedente", u(C.antecedente).valor != null ? num(u(C.antecedente).valor, 1) : "—", `OCDE · 100 = tendência · ${mes(C.antecedente)}`)],
      graficos: [
        { t: "PIB", info: "pib_china", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Tri/tri (dessaz.)", valores: Pares(C.pib_tri), cor: COR.azul }, { nome: "Contra o mesmo tri do ano anterior", valores: Pares(C.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] }) },
        { t: "Comércio exterior: exportações e importações (12 meses, em dólares)", info: "comercio_china", op: t(10, { series: [
          { nome: "Exportações", valores: Pares(C.exportacoes_12m), tipo: "line", cor: COR.verde }, { nome: "Importações", valores: Pares(C.importacoes_12m), tipo: "line", cor: COR.vermelho }] }) },
        { t: "Produção industrial e varejo (12 meses) — série interrompida", info: "descontinuada_china", aviso: true, op: t(3, { series: [
          { nome: "Valor adicionado da indústria", valores: Pares(C.producao_12m), tipo: "line", cor: COR.azul },
          { nome: "Vendas no varejo", valores: Pares(C.varejo_12m), tipo: "line", cor: COR.verde }] }) },
        { t: "Indicador antecedente e confiança", info: "antecedente_china", op: t(10, { eixoEsq: "numero", eixoDir: "numero", series: [
          { nome: "Indicador antecedente (OCDE, 100 = tendência)", valores: Pares(C.antecedente), tipo: "line", cor: COR.ambar },
          { nome: "Confiança do consumidor", valores: Pares(C.confianca_consumidor), tipo: "line", eixo: "dir", cor: COR.azul },
          { nome: "Confiança das empresas (saldo)", valores: Pares(C.confianca_empresas), tipo: "line", eixo: "dir", cor: COR.verde, tracejado: true }] }) }] },
    inflacao: { fonte: "OCDE (dados do NBS)",
      cartoes: [cartao("CPI 12 meses", pctPronto(u(C.cpi_12m).valor, 1), `meta do governo ~3% · ${mes(C.cpi_12m)}`), cartao("CPI no mês", pctPronto(u(C.cpi_mensal).valor, 1), mes(C.cpi_mensal))],
      graficos: [{ t: "Inflação ao consumidor (CPI)", info: "cpi_china", largo: true, op: t(10, { eixoDir: "pctPronto", series: [
        { nome: "Mensal", valores: Pares(C.cpi_mensal), cor: COR.azul }, { nome: "12 meses", valores: Pares(C.cpi_12m), tipo: "line", eixo: "dir", cor: COR.vermelho }] }) }] },
    emprego: { fonte: "NBS via DBnomics (série interrompida)",
      cartoes: [cartao("Desemprego urbano", pctPronto(u(C.desemprego).valor, 1), `último dado: ${mes(C.desemprego)}`),
        cartao("Desemprego 16–24 anos", pctPronto(u(C.desemprego_jovens).valor, 1), `último dado: ${mes(C.desemprego_jovens)}`)],
      graficos: [{ t: "Desemprego urbano (pesquisa) — série interrompida", info: "descontinuada_china", aviso: true, largo: true, op: t(3, { series: [
        { nome: "Total", valores: Pares(C.desemprego), tipo: "line", cor: COR.vermelho },
        { nome: "16 a 24 anos (eixo direito)", valores: Pares(C.desemprego_jovens), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoDir: "pctPronto" }) }] },
    monetaria: { fonte: "OCDE",
      cartoes: [cartao("Juros curtos (3 meses)", pctPronto(u(C.juros_curto).valor), `interbancário · ${mes(C.juros_curto)}`), cartao("Juros longos (10 anos)", pctPronto(u(C.juros_longo).valor), mes(C.juros_longo)),
        cartao("Câmbio", u(C.cambio).valor != null ? `¥ ${num(u(C.cambio).valor, 2)}` : "—", `yuans por dólar · ${mes(C.cambio)}`)],
      graficos: [
        { t: "Juros: curto (interbancário 3 meses) e longo (10 anos)", info: "juros_china", op: t(10, { series: [
          { nome: "Curto prazo (3 meses)", valores: Pares(C.juros_curto), tipo: "line", cor: COR.ambar }, { nome: "Longo prazo (10 anos)", valores: Pares(C.juros_longo), tipo: "line", cor: COR.azul }] }) },
        { t: "Câmbio: yuans por dólar", info: "cambio_china", op: t(10, { eixoEsq: "preco", series: [
          { nome: "CNY por US$", valores: Pares(C.cambio), tipo: "line", cor: COR.verde }] }) }] },
  } : pais === "eua" ? {
    atividade: { fonte: "FRED (BEA, Fed, Census, Universidade de Michigan)",
      cartoes: [cartao("PIB tri/tri anualizado", pctPronto(u(R.pib_tri_anual).valor, 1), tri(R.pib_tri_anual)),
        cartao("PIB contra um ano antes", pctPronto(u(R.pib_12m).valor, 1), tri(R.pib_12m)),
        cartao("Produção industrial 12m", pctPronto(u(R.producao_12m).valor, 1), mes(R.producao_12m)),
        cartao("Varejo 12m", pctPronto(u(R.varejo_12m).valor, 1), mes(R.varejo_12m)),
        cartao("Confiança do consumidor", u(R.confianca).valor != null ? num(u(R.confianca).valor, 1) : "—", `Michigan · ${mes(R.confianca)}`)],
      graficos: [
        { t: "PIB real", info: "pib_eua", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Tri/tri anualizado (dessaz.)", valores: Pares(R.pib_tri_anual), cor: COR.azul },
          { nome: "Contra o mesmo tri do ano anterior", valores: Pares(R.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] }) },
        { t: "Produção industrial", info: "producao_eua", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Mensal (dessaz.)", valores: Pares(R.producao_mensal), cor: COR.azul },
          { nome: "12 meses", valores: Pares(R.producao_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] }) },
        { t: "Vendas no varejo (nominal)", info: "varejo_eua", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Mensal (dessaz.)", valores: Pares(R.varejo_mensal), cor: COR.azul },
          { nome: "12 meses", valores: Pares(R.varejo_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] }) },
        { t: "Confiança do consumidor (Universidade de Michigan)", info: "confianca_eua", op: t(10, { eixoEsq: "numero", series: [
          { nome: "Índice de sentimento do consumidor", valores: Pares(R.confianca), tipo: "line", cor: COR.verde }] }) }] },
    inflacao: { fonte: "BLS (CPI) e FRED (PCE, do BEA)",
      cartoes: [cartao("CPI 12 meses", pctPronto(u(B.cpi_12m).valor), mes(B.cpi_12m)), cartao("Núcleo do CPI 12m", pctPronto(u(B.cpi_nucleo_12m).valor), mes(B.cpi_nucleo_12m)),
        cartao("PCE 12 meses", pctPronto(u(R.pce_12m).valor), `meta do Fed 2% · ${mes(R.pce_12m)}`), cartao("Núcleo do PCE 12m", pctPronto(u(R.pce_nucleo_12m).valor), mes(R.pce_nucleo_12m))],
      graficos: [
        { t: "Inflação ao consumidor (CPI)", info: "cpi_eua", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Mensal (dessaz.)", valores: Pares(B.cpi_mensal), cor: COR.azul }, { nome: "12 meses", valores: Pares(B.cpi_12m), tipo: "line", eixo: "dir", cor: COR.vermelho },
          { nome: "Núcleo 12 meses", valores: Pares(B.cpi_nucleo_12m), tipo: "line", eixo: "dir", cor: COR.ambar, tracejado: true }] }) },
        { t: "Inflação do PCE (a medida da meta do Fed)", info: "pce_eua", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Mensal", valores: Pares(R.pce_mensal), cor: COR.azul }, { nome: "12 meses", valores: Pares(R.pce_12m), tipo: "line", eixo: "dir", cor: COR.vermelho },
          { nome: "Núcleo 12 meses", valores: Pares(R.pce_nucleo_12m), tipo: "line", eixo: "dir", cor: COR.ambar, tracejado: true }] }) },
        { t: "Núcleos em 12 meses: CPI × PCE e a meta de 2%", info: "pce_eua", largo: true, op: t(10, { series: [
          { nome: "Núcleo do CPI", valores: Pares(B.cpi_nucleo_12m), tipo: "line", cor: COR.vermelho },
          { nome: "Núcleo do PCE", valores: Pares(R.pce_nucleo_12m), tipo: "line", cor: COR.ambar }, meta(R.pce_nucleo_12m, 2, "Meta do Fed (2%)")] }) }] },
    emprego: { fonte: "BLS",
      cartoes: [cartao("Desemprego", pctPronto(u(B.desemprego).valor, 1), mes(B.desemprego)),
        cartao("Payroll (vagas no mês)", u(B.payroll_var).valor != null ? `${num(u(B.payroll_var).valor, 0)} mil` : "—", mes(B.payroll_var))],
      graficos: [
        { t: "Payroll: vagas criadas no mês (mil)", info: "emprego_eua", op: t(5, { eixoEsq: "numero", series: [
          { nome: "Payroll (mil vagas)", valores: Pares(B.payroll_var), cor: COR.verde }] }) },
        { t: "Taxa de desemprego", info: "emprego_eua", op: t(10, { series: [
          { nome: "Desemprego (dessaz.)", valores: Pares(B.desemprego), tipo: "line", cor: COR.vermelho }] }) }] },
    monetaria: { fonte: "Fed de Nova York, BLS e FRED",
      cartoes: [cartao("Fed Funds (meta)", `${pctPronto(u(F.meta_min).valor)}–${pctPronto(u(F.meta_max).valor)}`, "banda definida pelo FOMC"),
        cartao("Fed Funds efetivo", pctPronto(u(F.effr).valor), dataBR(u(F.effr).data)), cartao("SOFR", pctPronto(u(F.sofr).valor), dataBR(u(F.sofr).data)),
        cartao("Juro real (núcleo do PCE)", (() => { const j = R.pce_nucleo_12m ? juroReal(F.meta_max, R.pce_nucleo_12m) : []; return j.length ? pctPronto(j[j.length - 1][1], 1) : "—"; })(), "teto da banda ÷ núcleo do PCE 12m")],
      graficos: [
        { t: "Fed Funds: banda da meta, efetivo e SOFR", info: "fed_funds", op: t(10, { degrau: true, series: [
          { nome: "Teto da banda", valores: ateHoje(F.meta_max), tipo: "line", cor: COR.vermelho }, { nome: "Piso da banda", valores: ateHoje(F.meta_min), tipo: "line", cor: COR.azul },
          { nome: "Fed Funds efetivo", valores: Pares(F.effr), tipo: "line", cor: COR.ambar }, { nome: "SOFR", valores: Pares(F.sofr), tipo: "line", cor: COR.cinza, tracejado: true }] }) },
        { t: "Juro real ex-post", info: "juro_real_eua", op: t(10, { series: [
          { nome: "Teto da banda ÷ CPI 12m", valores: B.cpi_12m ? juroReal(F.meta_max, B.cpi_12m) : [], tipo: "line", cor: COR.vermelho },
          { nome: "Teto da banda ÷ núcleo do PCE 12m", valores: R.pce_nucleo_12m ? juroReal(F.meta_max, R.pce_nucleo_12m) : [], tipo: "line", cor: COR.ambar }] }) }] },
  } : {
    atividade: { fonte: "Eurostat",
      cartoes: [cartao("PIB tri/tri", pctPronto(u(Z.pib_tri).valor, 1), tri(Z.pib_tri)), cartao("PIB contra um ano antes", pctPronto(u(Z.pib_12m).valor, 1), tri(Z.pib_12m)),
        cartao("Produção industrial 12m", pctPronto(u(Z.producao_12m).valor, 1), mes(Z.producao_12m)), cartao("Varejo 12m (volume)", pctPronto(u(Z.varejo_12m).valor, 1), mes(Z.varejo_12m))],
      graficos: [
        { t: "PIB", info: "pib_euro", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Tri/tri (dessaz.)", valores: Pares(Z.pib_tri), cor: COR.azul }, { nome: "Contra o mesmo tri do ano anterior", valores: Pares(Z.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] }) },
        { t: "Produção industrial (sem construção)", info: "producao_euro", op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Mensal (dessaz.)", valores: Pares(Z.producao_mensal), cor: COR.azul }, { nome: "12 meses (ajustado por dias úteis)", valores: Pares(Z.producao_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] }) },
        { t: "Vendas no varejo (volume)", info: "varejo_euro", largo: true, op: t(10, { eixoDir: "pctPronto", series: [
          { nome: "Mensal (dessaz.)", valores: Pares(Z.varejo_mensal), cor: COR.azul }, { nome: "12 meses (ajustado por dias úteis)", valores: Pares(Z.varejo_12m), tipo: "line", eixo: "dir", cor: COR.ambar }] }) }] },
    inflacao: { fonte: "Eurostat",
      cartoes: [cartao("HICP 12 meses", pctPronto(u(Z.hicp_12m).valor, 1), `meta do BCE 2% · ${mes(Z.hicp_12m)}`),
        cartao("Núcleo 12m", pctPronto(u(Z.hicp_nucleo_12m).valor, 1), "sem energia, alimentos, álcool e fumo"), cartao("Serviços 12m", pctPronto(u(Z.hicp_servicos_12m).valor, 1), mes(Z.hicp_servicos_12m))],
      graficos: [
        { t: "Inflação (HICP) — 12 meses", info: "hicp", largo: true, op: t(10, { series: [
          { nome: "Cheio", valores: Pares(Z.hicp_12m), tipo: "line", cor: COR.vermelho }, { nome: "Núcleo", valores: Pares(Z.hicp_nucleo_12m), tipo: "line", cor: COR.ambar },
          { nome: "Serviços", valores: Pares(Z.hicp_servicos_12m), tipo: "line", cor: COR.ciano, tracejado: true }, meta(Z.hicp_12m, 2, "Meta do BCE (2%)")] }) }] },
    emprego: { fonte: "Eurostat",
      cartoes: [cartao("Desemprego", pctPronto(u(Z.desemprego).valor, 1), mes(Z.desemprego))],
      graficos: [{ t: "Taxa de desemprego", info: "desemprego_euro", largo: true, op: t(10, { series: [
        { nome: "Desemprego (dessaz.)", valores: Pares(Z.desemprego), tipo: "line", cor: COR.vermelho }] }) }] },
    monetaria: { fonte: "BCE e Eurostat",
      cartoes: [cartao("Taxa de depósito", pctPronto(u(E.deposito).valor), "a de referência hoje"), cartao("Refinanciamento (MRO)", pctPronto(u(E.refinanciamento).valor), ""),
        cartao("€STR", pctPronto(u(E.estr).valor), dataBR(u(E.estr).data)),
        cartao("Juro real", (() => { const j = Z.hicp_12m ? juroReal(E.deposito, Z.hicp_12m) : []; return j.length ? pctPronto(j[j.length - 1][1], 1) : "—"; })(), "depósito ÷ HICP 12m")],
      graficos: [
        { t: "Taxas do BCE e €STR", info: "bce_juros", op: t(10, { degrau: true, series: [
          { nome: "Refinanciamento (MRO)", valores: ateHoje(E.refinanciamento), tipo: "line", cor: COR.vermelho }, { nome: "Depósito", valores: ateHoje(E.deposito), tipo: "line", cor: COR.azul },
          { nome: "€STR", valores: Pares(E.estr), tipo: "line", cor: COR.ambar }] }) },
        { t: "Juro real ex-post", info: "juro_real_euro", op: t(10, { series: [
          { nome: "Depósito ÷ HICP 12m", valores: Z.hicp_12m ? juroReal(E.deposito, Z.hicp_12m) : [], tipo: "line", cor: COR.ambar },
          { nome: "Depósito ÷ núcleo 12m", valores: Z.hicp_nucleo_12m ? juroReal(E.deposito, Z.hicp_nucleo_12m) : [], tipo: "line", cor: COR.vermelho, tracejado: true }] }) }] },
  };
  if (!D[ABA_PAIS_OFF]) ABA_PAIS_OFF = "atividade";
  const a = D[ABA_PAIS_OFF];
  const nomePais = { eua: "Estados Unidos", euro: "Europa (Zona do Euro)", china: "China" }[pais];
  const abasPais = ABAS_PAIS_OFF.filter(([k]) => D[k]);
  app.innerHTML = `${cab("Mundo · Macro", `${nomePais}: ${a.fonte} (APIs oficiais)`)}${abas}
    <div class="seletor seletor-editoria" id="sub-pais" style="margin:-4px 0 12px">${abasPais.map(([k, n]) => `<button data-k="${k}" class="${k === ABA_PAIS_OFF ? "ativo" : ""}">${n}</button>`).join("")}</div>

    ${semFred && ["atividade", "inflacao"].includes(ABA_PAIS_OFF) ? `<div class="aviso">Aguardando a primeira coleta do FRED (chave cadastrada; os dados entram na próxima atualização).</div>` : ""}
    <div class="grade-cartoes">${a.cartoes.join("")}</div>
    <div class="grade">${a.graficos.map((g, i) => painelG(`gp-${i}`, g.t, g.info, g.aviso ? `<div class="aviso" style="margin-top:8px">Sem continuidade: esta série vem do espelho
      gratuito dos dados oficiais da China (NBS, via DBnomics), que guarda só 13 meses e não é atualizado desde fev/2026. Não há outra fonte oficial
      gratuita em dia; os valores servem como referência histórica.</div>` : "", g.largo ? "largo" : "")).join("")}</div>`;
  a.graficos.forEach((g, i) => grafico(document.getElementById(`gp-${i}`), g.op));
  document.getElementById("sub-pais").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    ABA_PAIS_OFF = b.dataset.k;
    limparGraficos();
    desenharPaisOff(pais, off, cab, abas, mundo);
  });
}

// ---------- Mundo → Macro → Global (FMI, World Economic Outlook) ----------
let IND_GLOBAL = "NGDP_RPCH";
function desenharGlobal(mundo, cab, abas) {
  const G = mundo.global || {};
  // o PIB em US$ (NGDPD) e o per capita (NGDPDPC) são usados só no Consolidado
  const inds = Object.fromEntries(Object.entries(G.indicadores || {}).filter(([k]) => !["NGDPD", "NGDPDPC"].includes(k))), paises = G.paises || {};
  if (!inds[IND_GLOBAL]) IND_GLOBAL = Object.keys(inds)[0];
  const ind = inds[IND_GLOBAL];
  const ano = G.ano_corrente || new Date().getFullYear();
  const anosTab = [ano - 2, ano - 1, ano, ano + 1, ano + 2];
  // grupos como nos Juros (convenção dos índices de mercado: Coreia do Sul entre os emergentes; o FMI a trata como avançada)
  const GRUPOS_FMI = { desenvolvidos: ["USA", "EURO", "DEU", "FRA", "ITA", "JPN", "GBR", "CAN", "AUS", "CHE"],
    emergentes: ["BRA", "CHN", "IND", "MEX", "ARG", "CHL", "COL", "PER", "ZAF", "KOR", "IDN", "TUR", "SAU", "RUS"] };
  const NOMES_GRUPO = { desenvolvidos: "Desenvolvidos", emergentes: "Em desenvolvimento", mundo: "Mundo" };
  const anos = [...new Set(Object.values(ind.valores).flatMap((v) => Object.keys(v)))].sort();
  const regioes = ["WEOWORLD", "ADVEC", "OEMDC"];
  const linhaTab = (c, classe = "") => `<tr class="${classe}"><td style="text-align:left">${esc(paises[c])}</td>
    ${anosTab.map((a) => { const v = ind.valores[c][String(a)]; return `<td class="${a >= ano ? "sub" : ""}">${v == null ? "—" : num(v, 1)}</td>`; }).join("")}</tr>`;
  const blocoTab = (titulo, codigos) => { const cs = codigos.filter((c) => paises[c] && ind.valores[c]); return cs.length
    ? `<tr><th colspan="${anosTab.length + 1}" style="text-align:left;color:var(--ambar)">${titulo}</th></tr>${cs.map((c) => linhaTab(c)).join("")}` : ""; };
  const botoes = `<div class="seletor" id="grupos-global">${Object.entries(NOMES_GRUPO).map(([k, n]) =>
    `<button data-k="${k}" class="${GRUPOS_ATIVOS[k] ? "ativo" : ""}" title="Mostrar ou tirar do gráfico os países do grupo">${n}</button>`).join("")}</div>`;
  app.innerHTML = `${cab("Mundo · Macro", "Global: FMI — World Economic Outlook (projeções revistas em abril e outubro)")}${abas}
    <div class="seletor seletor-editoria" id="ind-global" style="margin:-4px 0 12px">${Object.entries(inds).map(([k, v]) => `<button data-k="${k}" class="${k === IND_GLOBAL ? "ativo" : ""}">${esc(v.nome)}</button>`).join("")}</div>
    <div class="grade">
      <div class="painel largo" data-info="global_fmi"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">${esc(ind.nome)} — por país</h2>${botoes}</div>
        <div class="grafico alto" id="gg-linhas"></div><div class="nota">A partir de ${ano} (inclusive), projeções do FMI. Clique no nome de um país na legenda para tirá-lo do gráfico.</div></div>
      <div class="painel largo" data-info="global_fmi"><h2>${esc(ind.nome)} por país</h2><div class="rolagem"><table class="tabela">
        <tr><th style="text-align:left">País / região</th>${anosTab.map((a) => `<th>${a}${a >= ano ? '<br><span class="sub">projeção</span>' : ""}</th>`).join("")}</tr>
        ${regioes.filter((c) => ind.valores[c]).map((c) => linhaTab(c, "subtotal")).join("")}
        ${blocoTab("Desenvolvidos", GRUPOS_FMI.desenvolvidos)}${blocoTab("Em desenvolvimento", GRUPOS_FMI.emergentes)}
      </table></div><div class="nota">Fonte: FMI, World Economic Outlook (DataMapper). Zona do Euro, Mundo e grupos de países são agregados do próprio FMI.</div></div>
    </div>`;
  const desenharLinhas = () => {
    const el = document.getElementById("gg-linhas"); const antigo = echarts.getInstanceByDom(el);
    if (antigo) { graficos.splice(graficos.indexOf(antigo), 1); antigo.dispose(); }
    const series = ["desenvolvidos", "emergentes"].flatMap((gr) => GRUPOS_FMI[gr].map((c) => [gr, c])).filter(([, c]) => ind.valores[c])
      .map(([gr, c], j) => [gr, { nome: paises[c], valores: anos.map((a) => ind.valores[c][a] ?? null), tipo: "line",
        cor: PALETA_GRAF[j % PALETA_GRAF.length], tracejado: gr === "emergentes" }])
      .filter(([gr]) => GRUPOS_ATIVOS[gr]).map(([, s]) => s);
    if (ind.valores.WEOWORLD && GRUPOS_ATIVOS.mundo) series.push({ nome: paises.WEOWORLD, valores: anos.map((a) => ind.valores.WEOWORLD[a] ?? null), tipo: "line", cor: COR.texto });
    grafico(el, { rotulos: anos, eixoEsq: "pctPronto", janela: 40, series });
    document.querySelectorAll("#grupos-global button").forEach((b) => b.classList.toggle("ativo", !!GRUPOS_ATIVOS[b.dataset.k]));
  };
  desenharLinhas();
  document.getElementById("grupos-global").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    const k = b.dataset.k;
    if (GRUPOS_ATIVOS[k] && Object.values(GRUPOS_ATIVOS).filter(Boolean).length === 1) return;  // pelo menos um grupo no gráfico
    GRUPOS_ATIVOS[k] = !GRUPOS_ATIVOS[k];
    desenharLinhas();
  });
  document.getElementById("ind-global").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    IND_GLOBAL = b.dataset.k; limparGraficos(); desenharGlobal(mundo, cab, abas);
  });
}

// ---------- Mundo → Macro → Mercados (FRED diário + Banco Mundial mensal) ----------
const ABAS_MERCADOS = [["acoes", "Ações e risco"], ["energia", "Petróleo e energia"], ["metais", "Metais e minério"], ["agricolas", "Agrícolas"], ["dolar", "Dólar e crédito"]];
let ABA_MERCADOS = "acoes";
const ESCOLHA_COMMODITY = {};
function desenharMercados(mundo, cab, abas) {
  const M = mundo.mercados || {}, K = mundo.commodities || {};
  const u = (x) => ultimo(x);
  const varia = (s, dias) => { const p = Pares(s); if (p.length < 2) return null; const fim = p[p.length - 1];
    const lim = new Date(`${fim[0]}T12:00:00`); lim.setDate(lim.getDate() - dias); const iso = lim.toISOString().slice(0, 10);
    const b = [...p].reverse().find(([d]) => d <= iso); return b ? fim[1] / b[1] - 1 : null; };
  const vtxt = (v) => (v == null ? "—" : `<span class="${classeSinal(v)}">${num(v * 100, 1)}%</span>`);
  const t = (anos, extra) => ({ xTempo: true, inicioTempo: desde(anos), deslizante: true, ...extra });
  const semFred = !mundo.mercados;
  const grupo = (g) => Object.entries(K).filter(([, v]) => v.grupo === g);
  // tabela + gráfico com botões para uma família de commodities do Banco Mundial
  const blocoCommodities = (g, titulo) => {
    const itens = grupo(g);
    if (!itens.length) return { html: `<p class="sub">Commodities indisponíveis.</p>`, desenhar: () => {} };
    const escolhida = ESCOLHA_COMMODITY[g] && K[ESCOLHA_COMMODITY[g]] ? ESCOLHA_COMMODITY[g] : itens[0][0];
    return {
      html: `<div class="painel largo" data-info="commodities"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">${titulo} — preço mensal</h2>
          <div class="seletor" id="sel-comm-${g}">${itens.map(([k, v]) => `<button data-k="${k}" class="${k === escolhida ? "ativo" : ""}">${esc(v.nome)}</button>`).join("")}</div></div>
          <div class="grafico alto" id="gk-${g}"></div></div>
        <div class="painel largo" data-info="commodities"><h2>${titulo} — último preço e variação</h2><div class="rolagem"><table class="tabela">
          <tr><th style="text-align:left">Produto</th><th>Unidade</th><th>Mês</th><th>Preço</th><th>1 mês</th><th>12 meses</th><th>5 anos</th></tr>
          ${itens.map(([, v]) => `<tr><td style="text-align:left">${esc(v.nome)}</td><td class="sub">${esc(v.unidade)}</td><td>${mesAno(u(v).data)}</td><td>${num(u(v).valor, 2)}</td>
            <td>${vtxt(varia(v, 31))}</td><td>${vtxt(varia(v, 365))}</td><td>${vtxt(varia(v, 5 * 365))}</td></tr>`).join("")}
        </table></div><div class="nota">Médias mensais em dólares — Banco Mundial, Commodity Price Data ("Pink Sheet"), atualizado no início de cada mês.</div></div>`,
      desenhar: () => {
        const v = K[escolhida];
        grafico(document.getElementById(`gk-${g}`), t(10, { eixoEsq: "preco", series: [{ nome: `${v.nome} (${v.unidade})`, valores: Pares(v), tipo: "line", cor: COR.ambar }] }));
        document.getElementById(`sel-comm-${g}`).addEventListener("click", (ev) => {
          const b = ev.target.closest("button"); if (!b) return;
          ESCOLHA_COMMODITY[g] = b.dataset.k; limparGraficos(); desenharMercados(mundo, cab, abas);
        });
      },
    };
  };
  const cartaoM = (rot, s, fmt, sub) => cartao(rot, u(s).valor != null ? fmt(u(s).valor) : "—", sub ?? `${dataBR(u(s).data)} · 12m ${varia(s, 365) == null ? "—" : `${num(varia(s, 365) * 100, 1)}%`}`);
  let corpo = "", depois = () => {};
  if (ABA_MERCADOS === "acoes") {
    corpo = `<div class="grade-cartoes">${cartaoM("S&P 500", M.sp500, (v) => num(v, 0))}${cartaoM("Nasdaq", M.nasdaq, (v) => num(v, 0))}${cartaoM("VIX", M.vix, (v) => num(v, 1), "volatilidade esperada do S&P 500")}</div>
      <div class="grade">${painelG("gm-acoes", "S&P 500 e Nasdaq", "acoes_eua")}${painelG("gm-vix", "VIX — volatilidade implícita do S&P 500", "vix")}</div>
      <div class="nota">Fechamento diário. O FRED só publica os últimos 10 anos do S&P 500 (licença da S&P Dow Jones Indices).</div>`;
    depois = () => {
      grafico(document.getElementById("gm-acoes"), t(5, { eixoEsq: "numero", eixoDir: "numero", series: [
        { nome: "S&P 500", valores: Pares(M.sp500), tipo: "line", cor: COR.azul }, { nome: "Nasdaq Composite (eixo direito)", valores: Pares(M.nasdaq), tipo: "line", eixo: "dir", cor: COR.ambar }] }));
      grafico(document.getElementById("gm-vix"), t(5, { eixoEsq: "numero", series: [{ nome: "VIX", valores: Pares(M.vix), tipo: "line", cor: COR.vermelho }] }));
    };
  } else if (ABA_MERCADOS === "energia") {
    const bloco = blocoCommodities("energia", "Energia");
    corpo = `<div class="grade-cartoes">${cartaoM("Brent", M.brent, (v) => `US$ ${num(v, 2)}`)}${cartaoM("WTI", M.wti, (v) => `US$ ${num(v, 2)}`)}
      ${K.gas_europa ? cartao("Gás natural Europa", `US$ ${num(u(K.gas_europa).valor, 2)}`, `por MMBtu · ${mesAno(u(K.gas_europa).data)}`) : ""}</div>
      <div class="grade">${painelG("gm-petroleo", "Petróleo Brent e WTI — diário (US$/barril)", "petroleo", "", "largo")}${bloco.html}</div>`;
    depois = () => {
      grafico(document.getElementById("gm-petroleo"), t(3, { eixoEsq: "preco", series: [
        { nome: "Brent", valores: Pares(M.brent), tipo: "line", cor: COR.ambar }, { nome: "WTI", valores: Pares(M.wti), tipo: "line", cor: COR.azul }] }));
      bloco.desenhar();
    };
  } else if (ABA_MERCADOS === "dolar") {
    corpo = `<div class="grade-cartoes">${cartaoM("Dólar global", M.dolar, (v) => num(v, 1), "índice amplo do Fed (jan/2006 = 100)")}
      ${cartaoM("Spread high yield", M.hy, (v) => `${num(v, 2)} p.p.`, "sobre Treasuries")}${cartaoM("Spread grau de investimento", M.ig, (v) => `${num(v, 2)} p.p.`, "sobre Treasuries")}
      ${cartaoM("Bitcoin", M.bitcoin, (v) => `US$ ${num(v, 0)}`)}</div>
      <div class="grade">${painelG("gm-dolar", "Dólar global — índice amplo do Fed", "dolar_global")}${painelG("gm-spread", "Spreads de crédito corporativo dos EUA (p.p. sobre Treasuries)", "spreads_credito")}
        ${painelG("gm-btc", "Bitcoin (US$)", "bitcoin", "", "largo")}</div>`;
    depois = () => {
      grafico(document.getElementById("gm-dolar"), t(10, { eixoEsq: "numero", series: [{ nome: "Índice amplo do dólar", valores: Pares(M.dolar), tipo: "line", cor: COR.verde }] }));
      grafico(document.getElementById("gm-spread"), t(10, { eixoEsq: "pctPronto", series: [
        { nome: "High yield", valores: Pares(M.hy), tipo: "line", cor: COR.vermelho }, { nome: "Grau de investimento", valores: Pares(M.ig), tipo: "line", cor: COR.azul }] }));
      grafico(document.getElementById("gm-btc"), t(5, { eixoEsq: "numero", series: [{ nome: "Bitcoin", valores: Pares(M.bitcoin), tipo: "line", cor: COR.ambar }] }));
    };
  } else {
    const bloco = blocoCommodities(ABA_MERCADOS, ABA_MERCADOS === "metais" ? "Metais e minério" : "Agrícolas");
    corpo = `<div class="grade">${bloco.html}</div>`;
    depois = bloco.desenhar;
  }
  app.innerHTML = `${cab("Mundo · Macro", "Mercados: FRED (diário) e Banco Mundial (mensal)")}${abas}
    <div class="seletor seletor-editoria" id="sub-mercados" style="margin:-4px 0 12px">${ABAS_MERCADOS.map(([k, n]) => `<button data-k="${k}" class="${k === ABA_MERCADOS ? "ativo" : ""}">${n}</button>`).join("")}</div>
    ${semFred && ["acoes", "energia", "dolar"].includes(ABA_MERCADOS) ? `<div class="aviso">Aguardando a primeira coleta do FRED (os dados diários entram na próxima atualização).</div>` : ""}
    ${corpo}`;
  depois();
  document.getElementById("sub-mercados").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    ABA_MERCADOS = b.dataset.k; limparGraficos(); desenharMercados(mundo, cab, abas);
  });
}
/* ============ Mundo → Empresas (S&P 500, SEC EDGAR) ============ */
let ORDEM_MUNDO = { campo: "peso", desc: true };
const COLUNAS_MUNDO = [
  ["peso", "Peso S&P", (v) => (v == null ? "—" : `${num(v, 2)}%`)], ["receita", "Receita LTM", (v) => usd(v)], ["lucro", "Lucro LTM", (v) => usd(v)],
  ["roe", "ROE", pct],
];
const usd = (v) => { const m = MOEDA; MOEDA = "US$"; const t = reais(v); MOEDA = m; return t; };
const ABAS_EMPRESAS_MUNDO = [["sp500", "S&P 500"], ["empresas", "Empresas"]];
let ABA_EMPRESAS_MUNDO = "sp500";
const PERIODO_SP = {};  // botão Anual / Trimestral de cada gráfico do S&P 500

async function paginaEmpresasMundo() {
  MOEDA = "US$";
  const [idx, sp] = await Promise.all([dados("dados/mundo_empresas.json").catch(() => null), dados("dados/sp500.json").catch(() => null)]);
  if (!idx || !idx.empresas || !idx.empresas.length) {
    app.innerHTML = `<div class="cabecalho"><div><h1>Mundo · Empresas</h1></div></div><p class="sub">As empresas do S&P 500 entram na próxima atualização.</p>`;
    return;
  }
  const abas = `<div class="seletor seletor-editoria" id="sub-sp" style="margin:0 0 12px">${ABAS_EMPRESAS_MUNDO.map(([k, n]) =>
    `<button data-k="${k}" class="${k === ABA_EMPRESAS_MUNDO ? "ativo" : ""}">${n}</button>`).join("")}</div>`;
  const ligarAbas = () => document.getElementById("sub-sp").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    ABA_EMPRESAS_MUNDO = b.dataset.k; limparGraficos(); paginaEmpresasMundo();
  });
  if (ABA_EMPRESAS_MUNDO === "sp500") { desenharSP500(sp, idx, abas); ligarAbas(); return; }

  const setorDe = (e) => ((sp && sp.setores) || {})[e.id] || e.setor || "";
  const setores = [...new Set(idx.empresas.map(setorDe).filter(Boolean))].sort();
  app.innerHTML = `<div class="cabecalho"><div><h1>Mundo · Empresas</h1><div class="sub">${idx.empresas.length} empresas do S&P 500 (carteira do SPY de ${esc(idx.spy_em || "—")})
      · balanços da SEC (10-K e 10-Q) · valores em US$, últimos 12 meses</div></div></div>${abas}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">
      <input class="filtro" id="busca-mundo" placeholder="Buscar por ticker ou nome (ex.: AAPL, Coca-Cola)">
      <select class="filtro" id="setor-mundo" style="max-width:320px"><option value="">Todos os setores</option>${setores.map((s) => `<option>${esc(s)}</option>`).join("")}</select></div>
    <div class="painel" data-info="empresas_mundo"><div class="rolagem rolagem-y" style="max-height:75vh"><table class="tabela" id="tab-mundo"></table></div>
      <div class="nota">Clique no título da coluna para ordenar e na linha para abrir a empresa. Receita e lucro dos últimos 12 meses (soma dos 4 trimestres dos 10-Q/10-K).
        Setor: atividade informada à SEC (SIC) agrupada nos 11 setores do mercado, com ajuste das empresas conhecidas em que o SIC destoa — aproximação da classificação GICS, que é paga.</div></div>`;
  const desenhar = () => {
    const q = document.getElementById("busca-mundo").value.trim().toLowerCase(), setor = document.getElementById("setor-mundo").value;
    const lista = idx.empresas.filter((e) => (!q || e.id.toLowerCase().includes(q) || (e.nome || "").toLowerCase().includes(q)) && (!setor || setorDe(e) === setor))
      .sort((a, b) => { const x = a[ORDEM_MUNDO.campo], y = b[ORDEM_MUNDO.campo]; if (x == null) return 1; if (y == null) return -1; return (x < y ? -1 : x > y ? 1 : 0) * (ORDEM_MUNDO.desc ? -1 : 1); });
    document.getElementById("tab-mundo").innerHTML = `<tr><th style="text-align:left">Empresa</th><th style="text-align:left">Setor</th>
      ${COLUNAS_MUNDO.map(([k, r]) => `<th data-ordem="${k}" style="cursor:pointer">${r}${ORDEM_MUNDO.campo === k ? (ORDEM_MUNDO.desc ? " ▾" : " ▴") : ""}</th>`).join("")}</tr>
      ${lista.map((e) => `<tr class="clicavel" data-id="${esc(e.id)}"><td style="text-align:left"><b>${esc(e.id)}</b> <span class="sub">${esc(e.nome)}</span></td>
        <td style="text-align:left;white-space:normal" class="sub">${esc(setorDe(e))}</td>${COLUNAS_MUNDO.map(([k, , f]) => `<td>${f(e[k])}</td>`).join("")}</tr>`).join("")}`;
  };
  document.getElementById("busca-mundo").addEventListener("input", desenhar);
  document.getElementById("setor-mundo").addEventListener("change", desenhar);
  document.getElementById("tab-mundo").addEventListener("click", (ev) => {
    const th = ev.target.closest("[data-ordem]");
    if (th) { const k = th.dataset.ordem; ORDEM_MUNDO = { campo: k, desc: ORDEM_MUNDO.campo === k ? !ORDEM_MUNDO.desc : true }; desenhar(); return; }
    const tr = ev.target.closest("[data-id]"); if (tr) location.hash = `#/off/empresa/${encodeURIComponent(tr.dataset.id)}`;
  });
  ligarAbas();
  desenhar();
}

// ---------- Mundo → Empresas → S&P 500: soma das empresas do índice (pipeline/sp500.py) ----------
function desenharSP500(sp, idx, abas) {
  if (!sp) {
    app.innerHTML = `<div class="cabecalho"><div><h1>Mundo · Empresas</h1></div></div>${abas}<p class="sub">Os números do S&P 500 entram na próxima atualização.</p>`;
    return;
  }
  const C = sp.cartoes || {}, T = sp.trimestral || {}, A = sp.anual || {}, I = sp.indicadores || {};
  const ultimo = (s) => (s && s.valores && s.valores.length ? s.valores[s.valores.length - 1] : null);
  const ultData = (s) => (s && s.datas && s.datas.length ? s.datas[s.datas.length - 1] : null);
  const triRot = (d) => (d ? `${Math.floor((Number(d.slice(5, 7)) - 1) / 3) + 1}º tri/${d.slice(0, 4)}` : "—");
  const cartoes = [
    cartao("Valor de mercado", C.valor_mercado ? usd(C.valor_mercado) : "—", `${C.n_empresas || ""} empresas`),
    cartao("P/L (12 meses)", C.pl != null ? `${num(C.pl, 1)}x` : "—", "valor de mercado ÷ lucro"),
    cartao("FCF yield", pctPronto(C.fcf_yield, 1), "fluxo de caixa livre ÷ valor de mercado"),
    cartao("ROE", pctPronto(C.roe, 1), `12 meses · ${triRot(ultData(I.roe))}`),
    cartao("ROIC", pctPronto(C.roic, 1), "não financeiras"),
    cartao("Dív. líquida / EBITDA", C.dl_ebitda != null ? `${num(C.dl_ebitda, 2)}x` : "—", "não financeiras"),
    cartao("Lucro — crescimento", pctPronto(ultimo(T.lucro_cresc), 1), `${triRot(ultData(T.lucro_cresc))} contra 1 ano antes`),
    cartao("Margem líquida", pctPronto(C.margem_liquida, 1), "lucro ÷ receita, 12 meses"),
  ];
  // barras (US$) + crescimento contra o ano anterior (linha, eixo direito), com botão Anual / Trimestral
  const comPeriodo = (id, chave, titulo, info, extra = null, eixoDir = "pctPronto") => ({ id, chave, titulo, info, extra, eixoDir });
  const graficosP = [
    comPeriodo("sp-receita", "receita", "Receita", "sp_receita"),
    comPeriodo("sp-ebitda", "ebitda", "EBITDA (não financeiras)", "sp_ebitda"),
    comPeriodo("sp-lucro", "lucro", "Lucro líquido", "sp_lucro"),
    null,  // ROE e ROIC entram aqui (ao lado do lucro)
    comPeriodo("sp-capex", "capex", "Capex (não financeiras)", "sp_capex"),
    comPeriodo("sp-fcf", "fcf", "Fluxo de caixa livre e FCF yield (não financeiras)", "sp_fcf",
      { nome: "FCF yield (eixo direito)", valores: Pares(sp.fcf_yield), tipo: "line", eixo: "dir", cor: COR.ambar }),
    comPeriodo("sp-divida", "divida_liquida", "Dívida líquida e dívida líquida / EBITDA (não financeiras)", "sp_divida",
      { nome: "Dívida líquida / EBITDA (eixo direito)", valores: Pares(I.dl_ebitda), tipo: "line", eixo: "dir", cor: COR.ambar }, "vezes"),
  ];
  const botoes = (g) => `<div class="seletor" data-periodo="${g.id}">${[["anual", "Anual"], ["trimestral", "Trimestral"]].map(([k, n]) =>
    `<button data-k="${k}" class="${(PERIODO_SP[g.id] || "anual") === k ? "ativo" : ""}">${n}</button>`).join("")}</div>`;
  const painelP = (g) => `<div class="painel${g.chave === "divida_liquida" ? " largo" : ""}" data-info="${g.info}"><div class="cabecalho" style="margin-bottom:6px">
    <h2 style="margin:0">${g.titulo}</h2>${botoes(g)}</div><div class="grafico" id="${g.id}"></div></div>`;
  app.innerHTML = `<div class="cabecalho"><div><h1>Mundo · Empresas</h1><div class="sub">S&P 500 como um todo: soma das ${C.n_empresas || ""} empresas do índice
      · balanços da SEC, cotações do Yahoo (não oficial) e índice do FRED · valores em US$ · atualizado em ${dataHoraBR(sp.gerado_em)}</div></div></div>${abas}
    <div class="grade-cartoes">${cartoes.join("")}</div>
    <div class="grade">
      ${painelG("sp-cotacao", "Cotação do S&P 500", "sp_cotacao")}${painelG("sp-pl", "P/L do S&P 500 (valor de mercado ÷ lucro de 12 meses)", "sp_pl")}
      ${graficosP.map((g) => (g ? painelP(g) : painelG("sp-roe", "ROE e ROIC (12 meses)", "sp_roe"))).join("")}
    </div>
    <div class="nota secao">Soma das empresas que estão hoje no índice (quem saiu no passado não entra) desde 2010, quando os balanços em formato de dados
      começam na SEC. Crescimento sempre sobre o mesmo conjunto de empresas nos dois períodos. Bancos, seguradoras e corretoras ficam fora de EBITDA, capex,
      fluxo de caixa livre, dívida e ROIC. ${sp.descartados && sp.descartados.length ? `Valores fora da soma por erro de escala no balanço entregue à SEC: ${esc(sp.descartados.join("; "))}.` : ""}</div>`;
  grafico(document.getElementById("sp-cotacao"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "preco", series: sp.cotacao && sp.cotacao.datas
    ? [{ nome: "S&P 500 (pontos)", valores: Pares(sp.cotacao), tipo: "line", cor: COR.azul }] : [] });
  grafico(document.getElementById("sp-pl"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "vezes", series: [
    { nome: "P/L (12 meses)", valores: Pares(sp.pl_historico), tipo: "line", cor: COR.ambar }] });
  grafico(document.getElementById("sp-roe"), { xTempo: true, inicioTempo: "2011-01-01", deslizante: true, eixoEsq: "pctPronto", series: [
    { nome: "ROE", valores: Pares(I.roe), tipo: "line", cor: COR.azul }, { nome: "ROIC (não financeiras)", valores: Pares(I.roic), tipo: "line", cor: COR.verde },
    { nome: "Margem líquida", valores: Pares(I.margem_liquida), tipo: "line", cor: COR.cinza, tracejado: true }] });
  const desenharP = (g) => {
    const el = document.getElementById(g.id), velho = echarts.getInstanceByDom(el);
    if (velho) { graficos.splice(graficos.indexOf(velho), 1); velho.dispose(); }
    const B = (PERIODO_SP[g.id] || "anual") === "anual" ? A : T;
    const barras = Pares(B[g.chave]).map(([d, v]) => [d, v == null ? null : v * 1e6]);
    grafico(el, { xTempo: true, inicioTempo: "2011-01-01", deslizante: true, eixoEsq: "reais", eixoDir: g.eixoDir, series: [
      { nome: g.titulo.split(" e ")[0].replace(" (não financeiras)", ""), valores: barras, cor: COR.azul },
      g.extra || { nome: "Crescimento contra 1 ano antes (eixo direito)", valores: Pares(B[`${g.chave}_cresc`]), tipo: "line", eixo: "dir", cor: COR.ambar }] });
  };
  graficosP.filter(Boolean).forEach(desenharP);
  document.querySelectorAll("[data-periodo]").forEach((sel) => sel.addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    const g = graficosP.find((x) => x && x.id === sel.dataset.periodo);
    PERIODO_SP[g.id] = b.dataset.k;
    sel.querySelectorAll("button").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharP(g);
  }));
}

// página de cada empresa do S&P 500: só Negócio e Documentos (os números ficam na aba S&P 500 e no tabelão)
const ABAS_EMPRESA_MUNDO = [["negocio", "Negócio"], ["eventos", "Documentos (SEC)"]];
let ABA_EMPRESA_MUNDO = "negocio", DEMONSTRACAO_MUNDO = "anual";

async function paginaEmpresaMundo(id) {
  const emp = await dados(`dados/mundo_empresas/${id}.json`).catch(() => null);
  if (!emp) { app.innerHTML = `<p class="erro">Empresa ${esc(id)} não encontrada no S&P 500.</p>`; return; }
  MOEDA = "US$";
  const ltm = emp.ltm, n = ltm.periodos.length - 1;
  const L = (k) => (n >= 0 ? (ltm.series[k] || [])[n] : null);
  const pos = (v) => (v != null && v > 0 ? v : null);
  const cot = emp.cotacao || {}, mc = emp.market_cap, dl = L("divida_liquida"), ev = mc != null && dl != null ? mc + dl : null;
  const k10 = (emp.cadastro || {}).ultimo_10k;
  app.innerHTML = `
    <div class="cabecalho"><div><h1>${esc(emp.tickers.join(" / "))} · ${esc(emp.nome)}</h1>
      <div class="sub">${esc(emp.setor || "")} · ${esc(emp.cnpj)} · ${emp.peso_sp500 != null ? `${num(emp.peso_sp500, 2)}% do S&P 500 · ` : ""}último período ${ltm.periodos.length ? dataBR(ltm.periodos[n]) : "—"} · valores em US$</div></div>
      ${k10 ? `<a class="botao" href="${esc(k10.link)}" target="_blank" rel="noopener">Último 10-K na SEC</a>` : ""}</div>
    <div class="grade-cartoes">
      ${cartao(`Preço ${esc(emp.id)}`, cot.preco ? `US$ ${num(cot.preco, 2)}` : "—", cot.preco ? `<span class="${classeSinal(cot.variacao_dia)}">${num(cot.variacao_dia, 2)}%</span> · ${dataBR(cot.data)} · Yahoo` : "")}
      ${cartao("Valor de mercado", reais(mc), "preço × ações em circulação")}
      ${cartao("EV", reais(ev), "valor de mercado + dív. líquida")}
      ${cartao("P/L", vezes(mc && pos(L("lucro_liquido")) ? mc / L("lucro_liquido") : null), "LTM")}
      ${cartao("P/VP", vezes(mc && pos(L("pl")) ? mc / L("pl") : null), "")}
      ${cartao("EV/EBITDA", vezes(ev && pos(L("ebitda")) ? ev / L("ebitda") : null), "LTM")}
      ${cartao("FCF yield", pct(mc && L("fcf") != null ? L("fcf") / mc : null), "FCF LTM ÷ valor de mercado")}
      ${cartao("Dividend yield", pct(mc ? (L("div_pagos") || 0) / mc : null, 2), "dividendos pagos LTM ÷ valor de mercado")}
      ${cartao("ROE / ROIC", `${pct(L("roe"))} / ${pct(L("roic"))}`, "LTM")}
    </div>
    <div class="abas" id="abas-empresa-mundo">${ABAS_EMPRESA_MUNDO.map(([k, r]) => `<button data-k="${k}" class="${k === ABA_EMPRESA_MUNDO ? "ativo" : ""}">${r}</button>`).join("")}</div>
    <div id="aba-empresa"></div>`;
  const area = () => document.getElementById("aba-empresa");
  const ABAS = {
    negocio: () => {
      const c = emp.cadastro || {};
      const linhas = [["Setor (código SIC)", `${c.setor || "—"}${c.sic ? ` (${c.sic})` : ""}`], ["Sede", c.sede || "—"], ["Estado de constituição", c.estado || "—"],
        ["Fim do exercício fiscal", c.exercicio_termina ? `${c.exercicio_termina.slice(2)}/${c.exercicio_termina.slice(0, 2)}` : "—"],
        ["Tickers", (c.tickers || emp.tickers).join(", ")], ["Bolsas", (c.bolsas || []).join(", ") || "—"], ["Categoria na SEC", c.categoria || "—"], ["Registro na SEC", emp.cnpj]];
      area().innerHTML = `<div class="grade grade-empilhada"><div class="painel" data-info="empresas_mundo"><h2>Cadastro na SEC</h2><table class="tabela">
        ${linhas.map(([k, v]) => `<tr><td style="text-align:left" class="sub">${k}</td><td style="text-align:left">${esc(v)}</td></tr>`).join("")}</table>
        <div class="nota">A descrição completa do negócio, dos riscos e da estratégia está no item 1 ("Business") e no item 1A ("Risk Factors") do relatório anual
          ${k10 ? `<a href="${esc(k10.link)}" target="_blank" rel="noopener">10-K entregue em ${dataBR(k10.data)}</a>` : "10-K"}. Fonte: SEC EDGAR.</div></div></div>`;
    },
    eventos: () => {
      const docs = emp.documentos || [];
      const filtros = [["todos", "Todos"], ["relevantes", "Fatos relevantes (8-K)"], ["resultados", "Resultados"], ["relatorios", "10-K e 10-Q"]];
      area().innerHTML = `<div class="grade grade-empilhada"><div class="painel" data-info="documentos_sec"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Documentos entregues à SEC</h2>
          <div class="seletor" id="sel-docs">${filtros.map(([k, r]) => `<button data-k="${k}" class="${k === "todos" ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
        <div class="rolagem rolagem-y" id="lista-docs"></div>
        <div class="nota">Últimos 3 anos, com link para o documento original na SEC. 8-K = comunicado de fato relevante; o assunto vem dos itens informados pela empresa.</div></div></div>`;
      const desenhar = (f) => {
        const lista = docs.filter((d) => f === "todos" || (f === "relevantes" && d.relevante) || (f === "resultados" && /Resultado/.test(d.assunto)) || (f === "relatorios" && /^10-[KQ]/.test(d.tipo)));
        document.getElementById("lista-docs").innerHTML = lista.length ? `<table class="tabela"><tr><th>Data</th><th style="text-align:left">Tipo</th><th style="text-align:left">Assunto</th></tr>
          ${lista.map((d) => `<tr><td>${dataBR(d.data)}</td><td style="text-align:left" class="${d.relevante ? "" : "sub"}">${esc(d.tipo)}</td>
            <td style="text-align:left;white-space:normal"><a href="${esc(d.link)}" target="_blank" rel="noopener">${esc(d.assunto)}</a></td></tr>`).join("")}</table>` : `<p class="sub">Nenhum documento desse tipo.</p>`;
      };
      document.getElementById("sel-docs").addEventListener("click", (ev) => {
        const b = ev.target.closest("button"); if (!b) return;
        document.querySelectorAll("#sel-docs button").forEach((x) => x.classList.toggle("ativo", x === b));
        desenhar(b.dataset.k);
      });
      desenhar("todos");
    },
    cotacao: () => {
      area().innerHTML = `<div id="cotacao-empresa"></div>`;
      desenharCotacao({ cotacao_semanal: emp.cotacao_semanal, papel_referencia: emp.id }, { cotacoes: cot.preco ? { [emp.id]: cot } : {} });
    },
    resultados: () => {
      const ds = emp.demonstracoes_sec || {};
      const opcoes = [["anual", "Anual (último 10-K)"], ["trimestral", "Trimestral (último 10-Q)"]].filter(([k]) => ds[k]);
      if (!ds[DEMONSTRACAO_MUNDO] && opcoes.length) DEMONSTRACAO_MUNDO = opcoes[0][0];
      const d = ds[DEMONSTRACAO_MUNDO];
      const tabela = (t, baseRe) => {
        if (!t) return `<p class="sub">Demonstração não encontrada no relatório.</p>`;
        const base = baseRe ? (t.linhas.find((l) => !l.secao && baseRe.test(l.r)) || null) : null;
        const av = (x, i) => (base && x != null && base.v[i] ? `${num((x / base.v[i]) * 100, 1)}%` : "");
        return `<table class="tabela tabela-av"><tr><th style="text-align:left">${esc(t.unidade)}</th>${t.colunas.map((c) => `<th>${esc(c)}</th>${base ? '<th class="sub">AV</th>' : ""}`).join("")}</tr>
          ${t.linhas.map((l) => `<tr class="${l.secao ? "subtotal" : /^total|^net income|^net (loss|earnings)|^gross (margin|profit)|^operating income/i.test(l.r) ? "subtotal" : ""}">
            <td style="text-align:left;${l.secao ? "color:var(--ambar)" : ""}">${esc(l.r)}</td>
            ${l.v.map((x, i) => `<td>${x == null ? "" : num(x, Math.abs(x) < 100 && x % 1 ? 2 : 0)}</td>${base ? `<td class="sub">${av(x, i)}</td>` : ""}`).join("")}</tr>`).join("")}</table>`;
      };
      area().innerHTML = `<div class="grade grade-empilhada">
        <div class="painel" id="painel-indicadores"><h2>Painel de indicadores</h2>
          <p class="sub">Espaço reservado para o painel de indicadores (em montagem).</p>
          <details><summary class="sub" style="cursor:pointer">Tabela de indicadores (anos fechados e LTM, padronizados)</summary><div class="rolagem" id="tab-ind"></div></details></div>
        <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Demonstrações como divulgadas à SEC</h2>
          <div class="seletor" id="sel-dem">${opcoes.map(([k, r]) => `<button data-k="${k}" class="${k === DEMONSTRACAO_MUNDO ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
          ${d ? `<div class="nota">${esc(d.documento)} entregue em ${dataBR(d.data)} · <a href="${esc(d.link)}" target="_blank" rel="noopener">abrir o documento na SEC</a> ·
            linhas, nomes e abertura exatamente como a empresa divulgou (em inglês); AV = análise vertical (DRE sobre a receita total; balanço sobre o ativo total).</div>` :
            `<p class="sub">Demonstrações indisponíveis.</p>`}</div>
        ${d ? `<div class="painel" data-info="demonstracoes_sec"><h2>${esc((d.dre || {}).titulo || "Income statement")}</h2><div class="rolagem">${tabela(d.dre, /^(total )?(net )?(revenues?|sales)|^net sales|^total net revenue|^revenues?,? net/i)}</div></div>
          <div class="painel" data-info="demonstracoes_sec"><h2>${esc((d.balanco || {}).titulo || "Balance sheet")}</h2><div class="rolagem">${tabela(d.balanco, /^total assets$/i)}</div></div>
          <div class="painel" data-info="demonstracoes_sec"><h2>${esc((d.caixa || {}).titulo || "Cash flows")}</h2><div class="rolagem">${tabela(d.caixa, null)}</div></div>` : ""}
      </div>`;
      desenharIndicadores(emp);
      const sel = document.getElementById("sel-dem");
      if (sel) sel.addEventListener("click", (ev) => { const b = ev.target.closest("button"); if (!b) return; DEMONSTRACAO_MUNDO = b.dataset.k; ABAS.resultados(); });
    },
    graficos: () => {
      area().innerHTML = `<div class="cabecalho"><h2 style="margin:0">Gráficos</h2>
          <div class="seletor" id="visao">${["trimestral", "semestral", "anual"].map((v) => `<button data-v="${v}" class="${v === VISAO ? "ativo" : ""}">${v[0].toUpperCase() + v.slice(1)}</button>`).join("")}</div></div>
        <div class="grade" id="graficos-empresa"></div>
        <div class="nota secao">Séries padronizadas a partir dos dados XBRL da SEC (US-GAAP), em US$: trimestres isolados pela diferença dos acumulados do ano;
          anos pelo número do 10-K. EBITDA = resultado operacional + depreciação e amortização da demonstração do fluxo de caixa. Bancos e seguradoras não divulgam
          lucro bruto nem resultado operacional e ficam com esses gráficos vazios.
          ${(emp.notas || {}).ebit_estimado ? `<b style="color:var(--ambar)">Esta empresa não divulga resultado operacional: EBIT e EBITDA são estimados (lucro antes do IR + despesas de juros − receitas financeiras).</b>` : ""}</div>`;
      document.getElementById("visao").addEventListener("click", (ev) => {
        const b = ev.target.closest("button"); if (!b) return;
        VISAO = b.dataset.v;
        document.querySelectorAll("#visao button").forEach((x) => x.classList.toggle("ativo", x === b));
        desenharGraficosEmpresa(emp);
      });
      desenharGraficosEmpresa(emp);
    },
    dividendos: () => {
      const A = emp.anual.series, rot = emp.anual.periodos.map((p) => rotuloPeriodo(p, "anual", emp.mes_fim_exercicio || 12));
      const dps = emp.dividendo_por_acao_ano || {}, anosDps = Object.keys(dps).sort();
      area().innerHTML = `<div class="grade">
        ${painelG("gd-pagos", "Dividendos e recompras de ações (DFC)", "dividendos_mundo")}
        ${painelG("gd-dps", "Dividendo por ação declarado (US$, por exercício)", "dividendos_mundo")}</div>`;
      grafico(document.getElementById("gd-pagos"), { rotulos: rot, eixoDir: "pct", series: [
        { nome: "Dividendos pagos", valores: A.div_pagos, cor: COR.verde, pilha: "r" },
        { nome: "Recompras de ações", valores: A.recompras || A.div_pagos.map(() => null), cor: COR.azul, pilha: "r" },
        { nome: "Payout (dividendos ÷ lucro)", valores: A.payout, tipo: "line", eixo: "dir", cor: COR.ambar }] });
      grafico(document.getElementById("gd-dps"), { rotulos: anosDps.map((d) => rotuloPeriodo(d, "anual", emp.mes_fim_exercicio || 12)), eixoEsq: "preco", series: [
        { nome: "US$ por ação", valores: anosDps.map((a) => dps[a]), cor: COR.verde }] });
    },
  };
  const mostrar = (k) => {
    limparGraficos();
    ABA_EMPRESA_MUNDO = ABAS[k] && ABAS_EMPRESA_MUNDO.some(([x]) => x === k) ? k : "negocio";
    document.querySelectorAll("#abas-empresa-mundo button").forEach((x) => x.classList.toggle("ativo", x.dataset.k === ABA_EMPRESA_MUNDO));
    ABAS[ABA_EMPRESA_MUNDO]();
  };
  document.getElementById("abas-empresa-mundo").addEventListener("click", (ev) => { const b = ev.target.closest("button"); if (b) mostrar(b.dataset.k); });
  mostrar(ABA_EMPRESA_MUNDO);
}

const mesAno = (iso) => (iso ? `${MESES[Number(iso.slice(5, 7)) - 1]}/${iso.slice(2, 4)}` : "—");

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

// Juros básicos (BIS): taxa atual, data da última mudança e variação em 12 meses; séries em degrau (datas de mudança + último dia)
function tabelaBancosCentrais(BC) {
  const linhas = Object.values(BC).filter((s) => s.datas && s.datas.length).map((s) => {
    const n = s.valores.length, atual = s.valores[n - 1];
    let i = n - 1;
    while (i > 0 && s.valores[i - 1] === atual) i--;
    const ha12 = desde(1);
    let antes = null;
    s.datas.forEach((d, j) => { if (d <= ha12) antes = s.valores[j]; });
    return { nome: s.nome, atual, mudou: i > 0 ? s.datas[i] : null, var12: antes == null ? null : atual - antes, ult: s.datas[n - 1] };
  }).sort((a, b) => b.atual - a.atual);
  return `<div class="painel largo" data-info="juros_bancos_centrais"><h2>Juros básicos dos bancos centrais</h2><div class="rolagem"><table class="tabela">
    <tr><th style="text-align:left">País / banco central</th><th>Juro básico</th><th>Última mudança</th><th>Variação em 12 meses</th><th>Dado de</th></tr>
    ${linhas.map((l) => `<tr><td style="text-align:left">${esc(l.nome)}</td><td>${num(l.atual, 2)}%</td><td>${l.mudou ? dataBR(l.mudou) : "—"}</td>
      <td>${l.var12 == null ? "—" : `<span class="${l.var12 > 0 ? "neg" : l.var12 < 0 ? "pos" : ""}">${l.var12 > 0 ? "+" : ""}${num(l.var12, 2)} p.p.</span>`}</td>
      <td class="sub">${dataBR(l.ult)}</td></tr>`).join("")}
  </table></div><div class="nota">Taxa de política monetária de cada banco central, como informada ao BIS. Em vermelho, alta em 12 meses; em verde, corte.
    Fonte: BIS — Central bank policy rates (série diária).</div></div>`;
}

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
    app.innerHTML = `<div class="cabecalho"><div><h1>Mundo · ${t}</h1><div class="sub">${sub}</div></div></div>${emConstrucao(itens)}`;
    return;
  }
  if (!off) { app.innerHTML = `<p class="erro">Dados do exterior indisponíveis.</p>`; return; }
  const cab = (titulo, sub, extra = "") => `<div class="cabecalho"><div><h1>${titulo}</h1><div class="sub">${sub} · atualizado em ${dataHoraBR(off.gerado_em)}</div></div>${extra}</div>`;
  const T = off.treasuries || {}, F = off.fed || {}, B = off.bls || {}, E = off.bce || {}, Z = off.eurostat || {};
  const u = (s) => ultimo(s);
  const mes = (s) => (u(s).data ? `${MESES[Number(u(s).data.slice(5, 7)) - 1]}/${u(s).data.slice(2, 4)}` : "");
  const ust10 = T.historico ? u(T.historico["10 anos"]) : {};

  if (secao === "macro") {
    const sub = SUBS_MACRO_OFF.some(([k]) => k === parametro) ? parametro : SUBS_MACRO_OFF[0][0];
    const abas = `<div class="abas">${SUBS_MACRO_OFF.map(([k, n]) => `<a href="#/off/macro/${k}" class="${k === sub ? "ativo" : ""}">${n}</a>`).join("")}</div>`;
    const mundo = ["china", "global", "mercados"].includes(sub) ? await dados("dados/mundo.json").catch(() => null) : null;
    if (["china", "global", "mercados"].includes(sub) && !mundo) { app.innerHTML = `${cab("Mundo · Macro", "")}${abas}<p class="sub">Dados indisponíveis no momento.</p>`; return; }
    if (sub === "global") { desenharGlobal(mundo, cab, abas); return; }
    if (sub === "mercados") { desenharMercados(mundo, cab, abas); return; }
    desenharPaisOff(sub, off, cab, abas, mundo);
    return;
  }

  if (secao === "juros") {
    const J = off.juros_mundo || {};
    if (!SUBS_JUROS_OFF.some(([k]) => k === ABA_JUROS_OFF)) ABA_JUROS_OFF = "mundo";
    const abasJ = `<div class="seletor seletor-editoria" id="sub-juros-off" style="margin:-4px 0 12px">${SUBS_JUROS_OFF.map(([k, n]) =>
      `<button data-k="${k}" class="${k === ABA_JUROS_OFF ? "ativo" : ""}">${n}</button>`).join("")}</div>`;
    const fontes = { mundo: "BIS (juros básicos, diário) e OCDE (juros de mercado, mensal)", eua: "Tesouro dos EUA e Fed de Nova York",
      euro: "BCE (taxas, curva AAA e juro de 10 anos por país)", china: "BIS (juro básico) e OCDE (juros de mercado, mensal)" }[ABA_JUROS_OFF];
    const H = T.historico || {};
    const BC = J.bancos_centrais || {}, LP = J.longo_prazo || {}, CP = J.curto_prazo || {}, EU = J.euro_10a || {};
    // série mensal da OCDE só entra se estiver em dia (a Indonésia, por exemplo, parou em dez/2024)
    const emDia = (s) => s && s.datas.length && s.datas[s.datas.length - 1] >= desde(1).slice(0, 7);
    const linhasPaises = (fonte, ids, degrau = false) => ids.filter((k) => fonte[k] && (degrau || emDia(fonte[k]))).map((k, j) => ({
      nome: fonte[k].nome, valores: degrau ? ateHoje(fonte[k]) : Pares(fonte[k]), tipo: "line", cor: PALETA_GRAF[j % PALETA_GRAF.length] }));
    let corpo = "", cartoes = [], desenhar = () => {}, depois = () => {};
    if (ABA_JUROS_OFF === "mundo") {
      cartoes = [["US", "Fed (EUA)"], ["XM", "BCE"], ["CN", "China"], ["JP", "Japão"], ["BR", "Brasil (Copom)"]]
        .map(([k, r]) => cartao(r, pctPronto(u(BC[k]).valor, 2), BC[k] ? `juro básico · ${dataBR(u(BC[k]).data)}` : ""))
        .concat([cartao("Treasury 10 anos", pctPronto(ust10.valor), dataBR(ust10.data))]);
      // um gráfico de juros básicos e um de 10 anos, cada um com os botões Desenvolvidos / Em desenvolvimento
      const GRUPOS = {
        desenvolvidos: { bc: ["US", "XM", "JP", "GB", "CA", "AU", "CH"], lp: ["USA", "EUAAA", "DEU", "FRA", "ITA", "ESP", "JPN", "GBR"] },
        // Turquia fica só na tabela: o juro dela (dezenas de %) achataria as outras linhas
        emergentes: { bc: ["BR", "CN", "MX", "CL", "CO", "PE", "ZA", "IN", "ID", "KR"], lp: ["BRA", "CHN", "MEX", "CHL", "COL", "ZAF", "IND", "KOR", "IDN"] },
      };
      const botoesGrupo = `<div class="seletor" data-grupo-juros>${[["desenvolvidos", "Desenvolvidos"], ["emergentes", "Em desenvolvimento"]].map(([k, n]) =>
        `<button data-k="${k}" class="${GRUPOS_JUROS[k] ? "ativo" : ""}" title="Mostrar ou tirar do gráfico os países do grupo">${n}</button>`).join("")}</div>`;
      // todos os países no mesmo gráfico; cor fixa por país; emergentes tracejados
      const linhasGrupos = (fonte, chave, degrau) => ["desenvolvidos", "emergentes"].flatMap((gr) => GRUPOS[gr][chave].map((k) => [gr, k]))
        .filter(([, k]) => fonte[k] && (degrau || emDia(fonte[k])))
        .map(([gr, k], j) => [gr, { nome: fonte[k].nome, valores: degrau ? ateHoje(fonte[k]) : Pares(fonte[k]), tipo: "line",
          cor: PALETA_GRAF[j % PALETA_GRAF.length], tracejado: gr === "emergentes" }])
        .filter(([gr]) => GRUPOS_JUROS[gr]).map(([, s]) => s);
      const painelBotoes = (id, titulo, info) => `<div class="painel" data-info="${info}"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">${titulo}</h2>
        ${botoesGrupo}</div><div class="grafico" id="${id}"></div></div>`;
      corpo = `${painelBotoes("gw-bc", "Juros básicos dos bancos centrais", "juros_bancos_centrais")}${painelBotoes("gw-10", "Juro de 10 anos", "juros_10a_paises")}
        ${tabelaBancosCentrais(BC)}`;
      desenhar = () => {
        ["gw-bc", "gw-10"].forEach((id) => { const el = document.getElementById(id); const a = echarts.getInstanceByDom(el); if (a) { graficos.splice(graficos.indexOf(a), 1); a.dispose(); } });
        grafico(document.getElementById("gw-bc"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", degrau: true,
          series: linhasGrupos(BC, "bc", true) });
        grafico(document.getElementById("gw-10"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto",
          series: linhasGrupos({ ...LP, ...(E.aaa_10a ? { EUAAA: { nome: "Zona do Euro (AAA, BCE)", ...E.aaa_10a } } : {}) }, "lp", false) });
        document.querySelectorAll("[data-grupo-juros] button").forEach((b) => b.classList.toggle("ativo", !!GRUPOS_JUROS[b.dataset.k]));
      };
      depois = () => document.querySelectorAll("[data-grupo-juros]").forEach((sel) => sel.addEventListener("click", (ev) => {
        const b = ev.target.closest("button"); if (!b) return;
        const k = b.dataset.k;
        if (GRUPOS_JUROS[k] && !(GRUPOS_JUROS.desenvolvidos && GRUPOS_JUROS.emergentes)) return;  // pelo menos um grupo de países no gráfico
        GRUPOS_JUROS[k] = !GRUPOS_JUROS[k];
        desenhar();
      }));
    } else if (ABA_JUROS_OFF === "eua") {
      // inflação implícita: juro nominal menos juro real (TIPS) de 10 anos, nas datas em que os dois existem
      const real10 = Object.fromEntries(Pares(H["10 anos real (TIPS)"]));
      const implicita = Pares(H["10 anos"]).filter(([d]) => real10[d] != null).map(([d, v]) => [d, Math.round((v - real10[d]) * 100) / 100]);
      cartoes = [cartao("Fed Funds (meta)", u(F.meta_min).valor != null ? `${num(u(F.meta_min).valor, 2)}–${num(u(F.meta_max).valor, 2)}%` : "—", `efetiva ${pctPronto(u(F.effr).valor)}`),
        cartao("Treasury 2 anos", pctPronto(u(H["2 anos"]).valor), dataBR(u(H["2 anos"]).data)), cartao("Treasury 10 anos", pctPronto(ust10.valor), dataBR(ust10.data)),
        cartao("Juro real 10 anos (TIPS)", pctPronto(u(H["10 anos real (TIPS)"]).valor), dataBR(u(H["10 anos real (TIPS)"]).data)),
        cartao("Inflação implícita 10 anos", pctPronto(implicita.length ? implicita[implicita.length - 1][1] : null), "nominal − TIPS"),
        cartao("Inclinação 10a − 2a", u(H["inclinação 10a − 2a"]).valor != null ? `${num(u(H["inclinação 10a − 2a"]).valor, 2)} p.p.` : "—", "Treasuries")];
      corpo = `${painelG("gq-ust", "Treasuries — curva nominal", "ust_curva")}${painelG("gq-tips", "Treasuries — curva real (TIPS)", "ust_real")}
        ${painelG("gq-hist", "Treasuries de 2, 10 e 30 anos", "ust_hist")}${painelG("gq-incl", "Inclinação da curva: 10 anos − 2 anos", "ust_hist")}
        ${painelG("gq-fed", "Fed Funds: meta, taxa efetiva e SOFR", "fed_funds")}${painelG("gq-be", "Inflação implícita de 10 anos (Treasury nominal − TIPS)", "breakeven_eua")}`;
      desenhar = () => {
        grafico(document.getElementById("gq-ust"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: curvasPorData(T.nominal) });
        grafico(document.getElementById("gq-tips"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: curvasPorData(T.real) });
        grafico(document.getElementById("gq-hist"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", series: [
          { nome: "2 anos", valores: Pares(H["2 anos"]), tipo: "line", cor: COR.ciano }, { nome: "10 anos", valores: Pares(H["10 anos"]), tipo: "line", cor: COR.ambar },
          { nome: "30 anos", valores: Pares(H["30 anos"]), tipo: "line", cor: COR.roxo }, { nome: "10 anos real (TIPS)", valores: Pares(H["10 anos real (TIPS)"]), tipo: "line", cor: COR.verde, tracejado: true }] });
        grafico(document.getElementById("gq-incl"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", series: [
          { nome: "10a − 2a (pontos percentuais)", valores: Pares(H["inclinação 10a − 2a"]), tipo: "line", cor: COR.ambar }] });
        grafico(document.getElementById("gq-fed"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", degrau: true, series: [
          { nome: "Meta — limite superior", valores: ateHoje(F.meta_max), tipo: "line", cor: COR.ambar }, { nome: "Meta — limite inferior", valores: ateHoje(F.meta_min), tipo: "line", cor: COR.ambar, tracejado: true },
          { nome: "Efetiva (EFFR)", valores: Pares(F.effr), tipo: "line", cor: COR.ciano }, { nome: "SOFR", valores: Pares(F.sofr), tipo: "line", cor: COR.roxo }] });
        grafico(document.getElementById("gq-be"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", series: [
          { nome: "Inflação implícita de 10 anos", valores: implicita, tipo: "line", cor: COR.vermelho }] });
      };
    } else if (ABA_JUROS_OFF === "euro") {
      const de = Object.fromEntries(Pares(EU.DE));
      const spread = (k) => Pares(EU[k]).filter(([d]) => de[d] != null).map(([d, v]) => [d, Math.round((v - de[d]) * 1000) / 1000]);
      cartoes = [cartao("BCE (depósito)", pctPronto(u(E.deposito).valor), dataBR(u(E.deposito).data)), cartao("€STR", pctPronto(u(E.estr).valor), dataBR(u(E.estr).data)),
        cartao("AAA 10 anos", pctPronto(u(E.aaa_10a).valor), dataBR(u(E.aaa_10a).data)),
        ...[["DE", "Alemanha 10 anos"], ["IT", "Itália 10 anos"], ["FR", "França 10 anos"]].map(([k, r]) => cartao(r, pctPronto(u(EU[k]).valor, 2), EU[k] ? `${mesAno(u(EU[k]).data)} · média do mês` : ""))];
      corpo = `${painelG("gq-bce", "BCE: taxa de depósito e €STR", "bce_juros")}${painelG("gq-eur", "Zona do Euro — curva de juros (títulos AAA)", "curva_euro")}
        ${painelG("gq-pais", "Juro de 10 anos por país", "juros_euro_paises")}${painelG("gq-spread", "Diferença para a Alemanha (pontos percentuais)", "spread_euro")}
        ${painelG("gq-eur10", "Juro de 10 anos: Treasury x Zona do Euro AAA", "curva_euro", "", "largo")}`;
      desenhar = () => {
        grafico(document.getElementById("gq-bce"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", degrau: true, series: [
          { nome: "Taxa de depósito", valores: ateHoje(E.deposito), tipo: "line", cor: COR.ambar }, { nome: "€STR", valores: Pares(E.estr), tipo: "line", cor: COR.ciano }] });
        grafico(document.getElementById("gq-eur"), { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: curvasPorData(E.curva) });
        grafico(document.getElementById("gq-pais"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto",
          series: linhasPaises(EU, ["DE", "FR", "IT", "ES", "PT", "GR", "NL"]) });
        grafico(document.getElementById("gq-spread"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto",
          series: ["IT", "FR", "ES", "PT", "GR"].filter((k) => EU[k]).map((k, j) => ({ nome: `${EU[k].nome} − Alemanha`, valores: spread(k), tipo: "line", cor: PALETA_GRAF[j] })) });
        grafico(document.getElementById("gq-eur10"), { xTempo: true, inicioTempo: desde(5), deslizante: true, eixoEsq: "pctPronto", series: [
          { nome: "Treasury 10 anos", valores: Pares(H["10 anos"]), tipo: "line", cor: COR.ambar }, { nome: "Zona do Euro AAA 10 anos", valores: Pares(E.aaa_10a), tipo: "line", cor: COR.roxo }] });
      };
    } else {  // China
      cartoes = [cartao("Juro básico (PBoC)", pctPronto(u(BC.CN).valor, 2), BC.CN ? `BIS · ${dataBR(u(BC.CN).data)}` : ""),
        cartao("Interbancário 3 meses", pctPronto(u(CP.CHN).valor, 2), CP.CHN ? `OCDE · ${mesAno(u(CP.CHN).data)}` : ""),
        cartao("Juro de 10 anos", pctPronto(u(LP.CHN).valor, 2), LP.CHN ? `OCDE · ${mesAno(u(LP.CHN).data)}` : "")];
      corpo = `<div class="painel largo"><h2>Sobre os dados da China</h2><p class="sub" style="line-height:1.6">Não há fonte oficial gratuita com acesso
          automático à curva de juros diária da China: o Banco do Povo da China (PBoC) e as bolsas chinesas não oferecem esses dados de forma aberta.
          Por isso, o juro básico vem do BIS (que reúne as taxas de política monetária informadas pelos bancos centrais) e os juros de mercado
          (interbancário de 3 meses e título do governo de 10 anos) vêm da OCDE, em <b>médias mensais</b> e com cerca de 1 a 2 meses de atraso.</p></div>
        ${painelG("gc-bc", "Juro básico da China (PBoC)", "juros_china")}${painelG("gc-merc", "Juros de mercado da China: 3 meses e 10 anos (mensal)", "juros_china")}
        ${painelG("gc-comp", "Juro de 10 anos: China x EUA (mensal)", "juros_10a_paises", "", "largo")}`;
      desenhar = () => {
        grafico(document.getElementById("gc-bc"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", degrau: true,
          series: BC.CN ? [{ nome: "Juro básico", valores: ateHoje(BC.CN), tipo: "line", cor: COR.vermelho }] : [] });
        grafico(document.getElementById("gc-merc"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto", series: [
          ...(CP.CHN ? [{ nome: "Interbancário 3 meses", valores: Pares(CP.CHN), tipo: "line", cor: COR.ciano }] : []),
          ...(LP.CHN ? [{ nome: "Título do governo 10 anos", valores: Pares(LP.CHN), tipo: "line", cor: COR.ambar }] : [])] });
        grafico(document.getElementById("gc-comp"), { xTempo: true, inicioTempo: desde(10), deslizante: true, eixoEsq: "pctPronto",
          series: linhasPaises(LP, ["CHN", "USA"]) });
      };
    }
    app.innerHTML = `${cab("Mundo · Juros", `${fontes} · taxas em % a.a.`, `<a class="botao" href="downloads/offshore.xlsx" download>Baixar planilha do Mundo</a>`)}
      ${abasJ}<div class="grade-cartoes">${cartoes.join("")}</div><div class="grade">${corpo}</div>`;
    desenhar();
    depois();
    document.getElementById("sub-juros-off").addEventListener("click", (ev) => {
      const b = ev.target.closest("button"); if (!b) return;
      ABA_JUROS_OFF = b.dataset.k;
      paginaOffshore("juros");
    });
    return;
  }

  if (secao === "downloads") {
    app.innerHTML = `${cab("Mundo · Downloads", "Planilha com as séries do exterior, atualizada todo dia")}
      <div class="grade"><div class="painel"><h2>Mundo</h2><p class="sub" style="line-height:1.6">Treasuries (curvas nas datas de comparação e histórico de 2, 10 e 30 anos),
        Fed Funds, SOFR, BCE (depósito, €STR e curva AAA), inflação e emprego dos EUA (BLS) e inflação, desemprego e PIB da Zona do Euro (Eurostat).</p>
        <a class="botao" href="downloads/offshore.xlsx" download>Baixar offshore.xlsx</a></div></div>
      <div class="nota secao">Cada gráfico do site também tem o botão ⤓ para baixar a série daquele gráfico em CSV.</div>`;
    return;
  }

  // Início do Offshore
  const [agenda, noticias] = await Promise.all([dados("dados/agenda_offshore.json").catch(() => null), dados("dados/noticias_offshore.json").catch(() => null)]);
  const mMin = u(F.meta_min), mMax = u(F.meta_max);
  const mercadoOff = ((noticias && noticias.itens) || []).filter((n) => n.tipo === "mercado");
  app.innerHTML = `${cab("Mundo · painel", "Agenda, indicadores e notícias dos EUA e da Zona do Euro")}
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

let PIB_CONS = "total";  // botão Total | Per capita do PIB no Consolidado
async function paginaConsolidado() {
  const [macro, off, mundo] = await Promise.all([dados("dados/macro.json"), dados("dados/offshore.json").catch(() => null), dados("dados/mundo.json").catch(() => null)]);
  const S = macro.series, F = (off && off.fed) || {}, B = (off && off.bls) || {}, E = (off && off.bce) || {}, Z = (off && off.eurostat) || {};
  const CH = (mundo && mundo.china) || {}, BC = ((off && off.juros_mundo) || {}).bancos_centrais || {};
  const G = (mundo && mundo.global) || {}, PIB = ((G.indicadores || {}).NGDPD) || null, PIB_PC = ((G.indicadores || {}).NGDPDPC) || null, paises = G.paises || {};
  const u = (s) => ultimo(s);
  const mes = (s) => (u(s).data ? `${MESES[Number(u(s).data.slice(5, 7)) - 1]}/${u(s).data.slice(2, 4)}` : "");
  const linha = (pais, nome, valores, extra = {}) => ({ nome, valores, tipo: "line", cor: PAISES[pais] ? PAISES[pais][1] : COR.vermelho, ...extra });
  const tempo = (anos = 10) => ({ xTempo: true, inicioTempo: desde(anos), deslizante: true, eixoEsq: "pctPronto" });
  const china = (s, nome) => (s && s.datas ? [linha("china", nome, Pares(s), { cor: COR.vermelho, tracejado: true })] : []);
  app.innerHTML = `<div class="cabecalho"><div><h1>Consolidado · Gráficos</h1>
      <div class="sub">Brasil e o mundo nos mesmos gráficos · mesmas fontes oficiais das seções Brasil e Mundo</div></div></div>
    <div class="grade-cartoes">
      ${cartao("Selic meta", pctPronto(u(S.selic_meta).valor), dataBR(u(S.selic_meta).data))}
      ${cartao("Fed Funds (teto)", pctPronto(u(F.meta_max).valor), dataBR(u(F.meta_max).data))}
      ${cartao("BCE (depósito)", pctPronto(u(E.deposito).valor), dataBR(u(E.deposito).data))}
      ${cartao("IPCA 12m", pctPronto(u(S.ipca_12m).valor, 1), mes(S.ipca_12m))}
      ${cartao("CPI EUA 12m", pctPronto(u(B.cpi_12m).valor, 1), mes(B.cpi_12m))}
      ${cartao("HICP 12m", pctPronto(u(Z.hicp_12m).valor, 1), mes(Z.hicp_12m))}
    </div>
    <div class="grade">
      ${PIB ? `<div class="painel largo" data-info="pib_nominal_mundo"><div class="cabecalho" style="margin-bottom:6px">
        <h2 style="margin:0">PIB nominal em US$ (FMI)</h2>${PIB_PC ? `<div class="seletor" id="pib-modo">${[["total", "Total"], ["pc", "Per capita"]].map(([k, n]) =>
          `<button data-k="${k}" class="${PIB_CONS === k ? "ativo" : ""}">${n}</button>`).join("")}</div>` : ""}</div>
        <div class="grafico alto" id="gc-pib"></div>
        <div class="nota">Anual, em dólares correntes; a partir de ${G.ano_corrente || new Date().getFullYear()} (inclusive), projeções do FMI.</div></div>` : ""}
      ${painelG("gc-inf", "Inflação em 12 meses", "inflacao_mundo", "", "largo")}
      ${painelG("gc-juros", "Juros básicos dos bancos centrais", "juros_bancos_centrais", "", "largo")}
      ${painelG("gc-des", "Desemprego", "desemprego_mundo", "", "largo")}
    </div>`;
  // botão Total | Per capita: mesmos países; o total vem em US$ bilhões, o per capita em US$ por habitante
  const desenharPib = () => {
    const ind = PIB_CONS === "pc" && PIB_PC ? PIB_PC : PIB, escala = ind === PIB ? 1e9 : 1;
    const CODIGOS = ["USA", "CHN", "EURO", "JPN", "DEU", "IND", "GBR", "FRA", "BRA", "ITA", "CAN", "MEX", "KOR"].filter((c) => ind.valores[c]);
    const anos = [...new Set(CODIGOS.flatMap((c) => Object.keys(ind.valores[c])))].sort();
    MOEDA = "US$";  // eixo e caixa de valores em dólares (a navegação seguinte volta para R$)
    grafico(document.getElementById("gc-pib"), { rotulos: anos, eixoEsq: "reais", janela: 40, series: CODIGOS.map((c, j) => ({
      nome: paises[c], valores: anos.map((a) => (ind.valores[c][a] != null ? ind.valores[c][a] * escala : null)), tipo: "line",
      cor: c === "BRA" ? PAISES.br[1] : PALETA_GRAF[j % PALETA_GRAF.length] })) });
  };
  if (PIB) {
    desenharPib();
    const sel = document.getElementById("pib-modo");
    if (sel) sel.addEventListener("click", (ev) => {
      const b = ev.target.closest("button"); if (!b) return;
      PIB_CONS = b.dataset.k;
      sel.querySelectorAll("button").forEach((x) => x.classList.toggle("ativo", x === b));
      desenharPib();
    });
  }
  grafico(document.getElementById("gc-inf"), { ...tempo(), series: [
    linha("br", "IPCA (Brasil)", Pares(S.ipca_12m)), linha("eua", "CPI (EUA)", Pares(B.cpi_12m)), linha("euro", "HICP (Zona do Euro)", Pares(Z.hicp_12m)),
    ...china(CH.cpi_12m, "CPI (China, OCDE)")] });
  // Turquia fica de fora: o juro dela (dezenas de %) achataria as outras linhas
  grafico(document.getElementById("gc-juros"), { ...tempo(), degrau: true, series: Object.entries(BC).filter(([k]) => k !== "TR")
    .map(([k, s], j) => ({ nome: s.nome, valores: ateHoje(s), tipo: "line", cor: k === "BR" ? PAISES.br[1] : PALETA_GRAF[j % PALETA_GRAF.length] })) });
  grafico(document.getElementById("gc-des"), { ...tempo(), series: [
    linha("br", "Brasil (PNAD Contínua)", Pares(S.desemprego)), linha("eua", "EUA", Pares(B.desemprego)), linha("euro", "Zona do Euro", Pares(Z.desemprego)),
    ...china(CH.desemprego, "China (urbano; série descontinuada)")] });
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
const ABAS_BANCO = [["perfil", "Perfil"], ["capital", "Capital"], ["dfs", "DFs"], ["carteira_resumo", "Carteira — resumo"], ["carteira_total", "Carteira — total"]];
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
  // Eventos e notícias logo depois do Perfil (só para bancos listados, que têm documentos na CVM)
  const abasBanco = ABAS_BANCO.filter(([k]) => !(soCvm && k.startsWith("carteira")))
    .flatMap((a) => (a[0] === "perfil" && tk ? [a, ["eventos", "Eventos e notícias"]] : [a]));
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
      </div>`;
      if (tk) { desenharFicha(ficha); desenharNegocio(negocio, resumoAp); }
      grafico(document.getElementById("gb-ativo"), { xTempo: true, eixoEsq: "reais", series: [
        { nome: "Ativo total", valores: P(H.ativo, H.datas), tipo: "line", cor: COR.azul },
        ...(H.carteira ? [{ nome: "Carteira de crédito", valores: P(H.carteira, H.datas), tipo: "line", cor: COR.ambar }] : []),
        ...(H.captacoes ? [{ nome: "Captações", valores: P(H.captacoes, H.datas), tipo: "line", cor: COR.cinza, tracejado: true }] : [])] });
      grafico(document.getElementById("gb-lucro"), { xTempo: true, eixoEsq: "reais", eixoDir: "reais", series: [
        { nome: "Lucro trimestral", valores: P(H.lucro_tri, H.datas), cor: COR.verde }, { nome: "Patrimônio líquido", valores: P(H.pl, H.datas), tipo: "line", eixo: "dir", cor: COR.ambar }] });
    },
    capital: () => {
      if (soCvm) { area().innerHTML = `<div class="painel"><h2>Capital</h2><p class="sub">Sem dados de capital (Basileia) para esta instituição: ela não está no IF.data.</p></div>`; return; }
      const rot = T.map(triIF);
      const C = (k) => (bk.capital.find((l) => l.k === k) || { v: [] }).v;
      const H = bk.historico;
      // mínimos regulatórios (Res. CMN 4.958/2021): capital principal 4,5%, nível I 6%, PR 8%, mais o adicional de conservação de 2,5%
      const linhaMin = (nome, v, datas) => ({ nome, valores: datas.map((d) => [d, v]), tipo: "line", cor: COR.vermelho, tracejado: true });
      area().innerHTML = `<div class="grade-cartoes">
          ${cartao("Índice de Basileia", pct(C("n")[n]), triIF(T[n]))}
          ${cartao("Índice de Nível I", pct(C("m")[n]), "")}
          ${cartao("Índice de Capital Principal", pct(C("l")[n]), "")}
          ${cartao("Razão de alavancagem", pct(C("o")[n]), "Nível I ÷ exposição total")}
          ${cartao("Patrimônio de Referência", reais(C("e")[n]), "PR")}
          ${cartao("RWA", reais(C("j")[n]), "ativos ponderados pelo risco")}
        </div>
        <div class="grade">
          ${painelG("gk-pr", "Composição do Patrimônio de Referência (R$)", "capital_banco")}
          ${painelG("gk-ind", "Índices de capital", "capital_banco")}
          ${painelG("gk-rwa", "RWA por tipo de risco (R$)", "capital_banco")}
          ${painelG("gk-alav", "Razão de alavancagem", "capital_banco")}
          ${painelG("gk-hist", "Índice de Basileia e Patrimônio de Referência (desde 2015)", "capital_banco", "", "largo")}
        </div>
        <div class="nota secao">Trimestres desde 1T25 (layout novo do IF.data); o gráfico de baixo usa o histórico do resumo do IF.data desde 2015.
          Linhas tracejadas: mínimos regulatórios com o adicional de conservação de capital (2,5%) — capital principal 7%, nível I 8,5% e PR 10,5%
          (sem os adicionais contracíclico e sistêmico, que variam por banco). Alavancagem mínima de 3% (S1 e S2).</div>`;
      grafico(document.getElementById("gk-pr"), { rotulos: rot, eixoEsq: "reais", series: [
        { nome: "Capital principal", valores: C("a"), cor: COR.azul, pilha: "pr" },
        { nome: "Capital complementar", valores: C("b"), cor: COR.ciano, pilha: "pr" },
        { nome: "Nível II", valores: C("d"), cor: COR.roxo, pilha: "pr" },
        { nome: "Patrimônio de Referência", valores: C("e"), tipo: "line", cor: COR.ambar }] });
      const minimo = (v) => rot.map(() => v);
      grafico(document.getElementById("gk-ind"), { rotulos: rot, eixoEsq: "pct", series: [
        { nome: "Basileia", valores: C("n"), tipo: "line", cor: COR.ambar },
        { nome: "Nível I", valores: C("m"), tipo: "line", cor: COR.azul },
        { nome: "Capital principal", valores: C("l"), tipo: "line", cor: COR.verde },
        { nome: "Mín. PR (10,5%)", valores: minimo(0.105), tipo: "line", cor: COR.ambar, tracejado: true },
        { nome: "Mín. nível I (8,5%)", valores: minimo(0.085), tipo: "line", cor: COR.azul, tracejado: true },
        { nome: "Mín. capital principal (7%)", valores: minimo(0.07), tipo: "line", cor: COR.verde, tracejado: true }] });
      grafico(document.getElementById("gk-rwa"), { rotulos: rot, eixoEsq: "reais", series: [
        { nome: "Risco de crédito", valores: C("f"), cor: COR.azul, pilha: "rwa" },
        { nome: "Risco de mercado", valores: C("g"), cor: COR.ambar, pilha: "rwa" },
        { nome: "Risco operacional", valores: C("h"), cor: COR.roxo, pilha: "rwa" },
        ...(C("i").some((x) => x) ? [{ nome: "RWAsp (serviços de pagamento)", valores: C("i"), cor: COR.ciano, pilha: "rwa" }] : [])] });
      grafico(document.getElementById("gk-alav"), { rotulos: rot, eixoEsq: "pct", series: [
        { nome: "Razão de alavancagem", valores: C("o"), tipo: "line", cor: COR.ambar },
        { nome: "Mínimo (3%)", valores: minimo(0.03), tipo: "line", cor: COR.vermelho, tracejado: true }] });
      grafico(document.getElementById("gk-hist"), { xTempo: true, eixoEsq: "pct", eixoDir: "reais", series: [
        { nome: "Índice de Basileia", valores: P(H.basileia, H.datas), tipo: "line", cor: COR.ambar },
        linhaMin("Mínimo com adicional de conservação (10,5%)", 0.105, H.datas),
        ...(H.pr ? [{ nome: "Patrimônio de Referência", valores: P(H.pr, H.datas), cor: COR.azul, eixo: "dir" }] : [])] });
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
      const not = await dados("dados/noticias_empresas.json").catch(() => dados("dados/noticias.json").catch(() => null));
      const doBanco = ((not && not.itens) || []).filter((x) => (x.empresas || []).includes(tk));
      // eventos na 1ª linha e notícias na 2ª, cada um na largura toda (igual à página das empresas)
      area().innerHTML = `<div class="grade grade-empilhada">
        <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Eventos (CVM)</h2>
          <div class="seletor" id="sel-ev">${OPCOES_EVENTOS.map(([k, r]) => `<button data-k="${k}" class="${k === "todos" ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
          <div class="rolagem rolagem-y" id="lista-eventos"></div>
          <div class="nota">Fatos relevantes, comunicados ao mercado e avisos aos acionistas dos últimos 3 anos, com link para o documento oficial na CVM.</div></div>
        <div class="painel"><h2>Notícias que citam o banco</h2>${listaNoticias(doBanco, 300)}
          <div class="nota">Manchetes que citam o ticker ou o nome de pregão, da mais recente para a mais antiga, nas mesmas fontes da seção
            Notícias e agenda, guardadas por até ${(not && not.dias) || 7} dias. Só a manchete, com link para a matéria.</div></div></div>`;
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
        ${painelG("gt-pf-prazo", `Carteira PF por modalidade e prazo — ${triIF(T[n])}`, "carteira_banco", "", "largo")}
        ${painelG("gt-pj-prazo", `Carteira PJ por modalidade e prazo — ${triIF(T[n])}`, "carteira_banco", "", "largo")}
        ${painelG("gt-pfpj", "Carteira PF x PJ (R$)", "carteira_banco", "", "largo")}
      </div>`;
      grafico(document.getElementById("gt-pf"), { rotulos: rot, eixoEsq: "reais", series: pfM.map((m, i) => ({ nome: m, valores: serieM(bk.pf, m), cor: PALETA_GRAF[i % PALETA_GRAF.length], pilha: "a" })) });
      grafico(document.getElementById("gt-pj"), { rotulos: rot, eixoEsq: "reais", series: pjM.map((m, i) => ({ nome: m.slice(0, 40), valores: serieM(bk.pj, m), cor: PALETA_GRAF[i % PALETA_GRAF.length], pilha: "a" })) });
      const porPrazo = (g, ms) => PRAZOS_IF.map((f, i) => ({ nome: f.replace("A Vencer ", "").replace("Entre ", ""), valores: ms.map((m) => faixasUlt(g, m)[i]), cor: PALETA_GRAF[i], pilha: "a" }));
      grafico(document.getElementById("gt-pf-prazo"), { rotulos: pfM.map((m) => m.slice(0, 28)), eixoEsq: "reais", series: porPrazo(bk.pf, pfM) });
      grafico(document.getElementById("gt-pj-prazo"), { rotulos: pjM.map((m) => m.slice(0, 28)), eixoEsq: "reais", series: porPrazo(bk.pj, pjM) });
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
  macro: "Macro (Banco Central, IBGE, FGV)", credito: "Crédito (Banco Central)", setor_externo: "Setor externo (Banco Central e Comex Stat)", mundo: "Mundo — mercados, commodities, China e Global (FRED, Banco Mundial, OCDE, FMI)", empresas_mundo: "Mundo — empresas do S&P 500 (SEC EDGAR)", agenda: "Agenda (Banco Central, IBGE, FGV)", tesouro: "Tesouro Direto", curva_di: "Curva DI (B3)",
  mercado: "Cotações e proventos (B3)", noticias: "Notícias", planilhas: "Planilhas de Macro e Juros", eventos: "Eventos (CVM)",
  ficha: "Ficha da empresa (FRE/FCA)", fre_textos: "Trechos do Formulário de Referência", resumos: "Resumos aprofundados",
  cvm_base: "Base de demonstrações (CVM)", empresas: "Empresas (JSON e Excel)", indice: "Índice de empresas",
  offshore: "Mundo (Tesouro dos EUA, Fed, BLS, BCE, Eurostat)", bancos: "Instituições financeiras (IF.data)", eleicoes: "Eleições 2026 (TSE)", calendario_resultados: "Calendário de resultados (CVM)", tesouro_intradia: "Tesouro Direto — tempo real (3x ao dia)",
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
