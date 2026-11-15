# Varredura do painel e sugestões de melhoria

Feita em 2026-11-14, sobre o site publicado e o código (`site/assets/app.js`, `site/dados/*.json`). **Nada aqui foi executado**: é um mapa do que existe e do que pode melhorar a leitura do cenário e a avaliação dos ativos.

Legenda de cada sugestão:

- **[V]** só visualização: o dado já está no site, muda a forma de mostrar.
- **[D]** dado novo de fonte que o site já usa (Banco Central, IBGE, B3, CVM, Tesouro, FRED, Focus).
- **[F]** fonte nova, que precisa ser pesquisada e testada antes (mantendo a regra: oficial e gratuita).
- Esforço: **P** (horas), **M** (um dia), **G** (vários dias).

As séries do Banco Central e do IBGE citadas existem nas bases públicas, mas os códigos e a disponibilidade precisam ser confirmados na hora de implementar.

---

## 1. Diagnóstico geral

**O que está forte**

- Política fiscal, crédito e setor externo do Brasil: cobertura ampla (mais de 350 séries), com abas internas.
- Juros do Brasil e do Mundo: curvas por data, juro real, inflação implícita, Treasuries, BCE, China.
- Empresas: demonstrações completas da CVM, nova aba Indicadores (resultado, endividamento, capital de giro), histórico de ajustes.
- FIIs de tijolo: visão por segmento, planilhão e página do fundo com fontes oficiais.
- Qualidade: monitor, validador, comparador de versões e teste de telas.

**Onde a leitura do cenário fica fraca**

1. **Não há uma tela de síntese.** Para saber "como está a conjuntura" é preciso abrir 8 abas de Macro, Juros e Mundo. Falta um painel de uma tela com os indicadores-chave, a direção e o quanto estão fora do normal.
2. **Atividade do Brasil é a seção mais magra**: só PIB, IBC-Br e desemprego. Faltam indústria, varejo, serviços, emprego formal, renda e confiança.
3. **Inflação sem abertura**: só o índice cheio e os núcleos. Faltam serviços, administrados, alimentos, difusão e a comparação com a meta.
4. **Câmbio só tem a cotação** (dólar e euro PTAX). Faltam câmbio real, fluxo cambial, moedas de emergentes e termos de troca.
5. **Não existe valuation da bolsa brasileira.** O site calcula P/L, ROE e FCF yield agregados do S&P 500, mas não do Brasil. Também não há Ibovespa, IFIX nem comparação de retorno entre classes de ativos.
6. **Múltiplos das empresas só no ponto atual**: P/L, EV/EBITDA e P/VP aparecem como cartão, sem histórico nem comparação com o setor. A tabela de empresas não ordena por coluna nem filtra por número.
7. **Gráficos pouco "analíticos"**: quase tudo é linha ou barra em nível. Faltam média histórica e bandas, médias móveis sob demanda, base 100, visão sazonal e marcações de eventos.

---

## 2. Ferramentas de gráfico que valem para o site inteiro

