# app.py -- CropSim + Crop Recommendation Flask backend (AgriChain hackathon project)
# Extends the ML yield prediction with stress modelling, MySQL logging, Fabric
# submission, sensor ingestion, and the AI-based Crop Recommendation feature.

import os
import sys
import logging
import datetime
import csv
import random
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import joblib

ROOT_DIR = Path(__file__).resolve().parent
CROPSIM_DIR = ROOT_DIR / "cropSim&crop_recommendation"
MODELS_DIR = CROPSIM_DIR / "models"
UTILS_DIR = CROPSIM_DIR / "utils"
FRONTEND_DIR = ROOT_DIR / "frontend"
for path in (str(ROOT_DIR), str(CROPSIM_DIR), str(MODELS_DIR), str(UTILS_DIR)):
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


def load_env_file(env_path):
    """Load key=value pairs from a .env file without requiring python-dotenv."""
    if not env_path or not os.path.exists(env_path):
        return
    for raw_line in open(env_path, "r", encoding="utf-8"):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_env_file(ROOT_DIR / ".env")
load_env_file(FRONTEND_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

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

BASE_DIR = ROOT_DIR
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)  # Allow the frontend (any origin) to talk to this API

# Load the pre-trained RandomForestRegressor (never retrain at runtime)
MODEL_PATH = MODELS_DIR / "cropsim_model.pkl"
if not MODEL_PATH.exists():
    raise FileNotFoundError(f"CropSim model not found at {MODEL_PATH}")
model = joblib.load(str(MODEL_PATH))

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
# Digital Twin / Crop Simulation endpoint aligned with the frontend contract
# ---------------------------------------------------------------------------

VALID_SOIL_TYPES = {"Clay": 1.3, "Sandy": 0.7, "Loamy": 1.0}


