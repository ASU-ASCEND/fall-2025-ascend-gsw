#!/usr/bin/env python3
"""Integration test with a fresh test database."""

import asyncio
import socket
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

from peewee import SqliteDatabase
from src.decoder import parse_packet
from src.schema import FlightTelemetry, BaseModel

# Create a temporary test database
test_db_file = NamedTemporaryFile(delete=False, suffix='.db')
test_db_file.close()
test_db = SqliteDatabase(test_db_file.name)

# Create a test model with the same schema
class TestFlightTelemetry(BaseModel):
    class Meta:
        database = test_db

# Copy all fields from FlightTelemetry
for field_name, field in FlightTelemetry._meta.fields.items():
    if field_name != 'id':  # Skip the primary key
        setattr(TestFlightTelemetry, field_name, field)

# Initialize test database
test_db.connect()
test_db.create_tables([TestFlightTelemetry], safe=True)

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

# Test decoding first
print("Testing decoder on first packet...")
try:
    decoded = parse_packet(test_bytes[0])
    print(f"✓ Decoded successfully!")
    print(f"  Millis: {decoded.get('millis')}")
    print(f"  Fields with values: {[k for k, v in decoded.items() if v is not None]}\n")
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
        model_fields = set(TestFlightTelemetry._meta.fields.keys())
        # Only include fields that have values
        filtered_decoded = {
            k: v for k, v in decoded.items() 
            if k in model_fields and v is not None
        }
        record_dict = {"raw_bytes": packet, **filtered_decoded}
        TestFlightTelemetry.create(**record_dict)
        processed += 1
        
        if i <= 3:  # Show first 3
            print(f"  ✓ Packet {i}: millis={decoded.get('millis')}, stored successfully")
    except Exception as e:
        errors += 1
        if i <= 3:
            print(f"  ✗ Packet {i}: Error - {e}")

print(f"\nProcessed: {processed}/{len(test_bytes)}")
print(f"Errors: {errors}")

# Check results
total_records = TestFlightTelemetry.select().count()
print(f"\nTotal records in test database: {total_records}")

if total_records > 0:
    print("\n✓ Test successful! Sample records:")
    recent_records = TestFlightTelemetry.select().order_by(TestFlightTelemetry.id.desc()).limit(min(3, total_records))
    for record in recent_records:
        print(f"\n  Record ID: {record.id}")
        # Access values directly from the record
        millis_val = record.millis if hasattr(record, 'millis') and record.millis is not None else None
        print(f"  Millis: {millis_val}")
        
        # Get raw_bytes
        try:
            raw_bytes_val = bytes(record.raw_bytes) if record.raw_bytes else None
            print(f"  Raw bytes: {len(raw_bytes_val) if raw_bytes_val else 0} bytes")
        except:
            print(f"  Raw bytes: (not accessible)")
        
        # Show any decoded fields that have values
        decoded_fields = []
        for field_name in ['ina260_current_ma', 'ina260_voltage_mv', 'picotemp_temp_c', 'ina260_power_mw']:
            try:
                value = getattr(record, field_name, None)
                if value is not None:
                    decoded_fields.append(f"{field_name}: {value}")
            except:
                pass
        if decoded_fields:
            print(f"  Decoded: {', '.join(decoded_fields)}")

test_db.close()
print(f"\n✓ Test database created at: {test_db_file.name}")
print("  (You can delete it manually if needed)")

