import csv
import json
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

def load_crm_tasks():
    """Load CRM tasks from CSV file"""
    with open(RAW_DIR / "crm_tasks.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def load_erp_materials():
    """Load ERP materials from JSON file"""
    with open(RAW_DIR / "erp_materials.json", encoding="utf-8") as f:
        return json.load(f)

def load_technician_logs():
    """Load technician logs from CSV file"""
    with open(RAW_DIR / "technician_logs.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))
