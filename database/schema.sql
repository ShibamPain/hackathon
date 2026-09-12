-- schema.sql
-- CropSim MySQL schema for AgriChain.
-- All tables are also auto-created at Flask startup via db.init_db().
-- This file is for manual setup, migrations, and DBA reference.

CREATE DATABASE IF NOT EXISTS agrichain
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE agrichain;

-- -----------------------------------------------------------------------
-- Table: cropsim_simulations
-- Stores every /api/cropsim prediction result for history & admin view.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cropsim_simulations (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    farmer_id           INT          DEFAULT NULL        COMMENT "NULL until auth is added",
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
    stress_breakdown_json JSON       NOT NULL            COMMENT "Per-parameter stress scores",
    growth_curve_json   JSON         NOT NULL            COMMENT "90-day daily yield array",
    created_at          TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_farmer_created (farmer_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------
-- Table: sensor_readings
-- Stores ESP32 telemetry pushed via POST /api/sensor-data.
-- Not every device has every sensor, so most columns are nullable.
-- -----------------------------------------------------------------------
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
