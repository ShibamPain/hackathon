# sensor_validator.py -- Input validation for ESP32 sensor data.
# All physically possible ranges are defined here; extend as new sensors are added.

# Each entry: field_name -> (min, max, unit_hint)
SENSOR_BOUNDS = {
    "moisture": (0.0,   100.0, "%"),
    "temp":     (-10.0,  60.0, "degC"),
    "humidity": (0.0,   100.0, "%"),
    "ph":       (0.0,    14.0, "pH"),
    "n_value":  (0.0,  1000.0, "mg/kg"),
    "p_value":  (0.0,  1000.0, "mg/kg"),
    "k_value":  (0.0,  1000.0, "mg/kg"),
    "rainfall": (0.0,  2000.0, "mm"),
}

# Map from JSON field names the client sends to the internal key used in DB / BOUNDS
FIELD_ALIASES = {
    "N": "n_value",
    "P": "p_value",
    "K": "k_value",
}


def validate_sensor_payload(data: dict):
    # Validate incoming sensor data.
    # Returns (normalised_dict, errors_list).
    # errors_list is empty on success; contains human-readable messages on failure.
    errors = []
    normalised = {}

    if not data.get("device_id"):
        errors.append("device_id is required and must not be empty.")
    else:
        normalised["device_id"] = str(data["device_id"]).strip()

    if "field_id" in data and data["field_id"] is not None:
        try:
            normalised["field_id"] = int(data["field_id"])
        except (TypeError, ValueError):
            errors.append("field_id must be an integer.")

    # Check each numeric sensor field
    for client_key, internal_key in FIELD_ALIASES.items():
        if client_key in data:
            data[internal_key] = data.pop(client_key)

    for field, (lo, hi, unit) in SENSOR_BOUNDS.items():
        if field not in data or data[field] is None:
            continue  # field not provided -- that's fine (partial sensor set)
        try:
            val = float(data[field])
        except (TypeError, ValueError):
            errors.append(f"{field} must be a number.")
            continue
        if not (lo <= val <= hi):
            errors.append(
                f"{field} value {val} is out of physically valid range "
                f"[{lo}, {hi}] {unit}."
            )
        else:
            normalised[field] = val

    return normalised, errors