Estas mudanças melhoram todas as seções de uma vez.

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| G1 | **Botão "transformar série"** em todo gráfico de série temporal: nível · variação no mês · variação em 12 meses · média móvel de 3 e de 12 meses · base 100 a partir de uma data · escala logarítmica. Hoje cada gráfico tem transformações fixas (só a inflação tem o botão 12 meses / 3 meses anualizado). | V | M |
| G2 | **Média histórica e banda de ±1 desvio-padrão** como linhas opcionais (5 anos, 10 anos, tudo). Responde "isto está alto ou baixo?" sem sair do gráfico. | V | P |
| G3 | **Visão sazonal** para séries mensais: uma linha por ano, eixo de janeiro a dezembro, com a média dos últimos 5 anos. Útil em arrecadação, vendas, produção, energia, emplacamentos e inflação mensal. | V | M |
| G4 | **Faixas de contexto no fundo**: recessões (CODACE/NBER), ciclos de alta e de corte da Selic, eleições. E **linhas de referência**: meta de inflação com a banda, 1,0x no P/VP, 100% na dívida/receita. | V | P |
| G5 | **Rótulo do último valor** na ponta de cada linha e variação contra 1 mês / 12 meses no título do painel. Hoje é preciso passar o mouse. | V | P |
| G6 | **Destaque em gráficos com muitas linhas** ("espaguete"): Mundo › Global tem mais de 20 países no mesmo gráfico. Deixar todos em cinza e destacar os escolhidos (Brasil + pares), ou trocar por **ranking em barras** do ano selecionado. | V | P |
| G7 | **Comparar duas séries quaisquer** no mesmo gráfico (eixo duplo) e **gráfico de dispersão** entre duas séries (ex.: desemprego × inflação de serviços, juro real × crédito). | V | G |
| G8 | **Mini-gráfico (sparkline) nos cartões** do topo de cada aba, com a seta de direção. O cartão passa a mostrar nível e tendência. | V | M |
| G9 | **Tabela-termômetro (mapa de calor)**: linhas = indicadores, colunas = últimos 12 a 24 meses, cor = quão longe da média histórica. Serve para inflação por grupo, atividade por setor, crédito por modalidade. | V | M |

---

## 3. Nova tela: Painel de conjuntura (síntese)

**Sugestão S1 [V + D, G].** Uma tela única, na abertura de Economia, com 4 blocos e cerca de 6 indicadores cada (último valor, variação, sparkline e posição frente à média de 5 anos):

- **Atividade**: PIB, IBC-Br, indústria, varejo, serviços, desemprego, emprego formal.
- **Preços**: IPCA 12 meses, núcleos, serviços, difusão, expectativa do Focus para o ano seguinte, inflação implícita.
- **Juros e crédito**: Selic, juro real esperado, inclinação da curva, concessões, inadimplência, spread.
- **Fiscal e externo**: resultado primário, dívida bruta, câmbio, transações correntes, reservas, índice de commodities.

Opcional, no mesmo espírito: **relógio do ciclo** (dispersão de crescimento × inflação, com o trajeto dos últimos 24 meses) para o Brasil e para os EUA.

Observação: você pediu para tirar os gráficos da antiga tela Consolidado. Esta proposta é diferente (tabela compacta de leitura rápida, sem repetir os gráficos das seções), mas fica à sua decisão.

---

## 4. Economia › Brasil

### 4.1 Atividade (hoje: PIB anual, IBC-Br, PIB trimestral, desemprego)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| A1 | **Indústria, varejo e serviços** (IBGE: PIM, PMC, PMS), em índice dessazonalizado e variação em 12 meses. O Banco Central republica essas séries, o que contorna os bloqueios do IBGE. | D | M |
| A2 | **Emprego formal** (saldo do Novo CAGED) e **renda**: rendimento médio real e massa salarial (PNAD Contínua). | D | M |
| A3 | **Confiança e capacidade**: confiança do consumidor, da indústria e de serviços, e utilização da capacidade instalada, se disponíveis no Banco Central. Os índices da FGV completos são pagos. | D/F | M |
| A4 | **PIB pela ótica da demanda e da oferta** (consumo, investimento, governo, exportações; agro, indústria, serviços): contribuição de cada um em barras empilhadas. | D | M |
| A5 | **Taxa de investimento e poupança** (% do PIB) e **hiato**: IBC-Br contra a própria tendência. | D/V | M |
| A6 | Ligação com **Empresas › Operacional** (energia, veículos, combustíveis, aviação): trazer 3 ou 4 desses como "indicadores de alta frequência" da atividade. | V | P |
| A7 | Visual: PIB trimestral como **barras de contribuição**; desemprego com a versão **dessazonalizada** e a média histórica. | V/D | P |

