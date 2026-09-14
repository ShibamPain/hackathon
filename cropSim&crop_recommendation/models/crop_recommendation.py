"""
crop_recommendation.py
------------------------
Inference-only module for the AI-based Crop Recommendation feature.

Loads the pre-trained RandomForestClassifier (produced by
train_crop_recommendation.py) and exposes a clean function for app.py to call.
No Flask/DB dependency here, same separation-of-concerns pattern as
stress_engine.py.
"""

import os
import joblib
import numpy as np

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(_BASE_DIR, "crop_recommendation_model.pkl")
CLASSES_PATH = os.path.join(_BASE_DIR, "crop_recommendation_classes.pkl")

FEATURE_COLUMNS = ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"]

_model = None


def _get_model():
    """Lazy-load so importing this module doesn't fail if the .pkl isn't
    present yet (e.g. before you've run the training script)."""
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def _validate_inputs(inputs: dict) -> list:
    """Returns a list of human-readable error strings, empty if all good."""
    errors = []
    ranges = {
        "N": (0, 200),
        "P": (0, 200),
        "K": (0, 200),
        "temperature": (-10, 60),
        "humidity": (0, 100),
        "ph": (0, 14),
        "rainfall": (0, 500),
    }
    for field in FEATURE_COLUMNS:
        if field not in inputs or inputs[field] is None:
            errors.append(f"Missing required field: {field}")
            continue
        try:
            value = float(inputs[field])
        except (TypeError, ValueError):
            errors.append(f"Field '{field}' must be numeric")
            continue
        low, high = ranges[field]
        if not (low <= value <= high):
            errors.append(f"Field '{field}' value {value} is outside plausible range [{low}, {high}]")
    return errors


def recommend_crops(inputs: dict, top_n: int = 3) -> dict:
    """
    Main entry point.

    inputs: dict with N, P, K, temperature, humidity, ph, rainfall
    top_n: how many ranked suggestions to return

    Returns:
    {
      "status": "success",
      "top_recommendation": "rice",
      "recommendations": [
          {"crop": "rice", "confidence": 0.62},
          {"crop": "jute", "confidence": 0.18},
          {"crop": "maize", "confidence": 0.09}
      ]
    }
    or, on validation failure:
    {
      "status": "error",
      "errors": [...]
    }
    """
    errors = _validate_inputs(inputs)
    if errors:
        return {"status": "error", "errors": errors}

    model = _get_model()

    feature_vector = [[float(inputs[f]) for f in FEATURE_COLUMNS]]
    probabilities = model.predict_proba(feature_vector)[0]
    classes = model.classes_

    ranked = sorted(zip(classes, probabilities), key=lambda x: x[1], reverse=True)
    top = ranked[:top_n]

    return {
        "status": "success",
        "top_recommendation": top[0][0],
        "recommendations": [
            {"crop": crop, "confidence": round(float(prob), 4)} for crop, prob in top
        ],
    }
