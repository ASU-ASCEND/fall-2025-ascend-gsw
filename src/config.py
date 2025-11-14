from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
# DB_PATH = ROOT_DIR / "data/flight-data.db" # OLD DATABASE FILE with mock data
CSV_PATH = ROOT_DIR / "data/flight-data.csv"
DB_PATH = ROOT_DIR / "data/sqlite3.db"


# Socket configuration
UDP_HOST = "localhost"
UDP_PORT = 1337
