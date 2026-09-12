# app.py -- CropSim + Crop Recommendation Flask backend (AgriChain hackathon project)
# Extends the ML yield prediction with stress modelling, MySQL logging, Fabric
# submission, sensor ingestion, and the AI-based Crop Recommendation feature.

import logging
import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import joblib

from stress_engine import apply_stress_to_yield
from crop_profiles import DEFAULT_CROP, CROP_PROFILES
from crop_recommendation import recommend_crops
from db import (
    init_db, log_simulation, get_simulation_history, get_simulation_by_id,
    init_sensor_db, insert_sensor_reading, get_latest_sensor_reading,
)
from fabric_client import submit_yield_record
from sensor_validator import validate_sensor_payload

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)  # Allow the frontend (any origin) to talk to this API

# Load the pre-trained RandomForestRegressor (never retrain at runtime)
model = joblib.load("cropsim_model.pkl")

# Ensure both DB tables exist before the first request arrives
init_db()
init_sensor_db()


# ---------------------------------------------------------------------------
# Shared pipeline helper
# ---------------------------------------------------------------------------
# /api/cropsim, /api/cropsim/auto, and /api/crop-recommendation/full-pipeline
# all need to: predict yield -> apply stress -> log to MySQL -> submit to
# Fabric. This helper does all four steps once so the three endpoints stay
# thin and can never drift out of sync with each other.

def run_cropsim_pipeline(temp, N, P, K, fertilizer, crop_type,
                          moisture=None, ph=None, farmer_id=None,
                          source="manual", device_id=None, sensor_reading_id=None):
    """
    Runs the full CropSim pipeline (predict -> stress -> log -> blockchain)
    and returns a dict ready to be merged straight into a jsonify() response.
    Never raises: DB and Fabric failures are caught and marked non-fatal,
    matching the existing behaviour of /api/cropsim and /api/cropsim/auto.
    """
    # 1. ML model predicts unstressed baseline yield
    features = [[temp, N, P, K, fertilizer]]
    predicted_yield = float(model.predict(features)[0])

    # 2. Stress engine adjusts yield and builds the 90-day growth curve
    stress_inputs = {"temp": temp, "N": N, "P": P, "K": K, "moisture": moisture, "ph": ph}
    stress_result = apply_stress_to_yield(predicted_yield, stress_inputs, crop_type)

    # 3. Persist simulation to MySQL (non-fatal)
    sim_id = None
    try:
        sim_id = log_simulation({
            "farmer_id":          farmer_id,
            "crop_type":          crop_type,
            "temp":               temp,
            "moisture":           moisture,
            "ph":                 ph,
            "N":                  N,
            "P":                  P,
            "K":                  K,
            "fertilizer":         fertilizer,
            "baseline_yield_kg":  round(predicted_yield, 2),
            "predicted_yield_kg": stress_result["adjusted_yield_kg"],
            "overall_stress_pct": stress_result["overall_stress_pct"],
            "stress_breakdown":   stress_result["stress_breakdown"],
            "growth_curve":       stress_result["growth_curve"],
        })
    except Exception as exc:
        app.logger.error("Simulation logging error (non-fatal): %s", exc)

    # 4. Submit to Fabric ledger (stub) -- non-fatal; never blocks the response
    blockchain_receipt = None
    try:
        blockchain_receipt = submit_yield_record({
            "simulation_id":      sim_id,
            "crop_type":          crop_type,
            "predicted_yield_kg": stress_result["adjusted_yield_kg"],
            "overall_stress_pct": stress_result["overall_stress_pct"],
            "created_at":         datetime.datetime.utcnow().isoformat() + "Z",
            "source":             source,
            "device_id":          device_id,
        })
    except Exception as exc:
        app.logger.error("Fabric submit error (non-fatal): %s", exc)

    result = {
        "simulation_id":       sim_id,
        "crop_type":           crop_type,
        "baseline_yield_kg":   round(predicted_yield, 2),
        "predicted_yield_kg":  stress_result["adjusted_yield_kg"],
        "overall_stress_pct":  stress_result["overall_stress_pct"],
        "stress_breakdown":    stress_result["stress_breakdown"],
        "days":                list(range(1, 91)),
        "growth_curve":        stress_result["growth_curve"],
        "daily_stress_factor": stress_result["daily_stress_factor"],
        "blockchain": {
            "status":    blockchain_receipt["status"]    if blockchain_receipt else "unavailable",
            "tx_id":     blockchain_receipt["tx_id"]     if blockchain_receipt else None,
            "chaincode": blockchain_receipt["chaincode"] if blockchain_receipt else None,
        },
    }
    if source == "sensor":
        result["source"] = "sensor"
        result["device_id"] = device_id
        result["sensor_reading_id"] = sensor_reading_id

    return result


