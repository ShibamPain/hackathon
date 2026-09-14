# Crop Simulation Integration

This document defines how the Digital Twin / Crop Simulation feature connects to the AgriChain Flask backend and the existing React frontend.

## Feature Location

- Frontend component: `CropSimulation.jsx`
- Main frontend shell: `index.html`
- Backend: `server.py`
- Backend base URL: `http://localhost:8000`
- Frontend route/view key: `digital_twin`

`index.html` already loads `CropSimulation.jsx` and renders it when `activeView === "digital_twin"`:

```jsx
{activeView === "digital_twin" && <CropSimulation />}
```

The current component calculates simulation results entirely in the browser. The endpoint below is the backend contract required when the simulation calculation, persistence, audit history, or shared results must be handled by the main backend.

## Feature API

### `POST /api/crop-simulation/evaluate`

Evaluates the current crop conditions and returns the calculated crop health, status, visual filter, and sensor values.

#### Request headers

```http
Content-Type: application/json
```

#### Request body

```json
{
  "sunlight": 80,
  "rainfall": 40,
  "temperature": 28,
  "soil_type": "Loamy",
  "irrigation": 20,
  "fertilizer": 50,
  "pesticide_applied": false,
  "insects": 10,
  "crop_name": "Corn",
  "location": "West Bengal, India"
}
```

#### Field definitions

| Field | Type | Required | Valid values | Description |
| --- | --- | --- | --- | --- |
| `sunlight` | number | yes | `0-100` | Normalized sunlight percentage |
| `rainfall` | number | yes | `0-100` | Rainfall input used by the current UI |
| `temperature` | number | yes | `0-50` | Temperature in Celsius |
| `soil_type` | string | yes | `Clay`, `Sandy`, `Loamy` | Soil water-retention profile |
| `irrigation` | number | yes | `0-100` | Manual irrigation units |
| `fertilizer` | number | yes | `0-100` | NPK/fertilizer level |
| `pesticide_applied` | boolean | yes | `true` or `false` | Removes effective pests when true |
| `insects` | number | yes | `0-100` | Insect population percentage |
| `crop_name` | string | no | Any crop name | Used for history and audit records |
| `location` | string | no | Any location | Used for history and audit records |

#### Success response: `200 OK`

```json
{
  "status": "success",
  "inputs": {
    "sunlight": 80,
    "rainfall": 40,
    "temperature": 28,
    "soil_type": "Loamy",
    "irrigation": 20,
    "fertilizer": 50,
    "pesticide_applied": false,
    "insects": 10
  },
  "results": {
    "health_score": 100,
    "status_text": "Optimal Conditions: Crop is thriving!",
    "total_water": 60,
    "effective_pests": 10,
    "image_filter": "brightness(1) sepia(0) hue-rotate(0deg) grayscale(0)"
  },
  "evaluated_at": "2026-09-12T12:00:00Z"
}
```

#### Validation error: `400 Bad Request`

```json
{
  "error": "soil_type must be one of: Clay, Sandy, Loamy"
}
```

### `GET /api/crop-simulation/history`

Optional endpoint for loading saved evaluations for a crop, farm, or user.

Supported query parameters:

```text
/api/crop-simulation/history?crop_name=Corn&location=West%20Bengal%2C%20India&limit=20
```

Response:

```json
{
  "items": [
    {
      "id": "SIM-001",
      "crop_name": "Corn",
      "location": "West Bengal, India",
      "health_score": 100,
      "status_text": "Optimal Conditions: Crop is thriving!",
      "evaluated_at": "2026-09-12T12:00:00Z"
    }
  ],
  "count": 1
}
```

This endpoint is not currently implemented in `server.py`. Add it only when the UI needs historical simulation results. A database table is preferred over CSV for multi-user history.

## Backend Implementation Contract

Add the evaluator near the other API routes in `server.py`. Keep the calculation in a pure helper so it can be unit tested independently from Flask:

```python
@app.route("/api/crop-simulation/evaluate", methods=["POST"])
def evaluate_crop_simulation():
    data = request.get_json(force=True)
    # Validate and normalize the fields listed above.
    # Apply the same calculation rules currently in CropSimulation.jsx.
    # Return jsonify({"status": "success", "inputs": inputs, "results": results}).
```

The backend evaluator must preserve these current rules:

1. Soil water multiplier: `Sandy = 0.7`, `Loamy = 1.0`, `Clay = 1.3`.
2. `total_water = (rainfall + irrigation) * water_multiplier`.
3. `effective_pests = 0` when `pesticide_applied` is true; otherwise use `insects`.
4. Priority order: severe pests, waterlogging, drought, extreme heat, low sunlight, fertilizer burn, then optimal conditions.
5. Health score must be clamped to a minimum of `0` before returning it.

Do not accept arbitrary values silently. Reject missing fields, unknown soil types, non-numeric ranges, and non-boolean `pesticide_applied` with `400`.

## Frontend Connection

Replace the local calculation block in `CropSimulation.jsx` with a request to the evaluator whenever an input changes. The request should be debounced, or triggered by an explicit `Evaluate` action, to avoid sending one request for every slider movement.

Example request helper:

