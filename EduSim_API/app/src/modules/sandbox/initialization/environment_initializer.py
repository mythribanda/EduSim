"""
environment_initializer.py
==========================
Defensive, robust environment initialisation module for EduSim.

It parses, normalizes, and hydrafts a raw, potentially malformed environment 
specification into a strongly-typed `SandboxEnvironment` Pydantic model. 

It handles scalar/vector gravity healing, default presets for atmospheres 
(vacuum, earth, custom, etc.), and wind/fluid field parameter completions.
"""


from __future__ import annotations
from typing import Any

from app.src.modules.sandbox.schemas.environment_schema import (
    SandboxEnvironment,
    GravityField,
    WindField,
    AtmosphereField,
    AtmosphereType,
    MagneticField,
    FluidField,
    LightingEnvironment
)
from app.src.modules.sandbox.initialization.normalizers import (
    normalize_gravity,
    normalize_number
)
from app.src.modules.sandbox.initialization.defaults import (
    DEFAULT_GRAVITY_X,
    DEFAULT_GRAVITY_Y,
    DEFAULT_GRAVITY_SCALE
)


def initialize_environment(raw_env: Any) -> SandboxEnvironment:
    """
    Takes an untrusted, raw environment specification and heals it into
    a validated, robust `SandboxEnvironment` instance.
    """
    if not isinstance(raw_env, dict):
        raw_env = {}

    # 1. Initialize Gravity
    grav_dict = normalize_gravity(raw_env.get("gravity"))
    gravity = GravityField(
        x=grav_dict.get("x", DEFAULT_GRAVITY_X),
        y=grav_dict.get("y", DEFAULT_GRAVITY_Y),
        scale=grav_dict.get("scale", DEFAULT_GRAVITY_SCALE)
    )

    # 2. Initialize Wind
    raw_wind = raw_env.get("wind") or {}
    if not isinstance(raw_wind, dict):
        raw_wind = {}
    wind = WindField(
        enabled=bool(raw_wind.get("enabled", False)),
        magnitude=normalize_number(raw_wind.get("magnitude", 0.0), 0.0),
        direction_deg=normalize_number(raw_wind.get("direction_deg", 0.0), 0.0),
        turbulence=normalize_number(raw_wind.get("turbulence", 0.0), 0.0)
    )

    # 3. Initialize Atmosphere
    raw_atm = raw_env.get("atmosphere") or {}
    if not isinstance(raw_atm, dict):
        raw_atm = {}
        
    atm_type_str = str(raw_atm.get("type", "earth")).strip().lower()
    atm_type = AtmosphereType.EARTH
    for preset in AtmosphereType:
        if preset.value == atm_type_str:
            atm_type = preset
            break
            
    # Apply baseline presets
    density_fallback = 1.225
    drag_fallback = 0.47
    sound_fallback = 343.0
    
    if atm_type == AtmosphereType.VACUUM:
        density_fallback = 0.0
        drag_fallback = 0.0
        sound_fallback = 343.0 # Speed of sound in custom vacuum medium has negligible effect
    elif atm_type == AtmosphereType.MOON:
        density_fallback = 1e-12
        drag_fallback = 0.0
    elif atm_type == AtmosphereType.WATER:
        density_fallback = 1000.0
        drag_fallback = 0.5
        sound_fallback = 1482.0
    elif atm_type == AtmosphereType.MARS:
        density_fallback = 0.02
        drag_fallback = 0.47
        sound_fallback = 240.0

    atmosphere = AtmosphereField(
        type=atm_type,
        air_density=normalize_number(raw_atm.get("air_density", density_fallback), density_fallback),
        drag_coeff=normalize_number(raw_atm.get("drag_coeff", drag_fallback), drag_fallback),
        sound_speed=normalize_number(raw_atm.get("sound_speed", sound_fallback), sound_fallback)
    )

    # 4. Initialize Magnetic Field
    raw_mag = raw_env.get("magnetic") or {}
    if not isinstance(raw_mag, dict):
        raw_mag = {}
    magnetic = MagneticField(
        enabled=bool(raw_mag.get("enabled", False)),
        strength=normalize_number(raw_mag.get("strength", 0.0), 0.0),
        direction_x=normalize_number(raw_mag.get("direction_x", 0.0), 0.0),
        direction_y=normalize_number(raw_mag.get("direction_y", 0.0), 0.0),
        direction_z=normalize_number(raw_mag.get("direction_z", 1.0), 1.0)
    )

    # 5. Initialize Fluid immersion zone
    raw_fluid = raw_env.get("fluid") or {}
    if not isinstance(raw_fluid, dict):
        raw_fluid = {}
    fluid = FluidField(
        enabled=bool(raw_fluid.get("enabled", False)),
        density=normalize_number(raw_fluid.get("density", 1000.0), 1000.0),
        viscosity=normalize_number(raw_fluid.get("viscosity", 0.001), 0.001),
        zone_y=normalize_number(raw_fluid.get("zone_y")) if "zone_y" in raw_fluid else None
    )

    # 6. Initialize Lighting & Visuals
    raw_light = raw_env.get("lighting") or {}
    if not isinstance(raw_light, dict):
        raw_light = {}
    lighting = LightingEnvironment(
        background_color=str(raw_light.get("background_color", "#1a1a2e")),
        ambient_light=normalize_number(raw_light.get("ambient_light", 0.8), 0.8),
        theme=str(raw_light.get("theme", "dark"))
    )

    # 7. Collect extra fields for future-proofing
    extra_fields = raw_env.get("extra_fields")
    if not isinstance(extra_fields, dict):
        extra_fields = {}

    return SandboxEnvironment(
        gravity=gravity,
        wind=wind,
        atmosphere=atmosphere,
        magnetic=magnetic,
        fluid=fluid,
        lighting=lighting,
        extra_fields=extra_fields
    )
