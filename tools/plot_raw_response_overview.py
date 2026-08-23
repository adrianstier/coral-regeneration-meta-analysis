#!/usr/bin/env python3
"""Plot the current raw legacy extraction rows by response variable."""

from __future__ import annotations

import csv
import os
import textwrap
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLOT_CACHE = Path("/tmp/coral-regeneration-meta-analysis-plot-cache")
os.environ["XDG_CACHE_HOME"] = str(PLOT_CACHE)
os.environ["MPLCONFIGDIR"] = str(PLOT_CACHE / "matplotlib")
os.environ["MPLBACKEND"] = "Agg"
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402


EXTRACTION_DIR = ROOT / "data" / "extraction"
OUT_DIR = ROOT / "figures"
PLOT_DATA = OUT_DIR / "raw_response_overview_plot_data.csv"
SOURCE_INDEX = OUT_DIR / "raw_response_overview_source_index.csv"
PNG_OUT = OUT_DIR / "raw_response_overview.png"
PDF_OUT = OUT_DIR / "raw_response_overview.pdf"

RATE_FILE = EXTRACTION_DIR / "EXTRACTION_RATES.csv"
FITNESS_FILE = EXTRACTION_DIR / "EXTRACTION_FITNESS.csv"
SURVIVAL_FILE = EXTRACTION_DIR / "EXTRACTION_SURVIVAL.csv"

OKABE_ITO = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "sky": "#56B4E9",
    "black": "#000000",
}

PLOT_FIELDS = [
    "source_table",
    "data_file",
    "csv_line",
    "source_id",
    "author",
    "year",
    "species",
    "response_type",
    "plot_panel",
    "condition",
    "value",
    "value_unit",
    "variance_type",
    "variance_value",
    "sample_size",
    "row_label",
    "qa_status",
    "notes",
]

