#!/usr/bin/env python3
"""Migration script to add analog_temp_0_adc_val column to FlightTelemetry table."""

import logging
import sqlite3
from pathlib import Path

from src.config import DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_add_analog_temp():
    """Add analog_temp_0_adc_val column to FlightTelemetry table if it doesn't exist."""
    db_path = Path(DB_PATH)
    
    if not db_path.exists():
        logger.warning(f"Database not found at {DB_PATH}. Run init_database() first.")
        return False
    
    logger.info(f"Connecting to database at {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(FlightTelemetry)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "analog_temp_0_adc_val" in columns:
            logger.info("Column 'analog_temp_0_adc_val' already exists. Migration not needed.")
            return True
        
        # Add the new column
        logger.info("Adding column 'analog_temp_0_adc_val' to FlightTelemetry table...")
        cursor.execute(
            "ALTER TABLE FlightTelemetry ADD COLUMN analog_temp_0_adc_val INTEGER"
        )
        conn.commit()
        
        logger.info("✓ Successfully added 'analog_temp_0_adc_val' column")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    success = migrate_add_analog_temp()
    exit(0 if success else 1)

