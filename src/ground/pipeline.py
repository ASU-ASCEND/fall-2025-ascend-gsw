import asyncio
import logging
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from .config import GroundConfig
from .decoder.packet_decoder import PacketDecoder
from .framing.serial_sorter import SerialSorter
from .mapping.telemetry_mapper import TelemetryMapper
from .persist.ndjson_writer import NDJSONWriter
from .sources.base import BaseSource
from .sources.binlog_source import BinaryLogSource
from .sources.csv_source import CSVSource
from .sources.serial_source import SerialSource

logger = logging.getLogger(__name__)


class BroadcastHub:
    """Async broadcast hub for SSE clients"""

    def __init__(self, max_queue_size: int = 1000):
        self.max_queue_size = max_queue_size
        self.subscribers = set()
        self._data_queue = asyncio.Queue(maxsize=max_queue_size)

    async def publish(self, telemetry: Dict[str, Any]):
        """Publish telemetry to all subscribers"""
        if telemetry == "ERROR":
            return

        try:
            self._data_queue.put_nowait(telemetry)
        except asyncio.QueueFull:
            logger.warning("Broadcast queue full, dropping telemetry")
            # Remove oldest item to make room
            try:
                self._data_queue.get_nowait()
                self._data_queue.put_nowait(telemetry)
            except asyncio.QueueEmpty:
                pass

    async def subscribe(self) -> AsyncIterator[Dict[str, Any]]:
        """Subscribe to telemetry stream"""
        subscriber_queue = asyncio.Queue(maxsize=self.max_queue_size)

        # Add subscriber
        self.subscribers.add(subscriber_queue)

        try:
            while True:
                # Get data from subscriber queue
                try:
                    telemetry = await asyncio.wait_for(
                        subscriber_queue.get(), timeout=1.0
                    )
                    yield telemetry
                except asyncio.TimeoutError:
                    # No data available, check if we should continue
                    continue

        except asyncio.CancelledError:
            pass
        finally:
            # Remove subscriber
            self.subscribers.discard(subscriber_queue)

    def get_subscriber_count(self) -> int:
        """Get number of active subscribers"""
        return len(self.subscribers)


class TelemetryPipeline:
    """Main pipeline orchestrating data flow from source to consumers"""

    def __init__(self, config: GroundConfig):
        self.config = config
        self.broadcast_hub = BroadcastHub(config.QUEUE_SIZE)
        self.ndjson_writer = NDJSONWriter(config.NDJSON_DIR, config.NDJSON_MAX_SIZE_MB)
        self._running = False

        # Components
        self.source: Optional[BaseSource] = None
        self.sorter = SerialSorter()
        self.decoder: Optional[PacketDecoder] = None
        self.mapper: Optional[TelemetryMapper] = None

        # Tasks
        self._pipeline_task: Optional[asyncio.Task] = None
        self._persistence_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the telemetry pipeline"""
        if self._running:
            logger.warning("Pipeline already running")
            return

        self._running = True

        # Initialize components
        await self._initialize_components()

        # Start background tasks
        self._pipeline_task = asyncio.create_task(self._run_pipeline())
        self._persistence_task = asyncio.create_task(self._run_persistence())

        logger.info("Telemetry pipeline started")

    async def stop(self):
        """Stop the telemetry pipeline"""
        if not self._running:
            return

        self._running = False

        # Stop source
        if self.source:
            await self.source.stop()

        # Cancel tasks
        if self._pipeline_task:
            self._pipeline_task.cancel()
            try:
                await self._pipeline_task
            except asyncio.CancelledError:
                pass

        if self._persistence_task:
            self._persistence_task.cancel()
            try:
                await self._persistence_task
            except asyncio.CancelledError:
                pass

        # Close NDJSON writer
        await self.ndjson_writer.close()

        logger.info("Telemetry pipeline stopped")

    async def _initialize_components(self):
        """Initialize pipeline components from config"""
        # Load sensor configuration
        import sys

        sys.path.append(str(Path(__file__).parent.parent.parent / "old-groundstation"))
        from ConfigLoader import load_config

        bitmask_to_struct, bitmask_to_name, num_sensors = load_config(
            self.config.CONFIG_PATH
        )

        # Set up header info (this needs to be extracted from config)
        # For now, create a basic header info structure
        header_arr = [
            "Millis",
            "ina260_current_ma",
            "ina260_voltage_mv",
            "picotemp_temp_c",
        ]
        header_key = {"Millis": 1, "ina260": 2, "picotemp": 1}
        sensor_arr = ["Millis", "ina260", "picotemp"]
        sensor_reading_order_key = {
            "ina260": ["current_ma", "voltage_mv"],
            "picotemp": ["temp_c"],
        }

        header_info = (header_key, header_arr, sensor_arr, sensor_reading_order_key)

        # Initialize components
        self.decoder = PacketDecoder(bitmask_to_struct, bitmask_to_name, num_sensors)
        self.mapper = TelemetryMapper(header_info)

        # Create appropriate source
        if self.config.SOURCE == "csv":
            self.source = CSVSource(self.config)
        elif self.config.SOURCE == "serial":
            self.source = SerialSource(self.config)
        elif self.config.SOURCE == "binlog":
            self.source = BinaryLogSource(self.config)
        else:
            raise ValueError(f"Unknown source: {self.config.SOURCE}")

    async def _run_pipeline(self):
        """Main pipeline loop"""
        try:
            logger.info("Starting pipeline processing")

            # Get data stream from source
            if self.config.SOURCE == "csv":
                # CSV source yields parsed telemetry directly
                async for telemetry_data in self.source:
                    if telemetry_data and telemetry_data != "ERROR":
                        await self.broadcast_hub.publish(telemetry_data)

            else:  # serial or binlog
                # Serial/binlog sources yield raw bytes, need processing
                async for raw_bytes in self.source:
                    if not raw_bytes:
                        continue

                    # Process bytes through sorter to extract packets
                    # For now, we'll handle packets directly since the sorter is complex
                    # In a real implementation, you'd integrate the sorter properly
                    if raw_bytes.startswith(b"ASU!"):
                        # This is a packet, decode it
                        decoded = await self.decoder.decode_packet(raw_bytes)
                        if decoded and decoded != "ERROR":
                            telemetry = self.mapper.map_telemetry(decoded)
                            if telemetry and telemetry != "ERROR":
                                await self.broadcast_hub.publish(telemetry)

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        finally:
            logger.info("Pipeline processing stopped")

    async def _run_persistence(self):
        """Background persistence task"""
        try:
            logger.info("Starting persistence task")

            # Create a subscriber to get telemetry data
            subscriber = asyncio.Queue(maxsize=1000)

            # Add subscriber to broadcast hub
            self.broadcast_hub.subscribers.add(subscriber)

            try:
                while self._running:
                    try:
                        # Wait for telemetry data with timeout
                        telemetry = await asyncio.wait_for(
                            subscriber.get(), timeout=1.0
                        )
                        await self.ndjson_writer.write_telemetry(telemetry)
                    except asyncio.TimeoutError:
                        continue  # No data, continue loop

            finally:
                # Remove subscriber
                self.broadcast_hub.subscribers.discard(subscriber)

        except Exception as e:
            logger.error(f"Persistence error: {e}")
        finally:
            logger.info("Persistence task stopped")

    def is_running(self) -> bool:
        """Check if pipeline is running"""
        return self._running

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return {
            "status": "running" if self._running else "stopped",
            "subscribers": self.broadcast_hub.get_subscriber_count(),
            "current_file": self.ndjson_writer.get_current_filename(),
            "file_size": self.ndjson_writer.get_current_size(),
        }
