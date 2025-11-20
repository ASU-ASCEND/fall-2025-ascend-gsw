"""Script to import CSV data into the flight telemetry database."""

import csv
import logging
from pathlib import Path

from peewee import FloatField, IntegerField

from src.config import DB_PATH, ROOT_DIR
from src.schema import FlightTelemetry, init_database

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def convert_value(value: str, field_type: type) -> int | float | None:
    """Convert CSV string value to appropriate type, handling empty strings."""
    if not value or value.strip() == "":
        return None
    try:
        if field_type is int:
            return int(float(value))  # Handle float strings that represent integers
        elif field_type is float:
            return float(value)
        else:
            return value
    except (ValueError, TypeError):
        return None


def import_csv_to_db(csv_path: Path, batch_size: int | None = None) -> None:
    """Import CSV data into the flight telemetry database.

    Args:
        csv_path: Path to the CSV file
        batch_size: Number of records to insert in each batch.
                   If None, automatically calculates based on SQLite's variable limit.
    """
    # Initialize database
    logger.info(f"Initializing database at {DB_PATH}")
    init_database()

    # Check if CSV file exists
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return

    logger.info(f"Reading CSV file: {csv_path}")

    # Get field types from the model
    field_types = {}
    for field_name, field in FlightTelemetry._meta.fields.items():
        if field_name == "raw_bytes":
            continue  # Skip raw_bytes field
        if isinstance(field, IntegerField):
            field_types[field_name] = int
        elif isinstance(field, FloatField):
            field_types[field_name] = float
        else:
            field_types[field_name] = str

    # Calculate safe batch size based on SQLite's variable limit (default 999)
    # Each field in each record counts as a variable
    num_fields = len(field_types)
    if batch_size is None:
        # SQLite default limit is 999 variables, leave some headroom
        sqlite_variable_limit = 999
        safe_batch_size = max(1, (sqlite_variable_limit // num_fields) - 1)
        batch_size = safe_batch_size
        logger.info(
            f"Auto-calculated batch size: {batch_size} records "
            f"(based on {num_fields} fields and SQLite limit of {sqlite_variable_limit})"
        )
    else:
        # Validate user-provided batch size
        max_safe_batch = 999 // num_fields
        if batch_size > max_safe_batch:
            logger.warning(
                f"Batch size {batch_size} may exceed SQLite variable limit. "
                f"Recommended max: {max_safe_batch}"
            )

    # Read CSV and insert data
    records_inserted = 0
    batch = []

    with open(csv_path, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Prepare data dictionary, converting values to appropriate types
                data = {}
                for field_name in field_types.keys():
                    csv_value = row.get(field_name, "")
                    data[field_name] = convert_value(csv_value, field_types[field_name])

                batch.append(data)

                # Insert batch when it reaches batch_size
                if len(batch) >= batch_size:
                    FlightTelemetry.insert_many(batch).execute()
                    records_inserted += len(batch)
                    logger.info(f"Inserted batch: {records_inserted} total records")
                    batch = []

            except Exception as e:
                logger.error(f"Error processing row {row_num}: {e}")
                continue

    # Insert remaining records
    if batch:
        FlightTelemetry.insert_many(batch).execute()
        records_inserted += len(batch)
        logger.info(f"Inserted final batch: {records_inserted} total records")

    logger.info(f"Import complete! Total records inserted: {records_inserted}")


if __name__ == "__main__":
    csv_path = ROOT_DIR / "data" / "spring-2025.csv"
    import_csv_to_db(csv_path)
