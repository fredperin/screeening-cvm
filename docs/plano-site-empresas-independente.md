# Plano — Site independente só com Empresas (Brasil + Mundo)

**Status:** guardado para realizar em algum momento futuro. Não executar sem pedido do usuário.
**Data:** 2026-10-21.
**Prompt para colar no outro chat:** `docs/replicar-site-empresas.md`, Caminho B.
**Onde roda:** em um **repositório novo**, com o Claude Code aberto numa pasta ligada a ele, e não aqui. Este plano serve de roteiro e checklist para aquele chat.

O mapeamento abaixo foi feito lendo o código deste repositório em 2026-10-21. Se a plataforma mudar até lá, refazer a Etapa 0.

---

## Decisão: Caminho B

**Decisão do usuário (2026-10-21): só o Caminho B, a cópia independente com pipeline próprio.** O Caminho A (espelho) foi descartado.

## Visão geral

| | |
|---|---|
| Resultado | Site estático novo no GitHub Pages, com **Brasil → Empresas** (empresas e bancos) e **Mundo → Empresas** (S&P 500), com pipeline próprio |
| Custo | Zero: GitHub Actions + Pages |
| Chave | Só o secret `SEC_USER_AGENT`, cadastrado pelo usuário no repositório novo |
| Primeira carga | 1 a 2 h: base da CVM desde 2010 + ~500 empresas da SEC |
| Esforço estimado | 2 a 4 sessões de trabalho; o grosso é enxugar o `app.js` |
| Dependência do site original | Nenhuma. O código é copiado uma vez e os dois sites evoluem separados |

---

## Mapa do que copiar

Levantado das importações reais do código.

### Python: Brasil
| Arquivo | Linhas | Depende de | Observação |
|---|---|---|---|
| `pipeline/__init__.py` | 40 | — | Contém `sem_segredos`, `DIR_DADOS_SITE`, `DIR_INTERMEDIARIO` e `RAIZ` |
| `config/config.py`, `empresas_selecionadas.csv`, `bancos_listados.csv` | — | — | Universo de empresas e bancos |
| `src/cvm_itr.py` | 835 | config | Leitura dos ITR/DFP e dados cadastrais |
| `src/screening.py` | 378 | config, cvm_itr | `universo_selecionado` e `universo_perfis` |
| `src/exportar.py` | 338 | config | Excel padrão das empresas |
| `src/indicadores.py`, `src/padrao_visual.py` | 371 / 221 | — | |
| `src/mapa_contas.py` | 64 | config, cvm_itr | Listado no prompt; confirmar se algo ainda o usa. Se nada usar, deixar de fora |
| `pipeline/cvm_lote.py` | 143 | config | ZIPs da CVM em Parquet |
| `pipeline/series_empresa.py` | 368 | src.indicadores | **Também é usado pelo Mundo** |
| `pipeline/gerar_empresas.py` | 202 | cvm_lote, series_empresa, src | |
| `pipeline/mercado.py` | 287 | src.screening | Gera `mercado.json`, que o `noticias.py` lê |
| `pipeline/noticias.py` | 269 | lê `mercado.json` | **Enxugar:** manter só o que gera `noticias_empresas.json` |
| `pipeline/eventos.py`, `ficha.py` | 74 / 191 | src.screening | |
| `pipeline/fre_textos.py`, `resumos.py` | 152 / 83 | — | `resumos.py` lê `conteudo/resumos/`. Copiar só o `LEIAME.txt`, não há resumos escritos ainda |
| `pipeline/calendario_resultados.py` | 89 | lê `empresas.json` e os ZIPs da CVM | Roda depois do índice |
| `pipeline/bancos.py` | 569 | **lê `macro.json`** | Ver a adaptação A1 |
| `pipeline/validar.py` | 131 | lê `empresas.json` e `mercado.json` | |
| `pipeline/limpar_segredos.py` | 33 | sem_segredos | |
| `pipeline/requirements.txt` | — | — | Copiar e enxugar |

### Python: Mundo
| Arquivo | Linhas | Depende de | Observação |
|---|---|---|---|
| `pipeline/empresas_mundo.py` | 675 | series_empresa, sem_segredos | Usa `SEC_USER_AGENT` |

### Manutenção
| Arquivo | Adaptação |
|---|---|
| `pipeline/monitor.py` (445) | Hoje confere agenda, crédito, macro, mundo, offshore, tesouro, setor externo e outros. **Manter só** as checagens de empresas, mercado, notícias de empresas, eventos, bancos e empresas do Mundo. Continua gerando `saude.json`, `observacoes.json` e `alerta.md` |
| `pipeline/teste_telas.py` (176) | Manter só as rotas `#/on/empresas`, `#/on/empresa/…`, `#/on/banco/…`, `#/off/empresas`, `#/off/empresa/…` e `#/status` |
| `pipeline/rodar.py` (171) | Refazer só com as etapas novas (ver Etapa 4). Manter `versao_do_codigo`, `entregas_cvm`, `tickers_com_entrega_nova`, `semanal_pendente` e o `status.json` |
| `.claude/agents/`: auditor-atualizacao, validador-dados, revisor-visual, mantenedor | Trocar nome do site, URL, lista de fontes e de abas |
| `.claude/skills/checkup/` | Mesma adaptação; a rotina na nuvem, se quiser, é criada à parte |
| `.claude/launch.json` | Para a pré-visualização local |

