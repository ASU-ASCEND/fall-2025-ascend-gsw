#!/usr/bin/env python3
"""Test script to send example bytes from output.txt to the UDP socket."""

import ast
import socket
import time
from pathlib import Path

from src.config import UDP_HOST, UDP_PORT
from src.schema import FlightTelemetry, db, init_database

# Parse bytes from output.txt
output_file = Path(__file__).parent / "output.txt"
test_bytes = []

with open(output_file, "rb") as f:
    content = f.read().decode("utf-8", errors="ignore")

for line in content.split("\n"):
    line = line.strip()
    if line.startswith("b'") or line.startswith('b"'):
        try:
            # Use eval instead of ast.literal_eval to handle null bytes
            # This is safe here since we control the input file
            byte_data = eval(line)
            if isinstance(byte_data, bytes):
                test_bytes.append(byte_data)
        except (ValueError, SyntaxError) as e:
            print(f"Skipping invalid line: {line[:50]}... ({e})")

print(f"Found {len(test_bytes)} test packets")
print(f"First packet: {test_bytes[0] if test_bytes else 'None'}")
print(f"First packet length: {len(test_bytes[0]) if test_bytes else 0} bytes\n")

# Initialize database to check results
init_database()

# Count records before
count_before = FlightTelemetry.select().count()
print(f"Records in database before: {count_before}")

# Create UDP socket and send packets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"\nSending {len(test_bytes)} packets to {UDP_HOST}:{UDP_PORT}...")
for i, packet in enumerate(test_bytes, 1):
    try:
        sock.sendto(packet, (UDP_HOST, UDP_PORT))
        print(f"Sent packet {i}/{len(test_bytes)} ({len(packet)} bytes)")
        time.sleep(0.1)  # Small delay between packets
    except Exception as e:
        print(f"Error sending packet {i}: {e}")

sock.close()
print("\nAll packets sent. Waiting 2 seconds for processing...")
time.sleep(2)

# Check results
count_after = FlightTelemetry.select().count()
new_records = count_after - count_before

print(f"\nRecords in database after: {count_after}")
print(f"New records created: {new_records}")

if new_records > 0:
    print("\nSample of stored records:")
    recent_records = (
        FlightTelemetry.select()
        .order_by(FlightTelemetry.id.desc())
        .limit(min(5, new_records))
    )
    for record in recent_records:
        print(f"\n  Record ID: {record.id}")
        print(f"  Millis: {record.millis}")
        print(f"  Raw bytes length: {len(record.raw_bytes) if record.raw_bytes else 0}")
        # Show a few decoded fields if available
        if record.ina260_current_ma is not None:
            print(f"  INA260 Current: {record.ina260_current_ma} mA")
        if record.ina260_voltage_mv is not None:
            print(f"  INA260 Voltage: {record.ina260_voltage_mv} mV")
        if record.picotemp_temp_c is not None:
            print(f"  Picotemp: {record.picotemp_temp_c} °C")
else:
    print("\n⚠️  No new records were created. Make sure the FastAPI server is running!")

db.close()

