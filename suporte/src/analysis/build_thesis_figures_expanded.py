"""Regenerates every thesis figure in tese/latex/figures/ for the round-7
expanded universe (185 companies, 2010-2025), following the "adjust the
universe" step of the advisor's feedback (universe expansion first, prose
second). Quarterly (ITR) is excluded from every figure here: as a quarterly
document its effect/impact is economically distinct from the four annual
sources and doesn't have a clean rationale for sitting alongside them --
see the "reduce to four sources" text edit in tese_jonathan.tex. The
survivorship (delisting) boxplot is also NOT regenerated -- "saida do Ibovespa" is only
a meaningful outcome for the original 111-company IBOV panel (66 current +
45 historical); the 74 IBX-extra companies were never IBOV constituents,
so that specific check stays scoped to its original 111-company/2015-2024
sample, unchanged.

Usage:
    python -u -m src.analysis.build_thesis_figures_expanded
"""
from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.features.build_m0_m5_controls_extension import build_panel_extended

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
POC = ROOT / "data" / "interim" / "poc"
INTERIM = ROOT / "data" / "interim"
FIG_DIR = ROOT.parent / "tese" / "latex" / "figures"

plt.rcParams.update({
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})
C_CURRENT = "#2c5f8a"
C_HIST = "#8aa9c4"
C_IBX = "#d9a441"
C_MAIN = "#2c5f8a"
C_ACCENT = "#c0504d"


def load_company_categories() -> dict[int, str]:
    current = pd.read_csv(INTERIM / "ibov_non_financial_universe.csv")["CD_CVM"].astype(int)
    hist = pd.read_csv(INTERIM / "ibov_historical_notes_download_log.csv")["CD_CVM"].astype(int).unique()
    ibx = pd.read_csv(INTERIM / "ibx_extra_universe.csv", dtype={"CD_CVM": str})["CD_CVM"].astype(int)
    cats: dict[int, str] = {}
    for cd in ibx:
        cats[cd] = "IBX (nunca no Ibovespa)"
    for cd in hist:
        cats[cd] = "Histórica (saiu do Ibovespa)"
    for cd in current:
        cats[cd] = "Atual (Ibovespa)"
    return cats


def fig_sample_composition() -> None:
    df = pd.read_csv(POC / "similarity_results_full_history_reliable.csv", dtype={"cd_cvm": str})
    df["cd_cvm"] = df["cd_cvm"].astype(int)
    cats = load_company_categories()
    df["categoria"] = df["cd_cvm"].map(cats)
    counts = df.groupby(["year_curr", "categoria"]).size().unstack(fill_value=0)
    order = ["Atual (Ibovespa)", "Histórica (saiu do Ibovespa)", "IBX (nunca no Ibovespa)"]
    order = [c for c in order if c in counts.columns]
    counts = counts[order]

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = {"Atual (Ibovespa)": C_CURRENT, "Histórica (saiu do Ibovespa)": C_HIST, "IBX (nunca no Ibovespa)": C_IBX}
    bottom = np.zeros(len(counts))
    for cat in order:
        ax.bar(counts.index.astype(str), counts[cat], bottom=bottom, label=cat, color=colors[cat])
        bottom += counts[cat].values
    ax.set_xlabel("Exercício fiscal")
    ax.set_ylabel("Pares empresa-ano (extração confiável)")
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "sample_composition.png")
    plt.close(fig)
    totals = counts.sum()
    print("sample_composition.png:", dict(totals), "total:", int(totals.sum()))


def fig_abnormal_return_dist() -> None:
    df = pd.read_csv(POC / "abnormal_returns_alpha_full_expanded_universe.csv")
    x = df["BHAR_ajustado"]
    lo, hi = x.quantile([0.01, 0.99])
    x_trim = x.clip(lo, hi)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(x_trim, bins=40, color=C_MAIN, alpha=0.85, edgecolor="white")
    ax.axvline(x_trim.median(), color=C_ACCENT, linestyle="--", linewidth=1.5,
               label=f"Mediana = {x_trim.median():.1%}")
    ax.set_xlabel("BHAR ajustado (12 meses)")
    ax.set_ylabel("Frequência")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "abnormal_return_dist.png")
    plt.close(fig)
    print(f"abnormal_return_dist.png: n={len(df)}, empresas={df['cd_cvm'].nunique()}, mediana={x_trim.median():.4f}")