### Site
| Arquivo | Linhas | Adaptação |
|---|---|---|
| `site/index.html` | 39 | Topo só com "Brasil" e "Mundo" |
| `site/assets/app.js` | 2.742 | **Maior trabalho** (ver Etapa 3) |
| `site/assets/explicativos.js` | 888 | Manter só os ⓘ das telas de empresas e bancos |
| `site/assets/estilo.css`, `logo.svg` | 192 | Copiar; trocar o logo/nome se quiser |

### Workflow
`.github/workflows/rv-mapp.yml` serve de base: agendamento às 06h30, cache de `data/raw`, `data/pipeline`, `site/dados` e `site/downloads`, teste das telas, monitor, validação, ocultar chaves, alerta por issue e publicação.

**Não copiar:**
- `tesouro-intradia.yml`;
- os secrets `FRED_API_KEY` e `BLS_API_KEY`;
- as etapas macro, crédito, setor externo, agenda, tesouro, curva DI, offshore, mundo, eleições e planilhas.

### Não copiar (regra do prompt)
- Dados gerados (`site/dados`, `site/downloads`, `data/`)
- Chaves, e-mails e relatórios (`relatorios/`)
- O app Streamlit antigo (`app.py`, `pages/`, `main.py`, `rodar_screening.py`, `gerar_mapa.py`, `src/exportar_screening.py`)

---

## Adaptações necessárias

- **A1. PIB para a classificação dos bancos (Res. 4.553).** `bancos.py:379` lê `macro.json["series"]["pib_nominal"]`, que é a série SGS **1207** ("PIB anual em R$ correntes", configurada em `macro.py:36`). No site novo, uma função pequena dentro de `bancos.py` baixa a SGS 1207 direto da API do BC e guarda o último valor em `data/pipeline/pib_nominal.json`. Se a API falhar, usa o último valor guardado. Conferir que a unidade continua igual (R$).
- **A2. Notícias.** `app.js` tenta `noticias_empresas.json` e, se falhar, cai em `noticias.json`. No site novo, garantir que o `noticias_empresas.json` sempre exista e trocar o fallback por uma mensagem "sem notícias".
- **A3. Página `#/status`.** Lê `status.json`, `saude.json`, `agenda.json` e `observacoes.json` (`app.js:2692`). Manter a página sem o bloco da agenda.
- **A4. Tela inicial Brasil (`#/on`).** Hoje reúne macro, tesouro, curva DI, agenda e notícias (`app.js:334`). No site novo, "Brasil" abre direto em `#/on/empresas` e "Mundo" em `#/off/empresas`. As duas rotas já existem: o roteador monta `#/{lado}/{secao}` a partir da lista `SECOES` (`app.js:269`), e o Mundo cai em `secao === "empresas"` (`app.js:2060`). Basta trocar a rota padrão de cada lado e enxugar `SECOES`.
- **A5. Busca por ticker.** Garantir que só procure em `empresas.json`, `bancos.json` e `mundo_empresas.json`.
- **A6. `.gitattributes`** com `.claude/** text eol=lf`. Com CRLF o cabeçalho dos agentes deixa de ser lido, como no commit `fc430ab`.

---

## Etapas de execução (no repositório novo)

Cada etapa é testada localmente e o resultado é relatado ao usuário antes de seguir.

**Etapa 0 — Leitura e plano (sem escrever nada)**
- Clonar `fredperin/screeening-cvm` numa pasta temporária.
- Refazer este mapa contra o código atual.
- Apresentar o plano, o que fica de fora e os riscos, e **esperar o ok**.

**Etapa 1 — Esqueleto**
- Estrutura de pastas, `.gitignore` (`data/`, `site/dados/`, `site/downloads/`, `__pycache__`), `.gitattributes`, `requirements.txt` enxuto.
- Copiar `config/`, `src/` e `pipeline/__init__.py`.
- **Teste:** `py -c "import src.cvm_itr, src.screening, pipeline"` sem erro.

**Etapa 2 — Pipeline Brasil**
- Copiar e ajustar os módulos do Brasil, com a A1 e o enxugamento das notícias.
- **Teste:** rodar com 3 a 5 tickers (`gerar_empresas` com filtro) e conferir `empresas.json`, `empresas/{id}.json`, o Excel, `bancos.json` e `calendario_resultados.json`.

