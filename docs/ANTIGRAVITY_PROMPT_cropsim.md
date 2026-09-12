# AgriChain — CropSim Feature: Backend Continuation Prompt

## Role
You are acting as a backend engineer continuing an already-in-progress feature called
**CropSim** inside a larger hackathon project called **AgriChain** (Track: AI for Real-World
Impact). Do not redesign what already exists — extend it. Match the existing code style
(Flask, plain functions, no classes unless necessary, minimal dependencies).

## Project Context
AgriChain is a smart agriculture platform combining IoT sensors, AI/ML analytics,
Hyperledger Fabric blockchain, IPFS storage, and role-based dashboards (Farmer, Retailer,
Admin, Consumer). CropSim is one feature inside the Farmer Dashboard: it simulates crop
growth over a 90-day cycle and predicts expected yield based on soil/climate inputs.

**Tech stack (do not deviate from this):**
- Backend: Python, Flask, flask-cors
- ML: scikit-learn (RandomForestRegressor), joblib, pandas, numpy
- Database: MySQL
- Blockchain: Hyperledger Fabric (chaincode/smart contracts), IPFS for off-chain files
- Hardware feed (future): ESP32 + Soil Moisture, DHT11/DHT22, pH sensor, NPK sensor, Rain Gauge

## Current Folder Structure
```
FU/
├── myenv/                              # Python virtual environment
├── app.py                              # Flask backend (see full contents below)
├── stress_engine.py                    # Stress penalty calculation engine (see below)
├── crop_profiles.py                    # Crop-specific optimal ranges (see below)
├── Crop Yiled with Soil and Weather.csv  # Training dataset used for cropsim_model.pkl
└── cropsim_model.pkl                   # Trained RandomForestRegressor (already built, do not retrain)
```

## What's Already Done (do not rebuild — extend these)

### 1. The ML model (`cropsim_model.pkl`)
- Algorithm: `RandomForestRegressor(n_estimators=50, random_state=42)` from scikit-learn
- Trained on `Crop Yiled with Soil and Weather.csv`
- **Exact input feature order the model expects:** `['temp', 'N', 'P', 'K', 'Fertilizer']`
- Output: a single float — predicted total yield in kg (unstressed baseline)
- Feature importances (for reference): temp ≈ 0.75, K ≈ 0.12, N ≈ 0.05, P ≈ 0.04, Fertilizer ≈ 0.03
- Loaded via `joblib.load('cropsim_model.pkl')`

### 2. `crop_profiles.py` — crop knowledge base
Defines, per crop (`rice`, `wheat`, `maize`, `potato`, `sugarcane`):
- `optimal` ranges (min, max) for `temp`, `moisture`, `ph`, `N`, `P`, `K`
- `stage_sensitivity`: how much each parameter's stress is amplified/dampened during
  4 growth stages mapped to day ranges: `germination` (1-15), `vegetative` (16-45),
  `flowering` (46-65), `maturity` (66-90)
- Helper functions: `get_crop_profile(crop_type)` (case-insensitive, falls back to `"rice"`),
  `get_stage_for_day(day)`

### 3. `stress_engine.py` — the calculation engine
Pure calculation module (no Flask/DB dependency), exposes:
- `compute_stress_breakdown(inputs, crop_type)` → dict of per-parameter stress scores (0-1)
- `compute_daily_stress_multipliers(inputs, crop_type)` → list of 90 multipliers (0.15-1.0)
- `apply_stress_to_yield(base_yield, inputs, crop_type)` → the main entry point, returns:
  ```python
  {
    "adjusted_yield_kg": float,        # final stress-adjusted yield at day 90
    "growth_curve": [float] * 90,      # stress-adjusted day-by-day growth
    "daily_stress_factor": [float] * 90,
    "stress_breakdown": {"temp": 0.0, "moisture": 0.0, "ph": 0.0, "N": 0.0, "P": 0.0, "K": 0.0},
    "overall_stress_pct": float,       # % yield lost to stress vs baseline
  }
  ```

