# Plano — Dados operacionais das empresas e central setorial

**Status:** guardado para depois. Começa só **depois de finalizada a plataforma inicial**.
**Origem:** conversa de 2026-10-17 (refinada em 2026-10-21).
**Regra:** nada aqui é implementado sem pedido explícito do usuário.

O objetivo é juntar num lugar só os dados que explicam o resultado das empresas acompanhadas, para melhorar a decisão de investimento:

- **Operacional de cada empresa:** volume vendido, produção, SSS (vendas nas mesmas lojas), SSR (aluguel nas mesmas lojas), lojas, ocupação etc.
- **Indicadores de cada setor (*drivers*):** petróleo, energia, minério, varejo e os demais.
- **Leitura dos releases por IA.**

---

## Decisões já tomadas pelo usuário

| Tema | Decisão |
|---|---|
| Escopo dos dados operacionais | **Só as empresas que o usuário acompanha ou de que é acionista.** O download de demonstrações continua para todas as 251. |
| Fonte principal do operacional | **Planilha de resultados do site de RI, enviada pelo usuário.** Claude organiza, padroniza e publica. Não haverá leitura automática dos sites de RI. |
| Onde aparece | Nova aba **"Operacional"** no Excel da central de download e **gráficos** na página da empresa |
| Visões dos gráficos | **Trimestral, semestral e anual** |
| Commodities pagas | Não substituir terminal pago; construir **proxies** com fontes gratuitas |
| Prioridade máxima | **Releases e teleconferências resumidos por IA** ("sensacional, deverá ser implementado") |
| Bom de ter | KPIs mensais das agências; China, clima, Google Trends, balança semanal |
| Passo mais adiante | Negociação de administradores (CVM VLMO), carteira dos fundos (CVM CDA), aluguel de ações e fluxo estrangeiro (B3) |
| Passo futuro | Calendário regulatório (reajustes ANEEL/ARSESP, leilões, CADE) |

---

## Regras que valem para todas as fases

Seguem o padrão que a plataforma já usa:

- **Custo zero.** As coletas rodam no workflow `rv-mapp.yml`. Fonte com chave usa uma chave gratuita guardada em *secret* do GitHub, sempre com `sem_segredos` e `limpar_segredos` (ver incidente BLS de 2026-10-20).
- **Fonte que falha mantém a versão anterior**, registrada em `falhas`, como em `offshore.py` e `setor_externo.py`.
- **Antes de cada fonte nova**, o agente `pesquisador-fontes` testa acesso, frequência, defasagem, histórico e licença. A lista de fontes deste plano foi feita de memória e não foi verificada.
- **Depois de cada entrega:**
  - `validador-dados` confere os números contra a fonte;
  - `revisor-visual` revisa as telas novas;
  - `monitor.py` passa a vigiar se a série nova está atrasada.
- **Versões do dado (*vintages*):** guardar a data de coleta e a fonte e nunca sobrescrever o histórico. Empresas e agências revisam números.
- **Formato longo** em todas as tabelas operacionais e setoriais:

  | periodo | kpi | valor | unidade | tipo | fonte | coletado_em |
  |---|---|---|---|---|---|---|
  | 2T26 | producao | 98,4 | mil boe/d | taxa_diaria | Planilha RI | 2026-08-05 |
  | 2026-07 | producao | 101,2 | mil boe/d | taxa_diaria | ANP | 2026-09-02 |

  Os valores acima são só para ilustrar o formato.

### Regras de agregação (coluna `tipo`)

| tipo | Exemplo | Trimestre → semestre/ano |
|---|---|---|
| `fluxo` | Volume vendido, receita por segmento | Soma |
| `estoque` | Nº de lojas, clientes, frota, beneficiários | Valor do fim do período |
| `taxa_diaria` | Produção em mil boe/d | Média ponderada pelos dias |
| `razao` | Ocupação, SSS, SSR, margem | Recalcular a partir do numerador e do denominador; **nunca somar nem tirar média simples de %** |

Quando o numerador e o denominador de uma `razao` não vierem na planilha, a visão semestral/anual usa o número que a empresa reportar. Se ela não reportar, o período fica vazio, em vez de mostrar um número inventado.

---

## Fase 0 — Pré-requisitos

1. Plataforma inicial finalizada (ver `lembretes-futuros-plataforma` e as pendências Offshore e fiscais).
2. O usuário passa a **lista das empresas acompanhadas**, com os tickers.
3. O usuário envia a **primeira planilha de RI** de cada empresa do piloto. Sugestão: 5 a 10 empresas de setores diferentes.

