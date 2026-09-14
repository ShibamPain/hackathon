# CropSim Backend API Reference

**Base URL (local dev):** `http://localhost:5000`
**Stack:** Python 3.x · Flask · mysql-connector-python · scikit-learn

> All endpoints return JSON.  On error, the response body always includes
> `"status": "error"` and a human-readable `"message"` (or `"errors"` list).

---

## Crop Simulation

### `POST /api/cropsim`
Run a CropSim prediction for a given set of soil/climate inputs.

**Request body (JSON)**

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `crop_type` | string | No | `"rice"` | One of: rice, wheat, maize, potato, sugarcane |
| `temp` | float | No | 25 | Celsius |
| `N` | float | No | 40 | Nitrogen mg/kg |
| `P` | float | No | 20 | Phosphorus mg/kg |
| `K` | float | No | 20 | Potassium mg/kg |
| `fertilizer` | float | No | 10 | kg/ha |
| `moisture` | float | No | null | 0-100 %; null = no stress applied |
| `ph` | float | No | null | 0-14; null = no stress applied |
| `farmer_id` | int | No | null | Reserved for auth; ignored for now |

**Response `200`**
```json
{
  "status": "success",
  "simulation_id": 7,
  "crop_type": "rice",
  "baseline_yield_kg": 5200.41,
  "predicted_yield_kg": 4913.87,
  "overall_stress_pct": 5.51,
  "stress_breakdown": {"temp": 0.0, "moisture": 0.04, "ph": 0.0, "N": 0.0, "P": 0.0, "K": 0.0},
  "days": [1, 2, "...90"],
  "growth_curve": [12.3, 14.7, "..."],
  "daily_stress_factor": [1.0, 1.0, "..."],
  "blockchain": {
    "status": "committed",
    "tx_id": "tx_9f3a1b2c4d5e6f70",
    "chaincode": "cropYieldContract"
  }
}
```

---

### `GET /api/cropsim/crops`
List all supported crop types.

**Response `200`**
```json
{ "status": "success", "supported_crops": ["rice", "wheat", "maize", "potato", "sugarcane"] }
```

---

### `GET /api/cropsim/history`
Return the last 20 simulations, most recent first.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `farmer_id` | int | No | Filter to a specific farmer |

**Response `200`**
```json
{
  "status": "success",
  "count": 3,
  "simulations": [
    {
      "id": 7,
      "farmer_id": null,
      "crop_type": "rice",
      "temp": 27.0,
      "moisture": 72.0,
      "ph": 6.2,
      "n_value": 40.0, "p_value": 20.0, "k_value": 20.0, "fertilizer": 10.0,
      "baseline_yield_kg": 5200.41,
      "predicted_yield_kg": 4913.87,
      "overall_stress_pct": 5.51,
      "stress_breakdown": {"temp": 0.0, "moisture": 0.04, "ph": 0.0, "N": 0.0, "P": 0.0, "K": 0.0},
      "growth_curve": [12.3, 14.7, "... (90 values)"],
      "created_at": "2026-09-11T18:00:00"
    }
  ]
}
```

---

### `GET /api/cropsim/history/<id>`
Full detail for a single simulation by its database ID.

**Path param:** `id` — integer primary key

**Response `200`** — same shape as a single item in the history list above.

**Response `404`** — `{ "status": "error", "message": "Simulation 99 not found." }`

---

### `POST /api/cropsim/auto`
Fetch the latest sensor reading for an ESP32 device and run CropSim on it automatically.
Falls back to safe defaults for any sensor field the device doesn't have.

**Request body (JSON)**

| Field | Type | Required | Notes |
|---|---|---|---|
| `device_id` | string | **Yes** | Must match a device that has sent readings |
| `crop_type` | string | No | Default `"rice"` |
| `farmer_id` | int | No | Reserved |
| `fertilizer` | float | No | Default 10 (sensors don't measure this) |
| `temp`, `N`, `P`, `K`, `moisture`, `ph` | float | No | Manual fallback if sensor is missing that field |

**Response `200`** — same shape as `POST /api/cropsim` plus:
```json
{
  "source": "sensor",
  "device_id": "ESP32-field-01",
  "sensor_reading_id": 14
}
```

**Response `404`** — device has no readings yet.

---

## Sensor Data

### `POST /api/sensor-data`
Accept a telemetry push from an ESP32. `device_id` is the only required field;
all sensor readings are optional (partial payloads are supported).

**Request body (JSON)**

| Field | Type | Required | Valid range |
|---|---|---|---|
| `device_id` | string | **Yes** | any non-empty string |
| `field_id` | int | No | — |
| `moisture` | float | No | 0 – 100 % |
| `temp` | float | No | -10 – 60 °C |
| `humidity` | float | No | 0 – 100 % |
| `ph` | float | No | 0 – 14 |
| `N` | float | No | 0 – 1000 mg/kg |
| `P` | float | No | 0 – 1000 mg/kg |
| `K` | float | No | 0 – 1000 mg/kg |
| `rainfall` | float | No | 0 – 2000 mm |

**Response `201`**
```json
{
  "status": "success",
  "reading": {
    "id": 14,
    "device_id": "ESP32-field-01",
    "field_id": null,
    "moisture": 68.4,
    "temp": 29.1,
    "humidity": null,
    "ph": 6.3,
    "n_value": 42.0, "p_value": null, "k_value": null,
    "rainfall": null,
    "recorded_at": "2026-09-11T18:00:00"
  }
}
```

**Response `400`** — one or more fields failed validation:
```json
{
  "status": "error",
  "errors": [
    "moisture value 150.0 is out of physically valid range [0.0, 100.0] %.",
    "ph value -1.0 is out of physically valid range [0.0, 14.0] pH."
  ]
}
```

---

### `GET /api/sensor-data/latest`
Return the most recent reading for a given device.

**Query params**

| Param | Type | Required |
|---|---|---|
| `device_id` | string | **Yes** |

**Response `200`** — same shape as the `reading` object above.

**Response `400`** — `device_id` param missing.

**Response `404`** — no readings found for that device.

---

## Blockchain (Hyperledger Fabric stub)

Every simulation response (`/api/cropsim` and `/api/cropsim/auto`) includes a
`"blockchain"` key:

```json
"blockchain": {
  "status":    "committed",
  "tx_id":     "tx_9f3a1b2c4d5e6f70",
  "chaincode": "cropYieldContract"
}
```

If the Fabric call fails for any reason the key is still present but `status` is
`"unavailable"` and `tx_id` / `chaincode` are `null`.  The simulation result is
always returned regardless.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | `` (empty) | MySQL password |
| `DB_NAME` | `agrichain` | Database name |

---

## Quick Start

```bash
# 1. Create the DB (once)
mysql -u root -p < schema.sql

# 2. Activate venv and run
myenv\Scripts\activate
python app.py
# Flask will auto-create tables and start on http://localhost:5000
```
