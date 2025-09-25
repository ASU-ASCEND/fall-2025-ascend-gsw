import sqlite3
from src.config import DB_PATH

db = sqlite3.connect(DB_PATH)

print(db)
