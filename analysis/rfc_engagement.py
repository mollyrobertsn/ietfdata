import argparse
import json
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ietfdata.rfcindex import RFCIndex

ERRATA_URL = "https://www.rfc-editor.org/api/v1/errata.json"


def load_errata(path):
    if path:
        with path.open(encoding="utf-8") as source:
            data = json.load(source)
    else:
        request = urllib.request.Request(
            ERRATA_URL,
            headers={"User-Agent": "RFC dissertation metadata analysis"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.load(response)

    if not isinstance(data, list):
        raise ValueError("The RFC Editor errata feed must contain a JSON list.")
    return data


def count_errata(errata, publication_dates):
    counts = {}
    for item in errata:
        doc_id = str(item.get("doc-id", "")).upper()
        if doc_id not in publication_dates:
            continue

        if doc_id not in counts:
            counts[doc_id] = {"total": 0, "within_5_years": 0}
        counts[doc_id]["total"] += 1

        submitted = item.get("submit_date")
        if submitted:
            report_date = date.fromisoformat(str(submitted)[:10])
            published = publication_dates[doc_id]
            months = (report_date.year - published.year) * 12
            months += report_date.month - published.month
            if 0 <= months < 60:
                counts[doc_id]["within_5_years"] += 1

    return counts


def build_rfc_rows(rfcs, errata_counts, current_year):
    rows = []
    keyword_counts = {}
    decade_keyword_counts = {}

    for rfc in rfcs:
        doc_id = str(rfc.doc_id).upper()
        abstract = ""
        if rfc.abstract is not None:
            abstract = " ".join(rfc.abstract.itertext()).strip()

        keywords = sorted(set(
            keyword.strip()
            for keyword in rfc.keywords
            if keyword.strip()
        ))
        decade = (rfc.year // 10) * 10
        for keyword in keywords:
            keyword = keyword.lower()
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
            decade_key = (decade, keyword)
            decade_keyword_counts[decade_key] = (
                decade_keyword_counts.get(decade_key, 0) + 1
            )

        metrics = errata_counts.get(doc_id, {})
        has_five_year_window = 2001 <= rfc.year <= current_year - 6
        title_and_abstract = f"{rfc.title} {abstract}"
        uppercase_tokens = set(
            re.findall(r"\b[A-Z][A-Z0-9-]{1,}\b", title_and_abstract)
        )

        rows.append({
            "rfc": doc_id,
            "year": rfc.year,
            "title": rfc.title,
            "pages": rfc.page_count,
            "author_count": len(rfc.authors),
            "working_group": rfc.wg or "",
            "publication_status": rfc.publ_status,
            "keywords": "; ".join(keywords),
            "keyword_count": len(keywords),
            "uppercase_tokens_title_abstract": len(uppercase_tokens),
            "errata_count": metrics.get("total", 0),
            "errata_reported_within_5_years": (
                metrics.get("within_5_years", 0)
                if has_five_year_window
                else pd.NA
            ),
        })

    keywords = [
        {"keyword": word, "rfc_count": count}
        for word, count in sorted(
            keyword_counts.items(), key=lambda item: item[1], reverse=True
        )
    ]
    decade_keywords = [
        {"decade": decade, "keyword": word, "rfc_count": count}
        for (decade, word), count in sorted(
            decade_keyword_counts.items(), key=lambda item: item[1], reverse=True
        )
    ]
    return pd.DataFrame(rows), pd.DataFrame(keywords), pd.DataFrame(decade_keywords)


def summarize_by_year(rfcs, current_year):
    summaries = []
    years = sorted(rfcs["year"].unique())

    for year in years:
        group = rfcs[rfcs["year"] == year]
        with_errata = group["errata_count"] > 0
        assigned_groups = group["working_group"].dropna()
        assigned_groups = assigned_groups[
            (assigned_groups != "")
            & (assigned_groups.str.upper() != "NON WORKING GROUP")
        ]
        five_year_counts = group["errata_reported_within_5_years"].dropna()

        summaries.append({
            "year": year,
            "rfc_count": len(group),
            "pct_with_any_errata": 100 * with_errata.mean(),
            "mean_errata_reported_within_5_years": five_year_counts.mean(),
            "pct_with_any_errata_within_5_years": (
                100 * (five_year_counts > 0).mean()
                if 2001 <= year <= current_year - 6
                else pd.NA
            ),
            "pct_with_keyword_metadata": 100 * (group["keyword_count"] > 0).mean(),
            "mean_keyword_count_per_rfc": group["keyword_count"].mean(),
            "mean_uppercase_tokens_title_abstract": (
                group["uppercase_tokens_title_abstract"].mean()
            ),
            "working_group_assigned_rfc_count": len(assigned_groups),
            "distinct_working_groups": assigned_groups.nunique(),
        })

    return pd.DataFrame(summaries)


def spearman_correlation(left, right):
    return left.rank().corr(right.rank())


def main():
    parser = argparse.ArgumentParser(
        description="Summarise RFC errata, keywords, and working groups."
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=ROOT / "excess" / "rfc-index.xml",
    )
    parser.add_argument(
        "--errata-json",
        type=Path,
        help="Use a saved errata feed instead of downloading it.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "analysis",
    )
    args = parser.parse_args()

    index = RFCIndex(rfc_index=str(args.index))
    rfcs = list(index.rfcs(stream="IETF"))
    publication_dates = {}
    for rfc in rfcs:
        doc_id = str(rfc.doc_id).upper()
        publication_dates[doc_id] = datetime.strptime(
            f"{rfc.month} {rfc.year}", "%B %Y"
        ).date()

    errata_counts = count_errata(
        load_errata(args.errata_json),
        publication_dates,
    )
    current_year = datetime.now().year
    per_rfc, keywords, decade_keywords = build_rfc_rows(
        rfcs, errata_counts, current_year
    )
    annual = summarize_by_year(per_rfc, current_year)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    per_rfc.to_csv(args.output_dir / "rfc_engagement_by_rfc.csv", index=False)
    annual.to_csv(args.output_dir / "rfc_engagement_by_year.csv", index=False)
    keywords.to_csv(args.output_dir / "rfc_keyword_frequency.csv", index=False)
    decade_keywords.to_csv(
        args.output_dir / "rfc_keyword_frequency_by_decade.csv",
        index=False,
    )

    complete_five_year_cohorts = per_rfc[
        per_rfc["errata_reported_within_5_years"].notna()
    ]
    page_correlation = spearman_correlation(
        complete_five_year_cohorts["errata_reported_within_5_years"],
        complete_five_year_cohorts["pages"],
    )
    author_correlation = spearman_correlation(
        complete_five_year_cohorts["errata_reported_within_5_years"],
        complete_five_year_cohorts["author_count"],
    )
    print(
        "Five-year errata correlations (pages, authors): "
        f"{page_correlation:.3f}, {author_correlation:.3f}"
    )
    print(f"Done. Results saved to {args.output_dir}.")


if __name__ == "__main__":
    main()
