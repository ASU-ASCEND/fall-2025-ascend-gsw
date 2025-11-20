#!/usr/bin/env python3
"""Script to validate packet decoding using output.txt and decoder.py"""

import codecs
import logging
import struct
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from src.decoder import parse_packet, validate_checksum

# Set up logging - suppress warnings about checksum failures in decoder
logging.basicConfig(
    level=logging.ERROR,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_bytes_literal(line: str) -> bytes:
    """Parse a Python bytes literal from a line of text."""
    line = line.strip()
    if not line:
        return None

    # Check if it looks like a bytes literal
    if not (line.startswith("b'") or line.startswith('b"')):
        return None

    try:
        # The line is already a string representation, so we need to encode and decode
        # First, remove the b' prefix and trailing quote
        if line.startswith("b'"):
            quote_char = "'"
        else:
            quote_char = '"'

        # Extract the inner string (without b'...' wrapper)
        inner_str = line[2:-1]  # Remove b' and final '

        # Decode escape sequences (handles \x01, \n, etc.)
        decoded_bytes, _ = codecs.escape_decode(inner_str.encode("latin-1"))

        return decoded_bytes
    except Exception as e:
        print(f"Error parsing line: {e}")
        print(f"Line content: {line[:100]}...")
        return None


def validate_packet_structure(decoded: Dict, packet_num: int) -> List[str]:
    """Validate the structure and basic sanity of decoded packet."""
    issues = []

    # Check that millis is present
    if "millis" not in decoded:
        issues.append("Missing millis field")

    # Check for reasonable values
    millis = decoded.get("millis")
    if millis is not None:
        if millis < 0 or millis > 0xFFFFFFFF:
            issues.append(f"Millis value out of range: {millis}")

    # Check temperature values are reasonable (rough sanity check)
    temp_fields = [
        "picotemp_temp_c",
        "tmp117_temp_c",
        "tmp117_o_temp_o_c",
        "shtc3_o_temp_o_c",
        "icm20948_temp_c",
        "bmp390_temp_c",
    ]
    for field in temp_fields:
        if field in decoded:
            temp = decoded[field]
            if abs(temp) > 200:  # Very rough sanity check
                issues.append(f"Suspicious temperature value: {field}={temp:.2f}°C")

    # Check date/time fields are reasonable
    year_fields = ["mtk3339_year", "pcf8523_year"]
    for field in year_fields:
        if field in decoded:
            year = decoded[field]
            if year < 2000 or year > 2100:
                issues.append(f"Suspicious year value: {field}={year}")

    return issues


def decode_packets_from_file(file_path: Path) -> Tuple[List[Dict], List[str]]:
    """Read and decode all packets from output.txt file."""
    decoded_packets = []
    errors = []

    if not file_path.exists():
        errors.append(f"File not found: {file_path}")
        return decoded_packets, errors

    print(f"Reading packets from: {file_path}")
    print("=" * 80)

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    packet_num = 0
    for line_num, line in enumerate(lines, start=1):
        if not line.strip() or line.strip().startswith("#"):
            continue

        # Parse bytes literal
        packet_data = parse_bytes_literal(line)
        if packet_data is None:
            continue

        packet_num += 1
        original_len = len(packet_data)

        # Check packet length before decoding
        if len(packet_data) >= 10:
            packet_length_field = struct.unpack("<H", packet_data[8:10])[0]

            # If there's a 1-byte mismatch, try trimming the last byte (might be extra newline)
            if (
                packet_length_field != len(packet_data)
                and packet_length_field == len(packet_data) - 1
            ):
                packet_data = packet_data[:-1]

        print(
            f"\n[Packet {packet_num}] (Line {line_num}, {len(packet_data)} bytes)",
            end="",
        )
        if original_len != len(packet_data):
            print(f" [trimmed from {original_len} bytes]", end="")
        print()

        try:
            # Decode packet
            decoded = parse_packet(packet_data)

            # Validate checksum
            data_end = len(packet_data) - 1
            checksum_valid = validate_checksum(packet_data, data_end)

            # Validate structure
            issues = validate_packet_structure(decoded, packet_num)

            # Display results
            print("  ✓ Decoded successfully")
            print(f"  ✓ Checksum: {'VALID' if checksum_valid else 'INVALID'}")
            print(f"  ✓ Millis: {decoded.get('millis', 'N/A')}")

            # Show presence bits
            presence_bits = struct.unpack("<I", packet_data[4:8])[0]
            present_sensors = [i for i in range(32) if presence_bits & (1 << i)]
            print(f"  ✓ Present sensors (bits): {present_sensors}")

            # Show decoded fields count
            field_count = len([k for k in decoded.keys() if k != "millis"])
            print(f"  ✓ Decoded fields: {field_count}")

            # Show sample of decoded data (first few non-millis fields)
            if decoded:
                non_millis_fields = [k for k in decoded.keys() if k != "millis"]
                if non_millis_fields:
                    sample_fields = non_millis_fields[:5]
                    print(f"  ✓ Sample fields: {', '.join(sample_fields)}")

            # Report issues
            if issues:
                print("  ⚠ Issues found:")
                for issue in issues:
                    print(f"    - {issue}")

            decoded_packets.append(decoded)

        except Exception as e:
            error_msg = (
                f"Packet {packet_num} (line {line_num}): {type(e).__name__}: {e}"
            )
            print(f"  ✗ ERROR: {error_msg}")
            errors.append(error_msg)
            # Only show full traceback for first few errors
            if len(errors) <= 3:
                logger.exception(f"Error decoding packet {packet_num}")

    return decoded_packets, errors


def print_summary(decoded_packets: List[Dict], errors: List[str]):
    """Print summary statistics."""
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total packets processed: {len(decoded_packets) + len(errors)}")
    print(f"Successfully decoded: {len(decoded_packets)}")
    print(f"Errors: {len(errors)}")

    if decoded_packets:
        print("\nDecoded packet statistics:")
        print(
            f"  Average fields per packet: {sum(len(p) for p in decoded_packets) / len(decoded_packets):.1f}"
        )

        # Find which sensors appear most frequently
        sensor_counts = {}
        for packet in decoded_packets:
            for key in packet.keys():
                if key != "millis":
                    sensor_counts[key] = sensor_counts.get(key, 0) + 1

        if sensor_counts:
            print("\n  Most common sensors:")
            sorted_sensors = sorted(
                sensor_counts.items(), key=lambda x: x[1], reverse=True
            )[:10]
            for sensor, count in sorted_sensors:
                print(f"    {sensor}: {count}/{len(decoded_packets)} packets")

    if errors:
        print("\nErrors encountered:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")


def main():
    """Main function."""
    # Get output.txt file path
    script_dir = Path(__file__).parent
    output_file = script_dir / "output.txt"

    if not output_file.exists():
        print(f"Error: {output_file} not found!")
        sys.exit(1)

    # Decode all packets
    decoded_packets, errors = decode_packets_from_file(output_file)

    # Print summary
    print_summary(decoded_packets, errors)

    # Exit with error code if there were failures
    if errors:
        sys.exit(1)
    else:
        print("\n✓ All packets decoded successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
