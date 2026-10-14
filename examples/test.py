import json
from pathlib import Path

org_path = Path(
    r"C:\Users\Molly\OneDrive - University of Glasgow\Documents\4th_year\diss\organisations.json"
)

with org_path.open(encoding="utf-8") as file:
    organisations = json.load(file)

for org_id, org in organisations.items():
    print(org_id, org["names"], org["domains"])