# Coisas que preciso que você forneça

Lista de itens que dependem de você (acesso, dados, decisões) para o projeto continuar. Vou adicionando conforme formos identificando novas necessidades.

- [ ] **Histórico completo de composição do Ibovespa (2015–2024)**

  A reconstrução atual (`src/acquisition/b3_ibov_historical.py`) usa snapshots do Internet Archive da página antiga da B3 e cobre apenas 8 períodos verificados entre 2013 e 2021. Há lacunas reais: praticamente todo 2016–2018 e todo 2022–2024 não têm snapshot arquivado disponível. Isso significa que empresas que entraram ou saíram do Ibovespa só nesses períodos não cobertos podem estar faltando na amostra, o que enfraquece a correção do viés de sobrevivência.

  O que resolveria: acesso a uma base com composição histórica trimestral/quadrimestral do Ibovespa — Bloomberg (`IBOV Index` → membros históricos) ou Economatica normalmente têm isso pronto. Se você tiver acesso a qualquer uma das duas, um export da composição por período já resolve.