### 4. `app.py` — current Flask endpoints
```python
from flask import Flask, jsonify, request
from flask_cors import CORS
import joblib
import numpy as np

from stress_engine import apply_stress_to_yield
from crop_profiles import DEFAULT_CROP

app = Flask(__name__)
CORS(app)

model = joblib.load('cropsim_model.pkl')


@app.route('/api/cropsim', methods=['POST'])
def simulate():
    data = request.json or {}

    temp = float(data.get('temp', 25))
    N = float(data.get('N', 40))
    P = float(data.get('P', 20))
    K = float(data.get('K', 20))
    fertilizer = float(data.get('fertilizer', 10))

    crop_type = data.get('crop_type', DEFAULT_CROP)
    moisture = data.get('moisture')
    ph = data.get('ph')

    features = [[temp, N, P, K, fertilizer]]
    predicted_yield = float(model.predict(features)[0])

    stress_inputs = {"temp": temp, "N": N, "P": P, "K": K, "moisture": moisture, "ph": ph}
    stress_result = apply_stress_to_yield(predicted_yield, stress_inputs, crop_type)

    return jsonify({
        'status': 'success',
        'crop_type': crop_type,
        'baseline_yield_kg': round(predicted_yield, 2),
        'predicted_yield_kg': stress_result['adjusted_yield_kg'],
        'overall_stress_pct': stress_result['overall_stress_pct'],
        'stress_breakdown': stress_result['stress_breakdown'],
        'days': list(range(1, 91)),
        'growth_curve': stress_result['growth_curve'],
        'daily_stress_factor': stress_result['daily_stress_factor'],
    })


@app.route('/api/cropsim/crops', methods=['GET'])
def list_supported_crops():
    from crop_profiles import CROP_PROFILES
    return jsonify({'status': 'success', 'supported_crops': list(CROP_PROFILES.keys())})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

---

## What To Build Next (in this priority order)

### PART A — MySQL Simulation Logging (build this first)

**Goal:** every call to `/api/cropsim` should persist its full input + output to MySQL, so
farmers can see simulation history and the Admin dashboard can monitor usage.

**Requirements:**
1. Create a new file `db.py` that:
   - Uses `mysql-connector-python` (or `PyMySQL` — pick one and be consistent)
   - Reads DB credentials from environment variables (`DB_HOST`, `DB_USER`, `DB_PASSWORD`,
     `DB_NAME`) with sane localhost defaults for hackathon demo purposes
   - Exposes a connection helper, e.g. `get_connection()`
2. Create a MySQL table `cropsim_simulations` with this schema (write the `CREATE TABLE`
   SQL in a `schema.sql` file, and also auto-create the table on first run if it doesn't exist):
   - `id` INT AUTO_INCREMENT PRIMARY KEY
   - `farmer_id` INT (nullable for now — no auth system yet, default NULL)
   - `crop_type` VARCHAR(50)
   - `temp` FLOAT, `moisture` FLOAT NULL, `ph` FLOAT NULL, `n_value` FLOAT, `p_value` FLOAT,
     `k_value` FLOAT, `fertilizer` FLOAT
   - `baseline_yield_kg` FLOAT
   - `predicted_yield_kg` FLOAT
   - `overall_stress_pct` FLOAT
   - `stress_breakdown_json` JSON (store the full per-parameter breakdown dict)
   - `growth_curve_json` JSON (store the full 90-day array — needed later for
     traceability / re-display without recomputation)
   - `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
3. In `app.py`, after computing `stress_result`, call a new function
   `log_simulation(data_dict)` (put this in `db.py` or a new `simulation_logger.py`) that
   inserts a row. **Do not let a DB failure break the API response** — wrap the insert in
   try/except, log the error to console, and still return the JSON response to the client.
4. Add a new endpoint `GET /api/cropsim/history?farmer_id=<id>` (farmer_id optional for now)
   that returns the last 20 simulations, most recent first, as JSON. Return the full row
   including parsed JSON columns (not raw JSON strings).
5. Add a new endpoint `GET /api/cropsim/history/<id>` returning one simulation's full detail
   by its `id`.

### PART B — Sensor Data Ingestion Endpoint

**Goal:** allow an ESP32 device to push live sensor telemetry, which gets stored and can
optionally auto-trigger a CropSim simulation using the latest readings instead of manual
slider input.

