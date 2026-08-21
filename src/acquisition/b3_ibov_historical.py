"""Historical (not just current) Ibovespa membership, 2013-2021, resolved to
CD_CVM. Fixes a real survivorship-bias gap in the original IBOV tranche
(`b3_ibov.py`): that module resolves *today's* IBOV composition only, so any
company that was in the index at some point in 2015-2024 but has since been
removed -- delisted, bankrupt, acquired, or just fell out on liquidity -- was
entirely absent. That's a serious gap for a thesis about debt-distress
signals specifically, since distressed companies are exactly the ones most
likely to both show large textual change *and* drop out of the index.

B3's live composition API (GetPortfolioDay, used in b3_ibov.py) does not
accept a historical date -- confirmed empirically, it ignores every
plausible date/year/month parameter and always returns today's portfolio.
There is no historical-composition endpoint or downloadable series on B3's
current site.

What does work: the Internet Archive has snapshots of B3's now-retired
"ResumoCarteiraQuadrimestre.aspx" portfolio page (the pre-2021 legacy site,
under two URL generations) at various points in time, each showing the
IBOV constituent list valid for that snapshot's 4-month rebalance period.
Real, verified periods recovered this way:

    2013-11-27, 2014-07-23, 2015-09-23, 2016-02-29,
    Jan-Apr 2019, Sep-Dec 2019, Sep-Dec 2020, Jan-Apr 2021

IMPORTANT LIMITATION: this does not cover every quadrimestre in
2015-2024 -- there are real gaps (most of 2016-2018, and all of 2022-2024,
have no archived snapshot of this page). The company list below is the
union of tickers seen across the periods that ARE recovered, resolved to
CD_CVM via the current B3 registry (`b3_ibov.fetch_b3_company_registry`)
where the company is still listed under a matching issuer code, plus manual
lookup in CVM's cadastral registry (`cvm_dfp.load_cadastral`, which retains
CANCELADA/delisted entries) for tickers that no longer resolve via the live
registry (renamed, merged away, or fully delisted). It is a real, evidenced
improvement on "current members only," but not a complete quadrimestre-by-
quadrimestre reconstruction. If more precision is needed later, filling the
2016-2018 and 2022-2024 gaps would need either more Wayback digging, a
paid provider (Bloomberg/Economatica both carry historical index
membership), or manually sourced B3 rebalance announcements.

A handful of tickers seen in the archived snapshots were NOT resolved
(genuinely delisted/deregistered older names not yet chased down further,
diminishing-returns cutoff): ALLL3 (ALL - América Latina Logística),
BTOW3 (B2W Digital), OGXP3 (OGX Petróleo), LLXL3 (LLX Logística), VVAR3
(Via Varejo). Several other unmatched tickers turned out to be old tickers
of companies already covered under a later name (Ambev, Fibria->Suzano,
Estácio->Yduqs, Kroton->Cogna, Tractebel->Engie, CTEEP->ISA Energia) or
financial-sector entities correctly excluded (Cetip, BM&FBovespa/Bovespa
Holding, SulAmérica).
"""
from __future__ import annotations

# CD_CVM codes found in IBOV during at least one recovered historical period
# (2013-2021) but not in the current (2026) composition. See module
# docstring for the methodology and its limitations.
NEW_HISTORICAL_CD_CVM: dict[int, str] = {
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
