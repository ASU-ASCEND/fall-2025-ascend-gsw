import csv
from pathlib import Path

from src.config import ROOT_DIR
from src.schema import FlightTelemetry, db

# with open(Path(ROOT_DIR, "data/spring-2025.csv")) as csvfile:
#     reader = csv.DictReader(csvfile)
#     db.connect()
#     for row in reader:
#         FlightTelemetry.insert(row).execute()
