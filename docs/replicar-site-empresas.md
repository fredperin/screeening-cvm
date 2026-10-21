# Replicar só as seções de Empresas (Brasil e Mundo) em outro site

> **Decisão do usuário (2026-10-21): será feito apenas o Caminho B (cópia independente).** O Caminho A fica só como registro e não deve ser executado.
> Plano completo: `docs/plano-site-empresas-independente.md`.

Há dois caminhos.

| | A — Site espelho (recomendado) | B — Cópia independente |
|---|---|---|
| Como funciona | Site novo só com as telas de Empresas; **lê os dados já publicados** pelo Bloomberg de Pobre | Site novo com **pipeline próprio** (CVM, B3, SEC) só das empresas |
| Esforço | Baixo (algumas horas) | Alto (dias) |
| Custo | Zero; nada roda no novo site | Zero (GitHub Actions), mas 60–90 min de atualização por dia |
| Chaves | Nenhuma | Precisa do `SEC_USER_AGENT` próprio |
| Dependência | Fica sempre igual ao site principal; se o principal parar, o espelho para | Totalmente independente |

O site principal já permite essa leitura: os arquivos em `https://fredperin.github.io/screeening-cvm/dados/` respondem com
`Access-Control-Allow-Origin: *` (qualquer site pode ler) e cache de 10 minutos.

---

## Caminho A — prompt para o Claude Code (descartado em 2026-10-21; só registro)

Crie uma pasta nova (ou um repositório novo no GitHub, ex.: `empresas-b3-sp500`), abra o Claude Code nela e cole:

```text
Quero criar um site estático novo, só com as seções de EMPRESAS de um site que já existe.
O site existente é o "Bloomberg de Pobre", repositório público https://github.com/fredperin/screeening-cvm,
publicado em https://fredperin.github.io/screeening-cvm/ (HTML/CSS/JS puro + ECharts, sem framework, sem Node).

Objetivo: um site "espelho" que NÃO tem pipeline de dados próprio. Ele usa o mesmo código de tela do site
original, mas lê todos os dados direto do site publicado:
  BASE_DADOS = "https://fredperin.github.io/screeening-cvm/"
(os arquivos de dados respondem com Access-Control-Allow-Origin: *, então a leitura entre sites funciona).

Passos:
1. Baixe do repositório original: site/index.html, site/assets/app.js, site/assets/estilo.css,
   site/assets/explicativos.js e site/assets/logo.svg.
2. No app.js, a função dados(caminho) busca arquivos relativos como "dados/empresas.json". Faça ela buscar
   em BASE_DADOS + caminho. Faça o mesmo com os links de download do Excel ("downloads/...xlsx"), que devem
   apontar para BASE_DADOS + "downloads/...".
3. Mantenha SOMENTE estas rotas e telas (e tudo de que elas dependem):
   - Brasil → Empresas: rota #/on/empresas com as abas Informações, Notícias e fatos relevantes,
     Empresas não financeiras e Instituições financeiras (funções paginaEmpresas, abaFinanceiras);
     página de cada empresa #/on/empresa/TICKER (paginaEmpresa e as abas Negócio, Eventos e notícias,
     Cotação, Resultados, Gráficos, Dividendos); página de cada banco #/on/banco/ID (paginaBanco).
   - Mundo → Empresas: rota #/off/empresas (paginaEmpresasMundo, tabelão do S&P 500) e
     #/off/empresa/TICKER (paginaEmpresaMundo, com Negócio, Documentos (SEC), Cotação, Resultados,
     Gráficos, Dividendos e recompras).
   Remova do menu e do roteador as demais seções (Consolidado, Início, Notícias e agenda, Macro, Juros,
   Downloads, Status) e o código que só elas usam. A navegação do topo vira: "Brasil" e "Mundo", cada um
   abrindo direto na lista de empresas. A busca por ticker no topo deve continuar funcionando.
4. Mantenha os explicativos (botões ⓘ), o download de CSV e a tela cheia dos gráficos.
5. Troque o nome e o título do site para: <NOME DO NOVO SITE>. No rodapé, cite as fontes (CVM, B3, Banco
   Central/IF.data, SEC EDGAR, Yahoo Finance) e que os dados vêm do Bloomberg de Pobre.
6. Teste localmente (python -m http.server na pasta) abrindo: a lista do Brasil, VALE3 em todas as abas,
   o banco c0080099 (Itaú), a lista do Mundo e AAPL em todas as abas. Nenhum erro no console.
7. Publique no GitHub Pages deste repositório (Settings → Pages → Source: GitHub Actions) com um workflow
   simples que só publica a pasta do site (sem pipeline, sem chaves, sem agendamento).

Regras: não copie nenhuma chave, e-mail ou arquivo de dados para o repositório novo; não crie pipeline.
Me mostre o resultado antes de publicar.
```