## Fase 1 — Dados operacionais das empresas acompanhadas (planilha de RI)

**Entrada:**
- Planilhas: `conteudo/operacional/{TICKER}/`, um arquivo por trimestre, com o nome original do RI.
- Mapeamento: `conteudo/operacional/{TICKER}/mapa.yml`, feito **uma vez por empresa** com a ajuda da IA. Diz qual aba e linha corresponde a qual KPI, com unidade, `tipo` e numerador/denominador das razões.
- Dicionário de KPIs por setor: `config/kpis_setor.yml`, com nomes padronizados para comparar empresas do mesmo setor. Por exemplo, todo varejo usa `sss`, `lojas_fim_periodo` e `area_venda_m2`.

**Processamento:** novo módulo `pipeline/operacional.py`.
1. Lê a planilha mais recente com o `mapa.yml`. É leitura determinística, sem IA.
2. Gera a tabela em formato longo e junta com o histórico, guardando as versões em `data/pipeline/operacional/{id}.parquet`.
3. Faz as conferências:
   - soma dos trimestres = ano reportado (KPIs `fluxo`);
   - variação absurda contra o trimestre anterior gera alerta;
   - KPI que sumiu da planilha indica mudança de layout e avisa o usuário.
4. Publica `site/dados/operacional/{id}.json`.

**Saídas:**
- **Excel:** aba "Operacional" no arquivo da empresa, gerado por `gerar_excel` em `pipeline/gerar_empresas.py`. Só entra nas empresas acompanhadas.
- **Site:** bloco de gráficos operacionais na página da empresa, com seletor Trimestral / Semestral / Anual, agregando pelo `tipo`.

**Rotina trimestral:** o usuário manda a planilha nova. Claude roda o módulo; se o layout mudou, ajusta o `mapa.yml`; depois confere e publica.

## Fase 2 — KPIs mensais das agências, por empresa (prévia do trimestre)

Só para as empresas acompanhadas que tiverem fonte. O módulo novo é `pipeline/operacional_agencias.py`, e o código de cada empresa em cada agência (CNPJ, código de campo, código da companhia aérea etc.) fica em `config/agencias_empresas.yml`.

| Agência | KPI | Empresas |
|---|---|---|
| ANP: produção por campo e operador | Petróleo e gás (boe/d) | PETR, PRIO, BRAV, RECV |
| ANP: vendas de distribuidoras | Volume de diesel, gasolina e etanol | VBBR, UGPA, Raízen |
| ANAC | Passageiros, RPK, ASK, ocupação | AZUL, GOLL |
| Anatel | Acessos por operadora | VIVT, TIMS |
| ANEEL (SAMP) | Mercado faturado por distribuidora | EQTL, CPFE, NEOE, CMIG, ENGI |
| ONS: geração por usina | MWh, *curtailment* | AURE, EGIE, ELET, CPFE |
| ANTT | Produção ferroviária (TKU), tráfego por praça | RAIL, MOTV, ECOR |
| ANTAQ | Movimentação por terminal | STBP |
| SUSEP (SES) | Prêmios e sinistros | BBSE, CXSE, PSSA, IRBR |
| ANS | Beneficiários e sinistralidade | HAPV, ODPV |
| ANM (CFEM) | Royalties por substância; por titular a verificar | VALE, CMIN, CBAV |

Os dados entram na mesma tabela da Fase 1, com `fonte` = agência. O gráfico mostra a série mensal e o **trimestre em andamento contra o mesmo período do ano anterior**, que funciona como prévia antes do balanço.

## Fase 3 — Central setorial (*drivers* e proxies)

Nova seção do site, **Setores**, com uma página por setor. Cada página mostra os *drivers*, com gráfico, variação e comparação histórica, e as empresas ligadas a cada um. O mapa de *drivers* por empresa fica em `config/drivers.yml`: empresa → 3 a 5 *drivers* → fonte.

**Piloto: petróleo.** Fontes: EIA API v2, com chave gratuita (Brent/WTI, estoques semanais dos EUA, STEO); FRED, já em uso; ANP produção total; Baker Hughes rig count.
Depois, nesta ordem:

| Setor | Fontes (🟢 API / 🟡 arquivo) |
|---|---|
| Energia elétrica | ONS 🟢 (carga, reservatórios, ENA, geração), CCEE 🟢 (PLD), ANEEL 🟢 |
| Mineração e aço | Comex Stat 🟢 (**já em uso em `setor_externo.py`, reaproveitar**), FRED/FMI 🟢 (minério mensal), China NBS, worldsteel 🔴 |
| Agro, açúcar e carnes | USDA PSD/NASS 🟢, CONAB 🟡, CEPEA 🟡 (licença), UNICA 🔴 |
| Varejo, farmácias e shoppings | IBGE PMC 🟢 por segmento, Abrafarma, Abrasce, Abras, CMED (reajuste de remédios) |
| Imobiliário | FipeZap 🟡, Abrainc, Secovi, crédito imobiliário (BC) |
| Bancos e seguros | BC Olinda 🟢 (IF.data, juros por banco; ver lembrete das IFs), SUSEP 🟡, ANS 🟡 |
| Telecom, transporte | Anatel, ANAC, ANTT, ANTAQ 🟡 |
| Saneamento | ANA SAR 🟢 (Cantareira) |

**Proxies de commodities pagas:**
- **Preço implícito:** Comex Stat, valor exportado ÷ volume, mensal, para minério, celulose, carnes e petróleo.
- **Preço mensal:** FMI/FRED.
- **Demanda da China por minério:** importações chinesas de minério.
- **Volume minerado:** CFEM da ANM.

Ficam de fora, porque são pagos: minério diário, celulose (FOEX), frete (Baltic), LME, OPEP e IEA.

**Extras desta fase:** alerta quando um *driver* foge mais de 2σ da média histórica e um resumo setorial semanal por IA.

## Fase 4 — Releases e teleconferências por IA (prioridade do usuário)

Segue o mesmo padrão de `pipeline/resumos.py`: o texto é escrito sob demanda, fica versionado em Markdown e é convertido para o site.

1. Índice **IPE da CVM** (dados abertos), filtrado pelas empresas acompanhadas e pelas categorias: release de resultados, prévia operacional, apresentação e fato relevante.
2. Baixar o PDF e extrair o texto localmente. Isso é mais barato que mandar o PDF inteiro para a IA.
3. Gerar o resumo do trimestre em `conteudo/releases/{TICKER}/{trimestre}.md`:
   - destaques;
   - KPIs citados, que complementam a Fase 1;
   - *guidance*;
   - **mudança de tom e de *guidance* contra o trimestre anterior**.
4. Publicar na página da empresa (`site/dados/releases/{id}.json`).

**Custo:** zero se rodar aqui pelo Claude Code, na assinatura, uma vez por trimestre. Pela API, as estimativas de out/2026 dão ~US$ 0,03 a 0,10 por documento (Sonnet ou Opus, em lote), irrisório para poucas empresas.

## Fase 5 — Mundo e dados alternativos

- China NBS: aço, setor imobiliário, importação de minério
- NOAA ENSO (El Niño/La Niña) e INMET: clima, safra, hidrologia
- Balança comercial semanal do MDIC: prévia da Comex Stat
- Google Trends, só com acesso não oficial: demanda por marcas e serviços

## Fase 6 — Posicionamento e fluxo

Este item se sobrepõe ao item 7 dos lembretes, sobre dados da B3.
- CVM **VLMO**: compras e vendas de administradores
- CVM **CDA**: carteira dos fundos
- B3: aluguel de ações (BTC) e fluxo do investidor estrangeiro

## Fase 7 — Calendário regulatório

Reajustes e revisões tarifárias (ANEEL, ARSESP), leilões de energia e de concessões, decisões do CADE. Integrar à agenda que já existe (`agenda.py`, `eventos.py`).

---

## Checklist ao retomar

1. Confirmar que a plataforma inicial está finalizada.
2. Pedir ao usuário a lista de empresas acompanhadas e as planilhas de RI do piloto.
3. Ler o **prompt guardado** abaixo, que tem prioridade sobre este plano se houver conflito.
4. Começar pela Fase 1, com o piloto de 5 a 10 empresas.
5. Para cada fonte nova das fases 2 e 3, rodar o `pesquisador-fontes` antes de escrever código.

---

## Prompt guardado pelo usuário

_(nenhum por enquanto. O prompt que o usuário enviou em 2026-10-21 é de outro projeto — o site independente só com Empresas — e está guardado em `docs/replicar-site-empresas.md`, Caminho B.)_