### 4.2 Inflação (hoje: IPCA, IGP-M, INCC, núcleos)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| I1 | **Abertura do IPCA**: serviços, serviços subjacentes, administrados, livres, alimentação no domicílio, bens industriais (séries do Banco Central). | D | M |
| I2 | **Índice de difusão** (quanto dos itens subiu no mês). | D | P |
| I3 | **Meta e banda** (3% ± 1,5) em todos os gráficos de 12 meses, e cartão "distância da meta". | V | P |
| I4 | **Contribuição por grupo** (9 grupos do IPCA) em barras empilhadas no mês e em 12 meses. | D | M |
| I5 | **IPCA-15** como prévia, e **IPCA mensal em visão sazonal** (o mês contra a média do mesmo mês em 5 anos). | D/V | P |
| I6 | **Mapa de calor dos núcleos e grupos** (G9) nos últimos 24 meses. | V | M |
| I7 | **Inflação implícita** (já existe em Juros) repetida aqui, ao lado do Focus: mercado × analistas × meta. | V | P |

### 4.3 Expectativas (hoje: IPCA, Selic, câmbio e PIB, todos os anos)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| E1 | **Mais indicadores do Focus**, no mesmo endereço já usado: resultado primário, dívida bruta, dívida líquida, conta corrente, balança comercial, investimento direto, IPCA de administrados, IGP-M. | D | P |
| E2 | **Tabela do boletim**: hoje × 1 semana × 4 semanas atrás, com seta de revisão, para cada indicador e ano. | V | P |
| E3 | **Inflação esperada 12 meses à frente** (suavizada) e **Selic esperada por reunião do Copom**: a trajetória prevista em degraus. | D | M |
| E4 | **Desancoragem**: expectativa de IPCA para 2 e 3 anos à frente menos a meta, ao longo do tempo. | V | P |
| E5 | **Dispersão** (desvio-padrão, mínimo e máximo das projeções) e **Top 5**, quando disponíveis. | D | M |

### 4.4 Política monetária (hoje: Selic, CDI, juro real ex-post, alguns gráficos fiscais)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| M1 | **Juro real esperado (ex-ante)**: taxa de 1 ano da curva DI menos a inflação esperada de 12 meses do Focus. É a medida que o Copom acompanha; hoje só há o ex-post. | V/D | P |
| M2 | **Selic precificada na curva**: trajetória da Selic embutida nos contratos de DI, por reunião do Copom, contra o Focus (E3). | V | M |
| M3 | **Agregados e condições**: base monetária, M1 a M4, compulsórios; opcionalmente um índice simples de condições financeiras (juro real, câmbio, spread de crédito, bolsa). | D | M |
| M4 | Tirar daqui os gráficos de dívida e resultado fiscal (já estão em Política fiscal) e deixar a aba só com política monetária. | V | P |
| M5 | Histórico das **decisões do Copom** (data, decisão, placar) em tabela, com link para a ata. | D | P |

### 4.5 Política fiscal (já ampla)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| F1 | **Resultado primário contra a meta do arcabouço** e a banda de tolerância, no ano e em 12 meses. | D | M |
| F2 | **Decomposição da variação da dívida bruta** (juros, primário, crescimento do PIB, câmbio, outros), que o Banco Central publica. | D | M |
| F3 | **Juro implícito da dívida** contra a Selic, e **detentores da dívida** (participação de não residentes, bancos, fundos, previdência). | D | M |
| F4 | **Leilões do Tesouro**: volume e taxa por título a cada leilão. | F | M |
| F5 | Orçamento previsto × executado e Prisma Fiscal (já é o lembrete 5). | — | — |

### 4.6 Crédito (já amplo)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| C1 | **Crescimento real do saldo** (descontado o IPCA) e **impulso de crédito** (variação das concessões em % do PIB). | V | P |
| C2 | **Mapa de calor por modalidade**: taxa, inadimplência e crescimento do saldo, lado a lado. | V | M |
| C3 | Atrasos de 15 a 90 dias como **indicador antecedente** da inadimplência (já há a série; destacar a relação). | V | P |
| C4 | Mercado de capitais como fonte de crédito: emissões de debêntures, CRI, CRA (dados da CVM/ANBIMA). | F | G |

