import os
from pathlib import Path

# Get root directory
ROOT_DIR = Path(__file__).parent.parent.parent


# Ground software configuration
class GroundConfig:
    # Source configuration
    SOURCE = os.getenv("GSW_SOURCE", "csv")  # serial, csv, binlog

    # Serial configuration
    SERIAL_PORT = os.getenv("GSW_SERIAL_PORT", "/dev/ttyUSB0")
    SERIAL_BAUD = int(os.getenv("GSW_SERIAL_BAUD", "115200"))

    # CSV replay configuration
    CSV_PATH = os.getenv("GSW_CSV_PATH", str(ROOT_DIR / "data/spring-2025.csv"))
    REPLAY_SPEED = float(os.getenv("GSW_REPLAY_SPEED", "1.0"))  # 1.0 = real-time

    # Binary log configuration
    BINLOG_PATH = os.getenv(
        "GSW_BINLOG_PATH", str(ROOT_DIR / "data/flight-data.binlog")
    )

    # NDJSON persistence configuration
    NDJSON_DIR = Path(os.getenv("GSW_NDJSON_DIR", str(ROOT_DIR / "data/out")))
    NDJSON_MAX_SIZE_MB = int(
        os.getenv("GSW_NDJSON_MAX_SIZE_MB", "50")
    )  # Max file size before rotation

    # Config file path (for sensor configuration)
    CONFIG_PATH = str(ROOT_DIR / "old-groundstation/config.csv")

    # Pipeline configuration
    QUEUE_SIZE = int(os.getenv("GSW_QUEUE_SIZE", "1000"))
    BATCH_SIZE = int(os.getenv("GSW_BATCH_SIZE", "100"))

    @classmethod
    def validate(cls):
        """Validate configuration values"""
        if cls.SOURCE not in ["serial", "csv", "binlog"]:
            raise ValueError(f"Invalid source: {cls.SOURCE}")

        if cls.SOURCE == "csv" and not Path(cls.CSV_PATH).exists():
            raise FileNotFoundError(f"CSV file not found: {cls.CSV_PATH}")

        if cls.SOURCE == "binlog" and not Path(cls.BINLOG_PATH).exists():
            raise FileNotFoundError(f"Binary log file not found: {cls.BINLOG_PATH}")

        # Ensure NDJSON directory exists
        cls.NDJSON_DIR.mkdir(parents=True, exist_ok=True)

        return True
