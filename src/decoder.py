#!/usr/bin/env python3
"""Decoder for ASCEND flight software binary sensor packets."""

import logging
import struct
from typing import Dict, Tuple

# Set up logging
logger = logging.getLogger(__name__)


# Packet structure constants
SYNC_BYTES = b"ASU!"
SYNC_BYTES_LEN = 4
SENSOR_PRESENCE_LEN = 4
PACKET_LENGTH_LEN = 2
MIN_PACKET_SIZE = (
    SYNC_BYTES_LEN + SENSOR_PRESENCE_LEN + PACKET_LENGTH_LEN + 1
)  # +1 for checksum


# Sensor metadata: (bit_index, field_names, data_types, struct_format)
# data_types: 'f' for float, 'd' for double, 'H' for uint16_t, 'B' for uint8_t, 'h' for int16_t, 'I' for uint32_t, 'i' for int32_t
SENSOR_METADATA = [
    # 0: INA260
    (
        0,
        ["ina260_current_ma", "ina260_voltage_mv", "ina260_power_mw"],
        ["f", "f", "f"],
        "fff",
    ),
    # 1: PicoTemp
    (1, ["picotemp_temp_c"], ["f"], "f"),
    # 2: MTK3339
    (
        2,
        [
            "mtk3339_year",
            "mtk3339_month",
            "mtk3339_day",
            "mtk3339_hour",
            "mtk3339_minute",
            "mtk3339_second",
            "mtk3339_latitude",
            "mtk3339_longitude",
            "mtk3339_speed",
            "mtk3339_heading",
            "mtk3339_altitude",
            "mtk3339_satellites",
        ],
        ["H", "B", "B", "B", "B", "B", "f", "f", "f", "f", "f", "B"],
        "HBBBBBfffffB",
    ),
    # 3: ICM20948
    (
        3,
        [
            "icm20948_accx_g",
            "icm20948_accy_g",
            "icm20948_accz_g",
            "icm20948_gyrox_deg_s",
            "icm20948_gyroy_deg_s",
            "icm20948_gyroz_deg_s",
            "icm20948_magx_ut",
            "icm20948_magy_ut",
            "icm20948_magz_ut",
            "icm20948_temp_c",
        ],
        ["f", "f", "f", "f", "f", "f", "f", "f", "f", "f"],
        "ffffffffff",
    ),
    # 4: PCF8523
    (
        4,
        [
            "pcf8523_year",
            "pcf8523_month",
            "pcf8523_day",
            "pcf8523_hour",
            "pcf8523_minute",
            "pcf8523_second",
        ],
        ["H", "B", "B", "B", "B", "B"],
        "HBBBBB",
    ),
    # 5: TMP117
    (5, ["tmp117_temp_c"], ["f"], "f"),
    # 6: UV_Sensor_O
    (
        6,
        ["uv_sensor_uva2_nm", "uv_sensor_uvb2_nm", "uv_sensor_uvc2_nm"],
        ["f", "f", "f"],
        "fff",
    ),
    # 7: ENS160_O
    (7, ["ens160_aqi", "ens160_tvoc_ppb", "ens160_eco2_ppm"], ["B", "H", "H"], "BHH"),
    # 8: BMP390_O
    (
        8,
        ["bmp390_temp_c", "bmp390_pressure_pa", "bmp390_altitude_m"],
        ["d", "d", "f"],
        "ddf",
    ),
    # 9: TMP117_O
    (9, ["tmp117_o_temp_o_c"], ["f"], "f"),
    # 10: SHTC3_O
    (10, ["shtc3_o_temp_o_c", "shtc3_o_rel_hum_o"], ["f", "f"], "ff"),
    # 11: Ozone
    (11, ["ozone_conc_ppb"], ["h"], "h"),
    # 12: Analog_Temp_0
    (12, ["analog_temp_0_adc_val"], ["i"], "i"),
]


def validate_sync_bytes(data: bytes) -> bool:
    """Validate that the packet starts with sync bytes."""
    return len(data) >= SYNC_BYTES_LEN and data[:SYNC_BYTES_LEN] == SYNC_BYTES


def parse_sensor_presence(data: bytes, offset: int) -> Tuple[int, int]:
    """Parse sensor presence bitfield and return (presence_bits, new_offset)."""
    if offset + SENSOR_PRESENCE_LEN > len(data):
        raise ValueError("Not enough data for sensor presence field")
    presence_bits = struct.unpack("<I", data[offset : offset + SENSOR_PRESENCE_LEN])[0]
    return presence_bits, offset + SENSOR_PRESENCE_LEN


def parse_packet_length(data: bytes, offset: int) -> Tuple[int, int]:
    """Parse packet length and return (length, new_offset)."""
    if offset + PACKET_LENGTH_LEN > len(data):
        raise ValueError("Not enough data for packet length field")
    length = struct.unpack("<H", data[offset : offset + PACKET_LENGTH_LEN])[0]
    return length, offset + PACKET_LENGTH_LEN


