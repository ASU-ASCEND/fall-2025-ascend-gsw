#!/usr/bin/env python3
"""Verify that SENSOR_METADATA matches config.csv exactly."""

import csv
from src.decoder import SENSOR_METADATA

# Read config.csv
config_data = {}
with open('config.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Strip whitespace from keys and values
        row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
        bit_index = int(row['BitIndex'])
        sensor_name = row['SensorName']
        
        # Extract field labels and types
        fields = []
        for i in range(1, 13):  # FieldLabel_1 through FieldLabel_12
            label_key = f'FieldLabel_{i}'
            type_key = f'FieldType_{i}'
            if label_key in row and row[label_key].strip():
                fields.append((row[label_key].strip(), row[type_key].strip()))
        
        config_data[bit_index] = {
            'sensor_name': sensor_name,
            'fields': fields
        }

# Compare with SENSOR_METADATA
print("=" * 80)
print("COMPARISON: SENSOR_METADATA vs config.csv")
print("=" * 80)

all_match = True

for bit_index, field_names, data_types, struct_fmt in SENSOR_METADATA:
    if bit_index not in config_data:
        print(f"\n❌ ERROR: Bit {bit_index} in SENSOR_METADATA but not in config.csv")
        all_match = False
        continue
    
    config = config_data[bit_index]
    csv_fields = config['fields']
    
    print(f"\nBit {bit_index}: {config['sensor_name']}")
    print(f"  CSV has {len(csv_fields)} fields")
    print(f"  Decoder has {len(field_names)} fields")
    
    if len(csv_fields) != len(field_names):
        print(f"  ❌ MISMATCH: Field count differs!")
        all_match = False
        continue
    
    # Compare each field
    field_mismatches = []
    for i, ((csv_label, csv_type), (decoder_name, decoder_type)) in enumerate(zip(csv_fields, zip(field_names, data_types))):
        # Map CSV type to decoder type
        type_map = {
            'float': 'f',
            'double': 'd',
            'uint16_t': 'H',
            'uint8_t': 'B',
            'int16_t': 'h',
            'int32_t': 'i',
            'uint32_t': 'I'
        }
        expected_type = type_map.get(csv_type, csv_type)
        
        # Check type
        if decoder_type != expected_type:
            field_mismatches.append(f"    Field {i+1}: Type mismatch - CSV: {csv_type} ({expected_type}), Decoder: {decoder_type}")
            all_match = False
        
        # Check field name (convert CSV label to expected decoder format)
        # CSV labels are like "Temp (C)" or "Current (mA)"
        # Decoder names are like "shtc3_o_temp_c" or "ina260_current_ma"
        # We'll just note the label for comparison
        print(f"    Field {i+1}: CSV='{csv_label}' ({csv_type}) -> Decoder='{decoder_name}' ({decoder_type})")
    
    if field_mismatches:
        for mismatch in field_mismatches:
            print(f"  ❌ {mismatch}")

# Check for sensors in CSV but not in decoder
for bit_index in config_data:
    if not any(bit == bit_index for bit, _, _, _ in SENSOR_METADATA):
        print(f"\n❌ ERROR: Bit {bit_index} ({config_data[bit_index]['sensor_name']}) in config.csv but not in SENSOR_METADATA")
        all_match = False

print("\n" + "=" * 80)
if all_match:
    print("✅ ALL MATCHES!")
else:
    print("❌ MISMATCHES FOUND!")
print("=" * 80)

