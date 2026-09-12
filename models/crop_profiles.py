# crop_profiles.py -- Crop-specific optimal parameter ranges and growth-stage sensitivity
DEFAULT_CROP = 'rice'

CROP_PROFILES = {
    'rice': {
        'optimal': {
            'temp':     {'min': 20, 'max': 35},
            'moisture': {'min': 60, 'max': 100},
            'ph':       {'min': 5.5, 'max': 7.0},
            'N':        {'min': 30, 'max': 60},
            'P':        {'min': 10, 'max': 30},
            'K':        {'min': 10, 'max': 40},
        },
        'stage_sensitivity': {
            'germination': {'temp': 1.2, 'moisture': 1.5, 'ph': 1.0, 'N': 0.8, 'P': 0.8, 'K': 0.8},
            'vegetative':  {'temp': 1.0, 'moisture': 1.2, 'ph': 0.9, 'N': 1.5, 'P': 1.0, 'K': 1.0},
            'flowering':   {'temp': 1.5, 'moisture': 1.3, 'ph': 1.1, 'N': 1.0, 'P': 1.5, 'K': 1.2},
            'maturity':    {'temp': 0.8, 'moisture': 0.7, 'ph': 0.7, 'N': 0.6, 'P': 0.8, 'K': 1.0},
        },
    },
    'wheat': {
        'optimal': {
            'temp':     {'min': 12, 'max': 25},
            'moisture': {'min': 40, 'max': 70},
            'ph':       {'min': 6.0, 'max': 7.5},
            'N':        {'min': 40, 'max': 80},
            'P':        {'min': 15, 'max': 40},
            'K':        {'min': 15, 'max': 45},
        },
        'stage_sensitivity': {
            'germination': {'temp': 1.3, 'moisture': 1.2, 'ph': 0.9, 'N': 0.7, 'P': 0.9, 'K': 0.8},
            'vegetative':  {'temp': 1.1, 'moisture': 1.0, 'ph': 0.8, 'N': 1.4, 'P': 1.1, 'K': 1.0},
            'flowering':   {'temp': 1.6, 'moisture': 1.2, 'ph': 1.0, 'N': 1.1, 'P': 1.4, 'K': 1.1},
            'maturity':    {'temp': 0.9, 'moisture': 0.6, 'ph': 0.7, 'N': 0.7, 'P': 0.7, 'K': 0.9},
        },
    },
    'maize': {
        'optimal': {
            'temp':     {'min': 18, 'max': 32},
            'moisture': {'min': 50, 'max': 80},
            'ph':       {'min': 5.8, 'max': 7.0},
            'N':        {'min': 50, 'max': 90},
            'P':        {'min': 20, 'max': 50},
            'K':        {'min': 20, 'max': 50},
        },
        'stage_sensitivity': {
            'germination': {'temp': 1.2, 'moisture': 1.3, 'ph': 0.9, 'N': 0.8, 'P': 1.0, 'K': 0.8},
            'vegetative':  {'temp': 1.0, 'moisture': 1.1, 'ph': 0.9, 'N': 1.6, 'P': 1.1, 'K': 1.0},
            'flowering':   {'temp': 1.4, 'moisture': 1.4, 'ph': 1.0, 'N': 1.2, 'P': 1.3, 'K': 1.2},
            'maturity':    {'temp': 0.8, 'moisture': 0.7, 'ph': 0.7, 'N': 0.7, 'P': 0.8, 'K': 1.0},
        },
    },
    'potato': {
        'optimal': {
            'temp':     {'min': 15, 'max': 25},
            'moisture': {'min': 60, 'max': 85},
            'ph':       {'min': 4.8, 'max': 6.5},
            'N':        {'min': 30, 'max': 70},
            'P':        {'min': 20, 'max': 55},
            'K':        {'min': 30, 'max': 70},
        },
        'stage_sensitivity': {
            'germination': {'temp': 1.1, 'moisture': 1.4, 'ph': 1.1, 'N': 0.8, 'P': 1.0, 'K': 0.9},
            'vegetative':  {'temp': 1.0, 'moisture': 1.2, 'ph': 1.0, 'N': 1.3, 'P': 1.2, 'K': 1.1},
            'flowering':   {'temp': 1.3, 'moisture': 1.3, 'ph': 1.1, 'N': 1.0, 'P': 1.2, 'K': 1.5},
            'maturity':    {'temp': 0.9, 'moisture': 0.8, 'ph': 0.8, 'N': 0.7, 'P': 0.8, 'K': 1.2},
        },
    },
    'sugarcane': {
        'optimal': {
            'temp':     {'min': 22, 'max': 38},
            'moisture': {'min': 65, 'max': 100},
            'ph':       {'min': 6.0, 'max': 7.5},
            'N':        {'min': 40, 'max': 80},
            'P':        {'min': 10, 'max': 35},
            'K':        {'min': 25, 'max': 60},
        },
        'stage_sensitivity': {
            'germination': {'temp': 1.3, 'moisture': 1.5, 'ph': 0.9, 'N': 0.9, 'P': 0.9, 'K': 0.9},
            'vegetative':  {'temp': 1.1, 'moisture': 1.3, 'ph': 0.8, 'N': 1.5, 'P': 1.0, 'K': 1.1},
            'flowering':   {'temp': 1.2, 'moisture': 1.2, 'ph': 1.0, 'N': 1.0, 'P': 1.3, 'K': 1.3},
            'maturity':    {'temp': 0.9, 'moisture': 0.9, 'ph': 0.7, 'N': 0.7, 'P': 0.8, 'K': 1.0},
        },
    },
}

GROWTH_STAGES = [
    ('germination', 1,  15),
    ('vegetative',  16, 45),
    ('flowering',   46, 65),
    ('maturity',    66, 90),
]


def get_crop_profile(crop_type: str) -> dict:
    return CROP_PROFILES.get(crop_type.lower(), CROP_PROFILES[DEFAULT_CROP])


def get_stage_for_day(day: int) -> str:
    for stage, start, end in GROWTH_STAGES:
        if start <= day <= end:
            return stage
    return 'maturity'
