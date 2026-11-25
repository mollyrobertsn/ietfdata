import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ietfdata.rfcindex import RFCIndex


def plot_trends(summary, output_path, stream):
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError(
            "Plotting requires matplotlib. Install it with "
            "`python -m pip install matplotlib`."
        ) from error

    figure, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    title_stream = stream if stream is not None else "all streams"
    figure.suptitle(f"RFC trends by publication year ({title_stream})")

    axes[0].plot(summary["year"], summary["rfc_count"], marker="o")
    axes[0].set_ylabel("RFCs published")
    axes[0].set_title("Annual publication count")

    axes[1].fill_between(
        summary["year"],
        summary["page_q1"],
        summary["page_q3"],
        alpha=0.25,
        label="Interquartile range (Q1-Q3)",
    )
    axes[1].plot(summary["year"], summary["mean_pages"], marker="o", label="Mean")
    axes[1].set_ylabel("Pages")
    axes[1].set_title("RFC length")
    axes[1].legend()

    axes[2].fill_between(
        summary["year"],
        summary["author_count_q1"],
        summary["author_count_q3"],
        alpha=0.25,
        label="Interquartile range (Q1-Q3)",
    )
    axes[2].plot(
        summary["year"],
        summary["mean_author_count"],
        marker="o",
        label="Mean",
    )
    axes[2].set_xlabel("Publication year")
    axes[2].set_ylabel("Authors per RFC")
    axes[2].set_title("RFC authorship")
    axes[2].legend()

    for axis in axes:
        axis.grid(axis="y", alpha=0.3)

    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(
        description="Summarise annual RFC publication, length, and authorship trends."
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=ROOT / "excess" / "rfc-index.xml",
        help="Path to an RFC index XML snapshot.",
    )
    parser.add_argument(
        "--stream",
        default="IETF",
        help="RFC stream to include; use 'all' to include every stream.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "analysis" / "rfc_trends.csv",
        help="Output path for the annual summary CSV.",
    )
    parser.add_argument(
        "--figure",
        type=Path,
        default=ROOT / "analysis" / "rfc_trends.png",
        help="Output path for the annual trends figure.",
    )
    parser.add_argument(
        "--dissertation-figure",
        type=Path,
        default=ROOT / "dissertation" / "images" / "rfc_trends.png",
        help="Output path for the figure included in the dissertation.",
    )
    args = parser.parse_args()
    stream = None if args.stream.lower() == "all" else args.stream

    index = RFCIndex(rfc_index=str(args.index))
    records = []
    for rfc in index.rfcs():
        if stream is not None and rfc.stream != stream:
            continue
        records.append({
            "rfc": rfc.doc_id,
            "year": rfc.year,
            "pages": rfc.page_count,
            "author_count": len(rfc.authors),
            "stream": rfc.stream,
        })

    if not records:
        selected_stream = stream if stream is not None else "all streams"
        raise ValueError(f"No RFC records found for {selected_stream}.")

    rfcs = pd.DataFrame.from_records(records)
    summary = (
        rfcs.groupby("year")
        .agg(
            rfc_count=("rfc", "count"),
            mean_pages=("pages", "mean"),
            page_q1=("pages", lambda values: values.quantile(0.25)),
            page_q3=("pages", lambda values: values.quantile(0.75)),
            mean_author_count=("author_count", "mean"),
            author_count_q1=("author_count", lambda values: values.quantile(0.25)),
            author_count_q3=("author_count", lambda values: values.quantile(0.75)),
            total_author_slots=("author_count", "sum"),
        )
        .reset_index()
        .sort_values("year")
    )

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(args.csv, index=False)
    plot_trends(summary, args.figure, stream)
    if args.dissertation_figure != args.figure:
        plot_trends(summary, args.dissertation_figure, stream)

    print(summary.tail(10).to_string(index=False))
    print(f"Saved annual summary to {args.csv}")
    print(f"Saved trends figure to {args.figure}")
    if args.dissertation_figure != args.figure:
        print(f"Saved dissertation figure to {args.dissertation_figure}")


if __name__ == "__main__":
    main()
