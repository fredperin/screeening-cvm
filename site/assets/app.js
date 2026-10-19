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
  on: { "": paginaInicio, noticias: paginaNoticias, macro: paginaMacro, juros: paginaJuros, empresas: paginaEmpresas, empresa: paginaEmpresa, downloads: paginaDownloads },
  off: Object.fromEntries(SECOES.map(([k]) => [k, () => paginaOffshore(k)])),
};
const ROTAS_ANTIGAS = { agenda: "noticias" };  // endereços de antes da divisão Onshore/Offshore

function desenharNav(lado, secao) {
  document.querySelectorAll("#lados a").forEach((a) => a.classList.toggle("ativo", a.dataset.lado === lado));
  document.getElementById("nav").innerHTML = SECOES.map(([k, nome]) =>
    `<a href="#/${lado || "on"}${k ? `/${k}` : ""}" class="${lado && k === secao ? "ativo" : ""}">${nome}</a>`).join("");
  document.body.dataset.lado = lado || "";
}

async function rotear() {
  limparGraficos();
  fecharTelaCheia();
  fecharModal();
  const partes = location.hash.replace(/^#\/?/, "").split("/");
  if (partes[0] === "status") { desenharNav(null, null); return executar(paginaStatus); }
  if (partes[0] !== "on" && partes[0] !== "off") {
    partes[0] = ROTAS_ANTIGAS[partes[0]] || partes[0];
    location.replace(`#/on/${partes.join("/")}`.replace(/\/+$/, ""));
    return;
  }
  const [lado, secao = "", parametro] = partes;
  desenharNav(lado, secao === "empresa" ? "empresas" : secao);
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
new MutationObserver(() => decorarPaineis()).observe(app, { childList: true, subtree: true });

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
  const [macro, tesouro, di, mercado, fatos, agenda] = await Promise.all([
    dados("dados/macro.json").catch(() => null), dados("dados/tesouro.json").catch(() => null),
    dados("dados/curva_di.json").catch(() => null), dados("dados/mercado.json").catch(() => null),
    dados("dados/eventos_recentes.json").catch(() => null), dados("dados/agenda.json").catch(() => null),
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
    <div class="cabecalho"><div><h1>Onshore · painel</h1><div class="sub">Macro, juros e empresas da lista selecionada</div></div></div>
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
      <div class="painel"><h2>Últimas divulgações</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Empresa</th><th>Período</th><th>Receita</th><th>Var. a/a</th><th>Lucro</th><th>Var. a/a</th></tr>
        ${recentes.map((e) => `<tr class="clicavel" onclick="location.hash='#/on/empresa/${esc(e.id)}'">
          <td>${esc(e.tickers[0])} <span class="sub">${esc(e.nome.slice(0, 22))}</span></td><td>${dataBR(e.ultimo_periodo)}</td>
          <td>${reais(e.receita_tri)}</td><td class="${classeSinal(e.cresc_receita_tri)}">${pct(e.cresc_receita_tri)}</td>
          <td>${reais(e.lucro_tri)}</td><td class="${classeSinal(e.cresc_lucro_tri)}">${pct(e.cresc_lucro_tri)}</td></tr>`).join("")}
      </table></div></div>
      <div class="painel"><h2>Agenda — próximos 14 dias</h2>${tabelaAgenda(agenda, 14)}
        <div class="nota"><a href="#/on/noticias">Ver agenda completa</a></div></div>
      <div class="painel"><h2>Fatos relevantes recentes</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Data</th><th>Papel</th><th style="text-align:left">Assunto</th></tr>
        ${fatos && fatos.eventos.length ? fatos.eventos.slice(0, 40).map((e) => `<tr><td>${dataBR(e.data)}</td>
          <td><a href="#/on/empresa/${esc(e.id)}">${esc(e.id)}</a></td>
          <td style="white-space:normal;text-align:left">${e.link ? `<a href="${esc(e.link)}" target="_blank" rel="noopener">${esc(e.assunto)}</a>` : esc(e.assunto)}</td></tr>`).join("")
          : `<tr><td colspan="3" class="sub">Sem fatos relevantes recentes.</td></tr>`}
      </table></div></div>
      <div class="painel"><h2>Próximos proventos (data-com ou pagamento futuros)</h2><div class="rolagem rolagem-y"><table class="tabela">
        <tr><th>Papel</th><th>Tipo</th><th>Data-com</th><th>Pagamento</th><th>R$/ação</th></tr>
        ${proximos.length ? proximos.slice(0, 40).map((p) => `<tr class="clicavel" onclick="location.hash='#/on/empresa/${esc(p.id)}'">
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
let ABA_EMPRESA = "resultados";
let NOTICIAS_CACHE = null;
const ABAS_EMPRESA = [["resultados", "Resultados"], ["indicadores", "Indicadores"], ["dividendos", "Dividendos"], ["negocio", "Negócio"], ["eventos", "Eventos e notícias"]];
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
        <div class="grade"><div class="painel" id="ficha"></div><div class="painel" id="negocio"></div></div>`;
      desenharFicha(ficha);
      desenharNegocio(negocio, resumo);
    },
    eventos: () => {
      const doEmp = ((NOTICIAS_CACHE && NOTICIAS_CACHE.itens) || []).filter((n) => (n.empresas || []).includes(id));
      document.getElementById("aba-empresa").innerHTML = `<div class="grade">
        <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Eventos (CVM)</h2>
          <div class="seletor" id="sel-ev">${OPCOES_EVENTOS.map(([k, r]) => `<button data-k="${k}" class="${k === "todos" ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
          <div class="rolagem rolagem-y" id="lista-eventos"></div>
          <div class="nota">Fatos relevantes, comunicados ao mercado e avisos aos acionistas dos últimos 3 anos, com link para o documento oficial na CVM.</div></div>
        <div class="painel"><h2>Notícias que citam a empresa</h2>${listaNoticias(doEmp, 60)}
          <div class="nota">Manchetes dos últimos 45 dias (Banco Central, IBGE, CVM e Agência Brasil) que citam o ticker ou o nome de pregão.</div></div></div>`;
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
    ABA_EMPRESA = ABAS[k] ? k : "resultados";
    document.querySelectorAll("#abas-empresa button").forEach((x) => x.classList.toggle("ativo", x.dataset.k === ABA_EMPRESA));
    ABAS[ABA_EMPRESA]();
  };
  document.getElementById("abas-empresa").addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (b) mostrar(b.dataset.k);
  });
  NOTICIAS_CACHE = await dados("dados/noticias.json").catch(() => null);
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
const SUBS_MACRO = [["inflacao", "Inflação"], ["atividade", "Atividade"], ["monetaria", "Política monetária"], ["cambio", "Câmbio"], ["expectativas", "Expectativas (Focus)"]];
const NOMES_FOCUS = { ipca: "IPCA (%)", selic: "Selic fim de ano (% a.a.)", cambio: "Câmbio fim de ano (R$/US$)", pib: "PIB (%)" };
const NUCLEOS = [["nucleo_ex0", "EX0", COR.azul], ["nucleo_ex2", "EX2", COR.cinza], ["nucleo_ex3", "EX3", COR.roxo],
  ["nucleo_ms", "MS", COR.ciano], ["nucleo_dp", "DP", COR.verde], ["nucleo_p55", "P55", "#db61a2"]];

async function paginaMacro(sub) {
  if (!SUBS_MACRO.some(([k]) => k === sub)) sub = "inflacao";
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
      cartao("IBC-Br m/m (dessaz.)", pctPronto(u("ibcbr_mensal").valor), mes("ibcbr_mensal")), cartao("IBC-Br 12 meses", pctPronto(u("ibcbr_12m").valor), mes("ibcbr_12m"))],
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
  // Histórico completo em todos os gráficos; os botões só escolhem a janela inicial (dá para dar zoom para trás)
  const inicio = (anos) => { if (anos >= 99) return null; const d = new Date(); d.setFullYear(d.getFullYear() - anos); return d.toISOString().slice(0, 10); };
  const corte = inicio(JANELA_MACRO);
  const P = (s) => (s ? s.datas.map((d, i) => [d, s.valores[i]]) : []);
  const inflacao = (k, nome) => ({ series: [
    { nome: "Mensal", valores: P(S[k]), cor: COR.azul },
    { nome: "12 meses", valores: P(S[`${k}_12m`]), tipo: "line", eixo: "dir", cor: COR.vermelho },
    { nome: "3 meses anualizado", valores: P(S[`${k}_mm3`]), tipo: "line", eixo: "dir", cor: COR.ambar, tracejado: true }], eixoEsq: "pctPronto", eixoDir: "pctPronto" });
  const anos = S.pib_anual ? S.pib_anual.datas.map((d) => d.slice(0, 4)) : [];
  const nominal = S.pib_nominal ? Object.fromEntries(S.pib_nominal.datas.map((d, i) => [d.slice(0, 4), S.pib_nominal.valores[i]])) : {};
  // [título, explicativo, opções, classe extra]
  const defs = {
    inflacao: [
      ["IPCA", "ipca", inflacao("ipca")],
      ["Núcleos do IPCA — acumulado em 12 meses", "nucleos", { eixoEsq: "pctPronto", series: [
        { nome: "Média dos 5 núcleos", valores: P(S.nucleos_media_12m), tipo: "line", cor: COR.ambar },
        ...NUCLEOS.map(([k, n, c]) => ({ nome: n, valores: P(S[`${k}_12m`]), tipo: "line", cor: c })),
        { nome: "IPCA cheio", valores: P(S.ipca_12m), tipo: "line", cor: COR.vermelho, tracejado: true }] }],
      ["Núcleos do IPCA — 3 meses anualizado", "nucleos", { eixoEsq: "pctPronto", series: [
        { nome: "Média dos 5 núcleos", valores: P(S.nucleos_media_mm3), tipo: "line", cor: COR.ambar },
        ...NUCLEOS.map(([k, n, c]) => ({ nome: n, valores: P(S[`${k}_mm3`]), tipo: "line", cor: c })),
        { nome: "IPCA cheio", valores: P(S.ipca_mm3), tipo: "line", cor: COR.vermelho, tracejado: true }] }],
      ["IGP-M", "igpm", inflacao("igpm")],
      ["INCC-DI (custo da construção)", "incc", inflacao("incc")],
      ["Inflação em 12 meses: IPCA, IGP-M e INCC", "ipca", { eixoEsq: "pctPronto", series: [
        { nome: "IPCA", valores: P(S.ipca_12m), tipo: "line", cor: COR.vermelho }, { nome: "IGP-M", valores: P(S.igpm_12m), tipo: "line", cor: COR.azul },
        { nome: "INCC-DI", valores: P(S.incc_12m), tipo: "line", cor: COR.verde }] }],
    ],
    atividade: [
      ["PIB trimestral", "pib_tri", { series: [{ nome: "Trimestral (dessaz., tri/tri)", valores: P(S.pib_tri), cor: COR.azul }, { nome: "Acumulado em 4 trimestres", valores: P(S.pib_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto" }],
      ["PIB anual (anos fechados)", "pib_anual", { xTempo: false, rotulos: anos, eixoEsq: "pctPronto", eixoDir: "reais", janela: 30, series: [
        { nome: "Crescimento real", valores: S.pib_anual ? S.pib_anual.valores : [], cor: COR.azul },
        { nome: "PIB nominal (R$ correntes)", valores: anos.map((a) => nominal[a] ?? null), tipo: "line", eixo: "dir", cor: COR.ambar }] }],
      ["IBC-Br (prévia mensal do PIB)", "ibcbr", { series: [{ nome: "Mensal (dessaz., m/m)", valores: P(S.ibcbr_mensal), cor: COR.azul }, { nome: "Acumulado em 12 meses", valores: P(S.ibcbr_12m), tipo: "line", eixo: "dir", cor: COR.ambar }], eixoEsq: "pctPronto", eixoDir: "pctPronto", inicio: inicio(Math.min(JANELA_MACRO, 3)) }],
    ],
    monetaria: [
      ["Selic meta e CDI", "selic", { series: [{ nome: "Selic meta", valores: P(S.selic_meta), tipo: "line", cor: COR.ambar }, { nome: "CDI", valores: P(S.cdi), tipo: "line", cor: COR.ciano }], eixoEsq: "pctPronto", degrau: true }],
      ["Juro real ex-post (Selic ÷ IPCA 12m)", "juro_real", { series: [{ nome: "Juro real", valores: P(S.juro_real), tipo: "line", cor: COR.verde }], eixoEsq: "pctPronto" }],
      ["Selic meta e IPCA 12 meses", "selic", { series: [{ nome: "Selic meta", valores: P(S.selic_meta), tipo: "line", cor: COR.ambar }, { nome: "IPCA 12m", valores: P(S.ipca_12m), tipo: "line", cor: COR.vermelho }, { nome: "Média dos núcleos 12m", valores: P(S.nucleos_media_12m), tipo: "line", cor: COR.roxo, tracejado: true }], eixoEsq: "pctPronto", degrau: true }],
    ],
    cambio: [
      ["Câmbio PTAX", "cambio", { series: [{ nome: "Dólar", valores: P(S.usd), tipo: "line", cor: COR.verde }, { nome: "Euro", valores: P(S.eur), tipo: "line", cor: COR.roxo }], eixoEsq: "preco" }, "largo"],
    ],
    expectativas: Object.keys(NOMES_FOCUS).map((k) => [NOMES_FOCUS[k], "focus", { focus: k }]),
  }[sub];
  const area = document.getElementById("graficos-macro");
  area.innerHTML = defs.map((d, i) => `<div class="painel${d[3] ? ` ${d[3]}` : ""}" data-info="${d[1]}"><h2>${d[0]}</h2><div class="grafico${d[3] ? " alto" : ""}" id="gm-${i}"></div></div>`).join("");
  defs.forEach((d, i) => {
    const el = document.getElementById(`gm-${i}`);
    if (d[2].focus) {
      const k = d[2].focus, anosF = Object.keys(F[k] || {}).sort();
      grafico(el, { xTempo: true, eixoEsq: k === "cambio" ? "preco" : "pctPronto",
        series: anosF.map((a, j) => ({ nome: a, valores: F[k][a].datas.map((x, n) => [x, F[k][a].valores[n]]), tipo: "line", cor: PALETA_DATAS[j % PALETA_DATAS.length] })) });
      return;
    }
    const { inicio: ini, xTempo = true, ...opcoes } = d[2];
    grafico(el, xTempo ? { xTempo: true, inicioTempo: (ini !== undefined ? ini : corte) || "1990-01-01", deslizante: true, ...opcoes } : opcoes);
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
// Tesouro Direto em tempo real (não oficial): painel separado, nunca misturado aos dados oficiais
function painelTempoReal(tes) {
  const tr = tes.tempo_real;
  if (!tr) return `<div class="painel largo tempo-real" data-info="tesouro_tempo_real"><h2>Tesouro Direto agora <span class="selo">tempo real · não oficial</span></h2>
    <p class="sub">${tes.falha_tempo_real ? `Indisponível no momento (${esc(tes.falha_tempo_real.slice(0, 160))}).`
      : "Sem preço mais novo que a referência oficial (fora do horário de negociação, ou o oficial já está em dia)."} Os dados oficiais abaixo seguem válidos.</p></div>`;
  const oficial = Object.fromEntries(tes.titulos.map((t) => [`${t.tipo}|${t.vencimento}`, t]));
  const [dia, hora] = [tr.precificado_em.slice(0, 10), tr.precificado_em.slice(11, 16)];
  return `<div class="painel largo tempo-real" data-info="tesouro_tempo_real">
    <h2>Tesouro Direto agora — preços de ${dataBR(dia)} às ${hora} <span class="selo">tempo real · não oficial</span></h2>
    <div class="grade"><div class="grafico alto" id="gj-agora"></div>
      <div class="rolagem rolagem-y"><table class="tabela"><tr><th>Título</th><th>Vencimento</th><th>Taxa agora</th><th>vs. oficial</th><th>PU agora</th><th>Hora</th></tr>
        ${tr.titulos.map((t) => { const o = oficial[`${t.tipo}|${t.vencimento}`]; const dif = o ? (t.taxa_compra - o.taxa_compra) * 100 : null;
          return `<tr><td>${esc(t.tipo.replace("Tesouro ", ""))}</td><td>${dataBR(t.vencimento)}</td><td>${num(t.taxa_compra, 2)}%</td>
            <td class="${dif == null ? "" : dif > 0 ? "neg" : "pos"}">${dif == null ? "—" : `${dif > 0 ? "+" : ""}${num(dif, 0)} bp`}</td>
            <td>R$ ${num(t.pu_compra, 2)}</td><td class="sub">${esc((t.precificado_em || "").slice(11, 16))}</td></tr>`; }).join("")}</table></div></div>
    <div class="nota">Fonte: site do Tesouro Direto — as taxas pelas quais o Tesouro Direto está vendendo agora, repreçadas ao longo do dia.
      <b>Não oficial:</b> lidas de um endereço interno do site, sem documentação nem garantia; cada taxa passa por travas (preço positivo e no máximo
      1 ponto de diferença da última taxa oficial) antes de ser publicada. Atualizado 3 vezes por dia útil. "vs. oficial" compara com a referência
      oficial de ${dataBR(tes.data_base)}.</div></div>`;
}

function desenharTempoReal(tes) {
  const tr = tes.tempo_real, el = document.getElementById("gj-agora");
  if (!tr || !el) return;
  const pts = (lista) => (lista || []).map((p) => [p.anos, p.taxa]);
  const of = tes.curvas.hoje || {};
  grafico(el, { xNome: "anos até o vencimento", eixoEsq: "pctPronto", series: [
    { nome: "Prefixado agora", valores: pts(tr.curva.prefixado), tipo: "line", cor: COR.ambar },
    { nome: `Prefixado oficial ${dataBR(of.data)}`, valores: pts(of.prefixado), tipo: "line", cor: COR.ambar, tracejado: true },
    { nome: "IPCA+ agora", valores: pts(tr.curva.ipca), tipo: "line", cor: COR.ciano },
    { nome: `IPCA+ oficial ${dataBR(of.data)}`, valores: pts(of.ipca), tipo: "line", cor: COR.ciano, tracejado: true }] });
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
      ${painelTempoReal(tes)}
      <div data-info="tesouro_pre" class="painel"><h2>Tesouro prefixado — oficial · ref. ${dataBR(tes.data_base)}</h2><div class="grafico alto" id="gj-pre"></div></div>
      <div data-info="tesouro_ipca" class="painel"><h2>Tesouro IPCA+ (juro real) — oficial · ref. ${dataBR(tes.data_base)}</h2><div class="grafico alto" id="gj-ipca"></div></div>
      <div data-info="inflacao_implicita" class="painel"><h2>Inflação implícita (prefixado × IPCA+) — oficial · ref. ${dataBR(tes.data_base)}</h2><div class="grafico alto" id="gj-impl"></div></div>
      <div data-info="vertices" class="painel"><h2>Taxas DI por prazo (B3)</h2><div class="rolagem" id="tab-vertices"></div>
        <div class="nota">Interpolação linear da curva DI nos prazos (anos de 252 dias úteis). DI x IPCA = juro real.</div></div>
      <div data-info="titulos" class="painel largo"><h2>Títulos — Tesouro Direto oficial · referência ${dataBR(tes.data_base)}</h2><div class="grade" id="tab-tit">
        ${GRUPOS_TESOURO.filter(([tipo]) => tes.titulos.some((t) => t.tipo === tipo)).map(([tipo, nome]) => `
          <div><div class="sub" style="margin:4px 0 6px;color:var(--ambar)">${esc(nome)}</div><table class="tabela">
            <tr><th>Vencimento</th><th>Taxa compra</th><th>Var. 1 sem.</th><th>PU compra</th></tr>
            ${tes.titulos.filter((t) => t.tipo === tipo).map((t) => { const v = variacaoSemana(tes, t);
              return `<tr class="clicavel" data-id="${esc(t.id)}"><td>${dataBR(t.vencimento)}</td><td>${num(t.taxa_compra, 2)}%</td>
                <td class="${v == null ? "" : v > 0 ? "neg" : "pos"}">${v == null ? "—" : `${v > 0 ? "+" : ""}${num(v * 100, 0)} bp`}</td><td>R$ ${num(t.pu_compra, 2)}</td></tr>`; }).join("")}
          </table></div>`).join("")}
      </div><div class="nota">Fonte oficial: Tesouro Transparente (dados abertos do Tesouro Nacional), taxa de compra da manhã de ${dataBR(tes.data_base)}.
        Clique num título para ver o histórico oficial de taxa e preço. Variação em pontos-base (bp) contra a curva de 1 semana antes.</div></div>
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

  desenharTempoReal(tes);

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
  const [nome, cor] = CATEGORIAS_AGENDA[e.categoria] || [e.categoria, COR.cinza];
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
      <td class="sub">${esc(n.fonte)}</td></tr>`).join("")}</table></div>`;
}

async function paginaNoticias() {
  const [noticias, agenda] = await Promise.all([dados("dados/noticias.json").catch(() => null), dados("dados/agenda.json").catch(() => null)]);
  const itens = noticias ? noticias.itens : [];
  const fontes = [...new Set(itens.map((n) => n.fonte))].sort();
  let fonte = "todas", filtro = "todos", janela = 30;
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Notícias e agenda</h1><div class="sub">Manchetes de fontes oficiais e públicas e o calendário de divulgações ·
      notícias atualizadas em ${noticias ? dataHoraBR(noticias.gerado_em) : "—"} · agenda em ${agenda ? dataBR(agenda.gerado_em) : "—"}</div></div></div>
    <div class="grade grade-noticias">
      <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Notícias</h2>
        <div class="seletor" id="filtro-fonte"><button data-k="todas" class="ativo">Todas</button>${fontes.map((f) => `<button data-k="${esc(f)}">${esc(f)}</button>`).join("")}</div></div>
        <div id="lista-noticias"></div>
        <div class="nota">Só o título e o link para a matéria original. Fontes: Banco Central (notícias e comunicados do Copom), IBGE (Agência de Notícias),
          CVM e Agência Brasil (economia). Últimos 45 dias. Etiquetas: empresas da lista citadas na manchete.</div></div>
      <div class="painel"><div class="cabecalho" style="margin-bottom:6px"><h2 style="margin:0">Agenda</h2>
        <div class="seletor" id="janela-ag">${[[14, "2 sem."], [30, "1 mês"], [90, "3 meses"], [400, "Tudo"]].map(([d, r]) => `<button data-d="${d}" class="${d === janela ? "ativo" : ""}">${r}</button>`).join("")}</div></div>
        <div class="seletor" id="filtro-ag" style="margin-bottom:8px">
          <button data-k="todos" class="ativo">Todos</button>
          ${Object.entries(CATEGORIAS_AGENDA).map(([k, [n, c]]) => `<button data-k="${k}"><span style="color:${c}">●</span> ${n}</button>`).join("")}
        </div>
        <div id="tab-agenda"></div>
        <div class="nota">Datas oficiais do Banco Central, IBGE e FGV; podem mudar. A decisão do Copom sai ao fim do segundo dia de reunião,
          e a ata na terça da semana seguinte. O calendário da FGV (IGP-M) cobre o mês corrente.</div></div>
    </div>`;
  const desenharNoticias = () => (document.getElementById("lista-noticias").innerHTML = listaNoticias(itens.filter((n) => fonte === "todas" || n.fonte === fonte)));
  const desenharAgenda = () => (document.getElementById("tab-agenda").innerHTML = tabelaAgenda(agenda, janela, filtro));
  const seletor = (id, aoEscolher) => document.getElementById(id).addEventListener("click", (ev) => {
    const b = ev.target.closest("button"); if (!b) return;
    document.querySelectorAll(`#${id} button`).forEach((x) => x.classList.toggle("ativo", x === b));
    aoEscolher(b);
  });
  seletor("filtro-fonte", (b) => { fonte = b.dataset.k; desenharNoticias(); });
  seletor("filtro-ag", (b) => { filtro = b.dataset.k; desenharAgenda(); });
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

/* ============ Offshore (estrutura; dados ainda não ligados) ============ */
const PLANO_OFFSHORE = {
  "": ["Offshore · painel", "Resumo do exterior: juros e inflação dos EUA e da Zona do Euro, curva de Treasuries, índices, commodities e dólar.", [
    ["Juros e inflação lá fora", "Fed Funds, Treasury de 10 anos, CPI dos EUA, taxas do BCE.", "FRED, Tesouro dos EUA, BCE"],
    ["Mercados", "S&P 500, Nasdaq, Stoxx, DXY, Brent, minério e ouro.", "FRED, EIA, Banco Mundial; Yahoo como reserva"],
    ["Próximas divulgações", "FOMC, CPI, payroll e reuniões do BCE.", "calendários do Fed, BLS e BCE"]]],
  noticias: ["Notícias e agenda", "Comunicados oficiais e o calendário de divulgações do exterior.", [
    ["Notícias", "Comunicados do Federal Reserve e do Banco Central Europeu (manchete e link).", "RSS oficiais do Fed e do BCE"],
    ["Agenda", "Reuniões do FOMC e do BCE; CPI, PCE, payroll e PIB dos EUA; inflação e PIB da Zona do Euro.", "Fed, BLS, BEA, BCE, Eurostat"]]],
  macro: ["Macro", "Atividade, inflação e emprego das principais economias.", [
    ["Estados Unidos", "Inflação (CPI, PCE e núcleos), emprego (payroll, desemprego), PIB e atividade.", "FRED, BLS, BEA (APIs oficiais, chave gratuita)"],
    ["Zona do Euro", "Inflação (HICP), PIB e desemprego.", "Eurostat e BCE (APIs oficiais)"],
    ["China", "PIB, inflação e produção industrial.", "DBnomics (dados do NBS)"],
    ["Global", "PIB e projeções por país.", "FMI (World Economic Outlook), Banco Mundial, OCDE"],
    ["Mercados", "Índices de ações, commodities e câmbio.", "FRED, EIA, Banco Mundial (Pink Sheet); Yahoo como reserva"]]],
  juros: ["Juros", "Curvas e taxas de referência do exterior.", [
    ["Treasuries", "Curva dos EUA, nominal e real (TIPS), em hoje, 1 semana, 1 mês, 6 meses e 1 ano.", "Tesouro dos EUA (arquivo diário oficial)"],
    ["Fed Funds e SOFR", "Taxa básica americana e taxas de um dia.", "Fed de Nova York (API oficial)"],
    ["Zona do Euro", "€STR, taxas do BCE e curva de juros.", "BCE (API oficial)"],
    ["Spreads de crédito", "High yield e grau de investimento.", "FRED (índices ICE BofA)"]]],
  empresas: ["Empresas", "Empresas estrangeiras para comparação setorial.", [
    ["Comparáveis estrangeiras", "Receita, margens, endividamento e retorno de empresas listadas nos EUA.", "SEC EDGAR (balanços XBRL, API oficial)"]]],
  downloads: ["Downloads", "Planilhas com as séries do exterior.", [
    ["Macro e Juros do exterior", "Séries históricas completas em Excel, como as do Onshore.", "geradas a partir das fontes acima"]]],
};

function paginaOffshore(secao) {
  const [titulo, sub, itens] = PLANO_OFFSHORE[secao] || PLANO_OFFSHORE[""];
  app.innerHTML = `
    <div class="cabecalho"><div><h1>${secao ? `Offshore · ${titulo}` : titulo}</h1><div class="sub">${sub}</div></div></div>
    <div class="aviso">Em construção: a estrutura está pronta e os dados entram nas próximas etapas, fonte por fonte.</div>
    <div class="grade">${itens.map(([nome, conteudo, fonte]) => `<div class="painel em-construcao"><h2>${nome}</h2>
      <p style="margin:0 0 8px;line-height:1.6">${conteudo}</p><div class="nota">Fonte prevista: ${fonte}</div></div>`).join("")}</div>`;
}

/* ============ Status dos dados ============ */
const NOMES_ETAPAS = {
  macro: "Macro (Banco Central, IBGE, FGV)", agenda: "Agenda (Banco Central, IBGE, FGV)", tesouro: "Tesouro Direto", curva_di: "Curva DI (B3)",
  mercado: "Cotações e proventos (B3)", noticias: "Notícias", planilhas: "Planilhas de Macro e Juros", eventos: "Eventos (CVM)",
  ficha: "Ficha da empresa (FRE/FCA)", fre_textos: "Trechos do Formulário de Referência", resumos: "Resumos aprofundados",
  cvm_base: "Base de demonstrações (CVM)", empresas: "Empresas (JSON e Excel)", indice: "Índice de empresas",
};

async function paginaStatus() {
  const [st, saude, agenda] = await Promise.all([dados("dados/status.json").catch(() => null), dados("dados/saude.json").catch(() => null),
    dados("dados/agenda.json").catch(() => null)]);
  const marca = (ok) => `<span class="${ok ? "pos" : "neg"}">${ok ? "✔" : "✖"}</span>`;
  const quando = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");
  app.innerHTML = `
    <div class="cabecalho"><div><h1>Status dos dados</h1><div class="sub">Resultado da última atualização automática e das checagens do monitor de fontes</div></div>
      <a class="botao" href="https://github.com/fredperin/screeening-cvm/actions" target="_blank" rel="noopener">Execuções no GitHub</a></div>
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

/* ============ início ============ */
iniciarBusca().then(rotear);
