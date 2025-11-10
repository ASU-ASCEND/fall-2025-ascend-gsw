"""
LoRa RF initialization for SX127x on Raspberry Pi Zero
Based on LoRaRF-Python library: https://github.com/chandrawi/LoRaRF-Python
Implements ASCEND packet system: https://asu-ascend.github.io/Spring-2025/md__2home_2runner_2work_2Spring-2025_2Spring-2025_2docs__src_2Packet__Definition.html
"""

import struct

from LoRaRF import SX127x

# Packet structure constants
SYNC_BYTES = bytes([0xAA, 0xBB, 0xCC, 0xDD])  # 4 bytes sync identifier
SENSOR_PRESENCE_SIZE = 4  # 4 bytes = 32 bits for sensor flags
PACKET_LENGTH_SIZE = 2  # 2 bytes for packet length
CHECKSUM_SIZE = 2  # 2 bytes for checksum

# Sensor indices matching the sensor array
SENSOR_INA260 = 0
SENSOR_TEMP = 1
SENSOR_GPS = 2
SENSOR_ICM = 3
SENSOR_RTC = 4
SENSOR_TMP = 5
SENSOR_UV_OUT = 6
SENSOR_ENS160_OUT = 7
SENSOR_BMP_OUT = 8
SENSOR_TMP_OUT = 9
SENSOR_SHTC3_OUT = 10
SENSOR_OZONE_OUT = 11

# Maximum number of sensors
MAX_SENSORS = 12


class ASCENDPacketBuilder:
    """
    Builds packets according to ASCEND packet system:
    - Sync Bytes (4 bytes)
    - Sensor Presence (4 bytes)
    - Packet Length (2 bytes)
    - Data (variable length)
    - Checksum (2 bytes)
    """

    def __init__(self):
        self.sync_bytes = SYNC_BYTES
        self.data_buffer = bytearray()
        # Track data for each sensor: {sensor_index: [bytes, bytes, ...]}
        self.sensor_data = {i: [] for i in range(MAX_SENSORS)}

    def reset(self):
        """Reset packet builder for new packet"""
        self.data_buffer = bytearray()
        self.sensor_data = {i: [] for i in range(MAX_SENSORS)}

    def _build_sensor_presence(self) -> int:
        """
        Build sensor presence mask by processing sensors in order.
        ASCEND logic: Shift left by 1 for each sensor, set bit if sensor has data.
        """
        sensor_presence = 0
        for sensor_index in range(MAX_SENSORS):
            # Shift left by 1
            sensor_presence = sensor_presence << 1
            # Set bit if sensor has data
            if self.sensor_data[sensor_index]:
                sensor_presence = sensor_presence | 1
        return sensor_presence

    def add_sensor_data(self, sensor_index: int, data: bytes):
        """
        Add sensor data to packet.
        Data should be packed binary format (e.g., struct.pack).
        Multiple calls for the same sensor will append data in order.
        """
        if 0 <= sensor_index < MAX_SENSORS:
            self.sensor_data[sensor_index].append(data)
        else:
            raise ValueError(f"Invalid sensor index: {sensor_index}")

    def add_float(self, sensor_index: int, value: float):
        """Add float value (4 bytes) to packet"""
        self.add_sensor_data(sensor_index, struct.pack("<f", value))

    def add_int32(self, sensor_index: int, value: int):
        """Add 32-bit integer (4 bytes) to packet"""
        self.add_sensor_data(sensor_index, struct.pack("<i", value))

    def add_uint32(self, sensor_index: int, value: int):
        """Add unsigned 32-bit integer (4 bytes) to packet"""
        self.add_sensor_data(sensor_index, struct.pack("<I", value))

    def add_int16(self, sensor_index: int, value: int):
        """Add 16-bit integer (2 bytes) to packet"""
        self.add_sensor_data(sensor_index, struct.pack("<h", value))

    def add_uint16(self, sensor_index: int, value: int):
        """Add unsigned 16-bit integer (2 bytes) to packet"""
        self.add_sensor_data(sensor_index, struct.pack("<H", value))

    def add_int8(self, sensor_index: int, value: int):
        """Add 8-bit integer (1 byte) to packet"""
        self.add_sensor_data(sensor_index, struct.pack("<b", value))

    def add_uint8(self, sensor_index: int, value: int):
        """Add unsigned 8-bit integer (1 byte) to packet"""
        self.add_sensor_data(sensor_index, struct.pack("<B", value))

    def calculate_checksum(self, data: bytes) -> int:
        """
        Calculate simple checksum for packet validation.
        Sums all bytes and returns 16-bit checksum.
        """
        checksum = sum(data) & 0xFFFF
        return checksum

    def build_packet(self) -> bytes:
        """
        Build complete packet:
        Sync Bytes (4) + Sensor Presence (4) + Packet Length (2) + Data + Checksum (2)

        Data is packed in sensor order (0 to MAX_SENSORS-1) for sensors that have data.
        """
        # Build data buffer in sensor order
        self.data_buffer = bytearray()
        for sensor_index in range(MAX_SENSORS):
            if self.sensor_data[sensor_index]:
                # Append all data chunks for this sensor in order
                for data_chunk in self.sensor_data[sensor_index]:
                    self.data_buffer.extend(data_chunk)

        # Build sensor presence mask
        sensor_presence = self._build_sensor_presence()

        # Calculate total packet length
        # Sync (4) + Presence (4) + Length (2) + Data + Checksum (2)
        total_length = (
            len(self.sync_bytes)
            + SENSOR_PRESENCE_SIZE
            + PACKET_LENGTH_SIZE
            + len(self.data_buffer)
            + CHECKSUM_SIZE
        )

        # Build packet without checksum first
        packet = bytearray()
        packet.extend(self.sync_bytes)
        packet.extend(struct.pack("<I", sensor_presence))  # Little-endian 32-bit
        packet.extend(struct.pack("<H", total_length))  # Little-endian 16-bit
        packet.extend(self.data_buffer)

        # Calculate and append checksum (excluding sync bytes and checksum itself)
        # Checksum covers: presence + length + data
        checksum_data = packet[len(self.sync_bytes) :]
        checksum = self.calculate_checksum(checksum_data)
        packet.extend(struct.pack("<H", checksum))

        return bytes(packet)

    def get_packet_length(self) -> int:
        """Get the total packet length that will be transmitted"""
        # Calculate data length
        data_length = sum(
            len(chunk)
            for sensor_data_list in self.sensor_data.values()
            for chunk in sensor_data_list
        )

        return (
            len(self.sync_bytes)
            + SENSOR_PRESENCE_SIZE
            + PACKET_LENGTH_SIZE
            + data_length
            + CHECKSUM_SIZE
        )

    def get_packet_info(self) -> dict:
        """
        Get information about the packet before building.
        Returns dict with sensor presence, data length, and total packet length.
        """
        data_length = sum(
            len(chunk)
            for sensor_data_list in self.sensor_data.values()
            for chunk in sensor_data_list
        )

        sensor_presence = self._build_sensor_presence()
        present_sensors = [i for i in range(MAX_SENSORS) if self.sensor_data[i]]

        return {
            "sensor_presence": sensor_presence,
            "present_sensors": present_sensors,
            "data_length": data_length,
            "total_packet_length": self.get_packet_length(),
            "sensor_data_sizes": {
                i: sum(len(chunk) for chunk in chunks)
                for i, chunks in self.sensor_data.items()
                if chunks
            },
        }