SOURCE_INDEX_FIELDS = [
    "source_table",
    "data_file",
    "csv_line",
    "source_id",
    "author",
    "year",
    "species",
    "response_type",
    "plot_status",
    "raw_value_summary",
    "qa_status",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def as_float(value: str) -> float | None:
    try:
        if str(value).strip() == "":
            return None
        return float(value)
    except ValueError:
        return None


def short_label(row: dict[str, str], extra: str = "", width: int = 58) -> str:
    base = f"{row.get('Author', '').strip()} {row.get('Year', '').strip()} | {row.get('Species', '').strip()}"
    if extra:
        base = f"{base} | {extra}"
    return textwrap.shorten(" ".join(base.split()), width=width, placeholder="...")


def common_fields(
    row: dict[str, str],
    source_table: str,
    csv_line: int,
    response_type: str,
    plot_panel: str,
    condition: str,
    value: float,
    value_unit: str,
    variance_type: str = "",
    variance_value: str = "",
    sample_size: str = "",
    label_extra: str = "",
) -> dict[str, object]:
    return {
        "source_table": source_table,
        "data_file": f"data/extraction/{source_table}",
        "csv_line": csv_line,
        "source_id": row.get("source_id", ""),
        "author": row.get("Author", ""),
        "year": row.get("Year", ""),
        "species": row.get("Species", ""),
        "response_type": response_type,
        "plot_panel": plot_panel,
        "condition": condition,
        "value": value,
        "value_unit": value_unit,
        "variance_type": variance_type,
        "variance_value": variance_value,
        "sample_size": sample_size,
        "row_label": short_label(row, label_extra),
        "qa_status": row.get("qa_status", ""),
        "notes": row.get("Notes", ""),
    }


def build_plot_rows() -> list[dict[str, object]]:
    plot_rows: list[dict[str, object]] = []

    for index, row in enumerate(read_csv(RATE_FILE), start=2):
        value = as_float(row.get("Rate_Value", ""))
        if value is None:
            continue
        plot_rows.append(
            common_fields(
                row=row,
                source_table="EXTRACTION_RATES.csv",
                csv_line=index,
                response_type="rate",
                plot_panel="A_rate",
                condition="reported",
                value=value,
                value_unit=row.get("Rate_Unit", ""),
                variance_type=row.get("Variance_Type", ""),
                variance_value=row.get("Variance_Value", ""),
                sample_size=row.get("Sample_Size", ""),
                label_extra=row.get("Rate_Unit", ""),
            )
        )

    for index, row in enumerate(read_csv(FITNESS_FILE), start=2):
        response_type = row.get("response_type", "")
        if response_type not in {"growth", "reproduction"}:
            continue
        panel = "B_growth" if response_type == "growth" else "C_reproduction"
        for condition, value_field, variance_field in [
            ("control", "Control_Mean", "Control_Var"),
            ("wounded", "Wounded_Mean", "Wounded_Var"),
        ]:
            value = as_float(row.get(value_field, ""))
            if value is None:
                continue
            plot_rows.append(
                common_fields(
                    row=row,
                    source_table="EXTRACTION_FITNESS.csv",
                    csv_line=index,
                    response_type=response_type,
                    plot_panel=panel,
                    condition=condition,
                    value=value,
                    value_unit=row.get("Outcome_Type", ""),
                    variance_type=row.get("Var_Type", ""),
                    variance_value=row.get(variance_field, ""),
                    sample_size=row.get("Sample_Size", ""),
                    label_extra=row.get("Outcome_Type", ""),
                )
            )

    for index, row in enumerate(read_csv(SURVIVAL_FILE), start=2):
        for condition, total_field, dead_field in [
            ("control", "Control_Total", "Control_Dead"),
            ("wounded", "Wounded_Total", "Wounded_Dead"),
        ]:
            total = as_float(row.get(total_field, ""))
            dead = as_float(row.get(dead_field, ""))
            if total is None or dead is None or total <= 0:
                continue
            plot_rows.append(
                common_fields(
                    row=row,
                    source_table="EXTRACTION_SURVIVAL.csv",
                    csv_line=index,
                    response_type="survival",
                    plot_panel="D_survival",
                    condition=condition,
                    value=dead / total * 100.0,
                    value_unit="% dead from raw dead/total",
                    variance_type="raw_counts",
                    variance_value=f"{int(dead)}/{int(total)}",
                    sample_size=str(int(total)),
                    label_extra=row.get("Stressor", ""),
                )
            )

    return plot_rows


def source_index_row(
    row: dict[str, str],
    source_table: str,
    csv_line: int,
    response_type: str,
    plot_status: str,
    raw_value_summary: str,
) -> dict[str, object]:
    return {
        "source_table": source_table,
        "data_file": f"data/extraction/{source_table}",
        "csv_line": csv_line,
        "source_id": row.get("source_id", ""),
        "author": row.get("Author", ""),
        "year": row.get("Year", ""),
        "species": row.get("Species", ""),
        "response_type": response_type,
        "plot_status": plot_status,
        "raw_value_summary": raw_value_summary,
        "qa_status": row.get("qa_status", ""),
        "notes": row.get("Notes", ""),
    }


def build_source_index_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, row in enumerate(read_csv(RATE_FILE), start=2):
        value = as_float(row.get("Rate_Value", ""))
        status = "plotted_rate_value" if value is not None else "not_plotted_missing_rate_value"
        rows.append(
            source_index_row(
                row,
                "EXTRACTION_RATES.csv",
                index,
                "rate",
                status,
                f"Rate_Value={row.get('Rate_Value', '')}; Rate_Unit={row.get('Rate_Unit', '')}; Sample_Size={row.get('Sample_Size', '')}",
            )
        )

    for index, row in enumerate(read_csv(FITNESS_FILE), start=2):
        response_type = row.get("response_type", "")
        control = as_float(row.get("Control_Mean", ""))
        wounded = as_float(row.get("Wounded_Mean", ""))
        status = "plotted_control_wounded_means" if control is not None and wounded is not None else "not_plotted_missing_mean"
        rows.append(
            source_index_row(
                row,
                "EXTRACTION_FITNESS.csv",
                index,
                response_type,
                status,
                (
                    f"Outcome_Type={row.get('Outcome_Type', '')}; Control_Mean={row.get('Control_Mean', '')}; "
                    f"Wounded_Mean={row.get('Wounded_Mean', '')}; Sample_Size={row.get('Sample_Size', '')}"
                ),
            )
        )

    for index, row in enumerate(read_csv(SURVIVAL_FILE), start=2):
        control_total = as_float(row.get("Control_Total", ""))
        wounded_total = as_float(row.get("Wounded_Total", ""))
        status = (
            "plotted_mortality_proportions"
            if control_total is not None and control_total > 0 and wounded_total is not None and wounded_total > 0
            else "not_plotted_zero_or_missing_total"
        )
        rows.append(
            source_index_row(
                row,
                "EXTRACTION_SURVIVAL.csv",
                index,
                "survival",
                status,
                (
                    f"Control_Dead/Total={row.get('Control_Dead', '')}/{row.get('Control_Total', '')}; "
                    f"Wounded_Dead/Total={row.get('Wounded_Dead', '')}/{row.get('Wounded_Total', '')}; "
                    f"Duration_Days={row.get('Duration_Days', '')}"
                ),
            )
        )
    return rows


def unique_row_order(rows: list[dict[str, object]], panel: str) -> list[str]:
    ordered: list[str] = []
    seen = set()
    for row in rows:
        if row["plot_panel"] != panel:
            continue
        key = f"{row['source_table']}:{row['csv_line']}:{row['row_label']}"
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def panel_rows(rows: list[dict[str, object]], panel: str) -> list[dict[str, object]]:
    return [row for row in rows if row["plot_panel"] == panel]


def style_axis(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    ax.set_axisbelow(True)


def plot_rate_panel(ax, rows: list[dict[str, object]]) -> None:
    ordered = unique_row_order(rows, "A_rate")
    labels = {f"{row['source_table']}:{row['csv_line']}:{row['row_label']}": row["row_label"] for row in rows}
    units = sorted({str(row["value_unit"]) for row in panel_rows(rows, "A_rate")})
    palette = [OKABE_ITO["blue"], OKABE_ITO["orange"], OKABE_ITO["green"], OKABE_ITO["purple"]]
    unit_color = {unit: palette[index % len(palette)] for index, unit in enumerate(units)}
    for row in panel_rows(rows, "A_rate"):
        key = f"{row['source_table']}:{row['csv_line']}:{row['row_label']}"
        y = ordered.index(key)
        ax.scatter(float(row["value"]), y, s=42, color=unit_color[str(row["value_unit"])], edgecolor="black", linewidth=0.4)
    ax.axvline(0, color="#777777", linewidth=0.8, linestyle=":")
    ax.set_yticks(range(len(ordered)))
    ax.set_yticklabels([labels[key] for key in ordered], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Reported rate value (native units)")
    ax.set_title(f"A  Regeneration rate rows (n={len(ordered)})", loc="left", fontweight="bold")
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=color, markeredgecolor="black", label=unit, markersize=6)
        for unit, color in unit_color.items()
    ]
    ax.legend(handles=handles, title="Rate unit", frameon=False, fontsize=7, title_fontsize=8, loc="lower right")
    style_axis(ax)


def plot_paired_panel(ax, rows: list[dict[str, object]], panel: str, title: str, xlabel: str) -> None:
    panel_specific = panel_rows(rows, panel)
    ordered = unique_row_order(rows, panel)
    labels = {f"{row['source_table']}:{row['csv_line']}:{row['row_label']}": row["row_label"] for row in panel_specific}
    by_key: dict[str, dict[str, dict[str, object]]] = {}
    for row in panel_specific:
        key = f"{row['source_table']}:{row['csv_line']}:{row['row_label']}"
        by_key.setdefault(key, {})[str(row["condition"])] = row
    for key in ordered:
        y = ordered.index(key)
        control = by_key.get(key, {}).get("control")
        wounded = by_key.get(key, {}).get("wounded")
        if control and wounded:
            ax.plot([float(control["value"]), float(wounded["value"])], [y, y], color="#bdbdbd", linewidth=1.2, zorder=1)
        if control:
            ax.scatter(float(control["value"]), y, s=42, facecolor="white", edgecolor=OKABE_ITO["orange"], linewidth=1.4, zorder=2)
        if wounded:
            ax.scatter(float(wounded["value"]), y, s=42, facecolor=OKABE_ITO["blue"], edgecolor=OKABE_ITO["blue"], linewidth=0.6, zorder=3)
    ax.set_yticks(range(len(ordered)))
    ax.set_yticklabels([labels[key] for key in ordered], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontweight="bold")
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor=OKABE_ITO["orange"], label="control", markersize=6),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=OKABE_ITO["blue"], markeredgecolor=OKABE_ITO["blue"], label="wounded", markersize=6),
    ]
    ax.legend(handles=handles, frameon=False, fontsize=7, loc="best")
    style_axis(ax)