def evaluate_crop_simulation_payload(payload):
    """Validate and compute a crop simulation result from raw UI inputs."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    required_fields = [
        "sunlight", "rainfall", "temperature", "soil_type", "irrigation",
        "fertilizer", "pesticide_applied", "insects"
    ]
    missing = [field for field in required_fields if field not in payload or payload[field] is None]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    soil_type = str(payload["soil_type"]).strip()
    if soil_type not in VALID_SOIL_TYPES:
        raise ValueError("soil_type must be one of: Clay, Sandy, Loamy")

    if not isinstance(payload["pesticide_applied"], bool):
        raise ValueError("pesticide_applied must be a boolean")

    numeric_fields = {
        "sunlight": (0, 100),
        "rainfall": (0, 100),
        "temperature": (0, 50),
        "irrigation": (0, 100),
        "fertilizer": (0, 100),
        "insects": (0, 100),
    }
    for field, (low, high) in numeric_fields.items():
        try:
            value = float(payload[field])
        except (TypeError, ValueError):
            raise ValueError(f"{field} must be numeric") from None
        if not (low <= value <= high):
            raise ValueError(f"{field} must be between {low} and {high}")
        payload[field] = value

    rainfall = float(payload["rainfall"])
    irrigation = float(payload["irrigation"])
    sunlight = float(payload["sunlight"])
    temperature = float(payload["temperature"])
    fertilizer = float(payload["fertilizer"])
    insects = float(payload["insects"])
    pesticide_applied = bool(payload["pesticide_applied"])

    water_multiplier = VALID_SOIL_TYPES[soil_type]
    total_water = (rainfall + irrigation) * water_multiplier
    effective_pests = 0 if pesticide_applied else insects

    status_text = "Optimal Conditions: Crop is thriving!"
    health_score = 100
    image_filter = "brightness(1) sepia(0) hue-rotate(0deg) grayscale(0)"

    if effective_pests > 60:
        status_text = "Critical: Severe Pest Attack!"
        health_score -= 60
        image_filter = "grayscale(0.8) brightness(0.6)"
    elif total_water > 130:
        status_text = f"Warning: Waterlogged! Roots are rotting in {soil_type} soil."
        health_score -= 40
        image_filter = "saturate(0.4) sepia(0.5) hue-rotate(-20deg)"
    elif total_water < 40:
        status_text = "Warning: Drought! Leaves are drying out."
        health_score -= 50
        image_filter = "sepia(0.8) hue-rotate(-30deg) brightness(0.9)"
    elif temperature > 38:
        status_text = "Stress: Extreme Heat!"
        health_score -= 30
        image_filter = "sepia(0.4) brightness(1.1)"
    elif sunlight < 30:
        status_text = "Notice: Low Sunlight. Growth stunted."
        health_score -= 20
        image_filter = "brightness(0.7) saturate(0.8)"
    elif fertilizer > 85:
        status_text = "Warning: Fertilizer Burn!"
        health_score -= 25
        image_filter = "saturate(1.5) hue-rotate(-10deg)"

    return {
        "inputs": {
            "sunlight": sunlight,
            "rainfall": rainfall,
            "temperature": temperature,
            "soil_type": soil_type,
            "irrigation": irrigation,
            "fertilizer": fertilizer,
            "pesticide_applied": pesticide_applied,
            "insects": insects,
        },
        "results": {
            "health_score": max(0, int(round(health_score))),
            "status_text": status_text,
            "total_water": round(total_water, 2),
            "effective_pests": round(effective_pests, 2),
            "image_filter": image_filter,
        },
        "evaluated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@app.route("/api/crop-simulation/evaluate", methods=["POST"])
def evaluate_crop_simulation():
    try:
        payload = request.get_json(force=True, silent=False)
        result = evaluate_crop_simulation_payload(payload)
        return jsonify({"status": "success", **result}), 200
    except (TypeError, ValueError) as exc:
        return jsonify({"status": "error", "error": str(exc)}), 400


@app.route("/api/crop-simulation/history", methods=["GET"])
def crop_simulation_history():
    records = get_simulation_history(limit=20)
    items = [{
        "id": item.get("id"),
        "crop_name": item.get("crop_type"),
        "location": "Local farm",
        "health_score": 0,
        "status_text": "Stored simulation",
        "evaluated_at": item.get("created_at"),
    } for item in records]
    return jsonify({"items": items, "count": len(items)})


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


def _read_crop_recommendations():
    """Compatibility helper for the frontend farm-info UI."""
    csv_path = os.path.join(ROOT_DIR, "frontend", "crops.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join(ROOT_DIR, "data", "crops.csv")

    rows = []
    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))

    if not rows:
        rows = [
            {"soil_type": "Clay", "crop_name": "Rice", "expected_profit": "₹25,000/acre", "risk_level": "Low"},
            {"soil_type": "Clay", "crop_name": "Wheat", "expected_profit": "₹18,000/acre", "risk_level": "Medium"},
            {"soil_type": "Sandy", "crop_name": "Groundnut", "expected_profit": "₹22,000/acre", "risk_level": "Medium"},
            {"soil_type": "Loamy", "crop_name": "Sugarcane", "expected_profit": "₹35,000/acre", "risk_level": "Low"},
            {"soil_type": "Red", "crop_name": "Millet", "expected_profit": "₹15,000/acre", "risk_level": "Low"},
            {"soil_type": "Black", "crop_name": "Soybean", "expected_profit": "₹24,000/acre", "risk_level": "Medium"},
            {"soil_type": "Alluvial", "crop_name": "Rice", "expected_profit": "₹27,000/acre", "risk_level": "Low"},
        ]

    return rows


@app.route("/api/recommend", methods=["POST"])
def recommend_compat():
    """Frontend compatibility endpoint for the Farmer dashboard."""
    data = request.get_json(force=True, silent=True) or {}
    soil_type = str(data.get("soil_type", "")).strip()
    location = str(data.get("location", "")).strip()

    if not soil_type:
        return jsonify({"error": "soil_type is required"}), 400

    matches = [
        row for row in _read_crop_recommendations()
        if str(row.get("soil_type", "")).lower() == soil_type.lower()
    ]

    return jsonify({
        "soil_type": soil_type,
        "location": location,
        "recommendations": matches,
    })


@app.route("/api/weather", methods=["GET"])
def weather_compat():
    """Frontend compatibility endpoint for the Predictor tab."""
    return jsonify({
        "rainfall_mm": round(random.uniform(50, 350), 1),
        "yield_prediction_pct": round(random.uniform(55, 98), 1),
        "temperature_c": round(random.uniform(22, 42), 1),
        "humidity_pct": round(random.uniform(40, 95), 1),
        "soil_ph": round(random.uniform(6.0, 7.5), 2),
        "season": random.choice(["Kharif", "Rabi", "Zaid"]),
    })


@app.route("/api/forum", methods=["GET"])
def forum_compat():
    """Forum data used by the frontend community tab."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/forum_questions?select=*",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                rows = resp.json()
                if rows:
                    return jsonify(rows)
        except Exception as exc:
            logging.warning("Supabase forum fetch failed: %s", exc)

    csv_path = FRONTEND_DIR / "forum.csv"
    if not csv_path.exists():
        csv_path = ROOT_DIR / "data" / "forum.csv"
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as handle:
            return jsonify(list(csv.DictReader(handle)))
    return jsonify([])


