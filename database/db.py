# db.py -- MySQL connection helper and simulation logging for CropSim.
# Credentials are read from environment variables with safe localhost defaults.

import os
import json
import logging

import mysql.connector
from mysql.connector import Error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (override with env vars in production)
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME",     "agrichain"),
    "port":     int(os.getenv("DB_PORT", 3306)),
}

_CREATE_SIMULATIONS = """
CREATE TABLE IF NOT EXISTS cropsim_simulations (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    farmer_id           INT          DEFAULT NULL,
    crop_type           VARCHAR(50)  NOT NULL,
    temp                FLOAT        NOT NULL,
    moisture            FLOAT        DEFAULT NULL,
    ph                  FLOAT        DEFAULT NULL,
    n_value             FLOAT        NOT NULL,
    p_value             FLOAT        NOT NULL,
    k_value             FLOAT        NOT NULL,
    fertilizer          FLOAT        NOT NULL,
    baseline_yield_kg   FLOAT        NOT NULL,
    predicted_yield_kg  FLOAT        NOT NULL,
    overall_stress_pct  FLOAT        NOT NULL,
    stress_breakdown_json JSON       NOT NULL,
    growth_curve_json   JSON         NOT NULL,
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def init_db():
    # Create required tables if they do not already exist. Non-fatal on failure.
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(_CREATE_SIMULATIONS)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("DB: cropsim_simulations table ready.")
    except Error as exc:
        logger.error("DB init failed (continuing without DB): %s", exc)


_INSERT_SIM = """
INSERT INTO cropsim_simulations
    (farmer_id, crop_type, temp, moisture, ph, n_value, p_value, k_value,
     fertilizer, baseline_yield_kg, predicted_yield_kg, overall_stress_pct,
     stress_breakdown_json, growth_curve_json)
VALUES
    (%(farmer_id)s, %(crop_type)s, %(temp)s, %(moisture)s, %(ph)s,
     %(n_value)s, %(p_value)s, %(k_value)s, %(fertilizer)s,
     %(baseline_yield_kg)s, %(predicted_yield_kg)s, %(overall_stress_pct)s,
     %(stress_breakdown_json)s, %(growth_curve_json)s)