class LoRaPacketTransmitter:
    """
    Handles LoRa transmission with ASCEND packet system
    """

    def __init__(self, lora: SX127x):
        self.lora = lora
        self.packet_builder = ASCENDPacketBuilder()

    def transmit_packet(self, packet: bytes) -> bool:
        """
        Transmit packet over LoRa.

        Note: LoRa maximum payload is 255 bytes with explicit header mode.
        If packet exceeds this, it will need to be split or truncated.

        Returns True if successful, False otherwise.
        """
        # Check packet size (LoRa max payload is 255 bytes)
        if len(packet) > 255:
            print(
                f"Warning: Packet size {len(packet)} bytes exceeds LoRa max payload of 255 bytes"
            )
            print("Consider reducing sensor data or splitting into multiple packets")
            return False

        try:
            self.lora.beginPacket()
            self.lora.write(packet, len(packet))
            self.lora.endPacket()
            self.lora.wait()
            return True
        except Exception as e:
            print(f"Error transmitting packet: {e}")
            return False

    def build_packet_from_sensors(self, sensor_data: dict):
        """
        Build packet from sensor data dictionary (does not transmit).

        sensor_data format:
        {
            'ina260': {'current_ma': float, 'voltage_mv': float, 'power_mw': float},
            'temp': {'temp_c': float},
            'gps': {'lat': float, 'lon': float, 'alt': float, 'year': int, ...},
            'icm': {'accx': float, 'accy': float, 'accz': float, ...},
            'rtc': {'year': int, 'month': int, 'day': int, ...},
            'tmp': {'temp_c': float},
            'uv_out': {'uva': float, 'uvb': float, 'uvc': float},
            'ens160_out': {'aqi': int, 'tvoc': float, 'eco2': float},
            'bmp_out': {'temp_c': float, 'pressure_pa': float, 'altitude_m': float},
            'tmp_out': {'temp_c': float},
            'shtc3_out': {'temp_c': float, 'rel_hum': float},
            'ozone_out': {'conc_ppb': float},
        }
        """
        self.packet_builder.reset()

        # INA260 Sensor (current, voltage, power)
        if "ina260" in sensor_data:
            data = sensor_data["ina260"]
            if "current_ma" in data:
                self.packet_builder.add_float(SENSOR_INA260, data["current_ma"])
            if "voltage_mv" in data:
                self.packet_builder.add_float(SENSOR_INA260, data["voltage_mv"])
            if "power_mw" in data:
                self.packet_builder.add_float(SENSOR_INA260, data["power_mw"])

        # Temperature Sensor (picotemp)
        if "temp" in sensor_data:
            data = sensor_data["temp"]
            if "temp_c" in data:
                self.packet_builder.add_float(SENSOR_TEMP, data["temp_c"])

        # GPS Sensor (mtk3339)
        if "gps" in sensor_data:
            data = sensor_data["gps"]
            if "lat" in data:
                self.packet_builder.add_float(SENSOR_GPS, data["lat"])
            if "lon" in data:
                self.packet_builder.add_float(SENSOR_GPS, data["lon"])
            if "alt" in data:
                self.packet_builder.add_float(SENSOR_GPS, data["alt"])
            if "year" in data:
                self.packet_builder.add_uint16(SENSOR_GPS, data["year"])
            if "month" in data:
                self.packet_builder.add_uint8(SENSOR_GPS, data["month"])
            if "day" in data:
                self.packet_builder.add_uint8(SENSOR_GPS, data["day"])
            if "hour" in data:
                self.packet_builder.add_uint8(SENSOR_GPS, data["hour"])
            if "minute" in data:
                self.packet_builder.add_uint8(SENSOR_GPS, data["minute"])
            if "second" in data:
                self.packet_builder.add_uint8(SENSOR_GPS, data["second"])
            if "satellites" in data:
                self.packet_builder.add_uint8(SENSOR_GPS, data["satellites"])

        # ICM Sensor (icm20948)
        if "icm" in sensor_data:
            data = sensor_data["icm"]
            if "accx" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["accx"])
            if "accy" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["accy"])
            if "accz" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["accz"])
            if "gyrox" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["gyrox"])
            if "gyroy" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["gyroy"])
            if "gyroz" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["gyroz"])
            if "magx" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["magx"])
            if "magy" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["magy"])
            if "magz" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["magz"])
            if "temp_c" in data:
                self.packet_builder.add_float(SENSOR_ICM, data["temp_c"])

        # RTC Sensor (pcf8523)
        if "rtc" in sensor_data:
            data = sensor_data["rtc"]
            if "year" in data:
                self.packet_builder.add_uint16(SENSOR_RTC, data["year"])
            if "month" in data:
                self.packet_builder.add_uint8(SENSOR_RTC, data["month"])
            if "day" in data:
                self.packet_builder.add_uint8(SENSOR_RTC, data["day"])
            if "hour" in data:
                self.packet_builder.add_uint8(SENSOR_RTC, data["hour"])
            if "minute" in data:
                self.packet_builder.add_uint8(SENSOR_RTC, data["minute"])
            if "second" in data:
                self.packet_builder.add_uint8(SENSOR_RTC, data["second"])

        # TMP Sensor (tmp117)
        if "tmp" in sensor_data:
            data = sensor_data["tmp"]
            if "temp_c" in data:
                self.packet_builder.add_float(SENSOR_TMP, data["temp_c"])

        # UV Sensor Out
        if "uv_out" in sensor_data:
            data = sensor_data["uv_out"]
            if "uva" in data:
                self.packet_builder.add_float(SENSOR_UV_OUT, data["uva"])
            if "uvb" in data:
                self.packet_builder.add_float(SENSOR_UV_OUT, data["uvb"])
            if "uvc" in data:
                self.packet_builder.add_float(SENSOR_UV_OUT, data["uvc"])

        # ENS160 Sensor Out
        if "ens160_out" in sensor_data:
            data = sensor_data["ens160_out"]
            if "aqi" in data:
                self.packet_builder.add_uint16(SENSOR_ENS160_OUT, data["aqi"])
            if "tvoc" in data:
                self.packet_builder.add_float(SENSOR_ENS160_OUT, data["tvoc"])
            if "eco2" in data:
                self.packet_builder.add_float(SENSOR_ENS160_OUT, data["eco2"])

        # BMP Sensor Out (bmp390)
        if "bmp_out" in sensor_data:
            data = sensor_data["bmp_out"]
            if "temp_c" in data:
                self.packet_builder.add_float(SENSOR_BMP_OUT, data["temp_c"])
            if "pressure_pa" in data:
                self.packet_builder.add_float(SENSOR_BMP_OUT, data["pressure_pa"])
            if "altitude_m" in data:
                self.packet_builder.add_float(SENSOR_BMP_OUT, data["altitude_m"])

        # TMP Sensor Out (tmp117_o)
        if "tmp_out" in sensor_data:
            data = sensor_data["tmp_out"]
            if "temp_c" in data:
                self.packet_builder.add_float(SENSOR_TMP_OUT, data["temp_c"])

        # SHTC3 Sensor Out
        if "shtc3_out" in sensor_data:
            data = sensor_data["shtc3_out"]
            if "temp_c" in data:
                self.packet_builder.add_float(SENSOR_SHTC3_OUT, data["temp_c"])
            if "rel_hum" in data:
                self.packet_builder.add_float(SENSOR_SHTC3_OUT, data["rel_hum"])

        # Ozone Sensor Out
        if "ozone_out" in sensor_data:
            data = sensor_data["ozone_out"]
            if "conc_ppb" in data:
                self.packet_builder.add_float(SENSOR_OZONE_OUT, data["conc_ppb"])

    def build_and_transmit(self, sensor_data: dict) -> bool:
        """
        Build packet from sensor data and transmit.
        Returns True if successful, False otherwise.
        """
        self.build_packet_from_sensors(sensor_data)
        packet = self.packet_builder.build_packet()
        return self.transmit_packet(packet)


