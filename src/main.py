import asyncio
import logging
import os
import socket
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.cors import CORSMiddleware

from src.config import UDP_HOST, UDP_PORT
from src.decoder import parse_packet, validate_checksum
from src.schema import FlightTelemetry as FlightTelemetryModel
from src.schema import db, init_database

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FlightTelemetry(BaseModel):
    millis: int
    pcf8523_year: Optional[int] = None
    pcf8523_month: Optional[int] = None
    pcf8523_day: Optional[int] = None
    pcf8523_hour: Optional[int] = None
    pcf8523_minute: Optional[int] = None
    pcf8523_second: Optional[int] = None
    ina260_current_ma: Optional[float] = None
    ina260_voltage_mv: Optional[float] = None
    ina260_power_mw: Optional[float] = None
    picotemp_temp_c: Optional[float] = None
    icm20948_accx_g: Optional[float] = None
    icm20948_accy_g: Optional[float] = None
    icm20948_accz_g: Optional[float] = None
    icm20948_gyrox_deg_s: Optional[float] = None
    icm20948_gyroy_deg_s: Optional[float] = None
    icm20948_gyroz_deg_s: Optional[float] = None
    icm20948_magx_ut: Optional[float] = None
    icm20948_magy_ut: Optional[float] = None
    icm20948_magz_ut: Optional[float] = None
    icm20948_temp_c: Optional[float] = None
    mtk3339_year: Optional[int] = None
    mtk3339_month: Optional[int] = None
    mtk3339_day: Optional[int] = None
    mtk3339_hour: Optional[int] = None
    mtk3339_minute: Optional[int] = None
    mtk3339_second: Optional[int] = None
    mtk3339_latitude: Optional[float] = None
    mtk3339_longitude: Optional[float] = None
    mtk3339_speed: Optional[float] = None
    mtk3339_heading: Optional[float] = None
    mtk3339_altitude: Optional[float] = None
    mtk3339_satellites: Optional[int] = None
    bmp390_temp_c: Optional[float] = None
    bmp390_pressure_pa: Optional[float] = None
    bmp390_altitude_m: Optional[float] = None
    tmp117_temp_c: Optional[float] = None
    shtc3_temp_c: Optional[float] = None
    shtc3_rel_hum: Optional[float] = None
    scd40_co2_conc_ppm: Optional[float] = None
    scd40_temp_c: Optional[float] = None
    scd40_rel_hum: Optional[float] = None
    ens160_aqi: Optional[int] = None
    ens160_tvoc_ppb: Optional[float] = None
    ens160_eco2_ppm: Optional[float] = None
    ozone_conc_ppb: Optional[float] = None
    uv_sensor_uva2_nm: Optional[float] = None
    uv_sensor_uvb2_nm: Optional[float] = None
    uv_sensor_uvc2_nm: Optional[float] = None
    scd40_o_co2_conc_o_ppm: Optional[float] = None
    scd40_o_temp_o_c: Optional[float] = None
    scd40_o_rel_hum_o: Optional[float] = None
    tmp117_o_temp_o_c: Optional[float] = None
    shtc3_o_temp_o_c: Optional[float] = None
    shtc3_o_rel_hum_o: Optional[float] = None
    ens160_o_aqi_o: Optional[int] = None
    ens160_o_tvoc_o_ppb: Optional[float] = None
    ens160_o_eco2_o_ppm: Optional[float] = None
    analog_temp_0_adc_val: Optional[int] = None

    class Config:
        from_attributes = True


app = FastAPI()

# Add CORS middleware - allow all origins for Pi hotspot clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Pi hotspot access
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for SSE
telemetry_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
socket_task: Optional[asyncio.Task] = None
sock: Optional[socket.socket] = None


def _recv_udp_packet(sock: socket.socket) -> tuple[bytes, tuple]:
    """Blocking UDP receive - called from thread."""
    return sock.recvfrom(1024)