@app.route("/api/retailer/locations", methods=["GET"])
def retailer_locations_compat():
    """District/crop dropdowns for the farmer/retailer dashboard."""
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/wb_crop_data?select=district,crop_name",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                rows = resp.json()
                if rows:
                    mapping = {}
                    for row in rows:
                        district = row.get("district")
                        crop = row.get("crop_name")
                        if district and crop:
                            mapping.setdefault(district, [])
                            if crop not in mapping[district]:
                                mapping[district].append(crop)
                    if mapping:
                        return jsonify(mapping)
        except Exception as exc:
            logging.warning("Supabase retailer locations fetch failed: %s", exc)

    csv_path = FRONTEND_DIR / "crops.csv"
    if not csv_path.exists():
        csv_path = ROOT_DIR / "data" / "crops.csv"
    mapping = {}
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                district = row.get("soil_type") or row.get("district")
                crop = row.get("crop_name")
                if district and crop:
                    mapping.setdefault(district, [])
                    if crop not in mapping[district]:
                        mapping[district].append(crop)
    return jsonify(mapping)


EXPERT_RESPONSES = [
    "Based on traditional farming wisdom, rotating crops between legumes and cereals improves soil nitrogen levels significantly. Consider planting moong dal after your wheat harvest.",
    "For your soil type, I recommend using vermicompost instead of chemical fertilizers. It improves water retention by up to 30% and costs less in the long run.",
    "The ideal time for sowing Rabi crops in your region is mid-October to November. Make sure to prepare the land with adequate irrigation channels.",
    "Drip irrigation can reduce your water usage by 40-60% compared to flood irrigation. Government subsidies under PMKSY can cover up to 55% of installation costs.",
    "Neem-based organic pesticide is very effective against aphids and whiteflies. Mix 5ml neem oil per litre of water and spray early morning for best results.",
    "To protect crops from unseasonal rain, consider raised-bed farming. It improves drainage and reduces root rot risk substantially.",
]


@app.route("/api/chat", methods=["POST"])
def chat_compat():
    """Connect the frontend chatbot and voice assistant to Sarvam AI."""
    data = request.get_json(force=True, silent=True) or {}
    message = str(data.get("message", "")).strip()
    client_key = str(data.get("api_key", "")).strip()
    active_key = SARVAM_API_KEY or client_key

    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400

    if active_key:
        try:
            resp = requests.post(
                "https://api.sarvam.ai/v1/chat/completions",
                headers={
                    "api-subscription-key": active_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sarvam-105b-conversations",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are AgriChain AI, an expert agricultural advisor for Indian farmers. Provide practical, concise advice in the same language the user asks in (English, Hindi or Bengali).",
                        },
                        {"role": "user", "content": message},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 512,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                payload = resp.json()
                if payload.get("choices"):
                    choice = payload["choices"][0].get("message", {})
                    reply = choice.get("content") or choice.get("reasoning_content") or ""
                    if reply.strip():
                        return jsonify({"reply": reply.strip(), "source": "sarvam"})
            logging.warning("Sarvam AI chat failed: %s", resp.text)
        except Exception as exc:
            logging.warning("Sarvam AI request error: %s", exc)

    return jsonify({
        "reply": random.choice(EXPERT_RESPONSES),
        "source": "expert",
    })


@app.route("/")
def serve_index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/<path:filename>")
def serve_frontend_asset(filename):
    if filename.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    if os.path.exists(os.path.join(FRONTEND_DIR, filename)):
        return send_from_directory(FRONTEND_DIR, filename)
    return jsonify({"error": "File not found"}), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)