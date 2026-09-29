# Como rodar este projeto (sem precisar do Claude)

Este é um projeto Python comum. Tudo que ele faz é baixar dados abertos da CVM,
processar e gerar um Excel. Não depende de nada do Claude Code — roda em
qualquer computador com Python instalado.

Tem duas formas de usar: pela **Central de Downloads** (tela no navegador,
sem digitar comando nenhum) ou pela **linha de comando** (mais rápido se você
já sabe o que quer). A Central de Downloads é a recomendada no dia a dia.

## 0. Central de Downloads (recomendado)

Depois de instalar as dependências (passo 2 abaixo), é só dar **duplo-clique
em `Iniciar_App.bat`**. Isso abre uma aba no seu navegador com:

- uma caixa de busca com a lista de todas as empresas da CVM (digite parte
  do nome e escolha da lista — não precisa acertar o nome oficial);
- os campos de ano inicial/final;
- um botão "Gerar relatório" que baixa o Excel prontinho.

Na primeira vez que você abrir, ele carrega a lista de empresas (pode levar
alguns segundos). Depois disso, é só selecionar, escolher o período e clicar
— igual usar um site. Pra fechar, feche a janela do navegador e a janelinha
preta que abriu junto (ou aperte uma tecla nela, como o próprio `.bat` avisa).

Se preferir rodar manualmente em vez do `.bat`:

```bash
py -m streamlit run app.py
```

## 1. Confirmar que o Python está instalado

Abra o **PowerShell** (ou Prompt de Comando) nesta pasta e rode:

```bash
py --version
```

Se aparecer algo como `Python 3.14.x`, está tudo certo. Se der erro, instale o
Python em https://www.python.org/downloads/ (marque a opção "Add python.exe
to PATH" durante a instalação).

## 2. Instalar as bibliotecas necessárias (só precisa fazer 1 vez)

Ainda no PowerShell, dentro da pasta do projeto:

```bash
py -m pip install -r requirements.txt
```

Isso instala `pandas`, `requests` e `openpyxl` — as únicas dependências do projeto.

## 3. Rodar pela linha de comando (alternativa à Central de Downloads)

O comando básico é:

```bash
py main.py "NOME DA EMPRESA" ANO_INICIO [ANO_FIM]
```

Exemplos:

```bash
# Um ano só
py main.py "WEG" 2024

# Faixa de anos (histórico) — o código já ajusta sozinho pro maior
# período comum disponível entre DRE, Balanço e DFC
py main.py "PETROBRAS" 2016 2026

# Buscando por CNPJ em vez de nome
py main.py "33.000.167/0001-01" 2024

# Forçando dados individuais em vez de consolidado (raro precisar)
py main.py "WEG" 2024 --tipo ind
```

O nome da empresa pode ser parcial (ex: "VALE" já encontra "VALE S.A."). Se
mais de uma empresa bater com o nome digitado, o programa avisa e usa a
primeira da lista — nesse caso, é mais seguro rodar de novo com o nome mais
específico ou o CNPJ.

## 4. Onde os arquivos aparecem

- **`data/processed/`** — é aqui que o Excel final é salvo. Nome do arquivo:
  `EMPRESA_Padrao_ANO-INICIO_ANO-FIM.xlsx`.
- **`data/raw/`** — cache dos ZIPs baixados da CVM (arquivos grandes, um por
  ano/fonte). Não precisa mexer aqui; o programa reusa o que já foi baixado
  em vez de baixar de novo. Se quiser forçar um download novo (raro
  necessário), é só apagar o arquivo `.zip` correspondente dessa pasta.

## 5. Primeira vez rodando um ano novo demora mais

Na primeira vez que você pedir um ano que ainda não está em `data/raw/`, o
programa baixa o ZIP anual da CVM inteiro (pode ter uns 30-200 MB,
dependendo do ano) — isso leva de alguns segundos a poucos minutos,
dependendo da internet. Da segunda vez em diante (mesmo ano, outra empresa),
é instantâneo, porque já está em cache.

## 6. Outro utilitário: mapa de contas (sem valores)

Se quiser ver só a estrutura de contas de uma empresa (sem números, útil pra
conferir o "padrão" de contas usado), tem o `gerar_mapa.py`:

```bash
py gerar_mapa.py "WEG" 2024
```

Gera um Excel em `data/processed/` com o código e a descrição de cada conta,
sem os valores.

## Erros comuns

- **`Python não foi encontrado`** → o Python não está instalado ou não está
  no PATH. Reinstale marcando "Add to PATH".
- **`Nenhuma empresa encontrada com esse nome`** → tente um nome mais curto
  ou mais próximo do nome oficial na CVM (ex: "BCO BRASIL" em vez de "Banco
  do Brasil"), ou use o CNPJ direto.
- **Demora muito na primeira vez** → normal, é o download do ZIP anual da
  CVM (ver item 5). Não precisa cancelar.
- **`PermissionError` ao salvar o Excel** → o arquivo já está aberto no
  Excel. Feche-o e rode de novo.

## Estrutura do projeto (referência rápida)

```
config/config.py       → URLs da CVM e configuração das demonstrações
src/cvm_itr.py          → busca, valida e monta o documento padrão (ITR/DFP)
src/padrao_visual.py    → regras de classificação de contas, cores, exclusões
src/exportar.py         → gera o Excel formatado
src/mapa_contas.py      → gera o mapa de contas (sem valores)
main.py                 → ponto de entrada por linha de comando
gerar_mapa.py           → ponto de entrada do mapa de contas
app.py                  → Central de Downloads (interface web local, Streamlit)
Iniciar_App.bat         → atalho de duplo-clique pra abrir a Central de Downloads
requirements.txt        → dependências (pandas, requests, openpyxl, streamlit)
```
