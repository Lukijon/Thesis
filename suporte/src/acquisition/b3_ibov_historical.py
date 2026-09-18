"""Historical (not just current) Ibovespa membership, resolved to CD_CVM.
Fixes a real survivorship-bias gap in the original IBOV tranche
(`b3_ibov.py`): that module resolves *today's* IBOV composition only, so any
company that was in the index at some point in 2015-2024 but has since been
removed -- delisted, bankrupt, acquired, or just fell out on liquidity -- was
entirely absent. That's a serious gap for a thesis about debt-distress
signals specifically, since distressed companies are exactly the ones most
likely to both show large textual change *and* drop out of the index.

Two sources, in the order they were used:

1. **Internet Archive snapshots** (`WAYBACK_ADDITIONS`) of B3's now-retired
   "ResumoCarteiraQuadrimestre.aspx" portfolio page, used first because
   B3's live composition API (GetPortfolioDay) does not accept a historical
   date -- confirmed empirically, it ignores every plausible date/year/month
   parameter and always returns today's portfolio, and there is no
   historical-composition endpoint on B3's current site. Real, verified
   periods recovered this way: 2013-11-27, 2014-07-23, 2015-09-23,
   2016-02-29, Jan-Apr 2019, Sep-Dec 2019, Sep-Dec 2020, Jan-Apr 2021 --
   real coverage, but with gaps (most of 2016-2018, all of 2022-2024).

2. **User-provided Bloomberg export** (`BLOOMBERG_ADDITIONS`) -- quarterly
   IBOV membership 2015-2024 pulled from Bloomberg
   (`data/raw/market/ibov_composition/ibov_members_bloomberg.csv` +
   `ibov_names_bloomberg.csv`, git-ignored like all Bloomberg-derived data --
   see .gitignore), which closes the gaps the Wayback method left. This is
   the authoritative source going forward; the Wayback list is kept for its
   own sake since it was independently verified and its companies all check
   out against the Bloomberg data too (cross-checked -- every Wayback-only
   addition is confirmed by a corresponding Bloomberg ticker for the same
   company).

Both sets resolve tickers to CD_CVM via the current B3 registry
(`b3_ibov.fetch_b3_company_registry`) where the company is still listed
under a matching issuer code, plus manual lookup in CVM's cadastral
registry (`cvm_dfp.load_cadastral`, which retains CANCELADA/delisted
entries) for tickers that no longer resolve via the live registry (renamed,
merged away, or fully delisted, e.g. a company acquired mid-sample whose
original CNPJ/CD_CVM stopped filing independently afterward).

Tickers seen in either source that resolved to a company *already* in the
current-IBOV set (`b3_ibov.build_ibov_non_financial_universe`) or renamed/
merged into one (e.g. Fibria->Suzano's ticker persisting historically,
Estácio->Yduqs, Kroton->Cogna, Tractebel->Engie, CTEEP->ISA Energia,
3R Petroleum/Enauta->Brava Energia, CCR->Motiva, Eletrobras->Axia,
ALL/Rumo->Rumo) are not repeated here -- they're already covered. A few
tickers remain unresolved after both passes (diminishing-returns cutoff,
not chased further): BTOW3 (B2W Digital), OGXP3 (OGX Petróleo), LLXL3 (LLX
Logística) -- all pre-2015-adjacent bankruptcies/mergers where the legal
entity appears to be fully purged from CVM's cadastral registry, not just
marked CANCELADA.

3. **`BLOOMBERG_FULL_CHECK_ADDITIONS`** -- found by a real gap in the process
   above, not a new source. When the Bloomberg file was first processed,
   only the tickers that *failed* direct ticker->CD_CVM resolution were
   cross-checked against what was already covered; the ~100+ tickers that
   *did* resolve cleanly were assumed to already be accounted for and never
   actually diffed against the covered set. They weren't all covered.
   Re-doing that diff properly (resolve every ticker in the file, non-
   financial filter, subtract the already-covered set) surfaced 10 more
   real companies, including Americanas S.A. -- the 2023 accounting-fraud/
   debt-restructuring case, about as on-theme for this thesis as it gets,
   and missed for over a week of work before this check. Lesson: "the
   unmatched ones are the only ones that need checking" was an unverified
   assumption, exactly the kind of thing this project has otherwise been
   careful to check against real data. If you add a fourth data source
   later, diff its *entire* resolved set against coverage, not just the
   leftovers.
"""
from __future__ import annotations

