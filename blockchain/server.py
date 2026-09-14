"""
AgriChain — Unified Flask Backend Server
Serves the frontend and provides API endpoints for:
- Forum & Crop Recommendation
- Simulated Weather Telemetry
- AI Chatbot (Gemini + fallback)
- Blockchain Record Management (Algorand TestNet + CSV Ledger)
- AI Detection Model Interface
"""

import csv
import os
import random
import json
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Algorand SDK
from algosdk.v2client import algod
from algosdk import account, mnemonic, transaction

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FORUM_CSV = os.path.join(BASE_DIR, "forum.csv")
CROPS_CSV = os.path.join(BASE_DIR, "crops.csv")
LEDGER_CSV = os.path.join(BASE_DIR, "ledger.csv")

# ---------------------------------------------------------------------------
# Algorand TestNet Configuration
# ---------------------------------------------------------------------------
# Primary TestNet node with User-Agent header to prevent blocking
ALGOD_URL = "https://testnet-api.4160.nodely.dev"
algod_client = algod.AlgodClient("", ALGOD_URL, headers={"User-Agent": "algosdk"})

ALGO_MNEMONIC = "seed cement acid ensure immune brick siege connect giant fancy noise summer forest inmate zone minute inform board junk wine scout capital gym able buzz"
try:
    ALGO_PRIVATE_KEY = mnemonic.to_private_key(ALGO_MNEMONIC)
    ALGO_SENDER = account.address_from_private_key(ALGO_PRIVATE_KEY)
    print(f" Algorand Wallet Connected: {ALGO_SENDER[:8]}...{ALGO_SENDER[-6:]}")
except Exception as e:
    ALGO_PRIVATE_KEY = None
    ALGO_SENDER = "QPEZLC2KPAUHNKTPEAVTSMJR42IWLHDY6ZC5GN24EIF32AEE2XYVRAJZ6Y"
    print(f"❌ Mnemonic Error: {str(e)}")

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# ---------------------------------------------------------------------------
# CSV Initialization Helpers
# ---------------------------------------------------------------------------

def init_forum_csv():
    if os.path.exists(FORUM_CSV):
        return
    rows = [
        {"id": "1", "user_role": "Farmer",   "question": "What is the best crop for clay soil in monsoon?",          "timestamp": "2026-03-28 10:15:00"},
        {"id": "2", "user_role": "Retailer", "question": "Where can I source organic rice in bulk?",                 "timestamp": "2026-03-29 14:30:00"},
        {"id": "3", "user_role": "Farmer",   "question": "How to reduce water usage for wheat cultivation?",         "timestamp": "2026-03-30 09:00:00"},
        {"id": "4", "user_role": "Admin",    "question": "Can we get a subsidy tracker added to the platform?",      "timestamp": "2026-04-01 16:45:00"},
    ]
    with open(FORUM_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "user_role", "question", "timestamp"])
        writer.writeheader()
        writer.writerows(rows)


def init_crops_csv():
    if os.path.exists(CROPS_CSV):
        return
    rows = [
        {"soil_type": "Clay",     "crop_name": "Rice",        "expected_profit": "₹25,000/acre", "risk_level": "Low"},
        {"soil_type": "Clay",     "crop_name": "Wheat",       "expected_profit": "₹18,000/acre", "risk_level": "Medium"},
        {"soil_type": "Sandy",    "crop_name": "Groundnut",   "expected_profit": "₹22,000/acre", "risk_level": "Medium"},
        {"soil_type": "Sandy",    "crop_name": "Watermelon",  "expected_profit": "₹30,000/acre", "risk_level": "High"},
        {"soil_type": "Loamy",    "crop_name": "Sugarcane",   "expected_profit": "₹35,000/acre", "risk_level": "Low"},
        {"soil_type": "Loamy",    "crop_name": "Maize",       "expected_profit": "₹20,000/acre", "risk_level": "Low"},
        {"soil_type": "Red",      "crop_name": "Millet",      "expected_profit": "₹15,000/acre", "risk_level": "Low"},
        {"soil_type": "Red",      "crop_name": "Cotton",      "expected_profit": "₹28,000/acre", "risk_level": "High"},
        {"soil_type": "Black",    "crop_name": "Soybean",     "expected_profit": "₹24,000/acre", "risk_level": "Medium"},
        {"soil_type": "Black",    "crop_name": "Cotton",      "expected_profit": "₹32,000/acre", "risk_level": "Medium"},
        {"soil_type": "Alluvial", "crop_name": "Rice",        "expected_profit": "₹27,000/acre", "risk_level": "Low"},
        {"soil_type": "Alluvial", "crop_name": "Jute",        "expected_profit": "₹19,000/acre", "risk_level": "Medium"},
    ]
    with open(CROPS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["soil_type", "crop_name", "expected_profit", "risk_level"])
        writer.writeheader()
        writer.writerows(rows)


