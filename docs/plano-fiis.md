# Plano — Fundos imobiliários (FII de tijolo)

Decidido com o usuário em 2026-11-02. Implementar num chat novo, a partir deste documento e do protótipo em `docs/exemplos/`.

> **Andamento (2026-11-02):** etapas 1, 2 e 3 implantadas em `pipeline/fiis.py` e no site (menu Fundos imobiliários: Visão geral e Planilhão;
> página `#/on/fii/{ticker}`). Diferenças em relação ao plano original:
> - **Cotação e liquidez oficiais**: arquivo diário COTAHIST da B3 (um arquivo por pregão, guardado só com os FIIs), no lugar da Yahoo. A Yahoo
>   ficou só para a cotação semanal dos gráficos e para os rendimentos anteriores ao primeiro aviso lido.
> - **Ticker de cada fundo**: pelo ISIN do informe mensal da CVM cruzado com o COTAHIST.
> - **Critério de tijolo**: imóveis físicos (Direitos_Bens_Imoveis) ≥ 50% do ativo + imóvel pronto para renda no trimestral + negócio na B3 no último mês
>   (125 fundos em 02/11/2026).
> - **Verificação automática** por fundo (`checar_fundo`): vacância que parece taxa de ocupação, percentuais acima de 100%, receita dos imóveis somando
>   mais de 100%, salto de patrimônio sem mudança de cotas. O número fica igual ao da fonte, com aviso na página.
> - Gestora: a CVM só traz o administrador; o filtro do planilhão é por administrador.
> - Etapa 4 (resumos dos relatórios gerenciais por IA) **adiada para o fim**, depois da publicação do site (pedido do usuário, 2026-11-02). Por ora a página fica só com os dados.

## Escopo

- **Só FIIs de tijolo**: os que investem em imóveis físicos. Fundos de papel (CRI), fundos de fundos e outros ficam de fora.
- Universo: fundos com cota negociada na bolsa e com imóveis prontos para renda no informe trimestral. Excluir os sem negociação e os encerrados.
- Nova seção no menu lateral: **Fundos imobiliários**, logo abaixo de Empresas.

## Páginas

1. **Visão geral do mercado**
   - Números do mercado de FIIs de tijolo: quantidade de fundos, patrimônio total e cotistas.
   - Medianas por segmento (logística, lajes corporativas, shoppings, renda urbana, híbridos etc.): P/VP, dividend yield de 12 meses e vacância.
   - Spread do dividend yield contra a NTN-B (juro real do Tesouro, que já está no site).
   - **Comparativo por segmento (pedido do usuário):**
     1. escolhe-se o segmento;
     2. aparece a tabela dos fundos desse segmento com P/VP, DY 12m, vacância, inadimplência, patrimônio e liquidez;
     3. uma linha com a média e a mediana do segmento;
     4. cada fundo é destacado acima ou abaixo da média em cada indicador;
     5. clicar abre a página do fundo.
2. **Planilhão de fundos**, igual ao planilhão de ações, com filtros por segmento, gestora e tamanho. Colunas:
   - ticker, nome, segmento, administrador;
   - preço, P/VP, DY 12m, último rendimento;
   - patrimônio líquido, liquidez média diária, cotistas;
   - vacância física e inadimplência.
3. **Página de cada fundo**: cartões no topo (cotação, P/VP, DY 12m, último rendimento, patrimônio e vacância física) e quatro abas, nesta ordem:
   - **Informações**: dados do fundo (nome, ticker, CNPJ, ISIN, administrador, segmento, mandato, gestão, público-alvo, início, cotas, cotistas, taxa de administração, site), composição do ativo e do passivo, gráfico cotação × valor patrimonial da cota, gráfico patrimônio líquido e cotistas.
   - **Documentos**: lista do Fundos.NET com link para cada documento. Filtros: Todos, Fatos relevantes (em negrito), Relatórios gerenciais, Rendimentos, Comunicados, Informes, Ofertas e emissões, Assembleias.
   - **Indicadores**: cartões (DY 12m, DY do mês, P/VP, rentabilidade efetiva do mês, vacância física, inadimplência) e gráficos (rendimentos por cota com DY de 12 meses; P/VP com a linha de 1,0x; vacância e inadimplência trimestrais; rentabilidade mensal informada à CVM).
   - **Carteira**: cartões (nº de imóveis, área total, vacância física, peso dos 5 maiores imóveis na receita), receita por setor dos locatários (tabela com os 15 maiores mais "Outros", e gráfico) e tabela dos imóveis (área, vacância, inadimplência, % da receita).

