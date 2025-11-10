"""
LoRa Receiver for SX1276 on Raspberry Pi Zero 2 W
Receives messages from Pi Pico using standard radiolib and prints to console.
Based on LoRaRF-Python library: https://github.com/chandrawi/LoRaRF-Python
"""

import sys

from LoRaRF import SX127x


def initialize_lora_receiver(
    frequency: int = 915000000,
    spreading_factor: int = 9,
    bandwidth: int = 125000,
    coding_rate: int = 7,
    sync_word: int = 0x12,
    preamble_length: int = 10,
    reset_pin: int = 22,
    dio1_pin: int = -1,
    txen_pin: int = -1,
    rxen_pin: int = -1,
) -> SX127x:
    """
    Initialize LoRa module for receiving on SX1276.

    Args:
        frequency: Operating frequency in Hz (default: 915 MHz)
        spreading_factor: Spreading factor 7-12 (default: 9, matches radiolib)
        bandwidth: Bandwidth in Hz (default: 125000)
        coding_rate: Coding rate 5-8, where 5=4/5, 6=4/6, 7=4/7, 8=4/8 (default: 7)
        sync_word: Synchronization word (default: 0x12, RADIOLIB_SX127X_SYNC_WORD)
        preamble_length: Preamble length in symbols (default: 10, matches radiolib)
        reset_pin: GPIO pin for RESET (default: 22)
        dio1_pin: GPIO pin for DIO1 interrupt (default: -1 unused)
        txen_pin: GPIO pin for TXEN (default: -1 unused)
        rxen_pin: GPIO pin for RXEN (default: -1 unused)

    Returns:
        Initialized SX127x LoRa object
    """
    # Initialize SX127x LoRa module
    LoRa = SX127x()

    # Configure GPIO pins if provided
    if reset_pin >= 0:
        LoRa.setPins(reset_pin, dio1_pin, txen_pin, rxen_pin)

    # Begin initialization (required before any operations)
    LoRa.begin()

    # Configure frequency
    LoRa.setFrequency(frequency)

    # Configure transmit power (not needed for receive, but set anyway)
    LoRa.setTxPower(14, LoRa.TX_POWER_SX1276)

    # Configure receive gain
    LoRa.setRxGain(LoRa.RX_GAIN_POWER_SAVING)

    # Configure LoRa modulation parameters
    # Low data rate optimization should be True for SF >= 11
    # For SF=9, it's not needed (only for SF >= 11)
    low_data_rate = spreading_factor >= 11
    LoRa.setLoRaModulation(spreading_factor, bandwidth, coding_rate, low_data_rate)

    # Configure LoRa packet parameters
    # Use explicit header mode for variable length packets
    # Maximum payload length for explicit header: 255 bytes
    # Preamble length: 10 (matches radiolib begin parameter 6)
    LoRa.setLoRaPacket(LoRa.HEADER_EXPLICIT, preamble_length, 255, True, False)

    # Set synchronize word
    LoRa.setSyncWord(sync_word)

    print("LoRa SX1276 Receiver initialized successfully!")
    print(f"  Frequency: {frequency / 1e6:.1f} MHz")
    print(f"  Spreading Factor: {spreading_factor}")
    print(f"  Bandwidth: {bandwidth} Hz")
    print(f"  Coding Rate: {coding_rate} (4/{coding_rate})")
    print(f"  Sync Word: 0x{sync_word:02X}")
    print(f"  Preamble Length: {preamble_length} symbols")
    print("\nWaiting for messages...\n")

    return LoRa


def receive_message(lora: SX127x) -> bytes:
    """
    Receive a message from LoRa.

    Args:
        lora: Initialized SX127x LoRa object

    Returns:
        Received message as bytes, or empty bytes if error
    """
    try:
        # Request to receive
        lora.request()

        # Wait for reception (blocks until packet received)
        lora.wait()

        # Check if data is available
        if lora.available() > 0:
            # Read all available bytes
            message = bytearray()
            while lora.available() > 0:
                message.append(lora.read())
            return bytes(message)
        else:
            return b""
    except Exception as e:
        print(f"Error receiving message: {e}")
        return b""


def bytes_to_text(data: bytes) -> str:
    """
    Convert bytes to text, trying UTF-8 first, then ASCII, then fallback to hex.

    Args:
        data: Bytes to convert

    Returns:
        String representation of the data
    """
    if not data:
        return ""

    # Try UTF-8 first
    try:
        text = data.decode("utf-8")
        # Remove null bytes and other control characters that might be padding
        text = text.rstrip("\x00")
        return text
    except UnicodeDecodeError:
        pass

    # Try ASCII
    try:
        text = data.decode("ascii")
        text = text.rstrip("\x00")
        return text
    except UnicodeDecodeError:
        pass

    # Fallback to hex representation
    return f"<hex: {data.hex()}>"


def main():
    """Main receiver loop"""
    # Configuration - MUST match your Pi Pico radiolib settings
    # Based on: radio.begin(915.0, 125.0, 9, 7, RADIOLIB_SX127X_SYNC_WORD, 10, 8, 0)
    FREQUENCY = 915000000  # 915 MHz
    SPREADING_FACTOR = 9  # SF9 (from radiolib begin: parameter 3)
    BANDWIDTH = 125000  # 125 kHz
    CODING_RATE = 7  # 4/7 (from radiolib begin: parameter 4, where 7 = 4/7)
    SYNC_WORD = 0x12  # RADIOLIB_SX127X_SYNC_WORD (from radiolib begin: parameter 5)
    PREAMBLE_LENGTH = 10  # 10 symbols (from radiolib begin: parameter 6)

    # GPIO pin configuration (adjust if your wiring is different)
    RESET_PIN = 22
    DIO1_PIN = -1  # -1 means unused
    TXEN_PIN = -1  # -1 means unused
    RXEN_PIN = -1  # -1 means unused

    try:
        # Initialize LoRa receiver
        lora = initialize_lora_receiver(
            frequency=FREQUENCY,
            spreading_factor=SPREADING_FACTOR,
            bandwidth=BANDWIDTH,
            coding_rate=CODING_RATE,
            sync_word=SYNC_WORD,
            preamble_length=PREAMBLE_LENGTH,
            reset_pin=RESET_PIN,
            dio1_pin=DIO1_PIN,
            txen_pin=TXEN_PIN,
            rxen_pin=RXEN_PIN,
        )

        # Continuous receive loop
        packet_count = 0
        while True:
            # Receive message (blocks until packet is received)
            message = receive_message(lora)

            if message:
                packet_count += 1
                # Convert to text
                text = bytes_to_text(message)

                # Print received message
                print(f"[Packet #{packet_count}]")
                print(f"  Length: {len(message)} bytes")
                print(f"  Data: {text}")
                print(f"  Hex: {message.hex()}")
                print()
            # If message is empty, continue waiting (shouldn't happen in normal operation)

    except KeyboardInterrupt:
        print("\n\nReceiver stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