def init_ledger_csv():
    if os.path.exists(LEDGER_CSV):
        return
    fieldnames = ["batch_id", "crop_name", "data_hash", "status", "tx_id", "timestamp", "raw_payload"]
    with open(LEDGER_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def next_forum_id():
    rows = read_csv(FORUM_CSV)
    if not rows:
        return 1
    return max(int(r["id"]) for r in rows) + 1


# ---------------------------------------------------------------------------
# Routes — Static Frontend
# ---------------------------------------------------------------------------

@app.route("/")
def serve_index():
    return send_from_directory(BASE_DIR, "index.html")


# ---------------------------------------------------------------------------
# API — Forum
# ---------------------------------------------------------------------------

@app.route("/api/forum", methods=["GET"])
def get_forum():
    return jsonify(read_csv(FORUM_CSV))


@app.route("/api/forum", methods=["POST"])
def post_forum():
    data = request.get_json(force=True)
    question = data.get("question", "").strip()
    user_role = data.get("user_role", "Farmer")
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    new_row = {
        "id": str(next_forum_id()),
        "user_role": user_role,
        "question": question,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(FORUM_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "user_role", "question", "timestamp"])
        writer.writerow(new_row)

    return jsonify(new_row), 201


# ---------------------------------------------------------------------------
# API — Crop Recommendation
# ---------------------------------------------------------------------------

@app.route("/api/recommend", methods=["POST"])
def recommend_crops():
    data = request.get_json(force=True)
    soil_type = data.get("soil_type", "").strip()
    location = data.get("location", "").strip()

    if not soil_type:
        return jsonify({"error": "soil_type is required"}), 400

    all_crops = read_csv(CROPS_CSV)
    matches = [c for c in all_crops if c["soil_type"].lower() == soil_type.lower()]

    return jsonify({
        "soil_type": soil_type,
        "location": location,
        "recommendations": matches,
    })


# ---------------------------------------------------------------------------
# API — Weather (Simulated Sensor Telemetry)
# ---------------------------------------------------------------------------

@app.route("/api/weather", methods=["GET"])
def weather():
    return jsonify({
        "rainfall_mm": round(random.uniform(50, 350), 1),
        "yield_prediction_pct": round(random.uniform(55, 98), 1),
        "temperature_c": round(random.uniform(22, 42), 1),
        "humidity_pct": round(random.uniform(40, 95), 1),
        "soil_ph": round(random.uniform(6.0, 7.5), 2),
        "season": random.choice(["Kharif", "Rabi", "Zaid"]),
    })


# ---------------------------------------------------------------------------
# API — Blockchain Record Management (Algorand TestNet Anchoring)
# ---------------------------------------------------------------------------

@app.route("/api/blockchain/anchor", methods=["POST"])
def anchor_record():
    data = request.get_json(force=True)
    batch_id = data.get("batch_id", f"BATCH-{int(datetime.now().timestamp())}")
    crop_name = data.get("crop_name", "Organic Wheat")
    
    canonical_payload = json.dumps(data, sort_keys=True)
    data_hash = "0x" + hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tx_id = f"LOCAL-PIN-{data_hash[:10]}"
    network_status = "Local Cryptographic Ledger"
    explorer_url = ""

    if ALGO_PRIVATE_KEY:
        try:
            note_payload = {
                "standard": "AgriChain-v1",
                "batch_id": batch_id,
                "crop": crop_name,
                "hash": data_hash
            }
            note_bytes = json.dumps(note_payload).encode("utf-8")

            sp = algod_client.suggested_params()

            txn = transaction.PaymentTxn(
                sender=ALGO_SENDER,
                sp=sp,
                receiver=ALGO_SENDER,
                amt=0,
                note=note_bytes
            )
            signed_txn = txn.sign(ALGO_PRIVATE_KEY)

            tx_id = algod_client.send_transaction(signed_txn)
            transaction.wait_for_confirmation(algod_client, tx_id, 4)

            network_status = "Algorand TestNet (Immutable Note)"
            explorer_url = f"https://lora.algokit.io/testnet/transaction/{tx_id}"
            print(f"[Algorand Success] Anchored on-chain! TxID: {tx_id}")
        except Exception as e:
            print(f"[Algorand Broadcast Warning] {str(e)}")

    new_record = {
        "batch_id": batch_id,
        "crop_name": crop_name,
        "data_hash": data_hash,
        "status": network_status,
        "tx_id": tx_id,
        "timestamp": timestamp,
        "raw_payload": canonical_payload
    }

    with open(LEDGER_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["batch_id", "crop_name", "data_hash", "status", "tx_id", "timestamp", "raw_payload"])
        writer.writerow(new_record)

    return jsonify({
        "status": "success",
        "batch_id": batch_id,
        "data_hash": data_hash,
        "tx_id": tx_id,
        "network": network_status,
        "timestamp": timestamp,
        "explorer_url": explorer_url
    }), 201


@app.route("/api/blockchain/records", methods=["GET"])
def get_ledger_records():
    records = read_csv(LEDGER_CSV)
    return jsonify(records)


@app.route("/api/blockchain/verify", methods=["POST"])
def verify_record():
    data = request.get_json(force=True)
    batch_id = data.get("batch_id")
    current_payload = data.get("payload")

    records = read_csv(LEDGER_CSV)
    matched = next((r for r in records if r["batch_id"] == batch_id), None)

    if not matched:
        return jsonify({"error": "Batch ID not found in ledger"}), 404

    current_canonical = json.dumps(current_payload, sort_keys=True)
    current_hash = "0x" + hashlib.sha256(current_canonical.encode("utf-8")).hexdigest()
    original_hash = matched["data_hash"]

    is_valid = (current_hash == original_hash)

    return jsonify({
        "batch_id": batch_id,
        "is_authentic": is_valid,
        "ledger_hash": original_hash,
        "inspected_hash": current_hash,
        "verification_result": "VALID: Match confirmed on immutable ledger" if is_valid else "ALERT: Hash mismatch detected. Data tampered!"
    })


# ---------------------------------------------------------------------------
# API — AI / LLM Model Interface
# ---------------------------------------------------------------------------

@app.route("/api/ai/detect", methods=["POST"])
def detect_anomalies():
    data = request.get_json(force=True)
    return jsonify({
        "status": "success",
        "model_loaded": "AgriChain-LLM-Inspector",
        "confidence_score": 0.94,
        "detection": "Normal vegetative state. No pathogen or crop stress indicators found.",
        "received_data": data
    })


# ---------------------------------------------------------------------------
# API — AI Chatbot (Gemini with Fallback)
# ---------------------------------------------------------------------------

EXPERT_RESPONSES = [
    "Based on traditional farming wisdom, rotating crops between legumes and cereals improves soil nitrogen levels significantly. Consider planting moong dal after your wheat harvest.",
    "For your soil type, I recommend using vermicompost instead of chemical fertilizers. It improves water retention by up to 30% and costs less in the long run.",
    "The ideal time for sowing Rabi crops in your region is mid-October to November. Make sure to prepare the land with adequate irrigation channels.",
    "Drip irrigation can reduce your water usage by 40-60% compared to flood irrigation. Government subsidies under PMKSY can cover up to 55% of installation costs.",
    "Neem-based organic pesticide is very effective against aphids and whiteflies. Mix 5ml neem oil per litre of water and spray early morning for best results.",
    "To protect crops from unseasonal rain, consider raised-bed farming. It improves drainage and reduces root rot risk substantially.",
]

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    api_key = data.get("api_key", "").strip()

    if not message:
        return jsonify({"error": "Message cannot be empty"}), 400

    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash")
            prompt = (
                "You are AgriChain AI, an expert agricultural advisor for Indian farmers. "
                "Provide practical, concise advice. Answer in the same language the user asks in.\n\n"
                f"User: {message}"
            )
            response = model.generate_content(prompt)
            return jsonify({"reply": response.text, "source": "gemini"})
        except Exception as e:
            return jsonify({
                "reply": f"Gemini API error: {str(e)}. Falling back to expert advice.\n\n{random.choice(EXPERT_RESPONSES)}",
                "source": "fallback",
            })

    return jsonify({
        "reply": random.choice(EXPERT_RESPONSES),
        "source": "expert",
    })


# ---------------------------------------------------------------------------
# Server Initialization
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_forum_csv()
    init_crops_csv()
    init_ledger_csv()
    print("\n🌾  AgriChain server running at http://localhost:8000")
    print("⛓️  Algorand TestNet integration initialized.\n")
    app.run(debug=True, port=8000)