### 4.7 Câmbio (hoje: só dólar e euro PTAX)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| X1 | **Taxa de câmbio real efetiva** (Banco Central) com média histórica: mostra se o real está caro ou barato. | D | P |
| X2 | **Real contra moedas de emergentes e contra o dólar global** (base 100): separa o que é Brasil do que é dólar. O índice amplo do dólar já está em Mundo. | D | M |
| X3 | **Fluxo cambial** (comercial e financeiro, semanal) e **posição de câmbio dos bancos**. | D | M |
| X4 | **Termos de troca** e **índice de commodities do Banco Central (IC-Br)**, total e por grupo, contra o câmbio. | D | P |
| X5 | **Volatilidade do câmbio** (janela de 21 dias) e diferencial de juros Brasil × EUA (as duas pontas já existem no site). | V | P |

### 4.8 Setor externo (já amplo)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| T1 | **Exportações e importações por volume e preço** (o peso do Comex Stat já é coletado): separar efeito preço de efeito quantidade. | V | M |
| T2 | **Reservas contra a dívida externa de curto prazo** e em meses de importação; posição de investimento internacional. | D | M |
| T3 | Importações por categoria (bens de capital, intermediários, consumo) como termômetro da atividade. | D | M |

---

## 5. Juros › Brasil

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| J1 | **Séries no tempo dos pontos da curva**: inclinação (10 anos − 2 anos, 5 − 1), juro real de 5 e 10 anos, inflação implícita de 2, 5 e 10 anos. Hoje a curva aparece por data; a evolução do spread não. | V | M |
| J2 | **Brasil × EUA**: diferença entre o juro de 10 anos daqui e o Treasury, nominal e real. | V | P |
| J3 | **Tabela de variação**: cada vértice hoje × 1 dia × 1 semana × 1 mês × início do ano, em pontos-base, com cor. | V | P |
| J4 | **Retorno dos títulos do Tesouro Direto** em janelas (mês, ano, 12 meses) e a **marcação a mercado**: quanto o preço muda se a taxa mexer 1 ponto. | V | M |
| J5 | Selic precificada por reunião (igual a M2). | V | M |

---

## 6. Economia › Mundo

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| W1 | **Painel de mercados global**: tabela com retorno no dia, mês, ano e 12 meses de bolsas, juros, moedas e commodities. Hoje "Mercados" mostra só S&P 500, Nasdaq e VIX em gráfico. | D/F | M |
| W2 | **EUA, atividade de alta frequência** (FRED): pedidos de seguro-desemprego, vagas abertas (JOLTS), salário por hora, construção de casas, estimativa do PIB em tempo real do Fed de Atlanta, índice de condições financeiras do Fed de Chicago, balanço do Fed. | D | M |
| W3 | **Probabilidade de recessão** pela curva de juros (Fed de Nova York) e inversão 10 anos − 3 meses com faixas de recessão. | D | P |
| W4 | **Commodities**: hoje preço mensal (Banco Mundial). Acrescentar índice agregado, base 100 comparando grupos, e a relação com os termos de troca do Brasil. Preço diário só existe para petróleo. | V/D | M |
| W5 | **China**: algumas séries estão interrompidas (desemprego urbano, produção industrial e varejo). Avaliar fontes alternativas (crédito, imóveis, PMI oficial) ou reduzir a aba ao que tem dado vivo. | F | M |
| W6 | **Global (FMI)**: trocar o gráfico de linhas de 20 países por ranking em barras do ano e por comparação Brasil × pares (G6). | V | P |
| W7 | Bolsas fora dos EUA (Europa, Japão, emergentes): índices oficiais costumam ser pagos; a alternativa é ETF pela Yahoo, sinalizada como não oficial. | F | M |

---

## 7. Empresas

