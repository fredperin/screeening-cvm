"use strict";
/* Textos dos botões "ⓘ" de cada gráfico: o que o indicador mede, como é montado e de onde vem.
   Edite à vontade: cada chave é usada por um ou mais gráficos (atributo data-info do painel). */
window.EXPLICATIVOS = {
  ipca: {
    titulo: "IPCA — Índice Nacional de Preços ao Consumidor Amplo",
    html: `<p>É a <b>inflação oficial do Brasil</b>, usada pelo Conselho Monetário Nacional para a meta de inflação
      (meta contínua de 3% ao ano, com tolerância de 1,5 ponto para cima ou para baixo). Calculado pelo <b>IBGE</b>.</p>
      <h4>Como é montado</h4>
      <ul>
        <li><b>Quem:</b> famílias com renda de 1 a 40 salários mínimos, em 16 áreas (10 regiões metropolitanas mais Brasília,
          Goiânia, Campo Grande, Rio Branco, São Luís e Aracaju).</li>
        <li><b>O quê:</b> cerca de 380 subitens de consumo, com pesos tirados da Pesquisa de Orçamentos Familiares (POF).
          Os pesos se ajustam todo mês conforme os preços relativos mudam.</li>
        <li><b>Grupos (peso aproximado):</b> Alimentação e bebidas (~21%), Transportes (~20%), Habitação (~15%),
          Saúde e cuidados pessoais (~14%), Despesas pessoais (~10%), Educação (~6%), Comunicação (~5%), Vestuário (~5%)
          e Artigos de residência (~4%).</li>
        <li><b>Coleta:</b> preços do primeiro ao último dia do mês de referência; divulgação por volta do dia 10 do mês seguinte.</li>
      </ul>
      <h4>No gráfico</h4>
      <p>Barras: variação do mês. Linhas: acumulado em 12 meses (produto das 12 últimas variações) e média de 3 meses anualizada
        (veja o explicativo próprio). <b>IPCA-15:</b> mesma metodologia, mas com coleta do dia 16 do mês anterior ao dia 15 do mês
        de referência — funciona como prévia do IPCA.</p>
      <p class="sub">Fonte: IBGE, série 433 do SGS do Banco Central.</p>`,
  },
  nucleos: {
    titulo: "Núcleos de inflação do IPCA",
    html: `<p>Os núcleos tentam separar a <b>tendência</b> da inflação dos choques passageiros (alimentos in natura, combustíveis,
      energia, reajustes de preços administrados). São calculados pelo <b>Banco Central</b> a partir dos subitens do IPCA, e o Copom
      acompanha especialmente a média deles.</p>
      <h4>Cada núcleo</h4>
      <ul>
        <li><b>EX0 (exclusão):</b> retira alimentação no domicílio e preços monitorados (energia, combustíveis, planos de saúde,
          tarifas públicas etc.).</li>
        <li><b>EX2 e EX3 (exclusão):</b> ficam basicamente com os serviços e os bens industriais "subjacentes", deixando de fora os
          itens mais voláteis (alimentos e energia); o EX3 é o recorte mais restrito.</li>
        <li><b>MS (médias aparadas com suavização):</b> descarta, a cada mês, as variações extremas dos dois lados da distribuição
          (cerca de 20% do peso em cada ponta) e distribui ao longo de 12 meses os itens com reajuste concentrado.</li>
        <li><b>DP (dupla ponderação):</b> reduz o peso dos itens mais voláteis, combinando o peso do IPCA com o inverso da
          volatilidade de cada item.</li>
        <li><b>P55 (percentil 55):</b> a variação que fica no percentil 55 da distribuição ponderada das variações dos subitens.</li>
      </ul>
      <p><b>Média dos 5 núcleos</b> (EX0, EX3, MS, DP e P55): média simples mês a mês, calculada por este site — é a medida de
        tendência que o Banco Central costuma citar.</p>
      <p class="sub">Fonte: Banco Central (SGS: EX0 11427, EX2 27838, EX3 27839, MS 4466, DP 16122, P55 28750).</p>`,
  },
  mm3: {
    titulo: "Média de 3 meses anualizada",
    html: `<p>Mostra o <b>ritmo recente</b> da inflação em termos anuais. O acumulado em 12 meses demora a reagir; esta medida
      responde em 3 meses.</p>
      <h4>Conta</h4>
      <p>Acumula as variações dos últimos 3 meses e eleva à 4ª potência (4 trimestres no ano):
        <code>[(1+m₁)·(1+m₂)·(1+m₃)]⁴ − 1</code>.</p>
      <h4>Cuidado</h4>
      <p>É calculada <b>sem ajuste sazonal</b>. Meses com sazonalidade forte (educação e IPTU no início do ano, alimentos na
        entressafra, reajustes concentrados) inflam ou reduzem a leitura. Compare com o mesmo período de anos anteriores, ou
        prefira os núcleos, que já tiram parte desse efeito.</p>`,
  },
  igpm: {
    titulo: "IGP-M — Índice Geral de Preços do Mercado",
    html: `<p>Índice da <b>FGV</b> que mistura preços no atacado, no varejo e na construção. Muito usado para reajustar
      <b>aluguéis</b> e contratos antigos (energia, telefonia, concessões).</p>
      <h4>Como é montado</h4>
      <ul>
        <li><b>IPA-M — preços ao produtor (60%):</b> commodities agrícolas e minerais, matérias-primas e bens industriais.
          Por isso reage muito a <b>câmbio e commodities</b> (minério, petróleo, soja, milho, carnes).</li>
        <li><b>IPC-M — preços ao consumidor (30%).</b></li>
        <li><b>INCC-M — custo da construção (10%).</b></li>
        <li><b>Coleta:</b> do dia 21 do mês anterior ao dia 20 do mês de referência; divulgação no fim do mês, com prévias decendiais.</li>
      </ul>
      <p class="sub">Fonte: FGV, série 189 do SGS do Banco Central.</p>`,
  },
  incc: {
    titulo: "INCC — Índice Nacional de Custo da Construção",
    html: `<p>Índice da <b>FGV</b> que mede o custo de construir habitações. Corrige o saldo de <b>imóveis comprados na planta</b>
      durante a obra e serve de termômetro de custos para incorporadoras e construtoras.</p>
      <h4>Como é montado</h4>
      <ul>
        <li><b>Componentes:</b> materiais e equipamentos, serviços e mão de obra (este último com forte efeito dos dissídios
          da construção civil, concentrados em alguns meses do ano).</li>
        <li><b>Abrangência:</b> 7 capitais (São Paulo, Rio de Janeiro, Belo Horizonte, Salvador, Recife, Porto Alegre e Brasília).</li>
        <li><b>Versões:</b> INCC-DI (mês civil, mostrado aqui) e INCC-M (de 21 a 20, que entra no IGP-M com peso de 10%).</li>
      </ul>
      <p class="sub">Fonte: FGV, série 192 do SGS do Banco Central.</p>`,
  },
  pib_tri: {
    titulo: "PIB trimestral",
    html: `<p>Produto Interno Bruto: valor de tudo o que a economia produz. Calculado pelo <b>IBGE</b> nas Contas Nacionais
      Trimestrais, divulgadas cerca de 60 dias depois do fim do trimestre.</p>
      <h4>Como é montado</h4>
      <ul>
        <li><b>Ótica da produção:</b> agropecuária, indústria e serviços, mais impostos.</li>
        <li><b>Ótica da demanda:</b> consumo das famílias, consumo do governo, investimento (FBCF), exportações menos importações.</li>
      </ul>
      <h4>No gráfico</h4>
      <p>Barras: variação contra o trimestre anterior, <b>com ajuste sazonal</b>. Linha: acumulado em 4 trimestres contra os 4
        anteriores (a "variação em 12 meses" que o IBGE divulga). Os números passados são revisados a cada divulgação.</p>
      <p class="sub">Fonte: IBGE, séries 22109 e 22099 do SGS do Banco Central.</p>`,
  },
  pib_anual: {
    titulo: "PIB anual",
    html: `<p>Resultado de <b>anos fechados</b>, conforme a divulgação oficial do IBGE. O número de cada ano sai junto com o
      PIB do 4º trimestre (no início de março) e é revisado depois, quando o IBGE publica as Contas Nacionais anuais.</p>
      <ul>
        <li><b>Barras:</b> crescimento real do ano (descontada a inflação).</li>
        <li><b>Linha:</b> PIB nominal, em reais correntes de cada ano.</li>
      </ul>
      <p class="sub">Fonte: IBGE, séries 7326 e 1207 do SGS do Banco Central.</p>`,
  },
  ibcbr: {
    titulo: "IBC-Br — Índice de Atividade Econômica do Banco Central",
    html: `<p>Indicador <b>mensal</b> criado pelo Banco Central para acompanhar a atividade antes de o PIB sair. Usa dados de
      agropecuária, indústria, serviços e impostos. É chamado de "prévia do PIB", mas não é igual a ele: a metodologia é mais
      simples e os números divergem com frequência.</p>
      <p>Barras: variação contra o mês anterior, com ajuste sazonal. Linha: acumulado em 12 meses (sem ajuste).
        Divulgação cerca de 45 dias depois do mês de referência.</p>
      <p class="sub">Fonte: Banco Central, séries 24363 e 24364 do SGS.</p>`,
  },
  selic: {
    titulo: "Selic e CDI",
    html: `<ul>
        <li><b>Selic meta:</b> taxa básica de juros, definida pelo <b>Copom</b> em 8 reuniões por ano (a cada ~45 dias). É o principal
          instrumento do Banco Central para levar a inflação à meta.</li>
        <li><b>Selic efetiva:</b> taxa média das operações de um dia entre instituições, lastreadas em títulos públicos; o Banco
          Central opera para mantê-la colada à meta.</li>
        <li><b>CDI:</b> taxa média dos empréstimos de um dia entre bancos (calculada pela B3). Anda praticamente junto da Selic e
          é a referência da renda fixa privada (CDB, debêntures, fundos).</li>
      </ul>
      <p class="sub">Fonte: Banco Central, séries 432 e 4389 do SGS.</p>`,
  },
  juro_real: {
    titulo: "Juro real ex-post",
    html: `<p>Quanto a Selic rende <b>acima da inflação</b> que já aconteceu: <code>(1 + Selic meta) ÷ (1 + IPCA 12 meses) − 1</code>.</p>
      <p>É "ex-post" porque usa a inflação passada. O juro real que o Banco Central olha para calibrar a política é o
        <b>ex-ante</b> (juro futuro contra a inflação esperada), que aparece na seção Juros na curva DI x IPCA e no Tesouro IPCA+.</p>`,
  },
  cambio: {
    titulo: "Câmbio PTAX",
    html: `<p>Taxa de câmbio de referência calculada pelo <b>Banco Central</b>: média de 4 consultas feitas aos dealers de câmbio
      ao longo do dia. A PTAX de venda é a usada em contratos, balanços e na liquidação de derivativos.</p>
      <p class="sub">Fonte: Banco Central, séries 1 (dólar) e 21619 (euro) do SGS.</p>`,
  },
  focus: {
    titulo: "Boletim Focus",
    html: `<p>Pesquisa semanal do <b>Banco Central</b> com bancos, gestoras e consultorias. Cada gráfico mostra a
      <b>mediana</b> das projeções para cada ano, ao longo do tempo — dá para ver como as expectativas mudaram.</p>
      <p>Divulgado às segundas-feiras de manhã. Para a Selic, o valor é o esperado para o fim de cada ano.</p>
      <p class="sub">Fonte: Banco Central (API Olinda de expectativas de mercado).</p>`,
  },
  curva_di: {
    titulo: "Curva DI x Pré",
    html: `<p>Taxas de juros prefixadas que o mercado negocia para cada prazo, tiradas dos contratos de swap DI x Pré da
      <b>B3</b> (fim do dia). Indicam quanto o mercado espera de CDI médio até cada vencimento, mais um prêmio de risco.</p>
      <ul>
        <li>Curva <b>inclinada para cima</b>: mercado espera juros maiores à frente (ou pede mais prêmio no longo prazo).</li>
        <li>Curva <b>invertida</b>: mercado espera cortes da Selic.</li>
      </ul>
      <p>Prazos em anos de 252 dias úteis. As linhas comparam hoje com 1 semana, 1 mês, 6 meses e 1 ano atrás.</p>
      <p class="sub">Fonte: B3, arquivo "Taxas de Mercado para Swaps".</p>`,
  },
  di_ipca: {
    titulo: "Curva DI x IPCA (juro real)",
    html: `<p>Taxa <b>real</b> (acima do IPCA) negociada em swaps DI x IPCA na B3, para cada prazo. Junto com a curva prefixada,
      mostra quanto da taxa nominal é juro real e quanto é inflação esperada mais prêmio.</p>
      <p>Prazos curtos (menos de 3 meses) ficam de fora porque oscilam com o IPCA do mês corrente.</p>
      <p class="sub">Fonte: B3, arquivo "Taxas de Mercado para Swaps".</p>`,
  },
  tesouro_pre: {
    titulo: "Tesouro prefixado",
    html: `<p>Taxa de compra dos títulos prefixados no <b>Tesouro Direto</b>, por prazo até o vencimento. Usa o título sem cupom
      (LTN) e, nos prazos onde ele não existe, o título com juros semestrais (NTN-F).</p>
      <p class="sub">Fonte: Tesouro Nacional (Tesouro Transparente).</p>`,
  },
  tesouro_ipca: {
    titulo: "Tesouro IPCA+",
    html: `<p>Taxa <b>real</b> (acima do IPCA) dos títulos IPCA+ no Tesouro Direto, por prazo. Usa o título sem cupom
      (NTN-B Principal) e, nos prazos onde ele não existe, o título com juros semestrais (NTN-B).</p>
      <p class="sub">Fonte: Tesouro Nacional (Tesouro Transparente).</p>`,
  },
  inflacao_implicita: {
    titulo: "Inflação implícita",
    html: `<p>A inflação que <b>iguala</b> o retorno de um prefixado e de um IPCA+ de mesmo prazo:
      <code>(1 + taxa prefixada) ÷ (1 + taxa real) − 1</code>. Também chamada de breakeven.</p>
      <p>Não é exatamente a expectativa de inflação: inclui um prêmio pelo risco de a inflação surpreender e diferenças de liquidez
        entre os títulos. A curva prefixada é interpolada nos vencimentos do IPCA+, sem extrapolar.</p>`,
  },
  vertices: {
    titulo: "Taxas DI por prazo",
    html: `<p>Taxas da curva DI (prefixada e real) em prazos fixos, interpoladas linearmente entre os vértices negociados.
      Facilita comparar a mesma maturidade em datas diferentes.</p>`,
  },
  titulos: {
    titulo: "Títulos à venda no Tesouro Direto",
    html: `<ul>
        <li><b>Prefixado (LTN)</b> e <b>Prefixado com juros semestrais (NTN-F):</b> taxa fixa definida na compra.</li>
        <li><b>IPCA+ (NTN-B Principal)</b> e <b>IPCA+ com juros semestrais (NTN-B):</b> IPCA mais uma taxa real.</li>
        <li><b>Selic (LFT):</b> acompanha a Selic.</li>
        <li><b>Renda+ e Educa+:</b> IPCA+ com pagamento em parcelas mensais a partir de uma data.</li>
      </ul>
      <p>PU = preço unitário. A variação semanal está em pontos-base (1 bp = 0,01 ponto percentual): taxa subindo = preço caindo.</p>`,
  },
  receita: {
    titulo: "Receita líquida",
    html: `<p>Vendas de produtos e serviços já descontados impostos sobre vendas, devoluções e abatimentos (linha 3.01 da DRE
      entregue à CVM). A linha mostra o crescimento contra o mesmo período do ano anterior.</p>`,
  },
  lucro_bruto: {
    titulo: "Lucro bruto e margem bruta",
    html: `<p>Receita líquida menos o custo dos produtos ou serviços vendidos. Margem bruta = lucro bruto ÷ receita.
      Bancos e seguradoras não têm essa linha no mesmo formato.</p>`,
  },
  ebitda: {
    titulo: "EBITDA",
    html: `<p>Lucro antes de juros, impostos, depreciação e amortização: <code>EBIT + D&amp;A</code>. Aproxima a geração de caixa
      operacional antes de investimentos e capital de giro.</p>
      <p>A D&amp;A não é conta padronizada da CVM: é somada a partir das linhas da DFC cuja descrição fala em depreciação,
        amortização ou exaustão (as linhas usadas aparecem nas notas da página). Sem essas linhas, EBITDA = EBIT.</p>`,
  },
  ebit: {
    titulo: "EBIT",
    html: `<p>Resultado antes do resultado financeiro e dos tributos sobre o lucro (linha 3.05 da DRE). Margem EBIT = EBIT ÷ receita.</p>`,
  },
  lucro_liquido: {
    titulo: "Lucro líquido",
    html: `<p>Resultado final do período (consolidado) depois de resultado financeiro e impostos. Margem líquida = lucro líquido ÷ receita.</p>`,
  },
  resultado_financeiro: {
    titulo: "Resultado financeiro",
    html: `<p>Receitas financeiras (rendimento do caixa, variação cambial ativa) menos despesas financeiras (juros da dívida,
      variação cambial passiva, encargos de arrendamento). As barras ficam empilhadas no mesmo ponto; a linha é o saldo.</p>`,
  },
  retorno: {
    titulo: "ROE e ROIC (últimos 12 meses)",
    html: `<ul>
        <li><b>ROE:</b> lucro líquido dos últimos 12 meses ÷ patrimônio líquido no fim do período.</li>
        <li><b>ROIC:</b> EBIT dos últimos 12 meses × (1 − 34%) ÷ (dívida líquida + patrimônio líquido) no fim do período.
          A alíquota de 34% (IR + CSLL) é uma simplificação.</li>
      </ul>`,
  },
  fluxo_caixa: {
    titulo: "Fluxo de caixa (DFC)",
    html: `<ul>
        <li><b>FCO:</b> caixa gerado pelas operações.</li>
        <li><b>FCI:</b> caixa usado em investimentos (capex, aquisições) ou recebido em vendas de ativos.</li>
        <li><b>FCFi:</b> caixa de financiamentos: captações, amortizações, dividendos e recompras.</li>
        <li><b>Soma:</b> FCO + FCI + FCFi = variação do caixa no período (antes da variação cambial sobre o caixa).</li>
      </ul>
      <p>FCF (fluxo de caixa livre), usado nos indicadores = FCO − capex.</p>`,
  },
  endividamento: {
    titulo: "Endividamento",
    html: `<ul>
        <li><b>Dívida bruta sem IFRS 16:</b> empréstimos, financiamentos e debêntures de curto e longo prazo.</li>
        <li><b>Arrendamentos (IFRS 16):</b> aluguéis, frota, aeronaves etc. registrados como passivo desde 2019; identificados
          pela descrição das linhas do balanço.</li>
        <li><b>Dívida líquida:</b> dívida bruta − (caixa + aplicações financeiras).</li>
        <li><b>Dív. líquida / EBITDA:</b> quantos anos de EBITDA (últimos 12 meses) pagariam a dívida líquida.</li>
      </ul>`,
  },
  dividendos_dfc: {
    titulo: "Dividendos e JCP pagos (DFC) e payout",
    html: `<p>Caixa <b>efetivamente pago</b> a acionistas no ano, pelas linhas da DFC de dividendos e juros sobre capital próprio.
      Payout = pagos no ano ÷ lucro líquido do ano. Como o pagamento costuma ocorrer no ano seguinte ao lucro, o payout de um
      ano isolado pode passar de 100%.</p>`,
  },
  proventos_acao: {
    titulo: "Proventos por ação e dividend yield",
    html: `<p>Dividendos e JCP <b>anunciados</b> por ação, somados pelo ano da data-com (fonte B3). O DY de cada ano soma,
      provento a provento, o valor ÷ preço de fechamento na data-com.</p>`,
  },
  cotacao: {
    titulo: "Cotação semanal",
    html: `<p>Preço de fechamento semanal dos últimos 10 anos, sem ajuste por proventos. Fonte: Yahoo Finance (não oficial).</p>`,
  },
};