"""


def log_simulation(data):
    # Insert a simulation record.  Returns new row id or None on failure.
    # A DB failure must NEVER propagate to the caller -- deliberately non-fatal.
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(_INSERT_SIM, {
            "farmer_id":             data.get("farmer_id"),
            "crop_type":             data["crop_type"],
            "temp":                  data["temp"],
            "moisture":              data.get("moisture"),
            "ph":                    data.get("ph"),
            "n_value":               data["N"],
            "p_value":               data["P"],
            "k_value":               data["K"],
            "fertilizer":            data["fertilizer"],
            "baseline_yield_kg":     data["baseline_yield_kg"],
            "predicted_yield_kg":    data["predicted_yield_kg"],
            "overall_stress_pct":    data["overall_stress_pct"],
            "stress_breakdown_json": json.dumps(data["stress_breakdown"]),
            "growth_curve_json":     json.dumps(data["growth_curve"]),
        })
        conn.commit()
        row_id = cur.lastrowid
        cur.close()
        conn.close()
        return row_id
    except Exception as exc:
        logger.error("DB log_simulation failed: %s", exc)
        return None


def _row_to_dict(columns, row):
    # Zip cursor description with a row, parsing JSON columns back to Python objects.
    record = dict(zip(columns, row))
    for json_col in ("stress_breakdown_json", "growth_curve_json"):
        if json_col in record and isinstance(record[json_col], str):
            record[json_col] = json.loads(record[json_col])
    # Rename JSON columns to friendlier API names
    record["stress_breakdown"] = record.pop("stress_breakdown_json", {})
    record["growth_curve"]     = record.pop("growth_curve_json", [])
    # Convert datetime to ISO-8601 string for JSON serialisation
    if record.get("created_at"):
        record["created_at"] = record["created_at"].isoformat()
    return record


def get_simulation_history(farmer_id=None, limit=20):
    # Return the last `limit` simulations (most recent first).
    # Optionally filter by farmer_id. Returns empty list on DB failure.
    try:
        conn = get_connection()
        cur = conn.cursor()
        if farmer_id is not None:
            cur.execute(
                "SELECT * FROM cropsim_simulations WHERE farmer_id = %s "
                "ORDER BY created_at DESC LIMIT %s",
                (farmer_id, limit)
            )
        else:
            cur.execute(
                "SELECT * FROM cropsim_simulations ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
        columns = [col[0] for col in cur.description]
        rows = [_row_to_dict(columns, row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as exc:
        logger.error("DB get_simulation_history failed: %s", exc)
        return []


def get_simulation_by_id(sim_id):
    # Return a single simulation record by primary key, or None if not found/on error.
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM cropsim_simulations WHERE id = %s", (sim_id,))
        row = cur.fetchone()
        columns = [col[0] for col in cur.description]
        cur.close()
        conn.close()
        if row is None:
            return None
        return _row_to_dict(columns, row)
    except Exception as exc:
        logger.error("DB get_simulation_by_id failed: %s", exc)
        return None

# ---------------------------------------------------------------------------
# sensor_readings table bootstrap  (Part B)
# ---------------------------------------------------------------------------

_CREATE_SENSOR_READINGS = """
CREATE TABLE IF NOT EXISTS sensor_readings (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    device_id   VARCHAR(100)  NOT NULL,
    field_id    INT           DEFAULT NULL,
    moisture    FLOAT         DEFAULT NULL,
    temp        FLOAT         DEFAULT NULL,
    humidity    FLOAT         DEFAULT NULL,
    ph          FLOAT         DEFAULT NULL,
    n_value     FLOAT         DEFAULT NULL,
    p_value     FLOAT         DEFAULT NULL,
    k_value     FLOAT         DEFAULT NULL,
    rainfall    FLOAT         DEFAULT NULL,
    recorded_at TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sensor_device_time (device_id, recorded_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def init_sensor_db():
    # Create sensor_readings table if it doesn't exist. Non-fatal on failure.
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(_CREATE_SENSOR_READINGS)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("DB: sensor_readings table ready.")
    except Error as exc:
        logger.error("DB init_sensor_db failed (continuing without DB): %s", exc)


# ---------------------------------------------------------------------------
# Sensor data insert  (Part B)
# ---------------------------------------------------------------------------

_INSERT_SENSOR = """
INSERT INTO sensor_readings
    (device_id, field_id, moisture, temp, humidity, ph,
     n_value, p_value, k_value, rainfall)
VALUES
    (%(device_id)s, %(field_id)s, %(moisture)s, %(temp)s, %(humidity)s, %(ph)s,
     %(n_value)s, %(p_value)s, %(k_value)s, %(rainfall)s)
"""


def insert_sensor_reading(data):
    # Insert a sensor reading row.  Returns the saved row as a dict, or None on failure.
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(_INSERT_SENSOR, {
            "device_id": data["device_id"],
            "field_id":  data.get("field_id"),
            "moisture":  data.get("moisture"),
            "temp":      data.get("temp"),
            "humidity":  data.get("humidity"),
            "ph":        data.get("ph"),
            "n_value":   data.get("N"),
            "p_value":   data.get("P"),
            "k_value":   data.get("K"),
            "rainfall":  data.get("rainfall"),
        })
        conn.commit()
        row_id = cur.lastrowid
        cur.close()

        # Fetch the saved row so we can return it to the client
        cur = conn.cursor()
        cur.execute("SELECT * FROM sensor_readings WHERE id = %s", (row_id,))
        row = cur.fetchone()
        columns = [col[0] for col in cur.description]
        cur.close()
        conn.close()
        record = dict(zip(columns, row))
        if record.get("recorded_at"):
            record["recorded_at"] = record["recorded_at"].isoformat()
        return record
    except Exception as exc:
        logger.error("DB insert_sensor_reading failed: %s", exc)
        return None


def get_latest_sensor_reading(device_id):
    # Return the most recent reading for device_id, or None if not found / on error.
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM sensor_readings WHERE device_id = %s "
            "ORDER BY recorded_at DESC LIMIT 1",
            (device_id,)
        )
        row = cur.fetchone()
        columns = [col[0] for col in cur.description]
        cur.close()
        conn.close()
        if row is None:
            return None
        record = dict(zip(columns, row))
        if record.get("recorded_at"):
            record["recorded_at"] = record["recorded_at"].isoformat()
        return record
    except Exception as exc:
        logger.error("DB get_latest_sensor_reading failed: %s", exc)
        return None