def fig_control_variables() -> None:
    ctrl = pd.read_csv(INTERIM / "control_variables_extension.csv")
    fig, axes = plt.subplots(2, 2, figsize=(9, 7))
    specs = [
        ("ln_total_assets", "Log(ativo total)", False),
        ("roa", "ROA", True),
        ("leverage", "Alavancagem", False),
        ("past_12m_return", "Retorno passado (12m)", True),
    ]
    for ax, (col, label, trim) in zip(axes.flat, specs):
        x = ctrl[col].dropna()
        if trim:
            lo, hi = x.quantile([0.01, 0.99])
            x = x.clip(lo, hi)
        ax.hist(x, bins=35, color=C_MAIN, alpha=0.85, edgecolor="white")
        ax.set_xlabel(label)
        ax.set_ylabel("Frequência")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "control_variables.png")
    plt.close(fig)
    print(f"control_variables.png: n={len(ctrl)}, empresas={ctrl['CD_CVM'].nunique()}")


def fig_m2_m3_controls() -> None:
    sample = pd.read_csv(POC / "abnormal_returns_alpha_full_expanded_universe.csv")
    panel = build_panel_extended(sample)

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
    specs_m2 = [("delta_roa", "$\\Delta$ROA"), ("delta_leverage", "$\\Delta$Alavancagem"), ("delta_debt", "$\\Delta$Dívida")]
    for ax, (col, label) in zip(axes, specs_m2):
        x = panel[col].dropna()
        lo, hi = x.quantile([0.01, 0.99])
        x = x.clip(lo, hi)
        ax.hist(x, bins=30, color=C_MAIN, alpha=0.85, edgecolor="white")
        ax.set_xlabel(label)
        ax.set_ylabel("Frequência")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "m2_controls.png")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8, 3.8))
    specs_m3 = [("btm", "Book-to-market"), ("volatility", "Volatilidade (desvio-padrão diário)")]
    for ax, (col, label) in zip(axes, specs_m3):
        x = panel[col].dropna()
        lo, hi = x.quantile([0.01, 0.99])
        x = x.clip(lo, hi)
        ax.hist(x, bins=30, color=C_MAIN, alpha=0.85, edgecolor="white")
        ax.set_xlabel(label)
        ax.set_ylabel("Frequência")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "m3_controls.png")
    plt.close(fig)
    n_pairs = len(panel)
    cov = panel[["delta_roa", "delta_leverage", "delta_debt", "btm", "volatility"]].notna().sum()
    print(f"m2_controls.png / m3_controls.png: n={n_pairs}")
    print(cov.to_string())


