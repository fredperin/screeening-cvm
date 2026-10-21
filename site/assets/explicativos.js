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
        prefira os núcleos, que já tiram parte desse efeito.</p>
      <p class="sub">Fonte: Cálculo do site a partir das séries mensais do IBGE (IPCA) e da FGV (IGP-M, INCC), via SGS do Banco Central.</p>`,
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
  dre_resumida: {
    titulo: "DRE com análise vertical",
    html: `<p>Demonstração do resultado dos últimos 4 exercícios fechados e dos últimos 12 meses (LTM), em R$ milhões, com as
      linhas principais da DRE da CVM: receita, custos, resultado bruto, despesas operacionais, EBIT, resultado financeiro,
      lucro antes dos tributos, IR/CSLL e lucro líquido. Ao lado de cada valor, a <b>análise vertical (AV)</b>: quanto a linha
      representa da receita líquida (ex.: AV do resultado bruto = margem bruta).</p>
      <p>A depreciação e amortização fica embutida em custos e despesas (a CVM não a separa na DRE); o EBITDA está na aba Gráficos.</p>
      <p class="sub">Fonte: CVM — demonstrações financeiras padronizadas (DFP e ITR), consolidado.</p>`,
  },
  balanco_resumido: {
    titulo: "Balanço patrimonial com análise vertical",
    html: `<p>Balanço no fim de cada exercício (e do último trimestre, na coluna LTM), em R$ milhões, com as mesmas contas do Excel
      (padrão da CVM: circulante, não circulante e patrimônio líquido abertos no primeiro nível de detalhe) e a
      <b>análise vertical</b> em % do ativo total.</p>
      <p class="sub">Fonte: CVM — demonstrações financeiras padronizadas (DFP e ITR), consolidado.</p>`,
  },
  credito_saldo: {
    titulo: "Saldo da carteira de crédito",
    html: `<p>Estoque de todos os empréstimos e financiamentos do sistema financeiro no fim de cada mês, separado em
      <b>recursos livres</b> (taxas negociadas livremente: capital de giro, cartão, consignado, veículos) e <b>direcionados</b>
      (regras do governo sobre taxa ou destino: imobiliário com poupança/FGTS, rural, BNDES, microcrédito).
      A linha mostra o crescimento nominal em 12 meses.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Estatísticas monetárias e de crédito (Nota de Crédito), via SGS. Desde 2011.</p>`,
  },
  credito_pib: {
    titulo: "Crédito em % do PIB",
    html: `<p>Saldo da carteira dividido pelo PIB acumulado em 12 meses, a valores correntes: mede o tamanho do crédito
      na economia (aprofundamento financeiro).</p>
      <p class="sub">Fonte: Banco Central do Brasil — Nota de Crédito, via SGS.</p>`,
  },
  credito_concessoes: {
    titulo: "Concessões de crédito",
    html: `<p>Valor dos empréstimos e financiamentos <b>novos</b> contratados no mês (fluxo, não estoque), com ajuste sazonal
      do Banco Central — mostra o ritmo da oferta e da demanda por crédito antes de aparecer no saldo.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Nota de Crédito, concessões dessazonalizadas, via SGS.</p>`,
  },
  credito_juros: {
    titulo: "Juros, spread e custo do crédito",
    html: `<p><b>Taxa média:</b> juro médio das operações <b>contratadas no mês</b> (% a.a.). <b>Spread:</b> diferença entre essa taxa e
      o custo de captação do banco (pontos percentuais) — inclui inadimplência esperada, impostos, despesas e lucro.
      <b>ICC (Indicador de Custo do Crédito):</b> juro médio de <b>toda a carteira</b> em aberto, inclusive contratos antigos — reage mais
      devagar à Selic. A Selic meta aparece tracejada como referência.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Nota de Crédito, via SGS.</p>`,
  },
  credito_inadimplencia: {
    titulo: "Inadimplência e atrasos",
    html: `<p><b>Inadimplência:</b> % da carteira com parcelas atrasadas há <b>mais de 90 dias</b>. <b>Atraso de 15 a 90 dias:</b> % da carteira
      com atraso curto — costuma antecipar a inadimplência dos meses seguintes.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Nota de Crédito, via SGS.</p>`,
  },
  credito_prazo: {
    titulo: "Prazo médio da carteira",
    html: `<p>Prazo médio, em meses, das operações em aberto (do início ao vencimento), ponderado pelo saldo. Os direcionados
      (imobiliário, BNDES) têm prazos bem maiores que os livres.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Nota de Crédito, via SGS.</p>`,
  },
  credito_familias: {
    titulo: "Endividamento e comprometimento de renda das famílias",
    html: `<p><b>Endividamento:</b> dívida das famílias com o sistema financeiro dividida pela renda disponível acumulada em 12 meses
      (com e sem o crédito habitacional, que é de prazo longo). <b>Comprometimento de renda:</b> quanto da renda mensal vai para
      pagar as dívidas (juros + amortização), com ajuste sazonal.</p>
      <p>Saem com cerca de 2 meses de atraso, porque dependem da estimativa da renda das famílias.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Indicadores de endividamento e comprometimento de renda (RNDBF), via SGS.</p>`,
  },
  credito_modalidades: {
    titulo: "Modalidades de crédito",
    html: `<p>Saldo, taxa média de juros (crédito novo) e inadimplência (> 90 dias) das principais linhas. Use os botões para trocar
      o indicador e clique na legenda para esconder ou mostrar uma modalidade (o cartão rotativo e o cheque especial têm juros muito
      acima das demais e achatam o gráfico).</p>
      <p>Algumas modalidades tiveram mudanças de regra no período (ex.: consignado, cartão de crédito), que podem gerar degraus nas séries.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Nota de Crédito, via SGS.</p>`,
  },
  credito_pfpj: {
    titulo: "Pessoa física × pessoa jurídica",
    html: `<p>Saldo da carteira de crédito das famílias e das empresas. Detalhes de cada um nas abas Pessoa física e Pessoa jurídica.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Nota de Crédito, via SGS.</p>`,
  },
  externo_tc: {
    titulo: "Transações correntes e investimento direto",
    html: `<p><b>Transações correntes:</b> saldo de tudo o que o Brasil vende e compra do exterior em bens, serviços e rendas (juros, lucros e
      dividendos remetidos). Negativo = déficit, que precisa ser financiado com capital de fora. <b>Investimento direto no país (IDP):</b>
      capital estrangeiro aplicado em empresas no Brasil — a forma mais estável de financiar o déficit. Quando o IDP supera o déficit em
      transações correntes, o financiamento externo é considerado confortável. Ambos em 12 meses e em % do PIB.</p>
      <p class="sub">Fonte: Banco Central do Brasil — balanço de pagamentos (BPM6), SGS 23079, 24419, 22701 e 22885. IDP em % do PIB calculado
      pelo PIB em dólares implícito na série de transações correntes.</p>`,
  },
  externo_balanca: {
    titulo: "Balança comercial",
    html: `<p>Exportações e importações de bens no mês, em dólares (valor FOB, sem frete e seguro), e o saldo. Registro aduaneiro do
      governo, divulgado no começo do mês seguinte (antes do balanço de pagamentos do BC).</p>
      <p class="sub">Fonte: Comex Stat — Ministério do Desenvolvimento, Indústria, Comércio e Serviços (API oficial).</p>`,
  },
  externo_produtos: {
    titulo: "Exportações por produto",
    html: `<p>Valor exportado nos últimos 12 meses dos produtos que mais pesam para as empresas da B3: minério de ferro (Vale), petróleo
      (Petrobras, Prio), soja, farelo e milho (agronegócio e tradings), carnes (JBS, BRF, Minerva), celulose (Suzano, Klabin), açúcar e
      café, aço (Gerdau, Usiminas) e aviões (Embraer). Classificação pela posição de 4 dígitos do Sistema Harmonizado.</p>
      <p class="sub">Fonte: Comex Stat (API oficial).</p>`,
  },
  externo_destinos: {
    titulo: "Exportações por destino",
    html: `<p>Valor exportado nos últimos 12 meses para os principais compradores do Brasil. A China compra sobretudo minério, soja,
      petróleo e carnes; os EUA, petróleo, aço, aviões e manufaturados.</p>
      <p class="sub">Fonte: Comex Stat (API oficial); União Europeia pelo bloco econômico.</p>`,
  },
  externo_carteira: {
    titulo: "Investimento estrangeiro em carteira",
    html: `<p>Compras líquidas de estrangeiros em <b>ações</b> e <b>títulos de dívida</b> (públicos e privados) no Brasil, somadas em 12 meses.
      Positivo = entrada de recursos. É o capital mais volátil: entra e sai rápido conforme juros e risco.</p>
      <p class="sub">Fonte: Banco Central do Brasil — balanço de pagamentos (SGS 22924, 22927 e 22939).</p>`,
  },
  externo_reservas: {
    titulo: "Reservas internacionais",
    html: `<p>Dólares e outros ativos externos em poder do Banco Central (conceito liquidez, que inclui as linhas de swap), na posição do fim
      de cada mês. Funcionam como colchão contra crises cambiais.</p>
      <p class="sub">Fonte: Banco Central do Brasil (SGS 13982).</p>`,
  },
  fiscal_divida: {
    titulo: "Dívida pública: bruta (DBGG) e líquida (DLSP)",
    html: `<p><b>Dívida bruta do governo geral (DBGG):</b> tudo o que governo federal, INSS, estados e municípios devem
      (títulos, dívida bancária e externa), sem descontar ativos — inclui as operações compromissadas do Banco Central.
      É o conceito mais usado em comparações internacionais (metodologia do BC a partir de 2008).</p>
      <p><b>Dívida líquida do setor público (DLSP):</b> dívida do setor público consolidado (governos, Banco Central e estatais,
      exceto Petrobras, Eletrobras e bancos públicos) <b>menos os ativos</b>, como reservas internacionais e créditos
      com bancos públicos. Por isso cai quando o real se desvaloriza (as reservas valem mais em reais).</p>
      <p>Ambas em % do PIB acumulado em 12 meses, valores no fim de cada mês, publicadas cerca de 30 dias depois.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Estatísticas Fiscais (SGS 13762 e 4513).</p>`,
  },
  fiscal_resultado: {
    titulo: "Resultado primário, juros e resultado nominal",
    html: `<p><b>Resultado primário:</b> receitas menos despesas do governo <b>sem contar juros</b>. Positivo = superávit
      (sobra para pagar juros); negativo = déficit. <b>Juros nominais:</b> custo dos juros da dívida no período.
      <b>Resultado nominal</b> = primário − juros: é quanto a dívida precisou crescer para fechar as contas.</p>
      <p>Setor público consolidado, acumulado em 12 meses, em % do PIB, pelo critério "abaixo da linha" do BC
      (variação da dívida). O BC publica como NFSP (necessidade de financiamento: positivo = déficit); aqui o sinal está
      invertido para ler como resultado.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Estatísticas Fiscais, NFSP sem desvalorização cambial (SGS 5793, 5760 e 5727).</p>`,
  },
  fiscal_esferas: {
    titulo: "Resultado primário por esfera de governo",
    html: `<p>Quanto cada parte do setor público contribui para o resultado primário em 12 meses (% do PIB):
      <b>Governo Federal e Banco Central</b> (o "governo central", que inclui o INSS), <b>estados e municípios</b> e
      <b>empresas estatais</b> (exceto Petrobras, Eletrobras e bancos). As barras somam o total (linha).
      Positivo = superávit; negativo = déficit.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Estatísticas Fiscais (SGS 5783, 5786, 5789 e 5793).</p>`,
  },
  fiscal_dmf: {
    titulo: "Composição da dívida mobiliária federal",
    html: `<p>Participação de cada indexador no estoque de títulos públicos federais (posição em carteira):
      <b>Selic</b> (LFT, pós-fixados — sobem e descem com a Selic), <b>prefixados</b> (LTN e NTN-F),
      <b>IPCA</b> (NTN-B) e o restante (câmbio, IGP-M, TR e outros, hoje residuais).
      Quanto mais pós-fixada a dívida, mais o custo dela reage aos juros do Copom.</p>
      <p>O BC não publica a fatia do IPCA numa série própria: ela é calculada aqui por diferença (100% menos os demais
      indexadores), a partir de 2003.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Dívida mobiliária, participação por indexador (SGS 4173 a 4180).</p>`,
  },
  fiscal_arrecadacao: {
    titulo: "Arrecadação federal por tributo",
    html: `<p>Tudo o que a União arrecada, separado por tributo: Imposto de Renda (pessoa física, empresas e retido na fonte),
      contribuição previdenciária, Cofins, PIS/Pasep, CSLL, IPI, impostos de importação e exportação, IOF e o que é administrado por
      outros órgãos. As barras somadas dão o total.</p>
      <p><b>Nominal</b> = valores correntes, como a Receita publica. <b>A preços de hoje</b> = cada mês corrigido pelo IPCA até o último mês
      disponível, para comparar anos diferentes sem o efeito da inflação. "Acumulado em 12 meses" tira a sazonalidade (o IR concentra
      pagamentos em março a maio, por exemplo).</p>
      <p class="sub">Fonte: Receita Federal — Arrecadação das receitas federais (dados abertos, por estado, somados para o Brasil); IPCA do IBGE pelo Banco Central (SGS 433).</p>`,
  },
  fiscal_arrecadacao_pib: {
    titulo: "Arrecadação federal em % do PIB e crescimento real",
    html: `<p>Arrecadação de 12 meses dividida pelo PIB de 12 meses (carga tributária federal) e o crescimento real: arrecadação dos
      últimos 12 meses a preços de hoje contra a dos 12 meses anteriores, também a preços de hoje.</p>
      <p class="sub">Fonte: Receita Federal — Arrecadação das receitas federais; Banco Central — PIB acumulado em 12 meses (SGS 4382) e IPCA (SGS 433).</p>`,
  },
  fiscal_tributos: {
    titulo: "Arrecadação federal por tributo — tabela",
    html: `<p>Valores do último mês publicado e dos últimos 12 meses, participação de cada tributo no total e crescimento real
      (12 meses a preços de hoje contra os 12 anteriores). O Imposto de Renda aparece também dividido em suas partes.</p>
      <p class="sub">Fonte: Receita Federal — Arrecadação das receitas federais (dados abertos); IPCA do IBGE pelo Banco Central.</p>`,
  },
  fiscal_receitas_rtn: {
    titulo: "Receita do Governo Central",
    html: `<p><b>Receita total</b> do Governo Central (Tesouro, Previdência e Banco Central) = receita líquida + transferências
      obrigatórias a estados e municípios (fundos de participação, royalties, salário-educação, Cide etc.). A <b>receita líquida</b>
      é o que fica com a União para pagar suas despesas.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais; PIB do Banco Central (SGS 4382).</p>`,
  },
  fiscal_nao_administradas: {
    titulo: "Receitas não administradas pela Receita Federal",
    html: `<p>Receitas da União que não são tributos: concessões e permissões (leilões de infraestrutura, petróleo, telecomunicações),
      dividendos das estatais, royalties e participações pela exploração de recursos naturais e demais receitas. Costumam oscilar
      bastante e ajudam a fechar o resultado em alguns anos.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais.</p>`,
  },
  fiscal_dividendos: {
    titulo: "Dividendos de estatais pagos à União",
    html: `<p>Dividendos e juros sobre capital próprio que as empresas controladas pela União pagaram ao Tesouro, por empresa, somados
      em 12 meses. Interessa ao acionista minoritário dessas empresas: mostra quanto o controlador depende desses pagamentos.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais.</p>`,
  },
  fiscal_despesa_grupos: {
    titulo: "Despesa do Governo Central por grupo",
    html: `<p>Despesa primária (sem juros) do Governo Central em 12 meses, nos grupos do Tesouro: <b>benefícios previdenciários</b>,
      <b>pessoal</b>, <b>outras obrigatórias</b> (BPC, abono e seguro-desemprego, precatórios, Fundeb, subsídios…), <b>obrigatórias com
      controle de fluxo</b> (Bolsa Família, parte de saúde e educação) e <b>discricionárias</b> do Executivo (o que o governo pode cortar).
      As barras somadas dão a despesa total.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais; PIB do Banco Central (SGS 4382).</p>`,
  },
  fiscal_resultado_central: {
    titulo: "Receita, despesa e resultado primário do Governo Central",
    html: `<p>Receita líquida e despesa total em 12 meses, em % do PIB, e o <b>resultado primário</b> (receita menos despesa, sem juros):
      positivo = superávit. É o conceito usado nas metas fiscais da União.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais; PIB do Banco Central (SGS 4382).</p>`,
  },
  fiscal_resultado_orgaos: {
    titulo: "Resultado primário do Governo Central por órgão",
    html: `<p>Resultado primário de 12 meses do Tesouro Nacional, da Previdência Social (contribuições menos benefícios do INSS)
      e do Banco Central. Positivo = superávit; a Previdência é deficitária e o Tesouro cobre a diferença.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais.</p>`,
  },
  fiscal_discricionarias: {
    titulo: "Despesas discricionárias por área",
    html: `<p>Gastos do Poder Executivo que não são obrigatórios por lei (custeio e investimento das áreas). São os primeiros a ser
      contingenciados quando a meta fiscal aperta.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais.</p>`,
  },
  fiscal_obrigatorias: {
    titulo: "Outras despesas obrigatórias",
    html: `<p>Despesas obrigatórias fora previdência e pessoal: BPC (benefício a idosos e pessoas com deficiência de baixa renda), abono
      salarial e seguro-desemprego, sentenças judiciais e precatórios, complemento da União ao Fundeb, subsídios, créditos
      extraordinários, compensação ao INSS pela desoneração da folha e demais.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais.</p>`,
  },
  fiscal_controle_fluxo: {
    titulo: "Obrigatórias com controle de fluxo",
    html: `<p>Despesas obrigatórias cujo ritmo de pagamento o Executivo programa ao longo do ano: Bolsa Família e parte das despesas
      de saúde e educação.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN), API Séries Temporais.</p>`,
  },
  fiscal_investimento: {
    titulo: "Investimento do governo federal",
    html: `<p>Investimento (obras e equipamentos) pago pelo governo federal em 12 meses, em reais e em % do PIB.</p>
      <p class="sub">Fonte: Tesouro Nacional — Resultado do Tesouro Nacional (RTN, item de memorando), API Séries Temporais; PIB do Banco Central (SGS 4382).</p>`,
  },
  fiscal_dlsp_esferas: {
    titulo: "Dívida líquida do setor público por esfera",
    html: `<p>Dívida líquida do setor público (dívidas menos ativos financeiros) dividida entre Governo Federal e Banco Central, estados,
      municípios e empresas estatais. As barras somadas dão a dívida líquida total; valor negativo = credor líquido.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Estatísticas fiscais (SGS 4503, 4507, 4508, 4509 e 4513).</p>`,
  },
  fiscal_dpf: {
    titulo: "Dívida Pública Federal em mercado",
    html: `<p>Estoque da Dívida Pública Federal em poder do mercado (fora da carteira do Banco Central), somado título a título pelo
      indexador: <b>Selic</b> (LFT), <b>prefixado</b> (LTN e NTN-F), <b>IPCA</b> (NTN-B), <b>IGP-M</b> (NTN-C), <b>câmbio</b> (dívida externa)
      e demais títulos e contratos. Em "% do estoque", a participação de cada um.</p>
      <p class="sub">Fonte: Tesouro Nacional — Estoque da Dívida Pública Federal (Tesouro Transparente, posição mensal desde set/2017).</p>`,
  },
  fiscal_dpf_vencimentos: {
    titulo: "Vencimentos da Dívida Pública Federal",
    html: `<p>Quanto do estoque em mercado vence em cada ano, pelo valor de hoje dos títulos. Muito vencimento concentrado num ano
      significa mais dívida para rolar de uma vez.</p>
      <p class="sub">Fonte: Tesouro Nacional — Estoque da Dívida Pública Federal (Tesouro Transparente).</p>`,
  },
  fiscal_dpf_12m: {
    titulo: "Dívida Pública Federal que vence em 12 meses",
    html: `<p>Parcela do estoque em mercado com vencimento nos 12 meses seguintes a cada mês: indicador de risco de refinanciamento
      acompanhado pelo próprio Tesouro.</p>
      <p class="sub">Fonte: Tesouro Nacional — Estoque da Dívida Pública Federal (Tesouro Transparente).</p>`,
  },
  fiscal_tesouro_direto: {
    titulo: "Estoque do Tesouro Direto",
    html: `<p>Quanto as pessoas físicas têm aplicado em títulos públicos pelo Tesouro Direto, por tipo de título, no fim de cada mês.</p>
      <p class="sub">Fonte: Tesouro Nacional — Estoque do Tesouro Direto (Tesouro Transparente).</p>`,
  },
  fiscal_estados: {
    titulo: "Dívida e gasto com pessoal dos estados",
    html: `<p><b>Dívida consolidada líquida</b> (dívida menos caixa e haveres) em % da <b>receita corrente líquida</b>: o limite do Senado
      para estados é 200%. <b>Pessoal do Poder Executivo</b> em % da receita corrente líquida: limite de 49% pela Lei de Responsabilidade
      Fiscal. No gráfico, os seis estados mais endividados (fim de cada ano e quadrimestres do ano corrente).</p>
      <p class="sub">Fonte: Tesouro Nacional — SICONFI, Relatório de Gestão Fiscal (anexos 1 e 2), API de dados abertos.</p>`,
  },
  fiscal_capitais: {
    titulo: "Dívida e gasto com pessoal das capitais",
    html: `<p>Mesmos indicadores dos estados para as capitais: dívida consolidada líquida em % da receita corrente líquida (limite de 120%
      para municípios) e pessoal do Poder Executivo em % da receita corrente líquida (limite de 54%).</p>
      <p class="sub">Fonte: Tesouro Nacional — SICONFI, Relatório de Gestão Fiscal (anexos 1 e 2), API de dados abertos.</p>`,
  },
  fiscal_prazo: {
    titulo: "Prazo médio da dívida mobiliária federal",
    html: `<p>Prazo médio, em meses, dos títulos do Tesouro Nacional em circulação: quanto maior, menos dívida vence a cada ano
      e menor o risco de refinanciamento.</p>
      <p class="sub">Fonte: Banco Central do Brasil — Dívida mobiliária federal, prazo médio dos títulos emitidos (SGS 10618).</p>`,
  },
  desemprego_br: {
    titulo: "Desemprego (PNAD Contínua)",
    html: `<p>Taxa de desocupação das pessoas de 14 anos ou mais, medida pelo <b>IBGE</b> na PNAD Contínua, pesquisa com domicílios
      em todo o país (padrão da OIT: quem procurou trabalho e não encontrou).</p>
      <p><b>Trimestre móvel:</b> cada ponto é a média de três meses (por exemplo, jul-ago-set), datado pelo último mês. Por isso a série
        é suave e não mostra um mês isolado. Não tem ajuste sazonal: compare com o mesmo trimestre de anos anteriores.</p>
      <p class="sub">Fonte: IBGE — PNAD Contínua, tabela 6381 do SIDRA (reserva: série 24369 do SGS do Banco Central).</p>`,
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
        <b>ex-ante</b> (juro futuro contra a inflação esperada), que aparece na seção Juros na curva DI x IPCA e no Tesouro IPCA+.</p>
      <p class="sub">Fonte: Cálculo do site com a Selic meta (SGS 432) e o IPCA 12 meses (IBGE, SGS 433).</p>`,
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
      <p class="sub">Fonte oficial: Tesouro Nacional (Tesouro Transparente), com 1 a 2 dias úteis de atraso; "último oficial" é a data de referência.</p>`,
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
        entre os títulos.</p>
      <p>Calculada em cada vencimento do IPCA+ e de cada prefixado dentro da faixa de prazos em que existem os dois tipos de título
        (a outra curva é interpolada linearmente nesse prazo, sem extrapolar). Antes do IPCA+ mais curto e depois do prefixado mais
        longo (hoje cerca de 10 anos) não há como calcular.</p>
      <p class="sub">Fonte: Cálculo do site com as taxas oficiais do Tesouro Direto (Tesouro Transparente).</p>`,
  },
  vertices: {
    titulo: "Taxas DI por prazo",
    html: `<p>Taxas da curva DI (prefixada e real) em prazos fixos, interpoladas linearmente entre os vértices negociados.
      Facilita comparar a mesma maturidade em datas diferentes.</p>
      <p class="sub">Fonte: B3, arquivo "Taxas de Mercado para Swaps"; interpolação do site.</p>`,
  },
  titulos: {
    titulo: "Títulos do Tesouro Direto",
    html: `<h4>Os títulos</h4>
      <ul>
        <li><b>Prefixado (LTN)</b> e <b>Prefixado com juros semestrais (NTN-F):</b> taxa fixa definida na compra.</li>
        <li><b>IPCA+ (NTN-B Principal)</b> e <b>IPCA+ com juros semestrais (NTN-B):</b> IPCA mais uma taxa real.</li>
        <li><b>Selic (LFT):</b> acompanha a Selic; a taxa mostrada é o ágio ou deságio sobre ela.</li>
        <li><b>Renda+ e Educa+:</b> IPCA+ com pagamento em parcelas mensais a partir de uma data (aposentadoria ou estudos).</li>
        <li><b>IGP-M+ com juros semestrais (NTN-C):</b> IGP-M mais uma taxa real.</li>
      </ul>
      <p>PU = preço unitário. Variação em pontos-base (1 bp = 0,01 ponto percentual): taxa subindo = preço caindo.</p>
      <h4>O botão de referência</h4>
      <ul>
        <li><b>Oficial (data base):</b> taxa e preço de compra da manhã da data de referência, nos dados abertos do Tesouro Nacional.
          Publicados com 1 a 2 dias úteis de atraso — por isso a data aparece no botão. A variação compara com a curva de 1 semana antes.</li>
        <li><b>Tempo real (não oficial):</b> as taxas que o site do Tesouro Direto pratica agora, repreçadas ao longo do dia.
          Lidas de um endereço interno do site, sem documentação nem garantia; cada taxa só é publicada se o preço for positivo e
          ficar a no máximo 1 ponto percentual da última taxa oficial. Atualizado 3 vezes por dia útil. "vs. oficial" compara com a data base.</li>
      </ul>
      <p>O histórico que abre ao clicar num título é sempre o oficial.</p>
      <p class="sub">Fontes: oficial — Tesouro Nacional, dados abertos do Tesouro Transparente (Preço e Taxa do Tesouro Direto);
        tempo real — site do Tesouro Direto (não oficial).</p>`,
  },
  ust_curva: {
    titulo: "Curva de Treasuries (EUA)",
    html: `<p>Rendimento dos títulos do Tesouro americano por prazo, de 1 mês a 30 anos (curva "par", calculada pelo próprio
      <b>Tesouro dos EUA</b> no fechamento de cada dia útil). É a referência de juros livre de risco do mundo.</p>
      <p>As linhas comparam hoje com 1 semana, 1 mês, 6 meses e 1 ano atrás. Curva invertida (curto acima do longo) costuma indicar
        expectativa de cortes de juros e, historicamente, antecedeu recessões.</p>
      <p class="sub">Fonte: U.S. Department of the Treasury — Daily Treasury Par Yield Curve Rates.</p>`,
  },
  ust_real: {
    titulo: "Curva real (TIPS)",
    html: `<p>Juro <b>acima da inflação</b> dos títulos americanos indexados ao CPI (TIPS), de 5 a 30 anos. A diferença entre a curva
      nominal e a real no mesmo prazo é a inflação implícita americana (breakeven).</p>
      <p class="sub">Fonte: U.S. Department of the Treasury — Daily Treasury Par Real Yield Curve Rates.</p>`,
  },
  ust_hist: {
    titulo: "Treasuries ao longo do tempo",
    html: `<p>Histórico diário dos prazos de 2, 10 e 30 anos e do 10 anos real (TIPS). A <b>inclinação 10a − 2a</b> é a diferença entre
      o 10 e o 2 anos: negativa = curva invertida.</p>
      <p class="sub">Fonte: U.S. Department of the Treasury — Daily Treasury Par Yield Curve Rates.</p>`,
  },
  fed_funds: {
    titulo: "Fed Funds e SOFR",
    html: `<ul>
        <li><b>Meta dos Fed Funds:</b> banda definida pelo FOMC (8 reuniões por ano) para os empréstimos de um dia entre bancos.</li>
        <li><b>EFFR:</b> taxa efetiva desses empréstimos, calculada pelo Fed de Nova York; fica dentro da banda.</li>
        <li><b>SOFR:</b> taxa de um dia com lastro em Treasuries (compromissadas); substituiu a Libor como referência em dólar.</li>
      </ul><p class="sub">Fonte: Federal Reserve Bank of New York (API oficial de taxas de referência).</p>`,
  },
  bce_juros: {
    titulo: "BCE: taxas de depósito e de refinanciamento e €STR",
    html: `<ul>
        <li><b>Taxa de depósito:</b> a taxa básica da Zona do Euro na prática — quanto os bancos recebem ao deixar recursos no BCE.</li>
        <li><b>Refinanciamento (MRO):</b> taxa das operações principais em que o BCE empresta aos bancos por uma semana; desde 2024 fica
          0,15 ponto acima da taxa de depósito.</li>
        <li><b>€STR:</b> taxa média dos empréstimos de um dia sem garantia entre bancos da Zona do Euro, calculada pelo BCE.</li>
      </ul><p class="sub">Fonte: Banco Central Europeu (ECB Data Portal, API oficial).</p>`,
  },
  curva_euro: {
    titulo: "Curva de juros da Zona do Euro (AAA)",
    html: `<p>Curva estimada pelo <b>BCE</b> a partir dos títulos de governos da Zona do Euro com nota AAA (como Alemanha e Holanda):
      taxas à vista por prazo. É a referência de juros longos em euro, comparável à curva de Treasuries.</p>
      <p class="sub">Fonte: Banco Central Europeu (ECB Data Portal, yield curves).</p>`,
  },
  pib_eua: {
    titulo: "PIB dos EUA",
    html: `<p>Produto interno bruto real (descontada a inflação) calculado pelo <b>BEA</b>. Os EUA divulgam a variação do trimestre contra o
      anterior <b>anualizada</b> (o ritmo do trimestre projetado para um ano inteiro) — por isso os números parecem maiores que os do
      Brasil e da Europa, que mostram a variação tri/tri simples. A linha mostra o crescimento contra o mesmo trimestre do ano anterior.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), séries A191RL1Q225SBEA e GDPC1 do BEA.</p>`,
  },
  producao_eua: {
    titulo: "Produção industrial dos EUA",
    html: `<p>Índice de produção da indústria (transformação, mineração e energia elétrica e gás), calculado pelo <b>Federal Reserve</b>,
      com ajuste sazonal. Barras: variação no mês; linha: variação em 12 meses.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), série INDPRO do Federal Reserve.</p>`,
  },
  varejo_eua: {
    titulo: "Vendas no varejo dos EUA",
    html: `<p>Vendas do varejo e de serviços de alimentação, em dólares correntes (<b>nominal</b>, sem descontar a inflação), com ajuste
      sazonal, apuradas pelo <b>Census Bureau</b>. Barras: variação no mês; linha: variação em 12 meses.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), série RSAFS do Census Bureau.</p>`,
  },
  confianca_eua: {
    titulo: "Confiança do consumidor (Michigan)",
    html: `<p>Índice de sentimento do consumidor da <b>Universidade de Michigan</b> (base 100 = 1º tri de 1966), a partir de entrevistas
      mensais sobre finanças pessoais e expectativas para a economia. Abaixo de 80 costuma indicar pessimismo.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), série UMCSENT da Universidade de Michigan.</p>`,
  },
  pce_eua: {
    titulo: "Inflação do PCE",
    html: `<p>Índice de preços dos gastos de consumo pessoal (<b>PCE</b>), calculado pelo <b>BEA</b>. É a medida que o <b>Fed usa na meta de
      2%</b>. Difere do CPI porque cobre mais gastos (inclusive os pagos por terceiros, como planos de saúde), tem pesos que mudam com o
      consumo e dá menos peso a aluguel — por isso costuma ficar abaixo do CPI. O núcleo exclui alimentos e energia.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), séries PCEPI e PCEPILFE do BEA.</p>`,
  },
  juro_real_eua: {
    titulo: "Juro real ex-post nos EUA",
    html: `<p>Teto da banda do Fed Funds vigente no fim de cada mês descontado da inflação dos 12 meses anteriores:
      <code>(1 + juro) ÷ (1 + inflação) − 1</code>, pelo CPI e pelo núcleo do PCE (a medida preferida do Fed).</p>
      <p class="sub">Fonte: cálculo do site com dados do Fed de Nova York, BLS e FRED.</p>`,
  },
  producao_euro: {
    titulo: "Produção industrial da Zona do Euro",
    html: `<p>Volume de produção da indústria (extrativa, transformação e energia; sem construção). Barras: variação no mês com ajuste sazonal;
      linha: 12 meses, ajustada por dias úteis.</p>
      <p class="sub">Fonte: Eurostat, tabela sts_inpr_m (EA21).</p>`,
  },
  varejo_euro: {
    titulo: "Vendas no varejo da Zona do Euro",
    html: `<p>Volume (descontada a inflação) das vendas do comércio varejista, exceto veículos. Barras: variação no mês com ajuste sazonal;
      linha: 12 meses, ajustada por dias úteis.</p>
      <p class="sub">Fonte: Eurostat, tabela sts_trtu_m (EA21).</p>`,
  },
  juro_real_euro: {
    titulo: "Juro real ex-post na Zona do Euro",
    html: `<p>Taxa de depósito do BCE (a taxa de referência da política monetária desde 2019) vigente no fim de cada mês descontada da
      inflação (HICP) dos 12 meses anteriores: <code>(1 + juro) ÷ (1 + inflação) − 1</code>.</p>
      <p class="sub">Fonte: cálculo do site com dados do BCE e do Eurostat.</p>`,
  },
  empresas_mundo: {
    titulo: "Empresas do S&P 500",
    html: `<p>As cerca de 500 maiores empresas listadas nos EUA, pela carteira diária do <b>SPY</b> (fundo da State Street que replica o S&P 500 —
      a lista oficial do índice é paga). Demonstrações e indicadores vêm dos dados XBRL que cada empresa entrega à <b>SEC</b> nos relatórios 10-K
      (anual) e 10-Q (trimestral); cotações do Yahoo Finance (não oficial). Valores em US$; indicadores pelos últimos 12 meses.</p>
      <p class="sub">Fontes: SEC EDGAR (companyfacts e submissions), State Street SPDR (carteira do SPY), Yahoo Finance.</p>`,
  },
  documentos_sec: {
    titulo: "Documentos entregues à SEC",
    html: `<p><b>8-K:</b> comunicado de fato relevante, com os itens informados pela empresa (ex.: 2.02 = resultado do período, 1.01 = contrato
      relevante, 5.02 = mudança de diretores, 8.01 = outros eventos). <b>10-K:</b> relatório anual auditado. <b>10-Q:</b> relatório trimestral.
      <b>DEF 14A:</b> convocação da assembleia anual.</p>
      <p class="sub">Fonte: SEC EDGAR (submissions), com link para cada documento.</p>`,
  },
  demonstracoes_sec: {
    titulo: "Demonstrações como divulgadas à SEC",
    html: `<p>Demonstração do resultado, balanço e fluxo de caixa do último 10-K (anual, com 3 anos de resultado e 2 de balanço) ou do último 10-Q
      (trimestral, com o trimestre e o acumulado do ano), exatamente com as linhas, os nomes e a abertura que a empresa divulgou — em inglês, pelo
      plano de contas americano (US-GAAP). A análise vertical (AV) usa a receita total na DRE e o ativo total no balanço.</p>
      <p class="sub">Fonte: SEC EDGAR — tabelas que a SEC gera a partir do XBRL de cada relatório ("Financial Report").</p>`,
  },
  dividendos_mundo: {
    titulo: "Dividendos e recompras",
    html: `<p>Nos EUA, boa parte do retorno ao acionista vem de <b>recompras de ações</b>, além dos dividendos. As barras somam os dois, pelo caixa
      efetivamente pago no exercício (demonstração do fluxo de caixa); a linha mostra o payout (dividendos ÷ lucro). O dividendo por ação é o
      declarado no exercício.</p>
      <p class="sub">Fonte: SEC EDGAR (XBRL dos 10-K).</p>`,
  },
  pib_china: {
    titulo: "PIB da China",
    html: `<p>Crescimento real do PIB chinês: contra o mesmo trimestre do ano anterior (o número que o governo divulga e compara com a meta
      anual, ~5%) e tri/tri com ajuste sazonal. Os dados são do <b>NBS</b> (escritório de estatísticas da China), repassados à OCDE.</p>
      <p class="sub">Fonte: OCDE, Key Short-Term Economic Indicators (dados do NBS).</p>`,
  },
  descontinuada_china: {
    titulo: "Séries da China sem continuidade",
    html: `<p><b>Valor adicionado da indústria</b> (produção industrial) e <b>vendas no varejo</b>: variação contra o mesmo mês do ano anterior.
      <b>Desemprego urbano:</b> pesquisa do NBS nas cidades (total e jovens de 16 a 24 anos).</p>
      <p>Estas séries vêm do <b>espelho gratuito</b> dos dados do NBS mantido pelo DBnomics, que guarda só os últimos 13 meses e
      <b>parou de atualizar em fevereiro de 2026</b>. O site oficial do NBS bloqueia acesso automatizado e a OCDE não repassa essas séries
      de forma estável. Em janeiro e fevereiro o NBS divulga só o acumulado dos dois meses.</p>
      <p class="sub">Fonte: NBS (Escritório Nacional de Estatísticas da China), via DBnomics — série interrompida.</p>`,
  },
  comercio_china: {
    titulo: "Comércio exterior da China",
    html: `<p>Variação em 12 meses do valor, em dólares, das exportações e importações de mercadorias — termômetro da demanda externa pela
      indústria chinesa e da demanda chinesa por commodities (minério, petróleo, soja).</p>
      <p class="sub">Fonte: OCDE, Key Short-Term Economic Indicators (dados da alfândega chinesa).</p>`,
  },
  antecedente_china: {
    titulo: "Indicador antecedente e confiança — China",
    html: `<p><b>Indicador antecedente composto (OCDE):</b> antecipa em 6 a 9 meses as viradas do ciclo; acima de 100 e subindo indica
      crescimento acima da tendência. <b>Confiança:</b> pesquisas com consumidores (índice) e empresas (saldo de respostas).</p>
      <p class="sub">Fonte: OCDE, Key Short-Term Economic Indicators.</p>`,
  },
  cpi_china: {
    titulo: "Inflação ao consumidor da China",
    html: `<p>Índice de preços ao consumidor (CPI) calculado pelo NBS. A meta informal do governo é de cerca de 3% ao ano; nos últimos anos a
      China conviveu com inflação perto de zero (risco de deflação).</p>
      <p class="sub">Fonte: OCDE, Key Short-Term Economic Indicators (dados do NBS).</p>`,
  },
  juros_china: {
    titulo: "Juros na China",
    html: `<p><b>Curto prazo:</b> taxa interbancária de 3 meses. <b>Longo prazo:</b> rendimento do título do governo de 10 anos.
      O Banco do Povo da China usa várias taxas (LPR, 7-day reverse repo), que não têm série oficial gratuita em dia; estas mostram a direção
      da política monetária.</p>
      <p class="sub">Fonte: OCDE, Key Short-Term Economic Indicators.</p>`,
  },
  cambio_china: {
    titulo: "Câmbio — yuan por dólar",
    html: `<p>Média mensal de yuans (CNY) por dólar. Subindo = yuan se desvalorizando.</p>
      <p class="sub">Fonte: OCDE, Key Short-Term Economic Indicators.</p>`,
  },
  global_fmi: {
    titulo: "Indicadores globais (FMI)",
    html: `<p>Dados anuais do <b>World Economic Outlook</b> do FMI para os principais países, com <b>projeções</b> para o ano corrente e os
      próximos (revistas em abril e outubro). Crescimento do PIB real, inflação média do ano, desemprego, dívida bruta e resultado nominal do
      governo (% do PIB) e saldo em conta corrente (% do PIB). Mundo, avançadas e emergentes são agregados do próprio FMI.</p>
      <p class="sub">Fonte: FMI, World Economic Outlook (DataMapper API).</p>`,
  },
  acoes_eua: {
    titulo: "Bolsas americanas",
    html: `<p><b>S&P 500:</b> as 500 maiores empresas dos EUA. <b>Nasdaq Composite:</b> todas as ações da Nasdaq, com peso grande de tecnologia.
      Pontos no fechamento diário, sem dividendos.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), séries SP500 (S&P Dow Jones Indices, só 10 anos) e NASDAQCOM.</p>`,
  },
  vix: {
    titulo: "VIX",
    html: `<p>Volatilidade que o mercado de opções espera para o S&P 500 nos próximos 30 dias (% ao ano). Acima de 30 costuma indicar estresse;
      abaixo de 15, calmaria.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), série VIXCLS da Cboe.</p>`,
  },
  petroleo: {
    titulo: "Petróleo Brent e WTI",
    html: `<p><b>Brent:</b> referência do Mar do Norte, usada pela Petrobras e pela maior parte do mundo. <b>WTI:</b> referência dos EUA.
      Preço à vista diário em dólares por barril.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), séries DCOILBRENTEU e DCOILWTICO da EIA (Departamento de Energia dos EUA).</p>`,
  },
  commodities: {
    titulo: "Commodities (Banco Mundial)",
    html: `<p>Preços médios mensais em dólares das principais commodities, compilados pelo <b>Banco Mundial</b> ("Pink Sheet"), com o mesmo
      critério desde 1960. Úteis para acompanhar o que importa para as exportadoras da B3: minério de ferro (Vale), petróleo (Petrobras),
      soja e milho (agronegócio), café e açúcar. Celulose não faz parte da base.</p>
      <p class="sub">Fonte: Banco Mundial, Commodity Price Data (Pink Sheet), mensal.</p>`,
  },
  dolar_global: {
    titulo: "Dólar global",
    html: `<p>Índice amplo do dólar calculado pelo <b>Federal Reserve</b>: valor do dólar contra as moedas dos principais parceiros comerciais
      dos EUA, ponderado pelo comércio (jan/2006 = 100). Subindo = dólar se fortalecendo no mundo.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), série DTWEXBGS do Federal Reserve.</p>`,
  },
  spreads_credito: {
    titulo: "Spreads de crédito",
    html: `<p>Prêmio, em pontos percentuais, que as empresas americanas pagam acima dos Treasuries: <b>high yield</b> (empresas com nota abaixo de
      grau de investimento) e <b>grau de investimento</b>. Abrem em momentos de estresse e fecham quando o apetite por risco aumenta.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), índices ICE BofA (BAMLH0A0HYM2 e BAMLC0A0CM).</p>`,
  },
  bitcoin: {
    titulo: "Bitcoin",
    html: `<p>Preço do bitcoin em dólares na Coinbase, diário.</p>
      <p class="sub">Fonte: FRED (Fed de St. Louis), série CBBTCUSD da Coinbase.</p>`,
  },
  cpi_eua: {
    titulo: "CPI — inflação ao consumidor dos EUA",
    html: `<p>Índice de preços ao consumidor urbano (CPI-U), calculado pelo <b>BLS</b>. O <b>núcleo</b> exclui alimentos e energia.
      O Fed persegue 2% ao ano, mas medido pelo PCE (deflator do consumo), que costuma ficar um pouco abaixo do CPI.</p>
      <p>Barras: variação mensal com ajuste sazonal. Linhas: acumulado em 12 meses (sem ajuste).</p>
      <p class="sub">Fonte: U.S. Bureau of Labor Statistics (API oficial), séries CUUR0000SA0, CUUR0000SA0L1E, CUSR0000SA0 e CUSR0000SA0L1E.</p>`,
  },
  emprego_eua: {
    titulo: "Payroll e desemprego (EUA)",
    html: `<ul>
        <li><b>Payroll:</b> vagas formais criadas no mês fora do setor agrícola (pesquisa com empresas), em milhares. Sai na primeira
          sexta-feira do mês, no relatório Employment Situation, e é revisado nos dois meses seguintes.</li>
        <li><b>Desemprego:</b> taxa da pesquisa com domicílios, com ajuste sazonal.</li>
      </ul><p class="sub">Fonte: U.S. Bureau of Labor Statistics (séries CES0000000001 e LNS14000000).</p>`,
  },
  hicp: {
    titulo: "HICP — inflação da Zona do Euro",
    html: `<p>Índice Harmonizado de Preços ao Consumidor, calculado pelo <b>Eurostat</b> com a mesma metodologia em todos os países.
      É a medida da meta de 2% do BCE. O <b>núcleo</b> exclui energia, alimentos, álcool e fumo.</p>
      <p>Desde 2026 o HICP usa a nova classificação de consumo (ECOICOP ver. 2); a série inclui o histórico recalculado.</p>
      <p class="sub">Fonte: Eurostat (prc_hicp_minr).</p>`,
  },
  desemprego_euro: {
    titulo: "Desemprego na Zona do Euro",
    html: `<p>Taxa de desemprego com ajuste sazonal, padrão da OIT, para os 21 países da Zona do Euro (com a Bulgária, desde 2026).</p>
      <p class="sub">Fonte: Eurostat (une_rt_m).</p>`,
  },
  pib_euro: {
    titulo: "PIB da Zona do Euro",
    html: `<p>Crescimento real do PIB: barras contra o trimestre anterior (com ajuste sazonal) e linha contra o mesmo trimestre do ano anterior.</p>
      <p class="sub">Fonte: Eurostat (namq_10_gdp).</p>`,
  },
  juros_mundo: {
    titulo: "Juros básicos comparados",
    html: `<ul>
        <li><b>Selic meta</b> (Copom, Banco Central do Brasil).</li>
        <li><b>Fed Funds</b>: o Fed define uma banda de 0,25 ponto; o gráfico usa o teto da banda.</li>
        <li><b>BCE</b>: taxa de depósito, a que na prática ancora os juros de curto prazo na Zona do Euro.</li>
      </ul>
      <p>O <b>diferencial</b> (Selic menos a taxa de fora) é o "carry": quanto mais alto, maior o atrativo de aplicar em reais —
        com o risco de câmbio e de crédito do Brasil.</p>
      <p class="sub">Fontes: Banco Central (SGS), Fed de Nova York, BCE.</p>`,
  },
  juro_real_mundo: {
    titulo: "Juro real ex-post comparado",
    html: `<p>Para cada país, a taxa básica vigente no fim do mês descontada da inflação acumulada em 12 meses:
      <code>(1 + taxa básica) ÷ (1 + inflação 12m) − 1</code>. Mostra quão apertada está a política monetária em cada lugar,
      olhando para a inflação que já aconteceu.</p>
      <p class="sub">Brasil: Selic e IPCA. EUA: teto dos Fed Funds e CPI. Zona do Euro: depósito do BCE e HICP.</p>
      <p class="sub">Fonte: Cálculo do site com Banco Central (Selic, IPCA), Fed de Nova York (Fed Funds), BLS (CPI), BCE (depósito) e Eurostat (HICP).</p>`,
  },
  curvas_mundo: {
    titulo: "Curvas de juros comparadas",
    html: `<ul>
        <li><b>Brasil:</b> curva DI x Pré da B3 (até 10 anos), fim do dia.</li>
        <li><b>EUA:</b> curva par de Treasuries do Tesouro americano (até 30 anos).</li>
        <li><b>Zona do Euro:</b> curva à vista dos títulos AAA estimada pelo BCE (até 30 anos).</li>
      </ul>
      <p>As três são nominais, cada uma na sua moeda. As datas de referência aparecem na legenda.</p>
      <p class="sub">Fonte: B3 (DI x Pré), U.S. Department of the Treasury (Treasuries) e Banco Central Europeu (curva AAA).</p>`,
  },
  inflacao_mundo: {
    titulo: "Inflação comparada",
    html: `<ul>
        <li><b>Brasil:</b> IPCA (IBGE), meta contínua de 3%; núcleos = média dos 5 núcleos do Banco Central.</li>
        <li><b>EUA:</b> CPI (BLS). O Fed persegue 2% medido pelo PCE, que costuma ficar um pouco abaixo do CPI; núcleo sem alimentos e energia.</li>
        <li><b>Zona do Euro:</b> HICP (Eurostat), meta de 2% do BCE; núcleo sem energia, alimentos, álcool e fumo.</li>
      </ul>
      <p>"Distância da meta" = inflação em 12 meses menos a meta de cada banco central (para os EUA, 2% aplicado ao CPI, como aproximação).</p>
      <p class="sub">Fonte: IBGE e Banco Central (IPCA e núcleos), U.S. Bureau of Labor Statistics (CPI) e Eurostat (HICP).</p>`,
  },
  pib_mundo: {
    titulo: "PIB comparado",
    html: `<p>Crescimento real contra um ano antes. Brasil: acumulado em 4 trimestres contra os 4 anteriores (IBGE).
      Zona do Euro: trimestre contra o mesmo trimestre do ano anterior (Eurostat). EUA entram quando houver a chave do FRED.</p>
      <p class="sub">Fonte: IBGE (via SGS do Banco Central) e Eurostat (namq_10_gdp).</p>`,
  },
  desemprego_mundo: {
    titulo: "Desemprego comparado",
    html: `<p>Taxas com ajuste sazonal: EUA (BLS) e Zona do Euro (Eurostat). O desemprego do Brasil (PNAD Contínua, IBGE) entra em seguida.
      As metodologias são próximas (padrão da OIT), mas não idênticas.</p>
      <p class="sub">Fonte: U.S. Bureau of Labor Statistics (LNS14000000), Eurostat (une_rt_m) e IBGE (PNAD Contínua, tabela 6381).</p>`,
  },
  eleicoes: {
    titulo: "Eleições — Presidente",
    html: `<p>Resultado oficial da eleição presidencial, nos arquivos públicos de divulgação do <b>Tribunal Superior Eleitoral</b>.
      Durante a apuração o TSE atualiza os arquivos; o cartão "apurado" mostra o % de seções já totalizadas.</p>
      <ul>
        <li><b>% válidos:</b> votos do candidato ÷ votos válidos (sem brancos e nulos) — é o critério da Constituição para vencer.</li>
        <li><b>2º turno:</b> quando ninguém passa de 50% dos válidos no 1º turno, os dois mais votados disputam o 2º.</li>
        <li><b>Por estado:</b> o mais votado e o segundo colocado em cada UF.</li>
      </ul>
      <p>Pesquisas eleitorais não entram: o TSE registra as pesquisas, mas os números são divulgados pelos institutos.</p>
      <p><b>Quando aparece:</b> a aba entra sozinha em ano de eleição federal (pelo calendário do TSE) e sai 15 dias depois
        da última votação.</p>
      <p class="sub">Fonte: TSE — Divulgação de Resultados (resultados.tse.jus.br).</p>`,
  },
  calendario_resultados: {
    titulo: "Calendário de resultados",
    html: `<p>Quando cada empresa da lista deve divulgar o próximo balanço (ITR trimestral ou DFP anual).</p>
      <ul>
        <li><b>Prazo legal:</b> ITR até 45 dias depois do fim do trimestre; DFP até 3 meses depois do fim do exercício.</li>
        <li><b>Data estimada ("est."):</b> a data em que a empresa entregou o mesmo período no ano anterior, um ano depois (mesmo dia
          da semana) e limitada ao prazo legal. Empresas costumam repetir o calendário, mas a data oficial é a que cada uma anuncia
          no seu calendário de eventos corporativos.</li>
        <li><b>Atrasado:</b> o prazo legal passou e a entrega ainda não aparece na CVM.</li>
      </ul>
      <p class="sub">Fonte: CVM — índice de documentos ITR e DFP dos dados abertos (data de entrega de cada documento); estimativa do site.</p>`,
  },
  ifdata: {
    titulo: "IF.data — dados das instituições financeiras",
    html: `<p>Relatórios trimestrais que o <b>Banco Central</b> publica para cada instituição supervisionada: resumo, balanço, DRE,
      capital e carteira de crédito. Os números são do <b>conglomerado prudencial</b> (o grupo que o BC supervisiona como um todo)
      ou da instituição independente — podem diferir um pouco do balanço consolidado em IFRS que o banco publica.</p>
      <ul>
        <li><b>Segmento (S1 a S5):</b> enquadramento prudencial pelo porte em relação ao PIB e pela atuação internacional; S1 são os maiores.
          Quando o cadastro do BC traz o segmento em branco (caso do Bradesco), o site o calcula pela regra da Resolução 4.553 com a exposição
          total e os ativos no exterior do relatório de Segmentação, e marca "seg. calculado".</li>
        <li><b>Tipo:</b> banco comercial/múltiplo, de investimento, de desenvolvimento, não bancária de crédito, mercado de capitais ou instituição de pagamento.</li>
        <li><b>Layout novo desde 2025:</b> com a Resolução CMN 4.966, o plano de contas mudou; o detalhe vem desde o 1º tri de 2025 e o
          histórico longo (desde 2015) fica com as linhas que existem nos dois layouts.</li>
        <li><b>Resultado:</b> o BC informa o trimestre em março e setembro e o semestre em junho e dezembro; o site separa o 2º e o 4º trimestres.</li>
      </ul>
      <p class="sub">Fonte: Banco Central do Brasil — IF.data (API Olinda), dados oficiais.</p>`,
  },
  ifdata_4966: {
    titulo: "O que mudou em 2025: Resolução CMN 4.966",
    html: `<p>Em <b>1º de janeiro de 2025</b> entrou em vigor a <b>Resolução CMN 4.966/2021</b>, complementada pela <b>Resolução BCB 352/2023</b>.
      Ela aproxima a contabilidade dos bancos brasileiros do padrão internacional <b>IFRS 9</b>. Como as regras mudaram, o Banco Central
      reorganizou o IF.data: os relatórios a partir da data-base de março de 2025 têm outro formato, e por isso o site mostra o
      detalhe das demonstrações e das carteiras só desde o 1º trimestre de 2025.</p>
      <h4>Principais mudanças</h4>
      <ul>
        <li><b>Provisão por perda esperada:</b> antes (Resolução 2.682), o banco classificava cada operação em níveis de risco de AA a H,
          com provisão mínima por nível — um modelo de perda <i>incorrida</i>. Agora a provisão é pela <b>perda esperada</b>: o banco estima
          o que deve perder já na concessão do crédito e revisa a estimativa quando o risco do cliente piora (estágios 1, 2 e 3).</li>
        <li><b>Ativos problemáticos:</b> conceito novo para operações com atraso acima de 90 dias ou com indício de que não serão pagas
          (como reestruturações). Para eles o banco deixa de reconhecer os juros como receita enquanto o problema durar.</li>
        <li><b>Carteiras C1 a C5:</b> o Banco Central passou a agrupar as operações por tipo e garantia, da C1 (garantias mais fortes)
          à C5 (sem garantia), com provisões mínimas que crescem com o atraso. Substituem, no IF.data, a carteira por nível de risco AA–H.</li>
        <li><b>Classificação dos ativos financeiros:</b> pelo modelo de negócio — custo amortizado, valor justo no resultado ou valor justo
          no patrimônio —, como no IFRS 9.</li>
        <li><b>Juros pela taxa efetiva:</b> tarifas e custos ligados à concessão do crédito passam a ser reconhecidos ao longo do prazo da
          operação, junto com os juros.</li>
        <li><b>Novo plano de contas (Cosif):</b> o balanço e a DRE do IF.data ganharam linhas novas — perda esperada destacada por tipo de
          ativo, transações de pagamento, ajustes de variação cambial e de hedge — e outras deixaram de existir.</li>
      </ul>
      <h4>Efeito na comparação</h4>
      <p>Números de 2024 para trás e de 2025 em diante não são diretamente comparáveis: a provisão, a receita de juros e o patrimônio
        dos bancos foram recalculados na transição (o ajuste inicial foi lançado no patrimônio). Por isso o histórico longo do site
        (desde 2015) usa só as linhas que existem nos dois formatos — ativo total, carteira, captações, patrimônio, lucro e Basileia.</p>
      <p class="sub">Fontes: Resolução CMN 4.966/2021 e Resolução BCB 352/2023 (Banco Central do Brasil); IF.data — Banco Central.</p>`,
  },
  capital_banco: {
    titulo: "Capital regulatório (Basileia)",
    html: `<ul>
        <li><b>Patrimônio de Referência (PR):</b> capital que conta para a regulação = Nível I (capital principal + complementar) + Nível II.</li>
        <li><b>RWA:</b> ativos ponderados pelo risco (crédito, mercado e operacional) — o "tamanho do risco" do banco.</li>
        <li><b>Índice de Basileia:</b> PR ÷ RWA. O mínimo exigido é 8% mais o adicional de conservação (2,5%), ou seja, 10,5%, além
          de adicionais para os bancos sistêmicos; o gráfico marca 10,5%.</li>
        <li><b>Índice de Capital Principal:</b> o capital de melhor qualidade ÷ RWA. <b>Razão de alavancagem:</b> Nível I ÷ exposição total, sem ponderar risco.</li>
      </ul>
      <p class="sub">Fonte: Banco Central do Brasil — IF.data, relatório Informações de Capital.</p>`,
  },
  historico_banco: {
    titulo: "Histórico desde 2015",
    html: `<p>Linhas do relatório Resumo do IF.data que existem tanto no layout antigo quanto no novo: ativo total, carteira de crédito,
      captações, patrimônio líquido, lucro líquido e índice de Basileia. O lucro é trimestral (o 2º e o 4º trimestres saem por diferença do semestre).</p>
      <p class="sub">Fonte: Banco Central do Brasil — IF.data, relatório Resumo.</p>`,
  },
  dfs_banco: {
    titulo: "Demonstrações financeiras (IF.data)",
    html: `<p>Balanço e DRE no layout do IF.data desde 2025, na estrutura da planilha de rating de emissores bancários.</p>
      <ul>
        <li><b>Receitas da intermediação financeira:</b> rendas de aplicações interfinanceiras, de TVM, de crédito, de arrendamento, de outras
          operações de crédito, derivativos e outros resultados de intermediação.</li>
        <li><b>Resultado da intermediação:</b> antes da perda esperada (PDD). <b>Resultado líquido da intermediação:</b> depois da PDD.</li>
        <li><b>Seletor:</b> trimestre, semestre, ano ou LTM (soma dos 4 últimos trimestres); o balanço mostra o saldo no fim de cada período.</li>
      </ul>
      <p class="sub">Fonte: Banco Central do Brasil — IF.data, relatórios Ativo, Passivo e Demonstração de Resultado.</p>`,
  },
  carteira_banco: {
    titulo: "Carteira de crédito",
    html: `<ul>
        <li><b>Prazo:</b> soma das modalidades de PF e PJ por faixa (vencido há mais de 15 dias e a vencer por prazo).</li>
        <li><b>C1 a C5:</b> classificação das carteiras na Resolução CMN 4.966 — da C1 (menor risco, com garantias mais fortes) à C5.</li>
        <li><b>Inadimplência</b> e <b>ativos problemáticos</b> como divulgados pelo BC, em % da carteira total.</li>
        <li><b>Indexador, região, porte do tomador e modalidades</b> (consignado, veículos, habitação, cartão, rural, capital de giro, comércio exterior etc.).</li>
      </ul>
      <p class="sub">Fonte: Banco Central do Brasil — IF.data, relatórios de carteira de crédito ativa.</p>`,
  },
  receita: {
    titulo: "Receita líquida",
    html: `<p>Vendas de produtos e serviços já descontados impostos sobre vendas, devoluções e abatimentos (linha 3.01 da DRE
      entregue à CVM). A linha mostra o crescimento contra o mesmo período do ano anterior.</p>
      <p class="sub">Fonte: CVM — demonstrações financeiras (ITR e DFP) entregues pela empresa.</p>`,
  },
  lucro_bruto: {
    titulo: "Lucro bruto e margem bruta",
    html: `<p>Receita líquida menos o custo dos produtos ou serviços vendidos. Margem bruta = lucro bruto ÷ receita.
      Bancos e seguradoras não têm essa linha no mesmo formato.</p>
      <p class="sub">Fonte: CVM — demonstrações financeiras (ITR e DFP).</p>`,
  },
  ebitda: {
    titulo: "EBITDA",
    html: `<p>Lucro antes de juros, impostos, depreciação e amortização: <code>EBIT + D&amp;A</code>. Aproxima a geração de caixa
      operacional antes de investimentos e capital de giro.</p>
      <p>A D&amp;A não é conta padronizada da CVM: é somada a partir das linhas da DFC cuja descrição fala em depreciação,
        amortização ou exaustão (as linhas usadas aparecem nas notas da página). Sem essas linhas, EBITDA = EBIT.</p>
      <p class="sub">Fonte: CVM — DRE e DFC (ITR e DFP); D&amp;A somada pelo site a partir das descrições da DFC.</p>`,
  },
  ebit: {
    titulo: "EBIT",
    html: `<p>Resultado antes do resultado financeiro e dos tributos sobre o lucro (linha 3.05 da DRE). Margem EBIT = EBIT ÷ receita.</p>
      <p class="sub">Fonte: CVM — demonstrações financeiras (ITR e DFP).</p>`,
  },
  lucro_liquido: {
    titulo: "Lucro líquido",
    html: `<p>Resultado final do período (consolidado) depois de resultado financeiro e impostos. Margem líquida = lucro líquido ÷ receita.</p>
      <p class="sub">Fonte: CVM — demonstrações financeiras (ITR e DFP).</p>`,
  },
  resultado_financeiro: {
    titulo: "Resultado financeiro",
    html: `<p>Receitas financeiras (rendimento do caixa, variação cambial ativa) menos despesas financeiras (juros da dívida,
      variação cambial passiva, encargos de arrendamento). As barras ficam empilhadas no mesmo ponto; a linha é o saldo.</p>
      <p class="sub">Fonte: CVM — demonstrações financeiras (ITR e DFP).</p>`,
  },
  retorno: {
    titulo: "ROE e ROIC (últimos 12 meses)",
    html: `<ul>
        <li><b>ROE:</b> lucro líquido dos últimos 12 meses ÷ patrimônio líquido no fim do período.</li>
        <li><b>ROIC:</b> EBIT dos últimos 12 meses × (1 − 34%) ÷ (dívida líquida + patrimônio líquido) no fim do período.
          A alíquota de 34% (IR + CSLL) é uma simplificação.</li>
      </ul>
      <p class="sub">Fonte: Cálculo do site com as demonstrações da CVM (ITR e DFP).</p>`,
  },
  fluxo_caixa: {
    titulo: "Fluxo de caixa (DFC)",
    html: `<ul>
        <li><b>FCO:</b> caixa gerado pelas operações.</li>
        <li><b>FCI:</b> caixa usado em investimentos (capex, aquisições) ou recebido em vendas de ativos.</li>
        <li><b>FCFi:</b> caixa de financiamentos: captações, amortizações, dividendos e recompras.</li>
        <li><b>Soma:</b> FCO + FCI + FCFi = variação do caixa no período (antes da variação cambial sobre o caixa).</li>
      </ul>
      <p>FCF (fluxo de caixa livre), usado nos indicadores = FCO − capex.</p>
      <p class="sub">Fonte: CVM — Demonstração dos Fluxos de Caixa (ITR e DFP).</p>`,
  },
  endividamento: {
    titulo: "Endividamento",
    html: `<ul>
        <li><b>Dívida bruta sem IFRS 16:</b> empréstimos, financiamentos e debêntures de curto e longo prazo.</li>
        <li><b>Arrendamentos (IFRS 16):</b> aluguéis, frota, aeronaves etc. registrados como passivo desde 2019; identificados
          pela descrição das linhas do balanço.</li>
        <li><b>Dívida líquida:</b> dívida bruta − (caixa + aplicações financeiras).</li>
        <li><b>Dív. líquida / EBITDA:</b> quantos anos de EBITDA (últimos 12 meses) pagariam a dívida líquida.</li>
      </ul>
      <p class="sub">Fonte: CVM — balanço patrimonial (ITR e DFP); EBITDA calculado pelo site.</p>`,
  },
  dividendos_dfc: {
    titulo: "Dividendos e JCP pagos (DFC) e payout",
    html: `<p>Caixa <b>efetivamente pago</b> a acionistas no ano, pelas linhas da DFC de dividendos e juros sobre capital próprio.
      Payout = pagos no ano ÷ lucro líquido do ano. Como o pagamento costuma ocorrer no ano seguinte ao lucro, o payout de um
      ano isolado pode passar de 100%.</p>
      <p class="sub">Fonte: CVM — Demonstração dos Fluxos de Caixa (DFP).</p>`,
  },
  proventos_acao: {
    titulo: "Proventos por ação e dividend yield",
    html: `<p>Dividendos e JCP <b>anunciados</b> por ação, somados pelo ano da data-com (fonte B3). O DY de cada ano soma,
      provento a provento, o valor ÷ preço de fechamento na data-com.</p>
      <p class="sub">Fonte: B3 — proventos em dinheiro e preço de fechamento na data-com.</p>`,
  },
  cotacao: {
    titulo: "Cotação semanal",
    html: `<p>Preço de fechamento semanal dos últimos 10 anos, sem ajuste por proventos. Fonte: Yahoo Finance (não oficial).</p>`,
  },
};
