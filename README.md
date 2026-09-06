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
├── docs/                 # Documentos da dissertação
│   ├── latex/              # main.tex — o documento de submissão atual (ABNT, compila via TinyTeX)
│   ├── pre-projeto.docx     # pré-projeto original, já aprovado
│   └── exame_qualificacao/  # guia do Exame de Qualificação (datas, requisitos)
├── data/
│   ├── raw/              # Dados brutos, exatamente como coletados (nunca editados manualmente)
│   │   ├── dfp/           # DFPs / notas explicativas de dívida (CVM), gitignorado
│   │   ├── itr/            # Notas trimestrais (CVM), gitignorado
│   │   ├── dfp_mgmt_report/ # Relatório da Administração (CVM), gitignorado
│   │   ├── risk_factors/    # Fatores de Risco / Formulário de Referência (CVM), gitignorado
│   │   ├── market/         # Preços, retornos, dados de mercado (Bloomberg), gitignorado
│   │   └── analysts/       # Consenso de previsões de EPS dos analistas (Bloomberg), gitignorado
│   └── interim/            # Dados intermediários versionados (manifestos, CSVs pequenos, POC)
├── src/
│   ├── acquisition/       # Scripts de coleta/download das fontes de dados
│   ├── processing/        # Extração e limpeza de texto, TF-IDF, similaridade de cosseno
│   ├── features/          # Construção de variáveis de controle (alavancagem, tamanho, retorno passado etc.)
│   ├── analysis/          # Regressões, testes de hipótese, resultados
│   └── utils/              # Funções auxiliares compartilhadas
├── notebooks/             # POC: exploração e validações, narradas em primeira pessoa
└── reports/               # Relatórios narrativos por rodada/investigação
    └── figures/            # Figuras geradas para relatórios (não as da dissertação, que ficam em docs/latex/figures)
```

A maior parte de `data/` é ignorada pelo git (ver [.gitignore](.gitignore)) — cache de download, dados de mercado/analistas (Bloomberg) e intermediários volumosos não são versionados. As notas de dívida já extraídas (`data/raw/dfp/<CD_CVM>/<ANO>/`) são gitignoradas e ficam só nesta máquina (ver `CLAUDE.md` para o histórico: chegaram a ser versionadas via git-lfs, decisão revertida depois).

## Status

Checklist resumido — para o detalhe rodada a rodada, ver `CLAUDE.md`.

- [x] Pré-projeto redigido (ver `docs/pre-projeto.docx`)
- [x] Aquisição das notas de dívida via CVM (nota isolada, documento inteiro, Relatório da Administração e Fatores de Risco), 111 empresas não financeiras (66 constituintes atuais do Ibovespa + 45 históricas/deslistadas, corrigindo viés de sobrevivência), 2015–2024, anual e trimestral
- [x] Extração e isolamento automático da nota de dívida — seis rodadas de aprimoramento da heurística, confiabilidade em **69,7%** na base anual e **62,0%** na trimestral (universo completo)
- [x] Cálculo de similaridade textual (TF-IDF e cosseno), nas cinco fontes de texto testadas
- [x] Dados de mercado (preços, Ibovespa) e consenso de EPS dos analistas (Bloomberg) recebidos e verificados
- [x] Variáveis de controle (tamanho, alavancagem, rentabilidade, retorno passado) construídas a partir dos dados contábeis estruturados da CVM
- [x] Cálculo de retorno anormal e modelo empírico completo — correlação simples, regressão agrupada (com e sem controles) e efeitos fixos de empresa e ano
- [x] Testes de H1 e H2, nas cinco fontes de texto — **nulos em todos os estágios de rigor**; o achado secundário mais bem sustentado é a associação entre similaridade nos Fatores de Risco e saída subsequente do Ibovespa
- [x] Aquisição parte 2 (universo não financeiro da B3 fora do Ibovespa) — não iniciada, não é mais necessária dado o resultado nulo já bem estabelecido no universo atual
- [ ] Conclusão e Resumo/Abstract definitivos da dissertação (`docs/latex/main.tex`) — deliberadamente deixados para o final, por instrução do próprio guia do Exame de Qualificação
