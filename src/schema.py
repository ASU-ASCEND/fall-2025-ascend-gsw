from peewee import (
    BlobField,
    FloatField,
    IntegerField,
    Model,
    SqliteDatabase,
)

from src.config import DB_PATH

db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class FlightTelemetry(BaseModel):
    millis = IntegerField()
    raw_bytes = BlobField(null=True)
    pcf8523_year = IntegerField(null=True)
    pcf8523_month = IntegerField(null=True)
    pcf8523_day = IntegerField(null=True)
    pcf8523_hour = IntegerField(null=True)
    pcf8523_minute = IntegerField(null=True)
    pcf8523_second = IntegerField(null=True)
    ina260_current_ma = FloatField(null=True)
    ina260_voltage_mv = FloatField(null=True)
    ina260_power_mw = FloatField(null=True)
    picotemp_temp_c = FloatField(null=True)
    icm20948_accx_g = FloatField(null=True)
    icm20948_accy_g = FloatField(null=True)
    icm20948_accz_g = FloatField(null=True)
    icm20948_gyrox_deg_s = FloatField(null=True)
    icm20948_gyroy_deg_s = FloatField(null=True)
    icm20948_gyroz_deg_s = FloatField(null=True)
    icm20948_magx_ut = FloatField(null=True)
    icm20948_magy_ut = FloatField(null=True)
    icm20948_magz_ut = FloatField(null=True)
    icm20948_temp_c = FloatField(null=True)
    mtk3339_year = IntegerField(null=True)
    mtk3339_month = IntegerField(null=True)
    mtk3339_day = IntegerField(null=True)
    mtk3339_hour = IntegerField(null=True)
    mtk3339_minute = IntegerField(null=True)
    mtk3339_second = IntegerField(null=True)
    mtk3339_latitude = FloatField(null=True)
    mtk3339_longitude = FloatField(null=True)
    mtk3339_speed = FloatField(null=True)
    mtk3339_heading = FloatField(null=True)
    mtk3339_altitude = FloatField(null=True)
    mtk3339_satellites = IntegerField(null=True)
    bmp390_temp_c = FloatField(null=True)
    bmp390_pressure_pa = FloatField(null=True)
    bmp390_altitude_m = FloatField(null=True)
    tmp117_temp_c = FloatField(null=True)
    shtc3_temp_c = FloatField(null=True)
    shtc3_rel_hum = FloatField(null=True)
    scd40_co2_conc_ppm = FloatField(null=True)
    scd40_temp_c = FloatField(null=True)
    scd40_rel_hum = FloatField(null=True)
    ens160_aqi = IntegerField(null=True)
    ens160_tvoc_ppb = FloatField(null=True)
    ens160_eco2_ppm = FloatField(null=True)
    ozone_conc_ppb = FloatField(null=True)
    uv_sensor_uva2_nm = FloatField(null=True)
    uv_sensor_uvb2_nm = FloatField(null=True)
    uv_sensor_uvc2_nm = FloatField(null=True)
    scd40_o_co2_conc_o_ppm = FloatField(null=True)
    scd40_o_temp_o_c = FloatField(null=True)
    scd40_o_rel_hum_o = FloatField(null=True)
    tmp117_o_temp_o_c = FloatField(null=True)
    shtc3_o_temp_o_c = FloatField(null=True)
    shtc3_o_rel_hum_o = FloatField(null=True)
    ens160_o_aqi_o = IntegerField(null=True)
    ens160_o_tvoc_o_ppb = FloatField(null=True)
    ens160_o_eco2_o_ppm = FloatField(null=True)
    analog_temp_0_adc_val = IntegerField(null=True)


def init_database():
    """Initialize database connection and create tables if they don't exist."""
    db.connect()
    db.create_tables([FlightTelemetry], safe=True)
    return db


if __name__ == "__main__":
    init_database()
    db.close()
