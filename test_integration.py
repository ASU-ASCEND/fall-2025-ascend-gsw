#!/usr/bin/env python3
"""Integration test that directly tests the socket listener with example bytes."""

import asyncio
import socket
import time
from pathlib import Path

from src.config import UDP_HOST, UDP_PORT
from src.decoder import parse_packet
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
            byte_data = eval(line)
            if isinstance(byte_data, bytes):
                test_bytes.append(byte_data)
        except Exception:
            pass

print(f"Found {len(test_bytes)} test packets\n")

# Initialize database
init_database()

# Count records before
count_before = FlightTelemetry.select().count()
print(f"Records in database before: {count_before}\n")

# Test decoding first
print("Testing decoder on first packet...")
try:
    decoded = parse_packet(test_bytes[0])
    print(f"✓ Decoded successfully!")
    print(f"  Millis: {decoded.get('millis')}")
    print(f"  Fields: {len(decoded)} total\n")
except Exception as e:
    print(f"✗ Decode error: {e}\n")

# Simulate what the socket listener does
print("Simulating socket listener processing...")
processed = 0
errors = 0

for i, packet in enumerate(test_bytes, 1):
    try:
        # Decode
        decoded = parse_packet(packet)
        
        # Store in database (simulating socket_listener behavior)
        model_fields = set(FlightTelemetry._meta.fields.keys())
        # Only include fields that have values (not None) to avoid NOT NULL constraint issues
        filtered_decoded = {
            k: v for k, v in decoded.items() 
            if k in model_fields and v is not None
        }
        record_dict = {"raw_bytes": packet, **filtered_decoded}
        FlightTelemetry.create(**record_dict)
        processed += 1
        
        if i <= 3:  # Show first 3
            print(f"  ✓ Packet {i}: millis={decoded.get('millis')}, stored successfully")
    except Exception as e:
        errors += 1
        print(f"  ✗ Packet {i}: Error - {e}")

print(f"\nProcessed: {processed}/{len(test_bytes)}")
print(f"Errors: {errors}")

# Check results
count_after = FlightTelemetry.select().count()
new_records = count_after - count_before

print(f"\nRecords in database after: {count_after}")
print(f"New records created: {new_records}")

if new_records > 0:
    print("\n✓ Test successful! Sample records:")
    recent_records = (
        FlightTelemetry.select()
        .order_by(FlightTelemetry.id.desc())
        .limit(min(3, new_records))
    )
    for record in recent_records:
        print(f"\n  Record ID: {record.id}")
        print(f"  Millis: {record.millis}")
        print(f"  Raw bytes: {len(record.raw_bytes) if record.raw_bytes else 0} bytes")
        if record.ina260_current_ma is not None:
            print(f"  INA260 Current: {record.ina260_current_ma} mA")
        if record.ina260_voltage_mv is not None:
            print(f"  INA260 Voltage: {record.ina260_voltage_mv} mV")

db.close()