# ---------------------------------------------------------------------------
# Core simulation endpoint
# ---------------------------------------------------------------------------

@app.route("/api/cropsim", methods=["POST"])
def simulate():
    data = request.json or {}

    # Collect inputs with sensible defaults so the UI can send partial data
    temp       = float(data.get("temp",       25))
    N          = float(data.get("N",          40))
    P          = float(data.get("P",          20))
    K          = float(data.get("K",          20))
    fertilizer = float(data.get("fertilizer", 10))
    crop_type  = data.get("crop_type", DEFAULT_CROP)
    moisture   = data.get("moisture")   # optional -- may be None
    ph         = data.get("ph")         # optional -- may be None
    farmer_id  = data.get("farmer_id")  # optional until auth exists

    result = run_cropsim_pipeline(
        temp, N, P, K, fertilizer, crop_type,
        moisture=moisture, ph=ph, farmer_id=farmer_id, source="manual",
    )
    return jsonify({"status": "success", **result})


# ---------------------------------------------------------------------------
# Supported crops listing
# ---------------------------------------------------------------------------

@app.route("/api/cropsim/crops", methods=["GET"])
def list_supported_crops():
    return jsonify({"status": "success", "supported_crops": list(CROP_PROFILES.keys())})


# ---------------------------------------------------------------------------
# Simulation history endpoints  (Part A)
# ---------------------------------------------------------------------------

@app.route("/api/cropsim/history", methods=["GET"])
def simulation_history():
    # Return the last 20 simulations; optionally filter by farmer_id query param.
    farmer_id = request.args.get("farmer_id", type=int)
    rows = get_simulation_history(farmer_id=farmer_id, limit=20)
    return jsonify({"status": "success", "count": len(rows), "simulations": rows})


@app.route("/api/cropsim/history/<int:sim_id>", methods=["GET"])
def simulation_detail(sim_id):
    # Return the full detail of a single simulation by its database id.
    row = get_simulation_by_id(sim_id)
    if row is None:
        return jsonify({"status": "error", "message": f"Simulation {sim_id} not found."}), 404
    return jsonify({"status": "success", "simulation": row})


# ---------------------------------------------------------------------------
# Part B: Sensor Data Ingestion
# ---------------------------------------------------------------------------

@app.route("/api/sensor-data", methods=["POST"])
def ingest_sensor_data():
    # Accept ESP32 telemetry.  device_id is required; all sensor fields optional.
    data = request.json or {}
    normalised, errors = validate_sensor_payload(data)

    if errors:
        return jsonify({"status": "error", "errors": errors}), 400

    saved = insert_sensor_reading(normalised)
    if saved is None:
        return jsonify({"status": "error", "message": "Failed to save sensor reading."}), 500

    return jsonify({"status": "success", "reading": saved}), 201


@app.route("/api/sensor-data/latest", methods=["GET"])
def latest_sensor_data():
    # Return the most recent reading for a given device_id.
    device_id = request.args.get("device_id", "").strip()
    if not device_id:
        return jsonify({"status": "error", "message": "device_id query param is required."}), 400

    reading = get_latest_sensor_reading(device_id)
    if reading is None:
        return jsonify({"status": "error", "message": f"No readings found for device '{device_id}'."}), 404

    return jsonify({"status": "success", "reading": reading})


