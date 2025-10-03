
*   **PCF8523 (Real-Time Clock):**
    *   **What it is:** A clock that keeps track of the current date and time.
    *   **Data:** `pcf8523_year`, `_month`, `_day`, `_hour`, `_minute`, `_second`.

*   **INA260 (Power Monitor):**
    *   **What it is:** Measures the power consumption of the system.
    *   **Data:** `ina260_current_ma` (current), `ina260_voltage_mv` (voltage), `ina260_power_mw` (power).

*   **PicoTemp (Internal Temperature):**
    *   **What it is:** The internal temperature sensor of the Raspberry Pi Pico microcontroller.
    *   **Data:** `picotemp_temp_c` (temperature in Celsius).

*   **ICM20948 (9-Axis Motion Sensor):**
    *   **What it is:** An Inertial Measurement Unit (IMU) that tracks motion and orientation.
    *   **Data:**
        *   `icm20948_accx_g`, `_accy_g`, `_accz_g`: Acceleration (G-force).
        *   `icm20948_gyrox_deg_s`, `_gyroy_deg_s`, `_gyroz_deg_s`: Rotational speed (degrees per second).
        *   `icm20948_magx_ut`, `_magy_ut`, `_magz_ut`: Magnetic field strength (micro-Teslas).
        *   `icm20948_temp_c`: Its own internal temperature.

*   **MTK3339 (GPS Module):**
    *   **What it is:** Provides global positioning information.
    *   **Data:** `mtk3339_latitude`, `_longitude`, `_altitude`, `_speed`, `_heading`, `_satellites` (number of satellites in view), and GPS time.

*   **BMP390 (Barometric Pressure Sensor):**
    *   **What it is:** Measures atmospheric pressure. Often used to calculate altitude more precisely than GPS alone.
    *   **Data:** `bmp390_pressure_pa` (pressure in Pascals), `bmp390_altitude_m` (calculated altitude), and its own temperature.

*   **TMP117 (High-Precision Temperature Sensor):**
    *   **What it is:** A dedicated sensor for accurate temperature readings.
    *   **Data:** `tmp117_temp_c` (temperature in Celsius).

*   **SHTC3 (Humidity and Temperature Sensor):**
    *   **What it is:** Measures relative humidity and temperature.
    *   **Data:** `shtc3_rel_hum` (relative humidity), `shtc3_temp_c` (temperature).

*   **SCD40 (CO2 Sensor):**
    *   **What it is:** Measures carbon dioxide concentration in the air.
    *   **Data:** `scd40_co2_conc_ppm` (CO2 in parts per million), and its own temperature and humidity readings.

*   **ENS160 (Air Quality Sensor):**
    *   **What it is:** Monitors various aspects of air quality.
    *   **Data:** `ens160_aqi` (Air Quality Index), `ens160_tvoc_ppb` (Total Volatile Organic Compounds), `ens160_eco2_ppm` (equivalent CO2).

*   **Ozone Sensor:**
    *   **What it is:** Measures the concentration of ozone gas.
    *   **Data:** `ozone_conc_ppb` (ozone in parts per billion).

*   **UV Sensor:**
    *   **What it is:** Measures the intensity of ultraviolet light across different bands.
    *   **Data:** `uv_sensor_uva2_nm`, `_uvb2_nm`, `_uvc2_nm` (intensity for UVA, UVB, and UVC bands).