### 7.1 Visão do mercado (não existe hoje)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| V1 | **Valuation agregado da bolsa brasileira**, como já é feito para o S&P 500: P/L, EV/EBITDA, P/VP, DY, ROE, margem e dívida líquida/EBITDA da soma das empresas acompanhadas, com histórico. | V/D | G |
| V2 | **Prêmio de risco**: lucro/preço da bolsa menos o juro real da NTN-B longa, no tempo. Mesma lógica do spread DY − NTN-B dos FIIs. | V | M |
| V3 | **Medianas por setor**: P/L, EV/EBITDA, ROE, margem, alavancagem, crescimento; e o **comparativo por setor** igual ao dos FIIs (empresa × média × mediana, com ▲▼). | V | M |
| V4 | **Ibovespa, IFIX e índices setoriais da B3**, com composição oficial da carteira; retorno comparado com CDI, dólar, IPCA+ e S&P 500 (base 100). | D | M |
| V5 | **Mapa de calor da bolsa** (retângulos por valor de mercado, cor pela variação no dia, mês ou ano), agrupado por setor. | V | M |
| V6 | **Fluxo de investidores na B3** (estrangeiro, institucional, pessoa física). É o lembrete 6. | F | M |
| V7 | **Temporada de resultados**: quantas empresas já divulgaram, crescimento agregado de receita e lucro, quem surpreendeu contra o próprio histórico. | V | M |

### 7.2 Tabela de empresas (planilhão)

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| P1 | **Ordenar por coluna** (como no planilhão de FIIs e no S&P 500) e **filtros numéricos** (ex.: ROE > 15%, dívida líquida/EBITDA < 2, P/L < 10). | V | P |
| P2 | **Mais colunas**: EV/EBITDA, P/VP, FCF yield, ROIC, crescimento de receita e lucro (12 meses e 5 anos), margem EBITDA, liquidez diária (o arquivo oficial da B3 já é baixado para os FIIs). | V/D | M |
| P3 | **Variação da cotação** no dia, mês, ano e 12 meses. | V | P |
| P4 | **Pontuação de qualidade e de preço** (ranking combinado) e a ideia já guardada de **ROIC × custo de capital**. | V | M |
| P5 | **Dispersão**: ROIC × EV/EBITDA, crescimento × P/L, com o setor em cores. | V | M |

### 7.3 Página de cada empresa

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| R1 | **Múltiplos no tempo com bandas**: P/L, EV/EBITDA, P/VP e DY históricos, com média e ±1 desvio-padrão. Exige cuidado com desdobramentos e variação do número de ações. | V/D | G |
| R2 | **Por ação**: lucro, valor patrimonial, fluxo de caixa livre e dividendos por ação, e a evolução do **número de ações** (diluição ou recompra). | D | M |
| R3 | **Decomposição do ROE** (margem × giro do ativo × alavancagem) em barras empilhadas ou tabela. | V | P |
| R4 | **Ponte (cascata)**: da receita ao lucro no período, e da dívida líquida de um ano para o outro (geração de caixa, capex, dividendos, juros). | V | M |
| R5 | **Qualidade do lucro**: conversão de caixa (FCO/EBITDA), FCF/lucro, capex/depreciação, payout e alíquota efetiva. Os números já existem na tabela; faltam os gráficos. | V | P |
| R6 | **Retorno total** (preço + proventos) contra Ibovespa e CDI, em janelas. | V/D | M |
| R7 | **Pares**: a empresa contra a mediana do setor em margem, ROIC, alavancagem e múltiplos. | V | M |
| R8 | **Cartões-resumo no topo de cada subseção de Indicadores** e opção de 2 gráficos por linha em tela larga: com um gráfico por linha, a rolagem ficou longa. | V | P |
| R9 | **Calendário próprio**: próxima divulgação e proventos anunciados na página da empresa (hoje só na lista geral). | V | P |
| R10 | **Cronograma de vencimento da dívida** e custo médio: só existem em nota explicativa (PDF), não nas contas padronizadas. Dependeria de leitura por IA. | F | G |

### 7.4 Bancos

Já há dois lembretes (juros por banco e métricas; seções da DRE). Acrescento: **Basileia, inadimplência, cobertura, custo de crédito, margem financeira e eficiência** em gráficos comparando os bancos, e **P/VP × ROE** em dispersão.