async def socket_listener():
    """Background task to listen for UDP packets, decode them, and store in database."""
    global sock

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.settimeout(1.0)  # Timeout to allow periodic checks

    logger.info(f"Socket listener started on {UDP_HOST}:{UDP_PORT}")

    while True:
        try:
            # Use asyncio.to_thread for blocking socket operation
            data, addr = await asyncio.to_thread(_recv_udp_packet, sock)
            logger.debug(f"Received {len(data)} bytes from {addr}")

            # Decode the packet
            try:
                decoded = parse_packet(data)

                # Validate checksum before processing
                checksum_position = len(data) - 1
                checksum_valid = validate_checksum(data, checksum_position)

                if not checksum_valid:
                    logger.warning(
                        f"Checksum validation failed for packet with millis={decoded.get('millis', 'unknown')}. "
                        "Skipping SSE broadcast but storing in database for analysis."
                    )

                logger.info(
                    f"Decoded packet with millis: {decoded.get('millis')} "
                    f"(checksum: {'VALID' if checksum_valid else 'INVALID'})"
                )

                # Store in database (even if checksum fails, for debugging/analysis)
                try:
                    # Create database record with raw bytes and decoded values
                    # Filter decoded dict to only include fields that exist in the model
                    model_fields = set(FlightTelemetryModel._meta.fields.keys())
                    filtered_decoded = {
                        k: v for k, v in decoded.items() if k in model_fields
                    }
                    record_dict = {"raw_bytes": data, **filtered_decoded}
                    FlightTelemetryModel.create(**record_dict)
                    logger.debug(
                        f"Stored telemetry record with millis: {decoded.get('millis')}"
                    )

                    # Only push to SSE queue if checksum is valid
                    if checksum_valid:
                        # Convert to Pydantic model for consistency
                        telemetry_event = FlightTelemetry(**decoded)
                        try:
                            await telemetry_queue.put(telemetry_event)
                        except asyncio.QueueFull:
                            logger.warning(
                                "Telemetry queue is full, dropping oldest event"
                            )
                            # Remove oldest and add new
                            try:
                                await asyncio.wait_for(
                                    telemetry_queue.get(), timeout=0.1
                                )
                                await telemetry_queue.put(telemetry_event)
                            except asyncio.TimeoutError:
                                logger.error(
                                    "Could not make room in queue, dropping event"
                                )
                    else:
                        logger.debug("Skipping SSE broadcast due to invalid checksum")

                except Exception as db_error:
                    logger.error(f"Database error: {db_error}", exc_info=True)

            except Exception as decode_error:
                logger.warning(f"Failed to decode packet: {decode_error}")
                # Still store raw bytes even if decode fails
                try:
                    FlightTelemetryModel.create(
                        raw_bytes=data,
                        millis=0,  # Default millis if decode fails
                    )
                except Exception as db_error:
                    logger.error(f"Failed to store raw bytes: {db_error}")

        except (socket.timeout, TimeoutError):
            # Timeout is expected, continue listening
            continue
        except asyncio.CancelledError:
            logger.info("Socket listener cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in socket listener: {e}", exc_info=True)
            await asyncio.sleep(1)  # Brief pause before retrying


async def get_telemetry_generator():
    """Generator function for SSE events - streams real-time telemetry from queue."""
    logger.info("SSE client connected")

    while True:
        try:
            # Wait for telemetry data from queue with timeout
            try:
                telemetry_event = await asyncio.wait_for(
                    telemetry_queue.get(), timeout=30.0
                )
            except asyncio.TimeoutError:
                # Send keepalive to prevent connection timeout
                yield {
                    "event": "ping",
                    "data": "keepalive",
                    "retry": 1000,
                }
                continue

            # Send telemetry event
            yield {
                "event": "telemetry",
                "data": telemetry_event.model_dump_json(),
                "retry": 1000,
            }

        except asyncio.CancelledError:
            logger.info("SSE client disconnected")
            break
        except Exception as e:
            logger.error(f"Error in SSE generator: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": f"Error: {str(e)}",
                "retry": 1000,
            }
            break


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health-check")
def health_check():
    return {
        "uname": os.uname(),
        "pid": os.getpid(),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/telemetry-events")
async def telemetry_events():
    """SSE endpoint for telemetry events"""
    return EventSourceResponse(get_telemetry_generator())


@app.on_event("startup")
async def startup_event():
    """Initialize database and start socket listener on startup."""
    global socket_task

    logger.info("Starting up FastAPI application...")

    # Initialize database
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise

    # Start socket listener as background task
    socket_task = asyncio.create_task(socket_listener())
    logger.info("Socket listener task started")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global socket_task, sock

    logger.info("Shutting down FastAPI application...")

    # Cancel socket listener task
    if socket_task:
        socket_task.cancel()
        try:
            await socket_task
        except asyncio.CancelledError:
            pass
        logger.info("Socket listener task cancelled")

    # Close socket
    if sock:
        sock.close()
        logger.info("Socket closed")

    # Close database connection
    if not db.is_closed():
        db.close()
        logger.info("Database connection closed")
