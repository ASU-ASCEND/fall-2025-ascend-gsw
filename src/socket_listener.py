#!/usr/bin/env python3
"""UDP listener for RFM9x radio messages on localhost:1337."""

import socket

UDP_HOST = "localhost"
UDP_PORT = 1337

# Create UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_HOST, UDP_PORT))

print(f"Listening for UDP messages on {UDP_HOST}:{UDP_PORT}...")

try:
    while True:
        # Receive data (buffer size 1024 bytes)
        data, addr = sock.recvfrom(1024)
        print(data)
except KeyboardInterrupt:
    print("\n\nStopping listener...")
finally:
    sock.close()
    print("Socket closed.")