**Etapa 3 — Site (enxugar o `app.js`)**
1. Partir das funções que **ficam**, conferidas em 2026-10-21, e de tudo de que elas dependem:

   | Tela | Função (linha no `app.js`) |
   |---|---|
   | Brasil → lista com as 4 abas | `paginaEmpresas` (389), `abaFinanceiras` (2332) |
   | Página da empresa | `paginaEmpresa` (499) e as abas Negócio, Eventos e notícias, Cotação, Resultados, Gráficos e Dividendos |
   | Página do banco | `paginaBanco` (2415) |
   | Mundo → tabelão S&P 500 | `paginaEmpresasMundo` (1852) |
   | Página da empresa do Mundo | `paginaEmpresaMundo` (1889) |
   | Status | a página de `#/status` (A3). Fica, porque o site novo tem monitor próprio |

   Marcar como removíveis as que só servem macro, juros, offshore, mundo (China/Global/Mercados), notícias gerais, agenda, tesouro e eleições.
2. Remover essas funções e as rotas `#/on/macro`, `#/on/noticias`, `#/off/macro` e `#/off/noticias`, mais as telas Consolidado, Início e Downloads.
3. Topo só com Brasil e Mundo (A4), busca (A5) e ⓘ só das telas mantidas.
- **Teste:** prévia local (`launch.json` ou `python -m http.server` na pasta `site/`), com zero erros no console. Roteiro:
  - lista do Brasil, nas 4 abas;
  - **VALE3** em todas as abas;
  - banco **c0080099** (Itaú);
  - lista do Mundo;
  - **AAPL** em todas as abas.

  Os tickers de teste da Etapa 2 precisam incluir VALE3 e o Itaú.

**Etapa 4 — Mundo e orquestração**
- Copiar `empresas_mundo.py`.
- Montar o `rodar.py` na ordem: mercado → noticias → bancos → eventos → ficha → fre_textos → resumos → base da CVM → empresas (incremental) → índice → calendário de resultados → empresas_mundo.
- Manter as regras: refazer uma empresa só quando sair documento novo na CVM/SEC; refazer tudo no fim de semana ou quando o código das empresas mudar.
- **Teste:** `empresas_mundo` com 3 tickers, usando o `SEC_USER_AGENT` só em variável de ambiente local, nunca em arquivo.

**Etapa 5 — Manutenção**
- Monitor, teste das telas e validação enxugados.
- Agentes e checkup adaptados, com LF.
- **Teste:** `py -m pipeline.teste_telas` e `py -m pipeline.monitor` passam com os dados de teste.

**Etapa 6 — Workflow e publicação**
- Workflow novo e `limpar_segredos` antes de publicar.
- **O usuário faz:**
  - cadastrar o secret `SEC_USER_AGENT`;
  - ativar Settings → Pages → Source: GitHub Actions.
- Primeira execução manual, com `tudo` = sim, de 1 a 2 h.
- **Teste:**
  - site publicado abrindo todas as rotas;
  - procurar o e-mail e o user agent nos arquivos publicados, para confirmar que não vazaram;
  - issue de alerta fechada.

**Etapa 7 — Conferência final**
- Rodar os agentes `validador-dados` (amostra Brasil + Mundo) e `revisor-visual`.
- Segunda execução diária, para confirmar que fica incremental e rápida.

---

## Riscos e cuidados

| Risco | Cuidado |
|---|---|
| Vazar o e-mail do `SEC_USER_AGENT` | Só como secret; `sem_segredos` em toda mensagem de erro; `limpar_segredos` antes de publicar; busca pelo valor nos arquivos publicados na Etapa 6 |
| Funções do `app.js` compartilhadas entre telas | Remover rota por rota e testar a cada remoção; nunca apagar um bloco grande de uma vez |
| `monitor.py` acusar falso alarme por arquivo que não existe mais | Tirar as checagens das fontes removidas antes do primeiro workflow |
| Primeira carga estourar o tempo do Actions (120 min) | Se estourar, rodar a carga inicial em duas partes (Brasil e depois Mundo) ou subir o `timeout-minutes` |
| Limites da SEC | Manter o ritmo de requisições do `empresas_mundo.py` original |
| Cache do Actions expirar (7 dias sem uso) | A execução diária mantém o cache vivo; se expirar, a próxima vira carga completa |
| Dois sites divergindo | Correção feita num site não passa para o outro. Anotar no README do novo qual commit do original foi a base |
| Yahoo Finance | Só histórico de cotação, marcado como não oficial, como no original |

---

## Checklist do usuário antes de começar
1. Criar o repositório novo no GitHub.
2. Abrir o Claude Code numa pasta ligada a ele.
3. Colar o prompt do Caminho B (`docs/replicar-site-empresas.md`).
4. Ter à mão o texto do `SEC_USER_AGENT` ("Nome e-mail") para cadastrar como secret quando for pedido. Nunca colar no chat.