def initialize_lora(
    frequency: int = 915000000,
    tx_power: int = 14,
    spreading_factor: int = 8,
    bandwidth: int = 125000,
    coding_rate: int = 5,
    sync_word: int = 0x3444,
    reset_pin: int = 22,
    dio1_pin: int = -1,
    txen_pin: int = -1,
    rxen_pin: int = -1,
) -> SX127x:
    """
    Initialize LoRa module for SX127x on Raspberry Pi Zero.

    Args:
        frequency: Operating frequency in Hz (default: 915 MHz)
        tx_power: Transmit power in dBm (default: 14)
        spreading_factor: Spreading factor 7-12 (default: 8)
        bandwidth: Bandwidth in Hz (default: 125000)
        coding_rate: Coding rate 5-8 (default: 5)
        sync_word: Synchronization word (default: 0x3444 for public network)
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

    # Configure transmit power
    LoRa.setTxPower(tx_power, LoRa.TX_POWER_SX1276)

    # Configure receive gain
    LoRa.setRxGain(LoRa.RX_GAIN_POWER_SAVING)

    # Configure LoRa modulation parameters
    # Low data rate optimization should be True for SF >= 11
    low_data_rate = spreading_factor >= 11
    LoRa.setLoRaModulation(spreading_factor, bandwidth, coding_rate, low_data_rate)

    # Configure LoRa packet parameters
    # Use explicit header mode for variable length packets
    # Maximum payload length for explicit header: 255 bytes
    # Preamble length: 12 (default)
    LoRa.setLoRaPacket(LoRa.HEADER_EXPLICIT, 12, 255, True, False)

    # Set synchronize word
    LoRa.setSyncWord(sync_word)

    print("LoRa SX127x initialized successfully!")
    print(f"  Frequency: {frequency / 1e6:.1f} MHz")
    print(f"  TX Power: {tx_power} dBm")
    print(f"  Spreading Factor: {spreading_factor}")
    print(f"  Bandwidth: {bandwidth} Hz")
    print(f"  Coding Rate: {coding_rate}")
    return LoRa


if __name__ == "__main__":
    try:
        # Initialize LoRa
        lora = initialize_lora()

        # Create packet transmitter
        transmitter = LoRaPacketTransmitter(lora)

        # Example: Build and transmit a test packet
        # In real usage, you would read from actual sensors
        test_sensor_data = {
            "ina260": {"current_ma": 123.45, "voltage_mv": 3456.78, "power_mw": 426.89},
            "temp": {"temp_c": 25.5},
            "tmp": {"temp_c": 24.8},
        }

        print("\nBuilding test packet...")
        # Build packet from sensor data
        transmitter.build_packet_from_sensors(test_sensor_data)

        # Get packet info before building
        packet_info = transmitter.packet_builder.get_packet_info()
        print("Packet info:")
        print(f"  Present sensors: {packet_info['present_sensors']}")
        print(f"  Sensor presence mask: 0x{packet_info['sensor_presence']:08X}")
        print(f"  Data length: {packet_info['data_length']} bytes")
        print(f"  Total packet length: {packet_info['total_packet_length']} bytes")

        # Build and transmit
        print("\nTransmitting test packet...")
        packet = transmitter.packet_builder.build_packet()
        success = transmitter.transmit_packet(packet)
        if success:
            print("Packet transmitted successfully!")
            print(f"Packet length: {len(packet)} bytes")
            print(f"Packet hex (first 64 bytes): {packet[:64].hex()}")
        else:
            print("Failed to transmit packet")

        # Alternative: use build_and_transmit for one-step operation
        # success = transmitter.build_and_transmit(test_sensor_data)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
