# Coisas que preciso que você forneça

Lista de itens que dependem de você (acesso, dados, decisões) para o projeto continuar. Vou adicionando conforme formos identificando novas necessidades.

- [x] **Histórico completo de composição do Ibovespa (2015–2024)** — ✅ resolvido

  Você forneceu `ibov members.csv` (composição trimestral via Bloomberg, 1/2015–2026) + `ibov names.csv` (mapa ticker→nome). Isso fecha as lacunas que a reconstrução via Internet Archive não cobria (2016–2018 e 2022–2024). Encontramos mais 10 empresas novas a partir desses arquivos (BR Properties, Atacadão, EDP Energias do Brasil, Fibria, Locamerica, Natura & Co Holding, Smiles/Smiles Fidelidade, Grupo de Moda Soma, Grupo Casas Bahia), somadas às 26 já encontradas via Wayback Machine — total de 36 empresas adicionadas à parte 1. Ver `src/acquisition/b3_ibov_historical.py` para o histórico completo do método e dos dois arquivos CSV combinados.

  Residual menor, não perseguido por retorno decrescente: 3 tickers de falências antigas (BTOW3/B2W, OGXP3/OGX, LLXL3/LLX) não resolveram para nenhum CD_CVM — parecem ter sido totalmente removidos do cadastro da CVM, não apenas marcados como cancelados.