### 7.5 Operacional

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| O1 | Variação em 12 meses e **visão sazonal** (G3) em todos os indicadores. | V | P |
| O2 | Na página da empresa, **o indicador operacional ao lado da receita** (ex.: produção de petróleo × receita da Petrobras; passageiros × receita da Azul). | V | M |
| O3 | Novos setores do plano já existente: IBGE por segmento, planilhas de RI (lembrete 7). | — | — |

---

## 8. Fundos imobiliários

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| FI1 | **Spread DY − NTN-B no tempo** (hoje só o valor atual) e P/VP mediano histórico do universo. | V | M |
| FI2 | **Valor de mercado por m²** (valor de mercado + dívidas ÷ área): compara fundos do mesmo segmento. A área já vem da CVM. | V | P |
| FI3 | **Alavancagem** (obrigações por aquisição e securitização ÷ ativo) como coluna do planilhão. | V | P |
| FI4 | **Dispersão P/VP × DY** por segmento e **retorno total** contra o IFIX. | V/D | M |
| FI5 | Concentração: maior imóvel e maior setor de locatário como colunas. | V | P |

---

## 9. Agenda e notícias

| # | Sugestão | Tipo | Esforço |
|---|---|---|---|
| N1 | Na agenda, mostrar **o último valor e o anterior** de cada indicador e o **link para o gráfico** correspondente. | V | M |
| N2 | **Visão de semana** (calendário) e marca de **alto impacto** (Copom, Fed, IPCA, payroll, PIB). | V | P |
| N3 | Depois da divulgação, a linha da agenda vira **"saiu: X (anterior: Y)"**. Consenso de mercado não é gratuito; só há o Focus para alguns. | V | M |

---

## 10. Disposição das seções

1. **Economia › Brasil** em duas camadas: **Conjuntura** (painel-síntese, S1) e as abas de detalhe na ordem Atividade → Emprego e renda → Inflação → Expectativas → Monetária → Crédito → Fiscal → Câmbio e setor externo.
2. **Mercados** como seção própria, juntando o que hoje está espalhado: bolsa do Brasil e do mundo, juros, moedas, commodities, com a tabela de retornos (W1) na abertura.
3. **Empresas › Brasil** com uma aba **Visão do mercado** (V1 a V7) antes da tabela.
4. Aba **Política monetária** só com política monetária (M4).
5. Em cada aba, a ordem **cartões → gráfico-síntese → detalhes**, com os detalhes recolhíveis.

---

## 11. Ordem sugerida

**Primeira onda — muito ganho, pouco risco (dados já existentes ou do Banco Central)**

1. G1, G2, G4, G5: ferramentas de gráfico (transformar série, média e bandas, meta e faixas, último valor).
2. A1, A2: indústria, varejo, serviços, emprego e renda.
3. I1, I2, I3: abertura do IPCA, difusão e meta.
4. E1, E2: mais indicadores do Focus e tabela de revisões.
5. P1, P2, P3: tabela de empresas ordenável, com mais múltiplos e filtros.
6. M1, J1, J3: juro real esperado, inclinações no tempo e tabela de variação da curva.

**Segunda onda — novas leituras**

7. S1: painel de conjuntura.
8. V1, V2, V3: valuation da bolsa, prêmio de risco e medianas por setor.
9. X1 a X4: câmbio real, emergentes, fluxo cambial, termos de troca.
10. R2, R3, R5: por ação, decomposição do ROE, qualidade do lucro.
11. W1, W2: painel de mercados global e alta frequência dos EUA.

**Terceira onda — mais trabalho ou fonte nova**

12. R1: múltiplos históricos com bandas.
13. G3, G9: visão sazonal e mapas de calor.
14. V4 a V7: índices da B3, mapa de calor da bolsa, fluxo de investidores, temporada de resultados.
15. F1 a F4, C4, W5, R10: itens que dependem de pesquisa de fonte.
