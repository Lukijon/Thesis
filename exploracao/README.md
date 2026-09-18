# Exploração

Tudo aqui é apoio histórico, não o pipeline ativo nem o entregável. Nada nesta pasta é necessário para reproduzir a tese em `tese/` a partir de `suporte/`.

- **`notebooks/`** — cadernos da fase de POC (prova de conceito), narrados em primeira pessoa, com gráficos e evidência textual real. Documentam como a ideia foi validada antes de escalar para o pipeline atual.
- **`reports/`** — relatórios narrativos de rodadas de investigação passadas (a maioria com resultado nulo ou descartado depois de escrutínio adicional — ver cada arquivo para o desfecho). Úteis como registro de o que já foi tentado e por quê não seguiu adiante.
- **`sidequest/`** — projeto paralelo *não relacionado* à tese principal (diversidade no conselho/administração vs. custo de dívida e volatilidade). Ver `sidequest/README.md`.
- **`src/`** — scripts que ficaram fora do pipeline ativo de `suporte/src/`: ou porque o próprio docstring os marca como superados por uma versão mais nova (ex.: `run_itr_pilot.py` → `run_itr_full.py`), ou porque são checagens pontuais/exploratórias cuja conclusão já está capturada em algum relatório de `reports/`.

## Se precisar rodar algo daqui de novo

Os scripts em `src/` ainda fazem `from src.analysis... import ...` (import absoluto, assumindo que `src/` está na raiz de execução) — mas `src/` agora mora em `suporte/src/`, não mais ao lado destes scripts. Para reexecutar um deles:

1. Copie o script de volta para dentro de `suporte/src/<subpasta>/` temporariamente, ou
2. Rode com `PYTHONPATH` apontando para `suporte/` (ex.: `PYTHONPATH=../suporte python -m src.analysis.nome_do_script`, a partir de `exploracao/`).

Na prática isso raramente deveria ser necessário — se um desses scripts importasse de volta, ele não estaria aqui.