@app.route("/api/cropsim/auto", methods=["POST"])
def auto_simulate():
    # Bridge endpoint: pull latest sensor data for a device and run CropSim on it.
    # Falls back to safe defaults for any sensor field the device doesn't provide.
    data = request.json or {}

    device_id = data.get("device_id", "").strip()
    if not device_id:
        return jsonify({"status": "error", "message": "device_id is required."}), 400

    crop_type = data.get("crop_type", DEFAULT_CROP)
    farmer_id = data.get("farmer_id")

    # Fetch latest sensor reading for this device
    reading = get_latest_sensor_reading(device_id)
    if reading is None:
        return jsonify({
            "status": "error",
            "message": f"No sensor readings found for device '{device_id}'. "
                       "Push data via POST /api/sensor-data first."
        }), 404

    # Map sensor reading -> simulation inputs, falling back to CropSim defaults
    temp       = float(reading.get("temp")     or data.get("temp",       25))
    N          = float(reading.get("n_value")  or data.get("N",          40))
    P          = float(reading.get("p_value")  or data.get("P",          20))
    K          = float(reading.get("k_value")  or data.get("K",          20))
    fertilizer = float(data.get("fertilizer",  10))   # sensors don't measure fertilizer
    moisture   = reading.get("moisture")  or data.get("moisture")
    ph         = reading.get("ph")        or data.get("ph")

    result = run_cropsim_pipeline(
        temp, N, P, K, fertilizer, crop_type,
        moisture=moisture, ph=ph, farmer_id=farmer_id,
        source="sensor", device_id=device_id, sensor_reading_id=reading.get("id"),
    )
    return jsonify({"status": "success", **result})


# ---------------------------------------------------------------------------
# AI-based Crop Recommendation
# ---------------------------------------------------------------------------

@app.route("/api/crop-recommendation", methods=["POST"])
def crop_recommendation():
    """
    Standalone recommendation. Expects: N, P, K, temperature, humidity, ph, rainfall
    Returns top-3 ranked crop suggestions with confidence scores.
    """
    data = request.json or {}
    result = recommend_crops(data, top_n=3)

    if result["status"] == "error":
        return jsonify(result), 400

    # Lets the frontend know whether it can immediately chain into CropSim
    result["cropsim_supported"] = result["top_recommendation"] in CROP_PROFILES
    return jsonify(result)


@app.route("/api/crop-recommendation/full-pipeline", methods=["POST"])
def crop_recommendation_full_pipeline():
    """
    Chains Crop Recommendation -> CropSim (with full DB logging + Fabric
    submission, via the same run_cropsim_pipeline() helper /api/cropsim uses).

    Expects: N, P, K, temperature, humidity, ph, rainfall
             optional: fertilizer, moisture, farmer_id
             ('moisture' is soil moisture; 'humidity' is air humidity used by
             the recommendation model -- both can be supplied separately)
    """
    data = request.json or {}
    rec_result = recommend_crops(data, top_n=3)

    if rec_result["status"] == "error":
        return jsonify(rec_result), 400

    top_crop = rec_result["top_recommendation"]

    if top_crop not in CROP_PROFILES:
        return jsonify({
            "status": "success",
            "recommendation": rec_result,
            "cropsim_result": None,
            "note": (
                f"'{top_crop}' was recommended but doesn't have a CropSim "
                f"stress profile yet. Supported crops: {list(CROP_PROFILES.keys())}"
            ),
        })

    fertilizer = float(data.get("fertilizer", 10))
    N          = float(data.get("N"))
    P          = float(data.get("P"))
    K          = float(data.get("K"))
    temp       = float(data.get("temperature"))
    ph         = data.get("ph")
    moisture   = data.get("moisture")   # optional, distinct from 'humidity'
    farmer_id  = data.get("farmer_id")

    cropsim_result = run_cropsim_pipeline(
        temp, N, P, K, fertilizer, top_crop,
        moisture=moisture, ph=ph, farmer_id=farmer_id, source="manual",
    )

    return jsonify({
        "status": "success",
        "recommendation": rec_result,
        "cropsim_result": cropsim_result,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)