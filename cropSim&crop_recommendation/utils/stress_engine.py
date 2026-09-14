# stress_engine.py -- Pure calculation module for crop stress scoring.
# No Flask or DB dependencies; safe to import anywhere.

from crop_profiles import get_crop_profile, get_stage_for_day


def _parameter_stress(value, optimal_range):
    # Return a stress score [0, 1] for a single parameter.
    # 0 = no stress (within optimal), 1 = maximum stress.
    lo, hi = optimal_range["min"], optimal_range["max"]
    if value is None:
        return 0.0  # sensor not available -- assume no stress
    if lo <= value <= hi:
        return 0.0
    if value < lo:
        return min(1.0, (lo - value) / (lo + 1e-9))
    return min(1.0, (value - hi) / (hi + 1e-9))


def compute_stress_breakdown(inputs, crop_type):
    # Compute per-parameter stress scores (0-1) for all tracked inputs.
    # inputs keys: temp, moisture, ph, N, P, K
    profile = get_crop_profile(crop_type)
    optimal = profile["optimal"]
    return {
        param: round(_parameter_stress(inputs.get(param), optimal[param]), 4)
        for param in ("temp", "moisture", "ph", "N", "P", "K")
    }


def compute_daily_stress_multipliers(inputs, crop_type):
    # Compute a stress multiplier for each of the 90 growing days.
    # The multiplier [0.15, 1.0] reflects stage-specific sensitivity weighting.
    profile = get_crop_profile(crop_type)
    stage_sensitivity = profile["stage_sensitivity"]
    base_stress = compute_stress_breakdown(inputs, crop_type)
    multipliers = []

    for day in range(1, 91):
        stage = get_stage_for_day(day)
        sens = stage_sensitivity[stage]
        weighted_stress = sum(
            base_stress[p] * sens.get(p, 1.0)
            for p in ("temp", "moisture", "ph", "N", "P", "K")
        ) / 6.0
        multiplier = round(max(0.15, 1.0 - weighted_stress), 4)
        multipliers.append(multiplier)

    return multipliers


def apply_stress_to_yield(base_yield, inputs, crop_type):
    # Main entry point. Given a ML-predicted baseline yield and input conditions,
    # compute the stress-adjusted yield and 90-day growth curve.
    import numpy as np

    stress_breakdown = compute_stress_breakdown(inputs, crop_type)
    daily_factors = compute_daily_stress_multipliers(inputs, crop_type)

    # Sigmoid baseline (unstressed), normalised so the final day equals base_yield
    days = list(range(1, 91))
    sigmoid_raw = [1.0 / (1.0 + np.exp(-0.1 * (d - 45))) for d in days]
    scale = base_yield / sigmoid_raw[-1]

    growth_curve = [
        round(sigmoid_raw[i] * scale * daily_factors[i], 2) for i in range(90)
    ]

    adjusted_yield_kg = round(growth_curve[-1], 2)
    overall_stress_pct = round((1.0 - adjusted_yield_kg / max(base_yield, 1e-9)) * 100, 2)

    return {
        "adjusted_yield_kg":   adjusted_yield_kg,
        "growth_curve":        growth_curve,
        "daily_stress_factor": daily_factors,
        "stress_breakdown":    stress_breakdown,
        "overall_stress_pct":  overall_stress_pct,
    }