### O que fazer depois
- No GitHub do repositório novo: **Settings → Pages → Source: GitHub Actions** (uma vez só).
- O espelho atualiza sozinho: toda vez que o site principal atualiza, o espelho passa a mostrar os dados novos
  (no máximo 10 minutos de cache).
- Mudanças de layout feitas no site principal **não** passam sozinhas para o espelho (o código de tela é uma
  cópia). Para trazer, peça: "atualize as telas do espelho com o app.js atual do Bloomberg de Pobre".

---

## Caminho B — cópia independente (só se precisar de autonomia total)

**Status:** prompt completo guardado pelo usuário em 2026-10-21 para realizar futuramente. Não executar sem pedido.
Plano completo mapeado (arquivos, adaptações, etapas e riscos): `docs/plano-site-empresas-independente.md`.

### Antes de colar no outro chat
1. Crie o repositório novo no GitHub e abra o Claude Code numa pasta ligada a ele.
2. Quando o novo chat pedir, cadastre o secret `SEC_USER_AGENT` em **Settings → Secrets → Actions** e ative
   **Settings → Pages → Source: GitHub Actions**.

### Prompt completo para o Claude Code no repositório novo

```text
Quero criar um projeto NOVO e INDEPENDENTE: um site estático, gratuito, só com as seções de EMPRESAS
(Brasil e Mundo) de um projeto que já existe. Responda sempre em português.

## Projeto de origem (só para copiar código — o novo não pode depender dele)
- Repositório público: https://github.com/fredperin/screeening-cvm
  (site "Bloomberg de Pobre", publicado em https://fredperin.github.io/screeening-cvm/)
- Arquitetura: pipeline Python (pastas pipeline/ e src/) roda no GitHub Actions, gera JSON e Excel em
  site/dados e site/downloads, e publica a pasta site/ (HTML/CSS/JS puro + ECharts, sem framework, sem Node)
  no GitHub Pages.

## O que o site novo deve ter
1. Brasil → Empresas (dados oficiais da CVM, B3 e Banco Central):
   - Lista com 4 abas: Informações (calendário de resultados, últimas divulgações, próximos proventos),
     Notícias e fatos relevantes, Empresas não financeiras (tabelão) e Instituições financeiras.
   - Página de cada empresa (#/on/empresa/TICKER): Negócio, Eventos e notícias, Cotação, Resultados
     (DRE simples e balanço com análise vertical), Gráficos, Dividendos; botão de Excel.
   - Página de cada banco (#/on/banco/ID) pelo IF.data do Banco Central: Perfil, Eventos e notícias, Capital,
     DFs, Carteiras; Excel para bancos S1–S3 e listados.
2. Mundo → Empresas (S&P 500 pela SEC EDGAR):
   - Tabelão (#/off/empresas) e página de cada empresa (#/off/empresa/TICKER): Negócio, Documentos (SEC),
     Cotação, Resultados (DRE, balanço e fluxo de caixa como divulgados à SEC, em inglês), Gráficos,
     Dividendos e recompras.
Navegação do topo só com "Brasil" e "Mundo", cada um abrindo direto na lista de empresas; manter a busca por
ticker, os botões ⓘ (explicativos com a fonte no fim), o download de CSV e a tela cheia dos gráficos.

## O que copiar do projeto de origem (e adaptar)
- Brasil: config/empresas_selecionadas.csv, config/bancos_listados.csv, config/config.py, src/ (cvm_itr.py,
  padrao_visual.py, indicadores.py, exportar.py, mapa_contas.py, screening.py), pipeline/__init__.py,
  cvm_lote.py, gerar_empresas.py, series_empresa.py, mercado.py, eventos.py, ficha.py, fre_textos.py,
  resumos.py, calendario_resultados.py, bancos.py, noticias.py (só o necessário para as manchetes ligadas
  às empresas), validar.py, limpar_segredos.py.
- Mundo: pipeline/empresas_mundo.py.
- Manutenção: pipeline/monitor.py (só as checagens dessas fontes), pipeline/teste_telas.py (só as rotas de
  empresas), .claude/agents/ (auditor-atualizacao, validador-dados, revisor-visual, mantenedor) e
  .claude/skills/checkup/, ajustados ao projeto novo.
- Site: site/index.html e site/assets/ (app.js, estilo.css, explicativos.js, logo.svg), removendo tudo o que
  não for Empresas (Consolidado, Início, Notícias e agenda, Macro, Juros, Downloads e o código usado só por
  eles). O macro.json é usado só para o PIB nominal na classificação dos bancos (Res. 4.553): baixe essa
  série direto do Banco Central (SGS 1207) em vez de copiar a etapa de Macro inteira.
- NÃO copie: dados gerados (site/dados, site/downloads, data/), chaves, e-mails nem relatórios.

## Pipeline e publicação
- pipeline/rodar.py só com as etapas acima, na ordem: mercado, noticias, bancos, eventos, ficha,
  fre_textos, resumos, base da CVM, empresas (incremental), índice, calendário de resultados, empresas_mundo.
- Manter as regras do original: refazer empresas só quando a CVM/SEC publicar documento novo; refazer tudo no
  fim de semana ou quando o código que monta as empresas mudar.
- Workflow do GitHub Actions: diário (~06h30 de Brasília), com cache de data/ e site/ entre execuções,
  teste das telas, monitor, etapa "Ocultar chaves de acesso" (pipeline.limpar_segredos) ANTES de publicar,
  e publicação no GitHub Pages. Secret necessário: SEC_USER_AGENT = "Seu Nome seu-email@exemplo.com"
  (a SEC exige identificação; eu cadastro, você nunca escreve o valor em arquivo).
- Arquivos em .claude/ sempre com quebra de linha LF (crie .gitattributes com ".claude/** text eol=lf").

## Regras
- Custo zero (GitHub Actions + Pages); só fontes oficiais ou já usadas no original (CVM, B3, Banco Central,
  SEC; Yahoo Finance só para histórico de cotação, marcado como não oficial).
- Segurança: nenhuma chave ou e-mail em código, log ou arquivo publicado; toda mensagem de erro passa por
  sem_segredos (pipeline/__init__.py).
- Antes de executar, me apresente o plano (o que vai copiar, o que fica de fora e os riscos) e espere meu ok.
  Faça em etapas, testando cada uma localmente, e me avise do resultado de cada etapa.
- A primeira carga baixa a base da CVM desde 2010 e as ~500 empresas da SEC: deve levar 1–2 horas.

Comece clonando o repositório de origem numa pasta temporária, leia o código das partes citadas e me
traga o plano.
```

Pontos de atenção do caminho B: a primeira carga baixa toda a base da CVM desde 2010 e as ~500 empresas da SEC
(1–2 h na primeira vez); o `SEC_USER_AGENT` precisa ser cadastrado como secret no repositório novo; e qualquer
correção feita num site precisa ser repetida no outro.
