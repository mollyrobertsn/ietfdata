from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ietfdata.rfcindex import RFCIndex

index = RFCIndex(rfc_index=str(ROOT / "excess" / "rfc-index.xml"))

records = [
    {
        "rfc": rfc.doc_id,
        "year": rfc.year,
        "stream": rfc.stream,
        "pages": rfc.page_count,
        "author_slots": len(rfc.authors),
    }
    for rfc in index.rfcs()
]

rfcs = pd.DataFrame(records)
yearly = (
    rfcs[rfcs["stream"] == "IETF"]
    .groupby("year")
    .agg(
        rfc_count=("rfc", "count"),
        median_pages=("pages", "median"),
        median_author_slots=("author_slots", "median"),
        mean_author_slots=("author_slots", "mean"),
    )
    .reset_index()
)

output = ROOT / "analysis" / "rfc_yearly_summary.csv"
output.parent.mkdir(exist_ok=True)
yearly.to_csv(output, index=False)
print(yearly.tail(10).to_string(index=False))
print(f"Saved {output}")