def fig_similarity_by_source() -> None:
    # Quarterly (ITR) dropped per user decision: as a quarterly document its
    # effect/impact is economically distinct from the annual sources and
    # doesn't have a clean rationale for sitting alongside them here -- see
    # the round-8 "reduce to four sources" edit.
    sources = {
        "Nota de dívida\n(anual, confiável)": POC / "similarity_results_full_history_reliable.csv",
        "Conjunto completo\nde notas": POC / "full_notes_similarity_results_full_history.csv",
        "Relatório da\nAdministração": POC / "mgmt_report_similarity_results_full_history.csv",
        "Fatores de Risco\n(FRE)": POC / "risk_factors_similarity_results_full_history.csv",
    }
    data, labels, medians = [], [], []
    for label, path in sources.items():
        s = pd.read_csv(path)["cosine_similarity"].dropna()
        data.append(s.values)
        labels.append(label)
        medians.append(s.median())
        print(f"  {label.replace(chr(10), ' ')}: n={len(s)}, mediana={s.median():.3f}")

    fig, ax = plt.subplots(figsize=(9, 5))
    bp = ax.boxplot(data, labels=labels, patch_artist=True, showfliers=True,
                     medianprops={"color": C_ACCENT, "linewidth": 2},
                     flierprops={"markersize": 3, "alpha": 0.4})
    for patch in bp["boxes"]:
        patch.set_facecolor(C_MAIN)
        patch.set_alpha(0.5)
    ax.set_ylabel("Similaridade de cosseno (ano a ano)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "similarity_by_source.png")
    plt.close(fig)


def fig_similarity_raw_vs_reliable() -> None:
    allp = pd.read_csv(POC / "similarity_results_full_history.csv")["cosine_similarity"].dropna()
    rel = pd.read_csv(POC / "similarity_results_full_history_reliable.csv")["cosine_similarity"].dropna()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bins = np.linspace(0, 1, 41)
    ax.hist(allp, bins=bins, alpha=0.5, label=f"Todos os pares (n={len(allp)})", color=C_HIST, density=True)
    ax.hist(rel, bins=bins, alpha=0.6, label=f"Extração confiável (n={len(rel)})", color=C_MAIN, density=True)
    ax.set_xlabel("Similaridade de cosseno")
    ax.set_ylabel("Densidade")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "similarity_raw_vs_reliable.png")
    plt.close(fig)
    print(f"raw vs reliable: média bruta={allp.mean():.3f}/mediana={allp.median():.3f}  "
          f"média confiável={rel.mean():.3f}/mediana={rel.median():.3f}")


def fig_extraction_hardening_trajectory() -> None:
    rounds = ["Rodada 4\n(111 empresas)", "Rodada 5", "Rodada 6\n(997 arq.)",
              "Rodada 6\nno corpus completo", "Rodada 7\n(2.129 arq.)"]
    values = [43.8, 65.0, 69.7, 77.5, 80.3]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot(rounds, values, marker="o", color=C_MAIN, linewidth=2, markersize=7)
    for i, v in enumerate(values):
        ax.annotate(f"{v:.1f}%", (i, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_ylabel("Taxa de extração confiável (font_heading)")
    ax.set_ylim(35, 90)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "extraction_hardening_trajectory.png")
    plt.close(fig)


def fig_extraction_reliability() -> None:
    labels = ["Nota de dívida\n(anual)", "Relatório da\nAdministração", "Fatores de Risco\n(FRE)"]
    values = [80.3, 71.5, 96.6]
    metric = ["Confiabilidade\nde extração", "Cobertura de\naquisição", "Cobertura de\naquisição"]
    colors = [C_MAIN, C_IBX, C_IBX]

    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(labels, values, color=colors, alpha=0.85)
    for bar, v, m in zip(bars, values, metric):
        ax.annotate(f"{v:.1f}%\n({m})", (bar.get_x() + bar.get_width() / 2, v),
                    textcoords="offset points", xytext=(0, 6), ha="center", fontsize=9)
    ax.set_ylabel("%")
    ax.set_ylim(0, 110)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "extraction_reliability.png")
    plt.close(fig)


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print("=== sample_composition ===")
    fig_sample_composition()
    print("\n=== abnormal_return_dist ===")
    fig_abnormal_return_dist()
    print("\n=== control_variables ===")
    fig_control_variables()
    print("\n=== m2/m3 controls ===")
    fig_m2_m3_controls()
    print("\n=== similarity_by_source ===")
    fig_similarity_by_source()
    print("\n=== similarity_raw_vs_reliable ===")
    fig_similarity_raw_vs_reliable()
    print("\n=== extraction_hardening_trajectory ===")
    fig_extraction_hardening_trajectory()
    print("\n=== extraction_reliability ===")
    fig_extraction_reliability()
    print("\nAll figures written to", FIG_DIR)


if __name__ == "__main__":
    main()
