import asyncio
import logging
import os
import socket
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.cors import CORSMiddleware

from src.config import UDP_HOST, UDP_PORT
from src.decoder import parse_packet, validate_checksum
from src.schema import FlightTelemetry as FlightTelemetryModel
from src.schema import db, init_database

# Configure logging to output to stderr (captured by systemd/journalctl)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,  # Output to stderr for journalctl
)
logger = logging.getLogger(__name__)


# Set up uncaught exception handler for async tasks
def handle_exception(loop, context):
    """Handle uncaught exceptions in asyncio event loop."""
    exception = context.get("exception")
    if exception:
        logger.error(
            f"Uncaught exception in event loop: {exception}", exc_info=exception
        )
    else:
        error_msg = context.get("message", "Unknown error")
        logger.error(f"Event loop error: {error_msg}")


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


# Add exception handler middleware to catch all exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to log all unhandled exceptions."""
    logger.error(
        f"Unhandled exception in {request.method} {request.url}: {exc}",
        exc_info=exc,
        extra={
            "path": str(request.url),
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "type": type(exc).__name__,
            "detail": str(exc),
        },
    )


# Add CORS middleware - allow all origins for Pi hotspot clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Pi hotspot access
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for SSE
# Reduced queue size for Pi Zero 2 W memory constraints
telemetry_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
socket_task: Optional[asyncio.Task] = None
sock: Optional[socket.socket] = None


def _recv_udp_packet(sock: socket.socket) -> tuple[bytes, tuple]:
    """Blocking UDP receive - called from thread."""
    return sock.recvfrom(1024)


def _create_db_record(record_dict: dict) -> None:
    """Blocking database create operation - called from thread."""
    try:
        FlightTelemetryModel.create(**record_dict)
    except Exception as e:
        # Re-raise so it can be caught by the caller
        raise e


async def socket_listener():
    """Background task to listen for UDP packets, decode them, and store in database."""
    global sock

    # Create UDP socket with SO_REUSEADDR for cleaner restarts
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_HOST, UDP_PORT))
    sock.settimeout(1.0)  # Timeout to allow periodic checks for cancellation
    logger.info(f"Socket listener started on {UDP_HOST}:{UDP_PORT}")

    try:
        while True:
            try:
                # Use asyncio.to_thread for blocking socket operation
                data, addr = await asyncio.to_thread(_recv_udp_packet, sock)
                logger.debug(f"Received {len(data)} bytes from {addr}")

                # Decode the packet
                try:
                    decoded = parse_packet(data)
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

                    # Store in database
                    try:
                        model_fields = set(FlightTelemetryModel._meta.fields.keys())
                        filtered_decoded = {
                            k: v for k, v in decoded.items() if k in model_fields
                        }
                        record_dict = {"raw_bytes": data, **filtered_decoded}
                        await asyncio.to_thread(_create_db_record, record_dict)

                        # Only push to SSE queue if checksum is valid
                        if checksum_valid:
                            telemetry_event = FlightTelemetry(**decoded)
                            try:
                                await telemetry_queue.put(telemetry_event)
                            except asyncio.QueueFull:
                                # Remove oldest and add new
                                try:
                                    await asyncio.wait_for(
                                        telemetry_queue.get(), timeout=0.1
                                    )
                                    await telemetry_queue.put(telemetry_event)
                                except asyncio.TimeoutError:
                                    logger.warning(
                                        "Could not make room in queue, dropping event"
                                    )
                    except Exception as db_error:
                        logger.error(f"Database error: {db_error}", exc_info=True)

                except Exception as decode_error:
                    logger.warning(f"Failed to decode packet: {decode_error}")
                    # Still store raw bytes even if decode fails
                    try:
                        record_dict = {"raw_bytes": data, "millis": 0}
                        await asyncio.to_thread(_create_db_record, record_dict)
                    except Exception as db_error:
                        logger.error(
                            f"Failed to store raw bytes: {db_error}", exc_info=True
                        )

            except (socket.timeout, TimeoutError):
                # Timeout is expected, continue listening
                continue
            except Exception as e:
                logger.error(f"Unexpected error in socket listener: {e}", exc_info=True)
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.info("Socket listener cancelled")
    finally:
        if sock:
            try:
                sock.close()
                logger.info("Socket closed")
            except Exception as e:
                logger.error(f"Error closing socket: {e}", exc_info=True)


async def get_telemetry_generator():
    """Generator function for SSE events - streams real-time telemetry from queue."""
    connection_id = id(asyncio.current_task())
    logger.info(f"SSE client connected (connection_id={connection_id})")

    try:
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
                try:
                    yield {
                        "event": "telemetry",
                        "data": telemetry_event.model_dump_json(),
                        "retry": 1000,
                    }
                except Exception as send_error:
                    # Client likely disconnected - break the loop
                    logger.info(
                        f"Error sending to SSE client (connection_id={connection_id}): {send_error}"
                    )
                    break

            except asyncio.CancelledError:
                logger.info(f"SSE client disconnected (connection_id={connection_id})")
                break
            except GeneratorExit:
                # Client disconnected - this is expected
                logger.info(
                    f"SSE client disconnected via GeneratorExit (connection_id={connection_id})"
                )
                break
            except Exception as e:
                logger.error(
                    f"Unexpected error in SSE generator (connection_id={connection_id}): {e}",
                    exc_info=True,
                )
                try:
                    yield {
                        "event": "error",
                        "data": f"Error: {str(e)}",
                        "retry": 1000,
                    }
                except Exception:
                    # Can't send error - client likely disconnected
                    pass
                break

    finally:
        logger.info(f"SSE generator cleaned up (connection_id={connection_id})")


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
    try:
        response = EventSourceResponse(get_telemetry_generator())
        return response
    except Exception as e:
        logger.error(f"Error creating SSE response: {e}", exc_info=True)
        raise


@app.on_event("startup")
async def startup_event():
    """Initialize database and start socket listener on startup."""
    global socket_task

    logger.info("Starting up FastAPI application...")

    # Set exception handler for this event loop
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)

    # Initialize database
    try:
        await asyncio.to_thread(init_database)
        logger.info("Database initialized")
    except Exception as e:
        logger.critical(f"Failed to initialize database: {e}", exc_info=True)
        raise

    # Start socket listener as background task
    socket_task = asyncio.create_task(socket_listener())
    socket_task.add_done_callback(
        lambda task: logger.error(
            f"Socket listener task ended unexpectedly: {task.exception()}",
            exc_info=task.exception(),
        )
        if task.exception()
        else None
    )
    logger.info("Socket listener task started")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    global socket_task, sock

    logger.info("Shutting down FastAPI application...")

    # Cancel socket listener task
    if socket_task and not socket_task.done():
        logger.info("Cancelling socket listener task...")
        socket_task.cancel()
        try:
            await asyncio.wait_for(socket_task, timeout=5.0)
        except asyncio.CancelledError:
            pass
        except asyncio.TimeoutError:
            logger.warning("Socket task did not cancel within timeout")
        except Exception as e:
            logger.error(f"Error cancelling socket task: {e}", exc_info=True)

    # Close socket
    if sock:
        try:
            sock.close()
            logger.info("Socket closed")
        except Exception as e:
            logger.error(f"Error closing socket: {e}", exc_info=True)

    # Close database connection
    try:
        if not db.is_closed():
            await asyncio.to_thread(db.close)
            logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}", exc_info=True)
