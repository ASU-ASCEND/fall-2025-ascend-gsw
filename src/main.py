import asyncio
import os
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.cors import CORSMiddleware

from src.schema import FlightTelemetry as FlightTelemetryModel
from src.schema import db


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

    class Config:
        from_attributes = True


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for SSE timing
telemetry_data = []
start_time = None
data_lock = asyncio.Lock()


async def load_telemetry_data():
    """Load telemetry data from database and sort by millis"""
    global telemetry_data
    if not telemetry_data:
        db.connect()
        query = FlightTelemetryModel.select().order_by(FlightTelemetryModel.millis)
        telemetry_data = list(query)
        db.close()
    return telemetry_data


async def get_telemetry_generator():
    """Generator function for SSE events"""
    global start_time

    # Load data if not already loaded
    data = await load_telemetry_data()
    if not data:
        yield {"event": "error", "data": "No telemetry data available"}
        return

    # Set start time on first connection
    async with data_lock:
        if start_time is None:
            start_time = time.time()

    # Get the start time for this session
    session_start = start_time

    # Find the earliest millis value to use as our reference point
    earliest_millis = data[0].millis if data else 0

    # Track which events we've sent
    sent_events = set()

    while True:
        try:
            # Calculate elapsed time since first connection (in milliseconds)
            current_time = time.time()
            elapsed_ms = int((current_time - session_start) * 1000)
            current_millis = earliest_millis + elapsed_ms

            # Check for events that should be sent now
            events_to_send = []
            for record in data:
                record_millis = record.millis
                record_id = record.id

                # Send event if it's time and we haven't sent it yet
                if record_millis <= current_millis and record_id not in sent_events:
                    events_to_send.append(record)
                    sent_events.add(record_id)

            # Send events
            for record in events_to_send:
                # Log the millisecond timestamp for each event
                print(f"Sent telemetry event at millis: {record.millis}")

                # Convert Peewee model to Pydantic model for proper JSON serialization
                record_dict = record.__data__
                # Handle None values and empty strings for optional fields
                cleaned_dict = {}
                for key, value in record_dict.items():
                    if value is None or value == "" or value == 0:
                        # Convert empty strings and 0 values to None for optional fields
                        cleaned_dict[key] = None
                    else:
                        cleaned_dict[key] = value

                telemetry_event = FlightTelemetry(**cleaned_dict)
                yield {
                    "event": "telemetry",
                    "data": telemetry_event.model_dump_json(),
                    "id": str(record.id),
                    "retry": 1000,
                }

            # Check if we've sent all events
            if len(sent_events) >= len(data):
                # All events sent, send completion event
                yield {
                    "event": "complete",
                    "data": "All telemetry events sent",
                    "id": "complete",
                    "retry": 1000,
                }
                break

            # Wait a bit before checking again (10ms precision)
            await asyncio.sleep(0.01)

        except asyncio.CancelledError:
            break
        except Exception as e:
            yield {"event": "error", "data": f"Error: {str(e)}", "retry": 1000}
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