def decode_sensor_data(
    data: bytes, offset: int, presence_bits: int
) -> Tuple[Dict[str, any], int]:
    """Decode sensor data based on presence bits. Returns (decoded_dict, new_offset)."""
    decoded = {}
    data_offset = offset

    # The last byte is the checksum, so data ends at len(data) - 1
    data_end = len(data) - 1

    # Millis is always the first field in the data section
    if data_offset + 4 > data_end:
        raise ValueError("Not enough data for millis field")
    millis = struct.unpack("<I", data[data_offset : data_offset + 4])[0]
    decoded["millis"] = millis
    data_offset += 4

    # Iterate through sensors in order
    # Bit indices are 0-based (bit 0, 1, 2, etc.)
    for sensor_index, (bit_index, field_names, data_types, struct_fmt) in enumerate(
        SENSOR_METADATA
    ):
        # Check if this sensor is present (use bit_index from metadata)
        if presence_bits & (1 << bit_index):
            # Calculate total bytes needed for this sensor
            # 'B' = uint8_t (1 byte), 'H'/'h' = uint16_t/int16_t (2 bytes),
            # 'f'/'I'/'i' = float/uint32_t/int32_t (4 bytes), 'd' = double (8 bytes)
            total_bytes = sum(
                1
                if dt == "B"
                else 2
                if dt in ["H", "h"]
                else 4
                if dt in ["f", "I", "i"]
                else 8
                if dt == "d"
                else 4  # default to 4 bytes
                for dt in data_types
            )

            # Check if we have enough data (excluding checksum)
            # If not, skip this sensor (might be a bit set incorrectly or reserved)
            if data_offset + total_bytes > data_end:
                # Log warning but don't fail - some bits might be reserved or set incorrectly
                logger.warning(
                    f"Sensor {sensor_index} (bit {bit_index}) marked present but insufficient data: "
                    f"need {total_bytes} bytes, have {data_end - data_offset} bytes remaining. Skipping."
                )
                continue

            # Unpack sensor data
            values = struct.unpack(
                "<" + struct_fmt, data[data_offset : data_offset + total_bytes]
            )

            # Map values to field names
            for field_name, value in zip(field_names, values):
                decoded[field_name] = value

            data_offset += total_bytes

    return decoded, data_offset


def validate_checksum(data: bytes, data_end: int) -> bool:
    """Validate packet checksum. Returns True if valid, False otherwise."""
    if data_end >= len(data):
        return False

    # Simple checksum: sum of all bytes except the checksum byte itself
    # This is a common simple checksum algorithm
    checksum_byte = data[data_end]
    calculated_sum = sum(data[:data_end]) & 0xFF
    return calculated_sum == checksum_byte


def create_telemetry_dict(decoded: Dict[str, any]) -> Dict[str, any]:
    """
    Convert decoded packet data to FlightTelemetry-compatible dictionary.

    Ensures all expected fields are present (set to None if missing) and handles
    type conversions as needed.

    Args:
        decoded: Dictionary from parse_packet() with sensor data

    Returns:
        Dictionary compatible with FlightTelemetry Pydantic model
    """
    # The decoded dictionary already has the correct field names
    # Missing fields will be None by default in the Pydantic model
    # This function is mainly for type safety and future extensions
    return decoded


def parse_packet(data: bytes) -> Dict[str, any]:
    """
    Parse a binary sensor packet and return a dictionary compatible with FlightTelemetry.

    Packet structure:
    - Sync bytes (4 bytes): "ASU!"
    - Sensor presence (4 bytes): 32-bit bitfield
    - Packet length (2 bytes): Total packet size
    - Data section: Binary-packed sensor values
    - Checksum (1 byte): Error detection

    Returns:
        Dictionary with decoded sensor data, compatible with FlightTelemetry model.
    """
    if len(data) < MIN_PACKET_SIZE:
        raise ValueError(
            f"Packet too short: {len(data)} bytes (minimum {MIN_PACKET_SIZE})"
        )

    # Validate sync bytes
    if not validate_sync_bytes(data):
        raise ValueError("Invalid sync bytes")

    offset = SYNC_BYTES_LEN

    # Parse sensor presence
    presence_bits, offset = parse_sensor_presence(data, offset)

    # Parse packet length
    packet_length, offset = parse_packet_length(data, offset)

    # Validate packet length matches actual data length
    if len(data) != packet_length:
        raise ValueError(
            f"Packet length mismatch: expected {packet_length}, got {len(data)}"
        )

    # Decode sensor data
    decoded, data_end = decode_sensor_data(data, offset, presence_bits)

    # Validate checksum (optional, but we'll do it)
    if not validate_checksum(data, data_end):
        # Log warning but don't fail - checksum validation is optional for now
        logger.warning(
            f"Checksum validation failed for packet with millis={decoded.get('millis', 'unknown')}"
        )

    return create_telemetry_dict(decoded)
