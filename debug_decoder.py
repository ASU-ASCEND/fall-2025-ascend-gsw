import ast
import json
import os
import sys

# Add the current directory to sys.path to ensure imports work correctly
sys.path.append(os.getcwd())

from src.decoder import parse_packet


def main():
    input_file = "output.txt"

    try:
        with open(input_file, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
        sys.exit(1)

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        # Remove trailing ')' if present (seems to be in some output lines)
        if line.endswith(")"):
            line = line[:-1]

        print(f"--- Processing Line {i + 1} ---")
        try:
            # Safely evaluate the string representation of bytes
            packet_data = ast.literal_eval(line)

            if not isinstance(packet_data, bytes):
                print(f"Error: Line {i + 1} does not evaluate to bytes object.")
                continue

            decoded_data = parse_packet(packet_data)
            # Convert bytes to hex string for JSON serialization if any exist in output
            # parse_packet returns a dict with mostly numbers, but let's be safe

            print(json.dumps(decoded_data, indent=2, default=str))

        except Exception as e:
            print(f"Error processing line {i + 1}: {e}")
        print("\n")


if __name__ == "__main__":
    main()