## Fontes (todas testadas em 2026-11-02)

| Dado | Fonte | Observações |
|---|---|---|
| Cadastro, PL, cotas, valor patrimonial da cota, cotistas, DY e rentabilidade do mês, taxa de administração | CVM — informe mensal de FII: `https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip` (arquivos `geral`, `complemento`, `ativo_passivo`) | CSV `;` latin1; ficar com a última `Versao` de cada `Data_Referencia`; campos do cadastro podem vir vazios no mês mais recente: usar o último preenchido |
| Composição do ativo e do passivo | idem, `ativo_passivo` | |
| Imóveis (área, vacância, inadimplência, % da receita), locatários por setor, contratos | CVM — informe trimestral: `https://dados.cvm.gov.br/dados/FII/DOC/INF_TRIMESTRAL/DADOS/inf_trimestral_fii_{ano}.zip` (`imovel`, `imovel_renda_acabado_inquilino`, `imovel_renda_acabado_contrato`, `imovel_desempenho` etc.) | Filtrar a classe "Imóveis para renda acabados". O arquivo de contratos veio vazio para o HGLG |
| Documentos e fatos relevantes | Fundos.NET (JSON público): `https://fnet.bmfbovespa.com.br/fnet/publico/pesquisarGerenciadorDocumentosDados?d=0&s=0&l=60&o[0][dataEntrega]=desc&cnpjFundo={cnpj só dígitos}` com o cabeçalho `X-Requested-With: XMLHttpRequest` | Link de cada documento: `https://fnet.bmfbovespa.com.br/fnet/publico/exibirDocumento?id={id}`. O HGLG tem 991 documentos |
| Rendimentos oficiais | Fundos.NET: documentos "Aviso aos Cotistas - Estruturado / Rendimentos e Amortizações" (estruturados) | Usar no lugar da Yahoo na versão final |
| Cotação | Yahoo (`{TICKER}.SA`, já usado nas ações; não oficial, sinalizado) | |

Contas conferidas no exemplo: o rendimento de set/26 da Yahoo (R$ 1,17) bate com o DY do mês da CVM × valor patrimonial (0,705% × R$ 165,48 = R$ 1,167).

## Cálculos (sempre indicados como cálculo)

- **P/VP** = preço ÷ valor patrimonial da cota do último informe mensal disponível naquela data.
- **DY 12m** = soma dos rendimentos com data-com nos últimos 12 meses ÷ preço atual.
- **Vacância física do fundo** = soma (área × vacância do imóvel) ÷ área total dos imóveis prontos.
- **Inadimplência do fundo** = média da inadimplência dos imóveis, ponderada pela participação de cada um na receita.

## Regras do projeto que valem aqui

- Número igual ao da fonte. Nada de valor "ajustado".
- Consultas mínimas: cada arquivo da CVM é baixado só quando ela o republica (como em `pipeline/cvm_lote.py`), e o Fundos.NET é consultado com ritmo controlado (`pipeline/rede.py`).
- Fonte que falha mantém a versão anterior; o monitor vigia a defasagem e o validador ganha checagens de FII (patrimônio que salta sem emissão, rendimento fora do padrão).
- Excel por fundo e da seção, como nas empresas.

## Protótipo guardado (`docs/exemplos/`)

- `fii_exemplo_dados.py` — monta o JSON do HGLG11 a partir dos zips da CVM, da lista do Fundos.NET e da Yahoo (CNPJ 11.728.688/0001-47, "Pátria Log FII").
- `fii_HGLG11_exemplo.json` — o JSON gerado em 2026-11-02 (formato que a página espera).
- `fii_pagina_prototipo.diff` — o código da página (`paginaFii`, abas, rota `#/on/fii/{ticker}`, item no menu) aplicado sobre `site/assets/app.js`. Para ver o exemplo de novo: `git apply docs/exemplos/fii_pagina_prototipo.diff` e copiar o JSON para `site/dados/fiis/HGLG11.json`.

## Ordem de implantação

1. Visão geral do mercado (com o comparativo por segmento) + planilhão + página de cada fundo (informes mensal e trimestral da CVM, cotação).
2. Documentos e fatos relevantes do Fundos.NET.
3. Rendimentos oficiais pelos avisos estruturados do Fundos.NET.
4. Depois: relatórios gerenciais resumidos por IA.
