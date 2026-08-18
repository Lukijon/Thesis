# Alterações Textuais em Notas de Dívida e Incorporação de Informação pelo Mercado Brasileiro

Repositório central da dissertação de mestrado (título provisório): **"Alterações textuais nas notas explicativas de dívida e a incorporação de informações pelo mercado brasileiro: evidências das notas de empréstimos, financiamentos e debêntures."**

O documento completo do pré-projeto está em [docs/pre-projeto.docx](docs/pre-projeto.docx). Este README resume o essencial para orientar o trabalho no repositório; o pré-projeto é a fonte de verdade para o embasamento teórico e a revisão de literatura.

## Pergunta de pesquisa

As alterações textuais nas notas explicativas de dívida das empresas brasileiras carregam informação que o mercado demora para incorporar aos preços das ações?

Mais especificamente: em que medida a mudança textual ano a ano (medida por TF-IDF e similaridade de cosseno) nas notas de empréstimos, financiamentos e debêntures das DFPs anuais de empresas não financeiras listadas na B3 está associada ao retorno anormal acumulado nos 12 meses seguintes à divulgação, controlando por mudanças nos fundamentos econômico-financeiros da empresa? Como análise complementar, verifica-se também a associação com a revisão do consenso de previsões de EPS dos analistas.

## Hipóteses

- **H1** — a mudança textual ano a ano nas notas de dívida está associada ao retorno anormal futuro das ações, mesmo controlando pelas mudanças observáveis nos fundamentos (sem direção definida a priori).
- **H1a** (exploratória, opcional) — maior mudança textual associa-se a retorno anormal futuro *menor*, na linha de *Lazy Prices* (Cohen, Malloy e Nguyen, 2020).
- **H2** (complementar) — a mudança textual nas notas de dívida também se associa à revisão do consenso de EPS dos analistas após a divulgação.

## Estrutura do repositório

```
.
├── docs/                # Documentos da dissertação (pré-projeto, versões futuras, texto final)
├── data/
│   ├── raw/              # Dados brutos, exatamente como coletados (nunca editados manualmente)
│   │   ├── dfp/           # DFPs / notas explicativas de dívida (CVM)
│   │   ├── market/        # Preços, retornos, dados de mercado (B3 / provedor de dados)
│   │   └── analysts/      # Consenso de previsões de EPS dos analistas
│   ├── interim/           # Dados intermediários (ex.: texto extraído e limpo das notas)
│   ├── processed/         # Datasets finais, prontos para as análises/regressões
│   └── external/          # Dados auxiliares de terceiros (ex.: listas de empresas, classificações setoriais)
├── src/
│   ├── acquisition/       # Scripts de coleta/download das fontes de dados
│   ├── processing/        # Extração e limpeza de texto, TF-IDF, similaridade de cosseno
│   ├── features/          # Construção de variáveis de controle (alavancagem, tamanho, retorno passado etc.)
│   ├── analysis/          # Regressões, testes de hipótese, resultados
│   └── utils/              # Funções auxiliares compartilhadas
├── notebooks/             # Exploração e validações pontuais
├── references/            # Material de apoio da revisão de literatura (bibliografia, PDFs de referência)
└── reports/
    └── figures/            # Figuras e tabelas geradas para a dissertação
```

`data/` é ignorado pelo git (ver [.gitignore](.gitignore)) — os dados não são versionados aqui, apenas o código que os gera/processa. Cada subpasta mantém um `.gitkeep` para preservar a estrutura.

## Dados a serem coletados

Etapa atual do projeto. Para viabilizar os testes de H1, H1a e H2, é necessário reunir:

1. **Notas explicativas de empréstimos, financiamentos e debêntures** das DFPs anuais de empresas não financeiras listadas na B3 (fonte: portal de dados abertos da CVM / ITR-DFP).
2. **Dados de mercado** — preços e retornos das ações para cálculo de retorno anormal acumulado nos 12 meses seguintes à divulgação.
3. **Fundamentos econômico-financeiros** — alavancagem, rentabilidade, tamanho, retorno passado e demais variáveis de controle.
4. **Consenso de previsões de EPS dos analistas** — dados para a análise complementar (H2).

## Status

- [x] Pré-projeto redigido (ver `docs/pre-projeto.docx`)
- [x] Estrutura do repositório definida
- [ ] Scripts de aquisição de dados (DFPs/notas, mercado, fundamentos, consenso de analistas)
- [ ] Extração e limpeza de texto das notas
- [ ] Cálculo de similaridade de cosseno / mudança textual (TF-IDF)
- [ ] Construção das variáveis de controle
- [ ] Cálculo de retorno anormal
- [ ] Modelos de regressão e testes de hipótese
- [ ] Análise complementar (consenso de analistas)
