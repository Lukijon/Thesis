# Coisas que preciso que você forneça

Lista de itens que dependem de você (acesso, dados, decisões) para o projeto continuar. Vou adicionando conforme formos identificando novas necessidades.

- [x] **Histórico completo de composição do Ibovespa (2015–2024)** — ✅ resolvido

  Você forneceu `ibov members.csv` (composição trimestral via Bloomberg, 1/2015–2026) + `ibov names.csv` (mapa ticker→nome). Isso fecha as lacunas que a reconstrução via Internet Archive não cobria (2016–2018 e 2022–2024). Encontramos mais 10 empresas novas a partir desses arquivos (BR Properties, Atacadão, EDP Energias do Brasil, Fibria, Locamerica, Natura & Co Holding, Smiles/Smiles Fidelidade, Grupo de Moda Soma, Grupo Casas Bahia), somadas às 26 já encontradas via Wayback Machine — total de 36 empresas adicionadas à parte 1. Ver `src/acquisition/b3_ibov_historical.py` para o histórico completo do método e dos dois arquivos CSV combinados.

  Residual menor, não perseguido por retorno decrescente: 3 tickers de falências antigas (BTOW3/B2W, OGXP3/OGX, LLXL3/LLX) não resolveram para nenhum CD_CVM — parecem ter sido totalmente removidos do cadastro da CVM, não apenas marcados como cancelados.

- [ ] **Dados de mercado: preços e retornos das ações**

  Necessário para calcular o retorno anormal acumulado nos 12 meses seguintes à divulgação (variável dependente de H1/H1a). Export do Bloomberg (`PX_LAST` diário ou mensal, mais um índice de mercado tipo Ibovespa para calcular retorno anormal) para as ~137 empresas do universo atual (66 + 36 históricas) cobrindo 2015–2025 (precisa de ~12 meses após a última divulgação de 2024).

- [ ] **Variáveis de controle (fundamentos econômico-financeiros)**

  Alavancagem, rentabilidade, tamanho (valor de mercado ou ativos totais), retorno passado — mencionados no pré-projeto como controles necessários para testar H1. Parte pode ser derivada diretamente das próprias DFPs já baixadas (ex.: alavancagem contábil), mas valor de mercado/capitalização precisa do Bloomberg. Vale definirmos juntos exatamente quais variáveis de controle entram no modelo antes de montar essa extração.

- [ ] **Consenso de previsões de EPS dos analistas (Bloomberg BEst)**

  Necessário para a análise complementar (H2) — revisão do consenso de EPS após a divulgação. Export do Bloomberg BEst (`BEST_EPS`, histórico de revisões) para o mesmo universo de empresas.

- [ ] **Decisão: Data Pack do GitHub para o LFS**

  O payload de PDFs já passa de ~2GB (parte 1 completa, incluindo o histórico do Ibovespa) e vai crescer bastante mais na parte 2. A cota gratuita do GitHub LFS é 1GB/mês (armazenamento e banda). Se quiser manter o repositório sincronizado no GitHub (não só local), em algum momento vamos precisar de um Data Pack pago (~$5/50GB) — vale decidir antes de tentarmos sincronizar tudo de uma vez.
