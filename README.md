# Alterações Textuais em Notas de Dívida e Incorporação de Informação pelo Mercado Brasileiro

Repositório central da dissertação de mestrado (título provisório): **"Alterações textuais nas notas explicativas de dívida e a incorporação de informações pelo mercado brasileiro: evidências das notas de empréstimos, financiamentos e debêntures."**

O documento completo do pré-projeto está em `privado/pre-projeto.docx` (local-only, não versionado -- ver a seção sobre `privado/` abaixo). Este README resume o essencial para orientar o trabalho no repositório; o texto da própria dissertação ([tese/latex/tese_jonathan.tex](tese/latex/tese_jonathan.tex)) é a fonte de verdade para o embasamento teórico, a metodologia e os resultados.

## Pergunta de pesquisa

As alterações textuais nas notas explicativas de dívida das empresas brasileiras carregam informação que o mercado demora para incorporar aos preços das ações — precisamente por estarem numa parte tecnicamente densa e pouco lida da divulgação financeira (atenção limitada)?

Mais especificamente: em que medida a mudança textual ano a ano (medida por TF-IDF e similaridade de cosseno) nas notas de empréstimos, financiamentos e debêntures das DFPs anuais de empresas não financeiras listadas na B3 está associada ao retorno anormal acumulado nos 12 meses seguintes à divulgação, controlando por mudanças nos fundamentos econômico-financeiros da empresa? Como análise complementar, verifica-se também a associação com a revisão do consenso de previsões de EPS dos analistas.

## Hipóteses

- **H1** — a mudança textual ano a ano nas notas de dívida está associada ao retorno anormal futuro das ações, mesmo controlando pelas mudanças observáveis nos fundamentos (sem direção definida a priori).
- **H1a** (exploratória, opcional) — maior mudança textual associa-se a retorno anormal futuro *menor*, na linha de *Lazy Prices* (Cohen, Malloy e Nguyen, 2020).
- **H2** (complementar) — a mudança textual nas notas de dívida também se associa à revisão do consenso de EPS dos analistas após a divulgação.

## Estrutura do repositório

O repositório é dividido em três pastas principais, cada uma com um papel diferente, mais uma quarta pasta local-only:

```
.
├── tese/                     # O DOCUMENTO da dissertação -- o entregável em si
│   └── latex/                   # tese_jonathan.tex + tese_jonathan.pdf (ABNT, compila via MiKTeX/TinyTeX)
│       └── figures/                # Figuras da dissertação (geradas a partir de suporte/data, ver abaixo)
│
├── suporte/                  # O que é PRECISO para produzir/reproduzir a tese: dados, código
│   ├── data/
│   │   ├── raw/                 # Dados brutos, exatamente como coletados (nunca editados manualmente)
│   │   │   ├── dfp/               # DFPs / notas explicativas de dívida (CVM), gitignorado
│   │   │   ├── itr/                # Notas trimestrais (CVM), gitignorado
│   │   │   ├── dfp_mgmt_report/     # Relatório da Administração (CVM), gitignorado
│   │   │   ├── risk_factors/        # Fatores de Risco / Formulário de Referência (CVM), gitignorado
│   │   │   ├── market/             # Preços, retornos, dados de mercado (Bloomberg), gitignorado
│   │   │   └── analysts/           # Consenso de previsões de EPS dos analistas (Bloomberg), gitignorado
│   │   └── interim/                # Dados intermediários versionados (manifestos, CSVs pequenos, POC)
│   ├── src/
│   │   ├── acquisition/         # Coleta/download das fontes de dados (CVM, B3)
│   │   ├── processing/          # Extração e limpeza de texto, TF-IDF, similaridade de cosseno
│   │   ├── features/            # Construção de variáveis de controle (alavancagem, tamanho, retorno passado etc.)
│   │   ├── analysis/            # Regressões, testes de hipótese, resultados, figuras da tese
│   │   └── utils/                # Funções auxiliares compartilhadas
│   ├── ibov.xlsx, ibx.xlsx, cdi.xlsx      # Exportações Bloomberg fornecidas pelo usuário (preços, IBX, CDI)
│   └── requirements.txt
│
├── exploracao/                # PoCs, testes, rodadas de investigação e sidequests -- não é o entregável
│   ├── notebooks/                # POC: exploração e validações, narradas em primeira pessoa
│   ├── reports/                  # Relatórios narrativos por rodada/investigação (muitos resultados nulos/descartados)
│   │   └── figures/                 # Figuras desses relatórios (não as da dissertação)
│   ├── sidequest/                 # Projeto paralelo não relacionado (diversidade de conselho vs. custo de dívida)
│   └── src/                       # Scripts exploratórios/superados (não fazem parte do pipeline ativo)
│
└── privado/                   # LOCAL-ONLY (gitignorado) -- nunca sobe pro GitHub
    ├── feedback_dissertacao.pdf, especificacoes_m0_m5_dissertacao.pdf,
    │   recomendacoes.txt, transcricao_conversa_orientador.txt   # Feedback/orientação do orientador
    ├── Exame_qualificacao_MPE22-parte2.pdf                        # Guia institucional do Exame de Qualificação
    ├── Lazy Prices_Cohen_Nguyen.pdf                                # Paper usado como referência de estrutura/conteúdo
    ├── latex_old/                                                  # Snapshot congelado do rascunho pré-expansão do universo
    ├── pre-projeto.docx                                            # Pré-projeto original, já aprovado
    └── NEXT_STEPS_AND_PRESENTATION_GUIDE.md
```