**Requirements:**
1. Create table `sensor_readings`:
   - `id` INT AUTO_INCREMENT PRIMARY KEY
   - `device_id` VARCHAR(100) (the ESP32's identifier)
   - `field_id` INT NULL (which farm field, for future multi-field support)
   - `moisture` FLOAT NULL, `temp` FLOAT NULL, `humidity` FLOAT NULL, `ph` FLOAT NULL,
     `n_value` FLOAT NULL, `p_value` FLOAT NULL, `k_value` FLOAT NULL, `rainfall` FLOAT NULL
   - `recorded_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
2. Add `POST /api/sensor-data`:
   - Accepts JSON body with any subset of the sensor fields above (`device_id` required,
     rest optional since not every device has every sensor)
   - **Validate incoming data** before inserting: reject/clip physically impossible values
     (e.g. `moisture` must be 0-100, `ph` must be 0-14, `temp` between -10 and 60°C). Return
     HTTP 400 with a clear error message listing which field(s) failed validation, rather
     than silently accepting garbage.
   - On success, insert into `sensor_readings` and return the saved row plus a
     `status: 'success'`.
3. Add `GET /api/sensor-data/latest?device_id=<id>` returning the most recent reading for
   that device.
4. Add `POST /api/cropsim/auto` — a convenience endpoint that:
   - Takes `device_id` and `crop_type` in the body
   - Fetches that device's latest sensor reading
   - Falls back to CropSim's existing defaults for any field the sensor doesn't provide
     (e.g. if there's no NPK sensor, use `N=40, P=20, K=20` as today)
   - Runs the exact same prediction + stress engine pipeline as `/api/cropsim`
   - Logs the result via the same `log_simulation()` function from Part A
   - This endpoint is the bridge between real IoT data and the existing simulation logic —
     it should reuse the prediction/stress code, not duplicate it.

### PART C — Hyperledger Fabric Smart Contract Trigger (stub only — hackathon scope)

**Goal:** we don't need a full working Fabric network wired up for the demo, but we need a
clean integration point that looks and behaves like a real trigger, so it can be swapped
for a real Fabric SDK call later without changing `app.py`.

**Requirements:**
1. Create `fabric_client.py` with a function `submit_yield_record(record: dict) -> dict`
   that:
   - In this stub version, does NOT actually connect to a Fabric network. Instead, simulate
     an on-chain write by generating a fake but realistic transaction ID (e.g.
     `"tx_" + uuid4().hex[:16]`) and returning something like:
     ```python
     {
       "status": "committed",
       "tx_id": "tx_...",
       "channel": "agrichain-channel",
       "chaincode": "cropYieldContract",
       "timestamp": <iso8601 string>,
       "record": record
     }
     ```
   - Include a clearly marked `# TODO: replace with real Hyperledger Fabric SDK / gateway
     call` comment block showing where the real `fabric-sdk-py` or Fabric Gateway client
     call would go, with a short comment describing what that call would look like
     (submitting a transaction to a chaincode function, e.g. `RecordYield`).
2. In `app.py`, when a simulation in `/api/cropsim` (or `/api/cropsim/auto`) completes,
   call `submit_yield_record()` with a summary payload (`crop_type`, `predicted_yield_kg`,
   `overall_stress_pct`, `created_at`, and the DB row's `id` as the off-chain reference).
   Include the returned `tx_id` in the API response under a `blockchain` key, e.g.:
   ```json
   "blockchain": {
     "status": "committed",
     "tx_id": "tx_9f3a1b2c4d5e6f70",
     "chaincode": "cropYieldContract"
   }
   ```
3. This should be non-blocking / fail-safe the same way DB logging is — if it throws for
   any reason, log it and still return the simulation result to the client.

---

## Constraints & Style Rules
- Keep everything in Flask, no framework switch.
- Do not modify `crop_profiles.py` or `stress_engine.py` unless explicitly necessary —
  they are considered stable/finished.
- Do not change the response shape of the existing `/api/cropsim` fields
  (`predicted_yield_kg`, `growth_curve`, etc.) — only add new keys, never rename or remove.
- All new DB/Fabric calls must be non-blocking to the API response (try/except, log, continue).
- Keep credentials out of code — use environment variables with safe local defaults.
- Add minimal inline comments explaining non-obvious logic, matching the existing file style.

## Deliverables
- `db.py`, `schema.sql`, `simulation_logger.py` (or merged into `db.py`)
- Updated `app.py` with the 5 new endpoints wired in
- `fabric_client.py`
- A short `README_backend.md` listing all endpoints (method, path, required/optional body
  fields, example response) so the frontend team can integrate without reading the code