def make_figure(plot_rows: list[dict[str, object]], source_index_rows: list[dict[str, object]]) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 10,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "figure.dpi": 150,
        }
    )

    fig, axes = plt.subplots(2, 2, figsize=(14, 10.5))
    plot_rate_panel(axes[0, 0], plot_rows)
    growth_count = len(unique_row_order(plot_rows, "B_growth"))
    reproduction_count = len(unique_row_order(plot_rows, "C_reproduction"))
    survival_count = len(unique_row_order(plot_rows, "D_survival"))
    plot_paired_panel(
        axes[0, 1],
        plot_rows,
        "B_growth",
        f"B  Growth/calcification rows (n={growth_count})",
        "Reported mean (native outcome units)",
    )
    plot_paired_panel(
        axes[1, 0],
        plot_rows,
        "C_reproduction",
        f"C  Reproduction rows (n={reproduction_count})",
        "Reported mean (native outcome units)",
    )
    plot_paired_panel(
        axes[1, 1],
        plot_rows,
        "D_survival",
        f"D  Survival rows (n={survival_count})",
        "Mortality (% dead from raw counts)",
    )

    qa_counts = Counter(row["qa_status"] for row in plot_rows)
    qa_text = ", ".join(f"{status}: {count}" for status, count in sorted(qa_counts.items()))
    indexed_source_rows = len(source_index_rows)
    plotted_source_rows = len({(row["source_table"], row["csv_line"]) for row in plot_rows})
    not_plotted_rows = indexed_source_rows - plotted_source_rows
    not_plotted_text = f"{indexed_source_rows} source rows indexed; {plotted_source_rows} numeric-plottable rows shown"
    if not_plotted_rows:
        not_plotted_text += f"; {not_plotted_rows} row not plotted because totals/values are missing or non-positive"
    fig.suptitle("Raw extracted response data currently in data/extraction/", fontsize=14, fontweight="bold", y=0.985)
    fig.text(
        0.5,
        0.945,
        "Exploratory view of legacy extracted rows. Values are shown in native reported units and are not standardized effect sizes.",
        ha="center",
        fontsize=9,
    )
    fig.text(
        0.5,
        0.035,
        f"{not_plotted_text}.",
        ha="center",
        fontsize=8,
    )
    fig.text(
        0.5,
        0.017,
        f"Provenance status across plotted points: {qa_text}. Data-file mapping: figures/raw_response_overview_source_index.csv.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=[0.02, 0.075, 0.98, 0.92], h_pad=2.2, w_pad=2.0)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG_OUT, dpi=300)
    fig.savefig(PDF_OUT)
    plt.close(fig)


def main() -> int:
    plot_rows = build_plot_rows()
    source_index_rows = build_source_index_rows()
    write_csv(PLOT_DATA, PLOT_FIELDS, plot_rows)
    write_csv(SOURCE_INDEX, SOURCE_INDEX_FIELDS, source_index_rows)
    make_figure(plot_rows, source_index_rows)
    source_rows = {
        (row["source_table"], row["csv_line"])
        for row in plot_rows
    }
    print(f"Wrote plot data: {PLOT_DATA.relative_to(ROOT)}")
    print(f"Wrote source index: {SOURCE_INDEX.relative_to(ROOT)}")
    print(f"Wrote PNG: {PNG_OUT.relative_to(ROOT)}")
    print(f"Wrote PDF: {PDF_OUT.relative_to(ROOT)}")
    print(f"Indexed source rows: {len(source_index_rows)}")
    print(f"Plotted source rows: {len(source_rows)}")
    print(f"Plotted points: {len(plot_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