# Found via Internet Archive snapshots of B3's retired portfolio page
# (2013-2021 coverage, with gaps). See module docstring.
WAYBACK_ADDITIONS: dict[int, str] = {
    2577: "CESP - Companhia Energética de São Paulo",
    4057: "Souza Cruz S.A.",
    8087: "Lojas Americanas S.A. (pre-2021 restructuring entity)",
    11312: "Oi S.A. - Em Recuperação Judicial",
    14176: "Eletropaulo Metropolitana Eletricidade de São Paulo S.A.",
    14761: "Cia Hering",
    14826: "Companhia Brasileira de Distribuição (GPA)",
    16101: "Gafisa S.A.",
    16292: "BRF S.A.",
    16306: "Rossi Residencial S.A. - Em Recuperação Judicial",
    17914: "Massa Falida da MMX Mineração e Metálicos S.A.",
    19453: "Ecorodovias Infraestrutura e Logística S.A.",
    19569: "Gol Linhas Aéreas Inteligentes S.A.",
    19623: "Diagnósticos da América S.A. (Dasa)",
    19879: "Light S.A. - Em Recuperação Judicial",
    19909: "BR Malls Participações S.A.",
    20478: "PDG Realty S.A. Empreendimentos e Participações",
    20494: "Iguatemi Empresa de Shopping Centers S/A (pre-restructuring entity)",
    20524: "Even Construtora e Incorporadora S/A",
    20605: "JHSF Participações S.A.",
    20770: "EZ Tec Empreendimentos e Participações S/A",
    21091: "Dexco S.A. (formerly Duratex)",
    23272: "LOG Commercial Properties e Participações",
    23310: "CVC Brasil Operadora e Agência de Viagens S.A.",
    24112: "Azul S.A.",
    24384: "Notre Dame Intermédica Participações S.A.",
}

# Found via the user-provided Bloomberg quarterly membership export
# (full 2015-2024 coverage), additional to WAYBACK_ADDITIONS above.
BLOOMBERG_ADDITIONS: dict[int, str] = {
    6505: "Grupo Casas Bahia S.A. (Via Varejo)",
    12793: "Fibria Celulose S.A. (pre-Suzano-merger entity)",
    19763: "EDP Energias do Brasil S/A",
    19925: "BR Properties S.A.",
    22691: "Companhia de Locação das Américas (Locamerica)",
    23140: "Smiles S.A.",
    24171: "Atacadão S.A.",
    24252: "Smiles Fidelidade S.A.",
    24783: "Natura & Co Holding S.A. (pre-restructuring parent entity)",
    25011: "Grupo de Moda Soma S.A.",
}

# Found by properly diffing *every* Bloomberg-resolved ticker (not just the
# ones that failed direct resolution) against the already-covered set. See
# module docstring point 3 for how this gap happened.
BLOOMBERG_FULL_CHECK_ADDITIONS: dict[int, str] = {
    10456: "Alpargatas S.A.",
    17892: "Santos Brasil Participações S.A.",
    18627: "Cia. de Saneamento do Paraná (Sanepar)",
    20362: "Positivo Tecnologia S.A.",
    20516: "São Martinho S.A.",
    20990: "Americanas S.A. - Em Recuperação Judicial",
    24910: "LWSA S/A (Locaweb)",
    25232: "Meliuz S.A.",
    25917: "Raízen S.A.",
    27707: "Automob Participações S.A.",
}

NEW_HISTORICAL_CD_CVM: dict[int, str] = {**WAYBACK_ADDITIONS, **BLOOMBERG_ADDITIONS, **BLOOMBERG_FULL_CHECK_ADDITIONS}