Todos os comandos `python -m src.<...>` devem ser executados com o diretório de trabalho em `suporte/` (é de lá que `src/` e `data/` enxergam um ao outro). Scripts em `exploracao/src/` foram movidos para fora de `suporte/` justamente por não fazerem mais parte do pipeline ativo — eles ainda importam de `src.*`, então, para rodá-los de novo, aponte `PYTHONPATH` para `suporte/` (ou copie o script de volta temporariamente); a maioria já teve sua conclusão incorporada a um relatório em `exploracao/reports/` e não precisa ser reexecutada.

A maior parte de `suporte/data/` é ignorada pelo git (ver [.gitignore](.gitignore)) — cache de download, dados de mercado/analistas (Bloomberg) e intermediários volumosos não são versionados. As notas de dívida já extraídas (`suporte/data/raw/dfp/<CD_CVM>/<ANO>/`) são gitignoradas e ficam só nesta máquina (ver `CLAUDE.md` para o histórico: chegaram a ser versionadas via git-lfs, decisão revertida depois).

## Status

Checklist resumido — para o detalhe rodada a rodada, ver `CLAUDE.md`.

- [x] Pré-projeto redigido (ver `privado/pre-projeto.docx`)
- [x] Universo expandido para 185 empresas não financeiras (66 constituintes atuais do Ibovespa + 45 históricas/deslistadas + 74 do índice IBX que nunca integraram o Ibovespa), 2010–2025
- [x] Extração e isolamento automático da nota de dívida — sete rodadas de aprimoramento da heurística, confiabilidade em **80,3%** na base anual (universo expandido)
- [x] Cálculo de similaridade textual (TF-IDF e cosseno), em **quatro fontes de texto** (nota de dívida anual, conjunto completo de notas, Relatório da Administração, Fatores de Risco do FRE) — o ITR (nota trimestral) foi removido do escopo: como documento trimestral seu efeito não é comparável aos das fontes anuais e não tinha justificativa econômica clara para permanecer
- [x] Retorno anormal medido como resíduo fora da amostra de um modelo de quatro fatores (BHAR ajustado), grade de controles M0-M3 pré-especificada
- [x] **Resultado principal**: a mudança textual da nota de dívida anual está associada ao retorno anormal futuro, significativa a 5% em toda a grade M0-M3 (M2: β=0,156, p=0,017), corroborada por um teste de portfólio calendário (p=0,0011) e pelo desenho de Santos & Coelho 2018 (p=0,043–0,080). Este é o único teste confirmatório pré-especificado da dissertação; as outras três fontes de texto servem como checagens de especificidade/generalização, não como testes confirmatórios independentes, e nenhuma mostra o mesmo padrão. (A correção de Benjamini-Hochberg para múltiplos testes, usada numa versão anterior do texto, foi removida junto com essa reformulação — deixou de fazer sentido tratar as fontes secundárias como uma "família" de testes independentes da mesma hipótese.)
- [x] H2 (revisão de consenso de EPS) — nulo em toda a grade, ainda no universo original de 111 empresas
- [x] Repositório reorganizado em três pastas principais (`tese/`, `suporte/`, `exploracao/`) + `privado/` (local-only)
- [x] Resumo/Abstract, Introdução (Capítulo 1) e Descrição dos Dados revisados para um tom mais direto, no estilo de paper de economia (Lazy Prices) em vez de texto acadêmico genérico — pedido explícito do orientador
- [ ] Conclusão da dissertação (`tese/latex/tese_jonathan.tex`) — ainda placeholder, deliberadamente deixada para o final
