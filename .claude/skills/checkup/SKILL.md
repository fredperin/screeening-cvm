---
name: checkup
description: Check-up completo da plataforma Bloomberg de Pobre (R.V. Mapp) — supervisor que coordena os agentes de manutenção (auditor de atualização, revisor visual, validador de dados e, se preciso, pesquisador de fontes), consolida um relatório único com prioridades e só corrige o que o usuário aprovar (via agente mantenedor). Usar quando o usuário pedir "check-up", "checkup da plataforma", "revise a plataforma toda", ou na rotina agendada a cada 15 dias.
---

# Check-up da plataforma (supervisor)

Você é o **supervisor** da manutenção do site Bloomberg de Pobre (projeto R.V. Mapp; repositório `fredperin/screeening-cvm`,
site `https://fredperin.github.io/screeening-cvm/`). Você coordena os agentes, não faz o trabalho deles, e **não corrige nada
sem aprovação explícita do usuário**.

## Contexto que os agentes não têm
- Site estático (HTML/JS + ECharts) gerado por pipeline Python (`pipeline/`) no GitHub Actions: atualização diária completa
  (`rv-mapp.yml`, ~06h30 de Brasília) e Tesouro + notícias 3x por dia útil (`tesouro-intradia.yml`).
- Seções: Consolidado · Brasil (Início, Notícias e agenda, Macro com 8 abas, Juros, Empresas com 4 abas, Downloads) ·
  Mundo (Macro: Global, Mercados, EUA, Europa, China; Juros; Empresas do S&P 500 via SEC).
- Já existe vigilância automática sem IA: `pipeline/monitor.py` (fontes em dia, faixas, buracos), `pipeline/validar.py`
  (anomalias nas empresas), `pipeline/teste_telas.py` (navegador percorre todas as telas), `pipeline/comparar.py`
  (dados novos x execução anterior: nada some, encurta ou recua; revisões das fontes registradas) e `pipeline/rede.py`
  (cliente único: ritmo por servidor e espera em recusas; contagem em `data/pipeline/consultas.json`). Resultados publicados em
  `dados/observacoes.json`, `dados/saude.json`, `dados/status.json`, `dados/comparacao.json`. O check-up vai **além** disso:
  julgamento, coerência e melhorias.
- Critério de "dado certo" do usuário: **igual ao que a fonte publica** (erro da própria fonte não é nosso). Downloads curtos
  (Banco Central, Yahoo) têm refação completa semanal; Tesouro e Comex só são baixados quando há dado novo.
- Regras do usuário: fontes oficiais e confiáveis (mesmo que defasadas); custo zero de infraestrutura; nunca publicar chaves
  de acesso (FRED_API_KEY, BLS_API_KEY, SEC_USER_AGENT) nem e-mail; não mudar layout sem pedido.

## Passos
1. **Rodar em paralelo** (uma única mensagem com as três chamadas):
   - `auditor-atualizacao`: situação da atualização, fonte por fonte, e falhas das últimas execuções.
   - `revisor-visual`: revisão das telas do site publicado.
   - `validador-dados`: amostra — 2 empresas brasileiras sorteadas, 1 banco, 1 empresa do S&P 500 e 3 séries do Macro
     (IPCA, Selic, uma de crédito ou setor externo) contra a fonte oficial.
2. Se o auditor apontar **fonte quebrada ou que mudou de formato**, acione `pesquisador-fontes` para propor a correção ou
   uma fonte substituta oficial.
3. **Consolidar** num relatório único (remova repetições entre agentes):
   - Veredito em uma linha (saudável / atenção / problemas sérios).
   - Tabela priorizada: nº · área · problema · gravidade (alta/média/baixa) · correção proposta · efeito colateral
     (ex.: "refaz todas as empresas", "muda layout").
   - Seção curta "Melhorias sugeridas" (até 5), separada dos problemas.
   - Custo: quantos agentes rodaram.
4. **Entrega**
   - *Sessão com o usuário presente*: mostre o relatório e pergunte quais itens corrigir. Para cada item aprovado, acione o
     agente `mantenedor` com o diagnóstico; revise o resultado; só então faça commit e push (mensagem em português, sem
     acentos no título, terminando com a linha de coautoria do Claude) e acompanhe a publicação.
   - *Rotina agendada (sem usuário)*: **não corrija nada**. Salve o relatório em `relatorios/checkup-AAAA-MM-DD.md`,
     faça commit e push só desse arquivo, e se o `gh` estiver disponível abra uma issue com o rótulo `rv-mapp-checkup`
     (título "Check-up AAAA-MM-DD — <veredito>", corpo = relatório). O usuário decide depois o que corrigir.

## Segurança
- Nunca copie para o relatório, issue ou arquivo valores de chaves de acesso ou e-mails que apareçam em logs ou arquivos.
- Os agentes de diagnóstico só leem; apenas o `mantenedor` edita, e só itens aprovados.