```jsx
const API_BASE_URL = window.location.origin;

async function evaluateSimulation(inputs, signal) {
  const response = await fetch(`${API_BASE_URL}/api/crop-simulation/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(inputs),
    signal,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Crop simulation failed");
  }
  return payload;
}
```

Example state wiring:

```jsx
const [simulation, setSimulation] = useState(null);
const [loading, setLoading] = useState(false);
const [error, setError] = useState("");

useEffect(() => {
  const controller = new AbortController();
  const inputs = {
    sunlight: Number(sunlight),
    rainfall: Number(rainfall),
    temperature: Number(temperature),
    soil_type: soilType,
    irrigation: Number(irrigation),
    fertilizer: Number(fertilizer),
    pesticide_applied: pesticideApplied,
    insects: Number(insects),
  };

  setLoading(true);
  setError("");
  evaluateSimulation(inputs, controller.signal)
    .then((payload) => setSimulation(payload.results))
    .catch((requestError) => {
      if (requestError.name !== "AbortError") setError(requestError.message);
    })
    .finally(() => setLoading(false));

  return () => controller.abort();
}, [sunlight, rainfall, temperature, soilType, irrigation, fertilizer, pesticideApplied, insects]);
```

Render backend values from `simulation`:

```jsx
const healthScore = simulation?.health_score ?? 0;
const statusText = simulation?.status_text ?? "Waiting for evaluation...";
const imageFilter = simulation?.image_filter ?? "none";
```

The component should show a loading state while evaluating and an error state when the backend is unavailable. Keep the current local calculation as a temporary fallback only if offline behavior is required; label the result as local so it is not mistaken for a backend evaluation.

## Existing Backend Routes

These routes are already available from `server.py` and can be used by the main dashboard alongside the simulation feature:

| Method | Route | Purpose | Frontend use |
| --- | --- | --- | --- |
| `GET` | `/` | Serves `index.html` | Browser entry point |
| `GET` | `/api/forum` | Lists forum posts | Community view |
| `POST` | `/api/forum` | Creates a forum post | Community view |
| `POST` | `/api/recommend` | Returns crop recommendations by soil | Farm info/predictor |
| `GET` | `/api/weather` | Returns simulated weather telemetry | Dashboard |
| `POST` | `/api/blockchain/anchor` | Hashes and anchors a batch record | Ledger view |
| `GET` | `/api/blockchain/records` | Lists ledger records | Ledger view |
| `POST` | `/api/blockchain/verify` | Verifies a payload against a ledger hash | Ledger view |
| `POST` | `/api/ai/detect` | Returns AI anomaly detection result | AI analysis |
| `POST` | `/api/chat` | Returns agricultural assistant response | Chat panel |
| `POST` | `/api/crop-simulation/evaluate` | Evaluates Digital Twin inputs | Crop Simulation |

All JSON `POST` requests must send `Content-Type: application/json`. The existing frontend uses same-origin paths such as `/api/weather`, so no absolute URL is needed when Flask serves `index.html`.

## Frontend View Wiring

The current shell already provides the navigation and mount point:

1. The header sets `activeView` to `digital_twin` when the user selects `Crop Sim`.
2. `index.html` loads `CropSimulation.jsx` before the main inline Babel script.
3. The standalone component is read from `window.exports.default`.
4. The `digital_twin` branch renders `<CropSimulation />`.

When moving this feature into the main application bundle, remove the standalone script tag and import the component through the project build system. Do not render both versions, or the browser will create duplicate component definitions.

## Local Development

Start the Flask backend from `FussionX`:

```powershell
python server.py
```

Expected backend URL:

```text
http://localhost:8000
```

Open the frontend through that Flask URL so the existing same-origin `/api/...` calls work:

```text
http://localhost:8000/
```

`CORS(app)` is enabled for separate frontend development servers, but a production deployment should restrict allowed origins instead of allowing every origin.

Note: `start.bat` currently prints port `5000`, while `server.py` actually starts Flask on port `8000`. Update the message or the Flask port before sharing setup instructions with other developers.

## Security and Production Requirements

- Move the Algorand mnemonic out of `server.py` into an environment variable immediately.
- Never send the Algorand private key or mnemonic to the frontend.
- Add authentication and ownership checks before exposing simulation history or blockchain records to multiple users.
- Use a database for concurrent writes; CSV files are suitable only for the current local demo.
- Add request size limits and strict numeric validation to every JSON endpoint.
- Restrict CORS origins in production.
- Do not expose user-provided Gemini API keys in logs or persisted payloads.
- Add tests for all simulation branches, boundary values, invalid payloads, and aborted frontend requests.

## Acceptance Checklist

- [ ] `POST /api/crop-simulation/evaluate` returns `200` for valid simulation input.
- [ ] Invalid ranges and unknown soil types return `400` with a useful `error` field.
- [ ] Pest, waterlogging, drought, heat, sunlight, fertilizer, and optimal branches match the current UI behavior.
- [ ] `CropSimulation.jsx` sends numeric values rather than slider string values.
- [ ] The UI renders backend `health_score`, `status_text`, and `image_filter`.
- [ ] Loading and backend error states are visible.
- [ ] The feature works from `http://localhost:8000/` without CORS errors.
- [ ] Existing dashboard, forum, recommendation, weather, chat, and blockchain routes remain unaffected.