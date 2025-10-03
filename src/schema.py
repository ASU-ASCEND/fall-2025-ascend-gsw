from peewee import (
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
    pcf8523_year = IntegerField()
    pcf8523_month = IntegerField()
    pcf8523_day = IntegerField()
    pcf8523_hour = IntegerField()
    pcf8523_minute = IntegerField()
    pcf8523_second = IntegerField()
    ina260_current_ma = FloatField()
    ina260_voltage_mv = FloatField()
    ina260_power_mw = FloatField()
    picotemp_temp_c = FloatField()
    icm20948_accx_g = FloatField()
    icm20948_accy_g = FloatField()
    icm20948_accz_g = FloatField()
    icm20948_gyrox_deg_s = FloatField()
    icm20948_gyroy_deg_s = FloatField()
    icm20948_gyroz_deg_s = FloatField()
    icm20948_magx_ut = FloatField()
    icm20948_magy_ut = FloatField()
    icm20948_magz_ut = FloatField()
    icm20948_temp_c = FloatField()
    mtk3339_year = IntegerField()
    mtk3339_month = IntegerField()
    mtk3339_day = IntegerField()
    mtk3339_hour = IntegerField()
    mtk3339_minute = IntegerField()
    mtk3339_second = IntegerField()
    mtk3339_latitude = FloatField()
    mtk3339_longitude = FloatField()
    mtk3339_speed = FloatField()
    mtk3339_heading = FloatField()
    mtk3339_altitude = FloatField()
    mtk3339_satellites = IntegerField()
    bmp390_temp_c = FloatField()
    bmp390_pressure_pa = FloatField()
    bmp390_altitude_m = FloatField()
    tmp117_temp_c = FloatField()
    shtc3_temp_c = FloatField()
    shtc3_rel_hum = FloatField()
    scd40_co2_conc_ppm = FloatField()
    scd40_temp_c = FloatField()
    scd40_rel_hum = FloatField()
    ens160_aqi = IntegerField()
    ens160_tvoc_ppb = FloatField()
    ens160_eco2_ppm = FloatField()
    ozone_conc_ppb = FloatField()
    uv_sensor_uva2_nm = FloatField()
    uv_sensor_uvb2_nm = FloatField()
    uv_sensor_uvc2_nm = FloatField()
    scd40_o_co2_conc_o_ppm = FloatField()
    scd40_o_temp_o_c = FloatField()
    scd40_o_rel_hum_o = FloatField()
    tmp117_o_temp_o_c = FloatField()
    shtc3_o_temp_o_c = FloatField()
    shtc3_o_rel_hum_o = FloatField()
    ens160_o_aqi_o = IntegerField()
    ens160_o_tvoc_o_ppb = FloatField()
    ens160_o_eco2_o_ppm = FloatField()


if __name__ == "__main__":
    db.connect()
    db.create_tables([FlightTelemetry])
    db.close()
