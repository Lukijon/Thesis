# Coisas que preciso que você forneça

Lista de itens que dependem de você (acesso, dados, decisões) para o projeto continuar. Vou adicionando conforme formos identificando novas necessidades.

- [x] **Histórico completo de composição do Ibovespa (2015–2024)** — ✅ resolvido

  Você forneceu `ibov members.csv` (composição trimestral via Bloomberg, 1/2015–2026) + `ibov names.csv` (mapa ticker→nome). Isso fecha as lacunas que a reconstrução via Internet Archive não cobria (2016–2018 e 2022–2024). Primeiro passe: 10 empresas novas (BR Properties, Atacadão, EDP Energias do Brasil, Fibria, Locamerica, Natura & Co Holding, Smiles/Smiles Fidelidade, Grupo de Moda Soma, Grupo Casas Bahia), somadas às 26 já encontradas via Wayback Machine.

  **Correção (você pediu para conferir e havia um furo real):** o primeiro passe só cruzou os tickers que *não* resolveram direto contra o que já estava coberto — os que resolveram foram assumidos como já cobertos sem checar de fato. Refazendo o diff corretamente apareceram mais 10 empresas, incluindo a **Americanas S.A.** (o caso de fraude contábil/crise de dívida de 2023 — bem relevante para a dissertação). Total agora: 45 empresas históricas + 66 atuais = **111 empresas**. Ver `src/acquisition/b3_ibov_historical.py` (ponto 3 do docstring) para o relato completo do furo.

  Residual menor, não perseguido por retorno decrescente: 3 tickers de falências antigas (BTOW3/B2W, OGXP3/OGX, LLXL3/LLX) não resolveram para nenhum CD_CVM — parecem ter sido totalmente removidos do cadastro da CVM, não apenas marcados como cancelados.

- [x] **Dados de mercado: preços e retornos das ações** — ✅ recebido (verificado)

  Você adicionou `data/interim/prices.csv` e `data/interim/ibov.csv` (exports do Bloomberg); movidos para `data/raw/market/prices/stock_prices_bloomberg.csv` e `ibov_index_bloomberg.csv` (git-ignorados, como todo dado Bloomberg). Conferido linha a linha antes de aceitar:

  - Preços diários (`PX_LAST`) de **153 ações**, 1/2014–8/2026 (dado real até 21/08/2026, os 2 últimos dias do arquivo são placeholder). Todos os 66 tickers do universo IBOV atual estão cobertos; os outros 87 tickers são nomes históricos/deslistados, consistente com o universo de 111 empresas do `b3_ibov_historical.py`.
  - Índice Ibovespa diário (mesmo período) para cálculo de retorno anormal — 3.138 pregões com valor, o resto são fins de semana/feriados (padrão esperado de calendário).
  - Achado, não é problema: **9 tickers** (CCRO3, ELET3, ELET6, EMBR3, GOLL4, MRFG3, AZUL4, RRRP3, TRPL4) retornam `#N/A` em 100% das linhas — são nomes *pré-mudança de ticker* (ex.: EMBR3→EMBJ3, MRFG3→MBRF3, CCRO3→MOTV3 após a fusão CCR/Motiva) cuja fórmula do Bloomberg só resolve pelo identificador atual. O ticker atual de cada uma já está no arquivo com dado completo (confirmado, ex. EMBJ3/MBRF3/MOTV3 com 3.137 valores não nulos) — ao mapear ticker→CD_CVM na etapa de processamento, usar o nome atual do B3 para essas 9 empresas, não o histórico.
  - **Atualização:** cruzamento feito. Das ~45 empresas históricas, **~40 têm ticker atual resolvível** (via registro vivo da B3, cruzando `codeCVM`) e cobertura de preço utilizável; as demais (Souza Cruz, MMX, Cia Hering, Fibria, Notre Dame Intermédica, EDP Energias do Brasil, entre outras) saíram de bolsa por fechamento de capital, fusão ou falência e não têm mais ticker negociável — gap real, não um problema de dados, e vai exigir uma decisão explícita (excluir vs. algum proxy) antes da regressão final. Ver `src/analysis/compute_abnormal_returns.py` e §7 do notebook.

- [x] **Data de divulgação de cada nota (evento de mercado)** — ✅ resolvido

  Não existia antes como arquivo próprio: o índice bruto da CVM já trazia a data real de recebimento/divulgação (`DT_RECEB`), mas o código de aquisição descartava esse campo. Criado `src/acquisition/build_filing_dates.py` → `data/interim/dfp_filing_dates.csv` (993 linhas, uma por arquivo-empresa-ano já adquirido, com `period_end_date` e `filing_date` separados). Essa é a data usada como evento no cálculo de retorno anormal abaixo.

- [x] **Primeiro cálculo de retorno anormal (checkpoint da POC)** — ✅ feito, resultado nulo esperado

  `src/analysis/compute_abnormal_returns.py` calcula retorno ajustado ao mercado (ação menos Ibovespa, buy-and-hold, 12 meses após a divulgação — não é um retorno de modelo de mercado com beta) para os pares empresa-ano que já têm similaridade calculada na POC. Resultado (297 pares): correlação com a similaridade textual é essencialmente zero (r de Pearson entre -0.06 e -0.05). Não é um resultado negativo para H1a — é o esperado nessa escala sem variáveis de controle, sem beta de mercado, e com amostra pequena. Ver §7 do `poc_overview.ipynb`. Confirma que o pipeline roda ponta a ponta; o teste de verdade precisa dos fundamentos (item abaixo) e do universo completo.

- [ ] **Variáveis de controle (fundamentos econômico-financeiros)**

  Alavancagem, rentabilidade, tamanho (valor de mercado ou ativos totais), retorno passado — mencionados no pré-projeto como controles necessários para testar H1. Parte pode ser derivada diretamente das próprias DFPs já baixadas (ex.: alavancagem contábil), mas valor de mercado/capitalização precisa do Bloomberg. Vale definirmos juntos exatamente quais variáveis de controle entram no modelo antes de montar essa extração.

- [x] **Consenso de previsões de EPS dos analistas (Bloomberg BEst)** — ✅ recebido (cobertura ainda não conferida a fundo)

  Você adicionou `data/interim/eps estimates.csv` (export do Bloomberg, `is_eps` com `fpt=Q`/`ae=E` — série histórica trimestral do consenso de EPS, uma linha por data de referência, confirmada como o histórico de estimativas por trimestre); movido para `data/raw/analysts/eps_consensus_bloomberg.csv` (git-ignorado, como todo dado Bloomberg). 153 tickers (mesmo conjunto do arquivo de preços), 133 datas trimestrais, 6/2013–12/2026. Conferido contra o universo antes de aceitar: **64 das 66 empresas atuais do Ibovespa têm pelo menos alguma cobertura** (58 com cobertura densa, ≥20 dos ~52 trimestres desde 2015); **Klabin (KLBN11) e Iguatemi (IGTI11) têm cobertura zero**. Ainda não cruzado contra as 46 empresas históricas/deslistadas. Falta ainda: confirmar a definição exata de "revisão" para o H2 (variação do consenso entre duas datas para o mesmo trimestre-alvo) e decidir a janela de revisão em torno de cada divulgação.

- [x] **Decisão: PDFs baixados no GitHub?** — ✅ resolvido: não

  Chegamos a subir os PDFs via git-lfs (payload ~1,8GB), mas você pediu para tirar do GitHub. Reescrevemos o histórico do git (`git-filter-repo`) e demos force-push para remover — os arquivos continuam seguros no seu disco local (`data/raw/dfp/`), só não estão mais no git/GitHub. Ver `CLAUDE.md` para o histórico completo dessa decisão.
