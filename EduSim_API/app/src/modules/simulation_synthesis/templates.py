"""
Subject-specific synthesis prompt templates for EduSim Simulation Synthesis System.
Each template emphasizes different educational visualization approaches for its domain.
"""

import re
from typing import Literal

SubjectType = Literal["physics", "chemistry", "astronomy", "biology", "mathematics"]


def detect_subject(prompt: str) -> SubjectType:
    """
    Automatically detect the subject/domain from the user prompt.
    Returns the detected subject or 'physics' as default.
    """
    lowered = prompt.lower()

    # Physics keywords
    physics_keywords = [
        "motion", "velocity", "acceleration", "force", "newton", "momentum",
        "energy", "kinetic", "potential", "gravity", "gravitational",
        "pendulum", "projectile", "collision", "friction", "tension",
        "wave", "oscillation", "frequency", "amplitude", "drag",
        "momentum conservation", "elastic", "inelastic", "circular motion",
        "centripetal", "torque", "angular", "rotation", "lever",
        "simple harmonic", "spring", "hooke", "displacement", "vector",
    ]
    
    # Chemistry keywords
    chemistry_keywords = [
        "molecule", "atom", "chemical", "element", "bond", "reaction",
        "oxidation", "reduction", "electron", "ion", "orbital", "valence",
        "acid", "base", "ph", "salt", "compound", "mixture", "solution",
        "concentration", "molarity", "atomic structure", "periodic table",
        "isotope", "radioactive", "polymer", "hydrocarbon", "alcohol",
        "amine", "carboxylic", "ester", "amide", "protein", "nucleic",
    ]
    
    # Astronomy keywords
    astronomy_keywords = [
        "orbit", "orbital", "planet", "star", "galaxy", "moon", "comet",
        "asteroid", "celestial", "solar system", "universe", "space",
        "gravity", "gravitational", "sun", "earth", "mars", "jupiter",
        "supernova", "nebula", "black hole", "dark matter", "cosmic",
        "eclipse", "rotation", "revolution", "kepler", "astronomy",
    ]
    
    # Biology keywords
    biology_keywords = [
        "cell", "dna", "protein", "enzyme", "photosynthesis", "respiration",
        "mitochondria", "chloroplast", "organ", "tissue", "system",
        "evolution", "mutation", "gene", "chromosome", "reproduction",
        "immune", "nervous", "circulatory", "digestive", "endocrine",
        "organism", "species", "ecosystem", "metabolism", "homeostasis",
        "anatomy", "physiology", "cell division", "meiosis", "mitosis",
    ]
    
    # Mathematics keywords
    mathematics_keywords = [
        "function", "graph", "equation", "calculus", "integral", "derivative",
        "limit", "series", "vector", "matrix", "algebra", "geometry",
        "trigonometry", "sine", "cosine", "tangent", "polynomial",
        "parabola", "hyperbola", "ellipse", "circle", "line",
        "probability", "statistics", "distribution", "linear", "quadratic",
        "exponential", "logarithm", "transform", "fourier",
    ]

    # Score each subject based on keyword matches
    scores = {
        "physics": sum(1 for kw in physics_keywords if kw in lowered),
        "chemistry": sum(1 for kw in chemistry_keywords if kw in lowered),
        "astronomy": sum(1 for kw in astronomy_keywords if kw in lowered),
        "biology": sum(1 for kw in biology_keywords if kw in lowered),
        "mathematics": sum(1 for kw in mathematics_keywords if kw in lowered),
    }

    # Return subject with highest score, or physics as default
    detected = max(scores, key=scores.get)
    return detected if scores[detected] > 0 else "physics"


def get_system_prompt(subject: SubjectType) -> str:
    """
    Return subject-specific system prompt for AI/Gemini synthesis.
    Each template emphasizes domain-specific visualization and interaction patterns.
    """
    
    base_requirements = (
        "You are Simulation Synthesis System for EduSim. "
        "Generate ONLY raw HTML (single self-contained document) for an interactive educational simulation. "
        "Do not return markdown, code fences, or explanation text.\n"
        "Base Requirements:\n"
        "- Use Canvas-based animation and plain HTML/CSS/JavaScript only.\n"
        "- Dark futuristic UI with clear educational overlays, labels, formulas, and controls.\n"
        "- Responsive layout for desktop and mobile.\n"
        "- Include sliders/playback controls and real-time updates.\n"
        "- No external dependencies and no network access.\n"
        "- Avoid eval, new Function, fetch, XMLHttpRequest, WebSocket, window.open, top navigation.\n"
        "- Use textbook terminology and keep equations/models accurate.\n"
        "- Add short educational annotations near visual elements.\n"
        "- Include a concise title and one-line concept summary in the UI.\n"
    )

    subject_prompts = {
        "physics": (
            base_requirements +
            "Physics-Specific Requirements:\n"
            "- Animate motion with velocity vectors and acceleration arrows.\n"
            "- Use color-coded force vectors (red=applied, blue=gravity, green=friction).\n"
            "- Show trajectory paths and collision detection visually.\n"
            "- Include real-time measurements: velocity, displacement, energy, momentum.\n"
            "- Use Canvas 2D with smooth requestAnimationFrame animations.\n"
            "- Emphasize Newton's laws, energy conservation, momentum conservation in labels.\n"
            "- Add interactive sliders for initial conditions (angle, velocity, mass).\n"
            "- Display equations of motion and calculated values prominently.\n"
            "- Show reference grids and scale indicators for spatial accuracy.\n"
        ),
        
        "chemistry": (
            base_requirements +
            "Chemistry-Specific Requirements:\n"
            "- Render atoms as circles with nucleus + electron shells/orbits.\n"
            "- Use color-coding for different elements (H=white, C=black, O=red, N=blue).\n"
            "- Animate electron orbitals and bonding interactions.\n"
            "- Show molecular structure with bonds (single=line, double=parallel lines).\n"
            "- Display atomic number, mass, electrons, and valence clearly.\n"
            "- Animate reaction sequences: reactants → products with energy visualization.\n"
            "- Include oxidation state labels and electron transfer arrows.\n"
            "- Use Canvas to draw 3D-like ball-and-stick or space-filling models.\n"
            "- Add pH scale, molarity, concentration sliders as interactive parameters.\n"
        ),
        
        "astronomy": (
            base_requirements +
            "Astronomy-Specific Requirements:\n"
            "- Render orbital mechanics with gravity field visualization.\n"
            "- Use circular orbits or Kepler ellipse paths with accurate scaling.\n"
            "- Color stars/planets realistically and show scale references.\n"
            "- Animate orbital motion with angular velocity calculated from Kepler's laws.\n"
            "- Display orbital parameters: semi-major axis, eccentricity, period, inclination.\n"
            "- Show gravitational force vectors and acceleration toward central body.\n"
            "- Include time-stepping controls (pause, play, speed-up).\n"
            "- Add constellation or solar system context.\n"
            "- Use Canvas with filled circles and rotation transforms for smooth animation.\n"
        ),
        
        "biology": (
            base_requirements +
            "Biology-Specific Requirements:\n"
            "- Render cell structures with organelles: nucleus, mitochondria, chloroplast, ER, etc.\n"
            "- Use color-coding for different cellular components.\n"
            "- Animate cellular processes: photosynthesis, respiration, cell division, protein synthesis.\n"
            "- Show molecular flow: glucose → ATP, CO2 fixation, DNA replication.\n"
            "- Display anatomical systems with organ connectivity (circulatory, nervous, digestive).\n"
            "- Include interactive controls to show/hide layers or cellular structures.\n"
            "- Add legend and labels for all biological components.\n"
            "- Use Canvas to draw organelles, cells, and tissue structures.\n"
            "- Emphasize biological accuracy and textbook terminology.\n"
        ),
        
        "mathematics": (
            base_requirements +
            "Mathematics-Specific Requirements:\n"
            "- Plot functions as curves on a Cartesian coordinate system.\n"
            "- Show axes with tick marks, labels, and gridlines.\n"
            "- Animate transformations: translation, scaling, rotation of functions.\n"
            "- Display equation in standard form near the graph (y = mx + b, etc.).\n"
            "- Include interactive sliders for coefficients (a, b, c) to modify functions in real-time.\n"
            "- Show key points: roots, vertex, asymptotes, inflection points.\n"
            "- Use color-coding for different functions if comparing multiple graphs.\n"
            "- Add derivative/integral visualization for calculus topics.\n"
            "- Use Canvas for smooth curve rendering with anti-aliasing.\n"
            "- Include numerical values and formulas prominently.\n"
        ),
    }

    return subject_prompts.get(subject, subject_prompts["physics"])


def get_user_content_enhancement(subject: SubjectType, extracted: dict) -> str:
    """
    Return subject-specific enhancement to the user content message.
    Guides the LLM to prioritize certain extracted features.
    """
    
    enhancements = {
        "physics": (
            "Subject Context: Physics/Mechanics\n"
            "Prioritize visualization of: motion, vectors, forces, energy conservation.\n"
            f"Key formulas to use prominently: {extracted.get('formulas', [])}\n"
            f"Constants: {extracted.get('constants', [])}\n"
            f"Laws: {extracted.get('laws', [])}\n"
            "Render interactive sliders for initial conditions.\n"
        ),
        
        "chemistry": (
            "Subject Context: Chemistry/Molecular Structure\n"
            "Prioritize visualization of: atoms, bonds, electron configuration, reactions.\n"
            f"Molecular components: {extracted.get('formulas', [])}\n"
            f"Constants (atomic weights, charges): {extracted.get('constants', [])}\n"
            f"Chemical principles: {extracted.get('definitions', [])}\n"
            "Use color-coded atoms and animated bonding.\n"
        ),
        
        "astronomy": (
            "Subject Context: Astronomy/Orbital Mechanics\n"
            "Prioritize visualization of: orbits, gravity, celestial motion, Kepler's laws.\n"
            f"Orbital parameters: {extracted.get('formulas', [])}\n"
            f"Constants (G, masses, distances): {extracted.get('constants', [])}\n"
            f"Laws of motion: {extracted.get('laws', [])}\n"
            "Animate smooth orbital paths with accurate physics.\n"
        ),
        
        "biology": (
            "Subject Context: Biology/Cell/Organism Structure\n"
            "Prioritize visualization of: cells, organelles, biological processes, anatomy.\n"
            f"Biological components/processes: {extracted.get('formulas', [])}\n"
            f"Biological parameters: {extracted.get('constants', [])}\n"
            f"Key definitions: {extracted.get('definitions', [])}\n"
            "Use color-coded organelles and animated processes.\n"
        ),
        
        "mathematics": (
            "Subject Context: Mathematics/Functions/Calculus\n"
            "Prioritize visualization of: graphs, functions, transformations, key points.\n"
            f"Functions and equations: {extracted.get('formulas', [])}\n"
            f"Key values (slopes, intercepts, roots): {extracted.get('constants', [])}\n"
            f"Mathematical principles: {extracted.get('laws', [])}\n"
            "Use interactive sliders to explore parameter changes in real-time.\n"
        ),
    }

    return enhancements.get(subject, enhancements["physics"])


PRECOMPILED_PHYSICS_TEMPLATES = {
    "newton": {
        "dsl": {
            "meta": {
                "id": "sim_newton_second_law",
                "title": "Newton's Second Law & Motion",
                "topic": "Newton's Laws of Motion",
                "simulationType": "Mechanics",
                "difficulty": "Class 9-11",
                "version": "2.0"
            },
            "environment": {
                "gravity": {"x": 0.0, "y": 9.8},
                "airResistance": 0.01,
                "world": {"width": 800, "height": 600, "unitSystem": "normalized"},
                "background": {"color": "#0f172a"},
                "camera": {"mode": "auto-fit", "padding": 0.15, "allowZoom": True, "allowPan": True},
                "boundaries": {"enabled": True, "type": "solid"}
            },
            "objects": [
                {
                    "id": "cart",
                    "category": "physics-object",
                    "bodyType": "dynamic",
                    "shape": {"type": "rectangle", "width": 4, "height": 2},
                    "position": {"x": 10, "y": 48},
                    "physics": {"mass": 2.0, "density": 1.0, "affectedByGravity": True, "fixedRotation": False, "isSensor": False},
                    "material": {"friction": 0.1, "restitution": 0.3},
                    "collision": {"enabled": True, "group": "default"},
                    "visual": {"color": "#38bdf8", "label": "Cart (2kg)", "showLabel": True, "showVelocityVector": True}
                },
                {
                    "id": "ground",
                    "category": "environment",
                    "bodyType": "static",
                    "shape": {"type": "rectangle", "width": 80, "height": 4},
                    "position": {"x": 40, "y": 56},
                    "physics": {"mass": 0.0, "density": 1.0, "affectedByGravity": False, "fixedRotation": True, "isSensor": False},
                    "material": {"friction": 0.2, "restitution": 0.0},
                    "collision": {"enabled": True, "group": "default"},
                    "visual": {"color": "#1e293b", "label": "Track", "showLabel": False}
                }
            ],
            "forces": [
                {"id": "applied_force", "type": "constantForce", "target": "cart", "vector": {"x": 10.0, "y": 0.0}, "active": True}
            ],
            "controls": {
                "parameters": [
                    {"id": "mass_ctrl", "type": "slider", "label": "Cart Mass", "symbol": "m", "bind": "objects[0].physics.mass", "min": 0.5, "max": 10.0, "step": 0.5},
                    {"id": "force_ctrl", "type": "slider", "label": "Applied Force", "symbol": "F", "bind": "forces[0].vector.x", "min": 0.0, "max": 50.0, "step": 1.0}
                ],
                "actions": [
                    {"id": "reset_btn", "type": "button", "label": "Reset", "action": "resetSimulation"}
                ]
            },
            "observables": [
                {"id": "obs_velocity", "label": "Velocity (v)", "source": "objects[0].velocity.x", "unit": "m/s", "precision": 2},
                {"id": "obs_accel", "label": "Acceleration (a)", "source": "objects[0].acceleration.x", "unit": "m/s²", "precision": 2}
            ],
            "formulaBindings": [
                {
                    "id": "f_ma_binding",
                    "formula": "a = F / m",
                    "variables": {
                        "F": {"path": "forces[0].vector.x", "role": "independent"},
                        "m": {"path": "objects[0].physics.mass", "role": "independent"},
                        "a": {"path": "objects[0].acceleration.x", "role": "dependent"}
                    }
                }
            ],
            "runtime": {
                "engine": "matter-js",
                "renderer": "pixi-js",
                "fps": 60,
                "paused": False
            }
        },
        "knowledge": {
            "relevant_formulas": ["F = m * a", "v = u + a * t", "s = u*t + 0.5*a*t^2"],
            "related_concepts": ["Force", "Mass", "Acceleration", "Inertia", "Friction"],
            "learningObjectives": ["Understand how varying force changes acceleration", "Observe inverse relationship between mass and acceleration"]
        },
        "metadata": {
            "subject": "physics",
            "chapter": "Laws of Motion",
            "difficulty": "medium",
            "curriculum": "CBSE / NCERT / Standard Physics",
            "simulationCategory": "Mechanics",
            "tags": ["Newton's Laws", "Force", "Acceleration", "Mass"]
        }
    },
    "projectile": {
        "dsl": {
            "meta": {
                "id": "sim_projectile_motion",
                "title": "Projectile Motion & Trajectory",
                "topic": "Projectile Motion",
                "simulationType": "Mechanics",
                "difficulty": "Class 10-11",
                "version": "2.0"
            },
            "environment": {
                "gravity": {"x": 0.0, "y": 9.8},
                "airResistance": 0.005,
                "world": {"width": 800, "height": 600, "unitSystem": "normalized"},
                "background": {"color": "#0f172a"},
                "camera": {"mode": "auto-fit", "padding": 0.15, "allowZoom": True, "allowPan": True},
                "boundaries": {"enabled": True, "type": "solid"}
            },
            "objects": [
                {
                    "id": "projectile_ball",
                    "category": "physics-object",
                    "bodyType": "dynamic",
                    "shape": {"type": "circle", "radius": 1.2},
                    "position": {"x": 5, "y": 48},
                    "velocity": {"x": 15.0, "y": -15.0},
                    "physics": {"mass": 1.0, "density": 1.0, "affectedByGravity": True, "fixedRotation": False, "isSensor": False},
                    "material": {"friction": 0.1, "restitution": 0.6},
                    "collision": {"enabled": True, "group": "default"},
                    "visual": {"color": "#f59e0b", "label": "Projectile", "showLabel": True, "showVelocityVector": True, "showTrail": True}
                },
                {
                    "id": "ground",
                    "category": "environment",
                    "bodyType": "static",
                    "shape": {"type": "rectangle", "width": 80, "height": 4},
                    "position": {"x": 40, "y": 56},
                    "physics": {"mass": 0.0, "density": 1.0, "affectedByGravity": False, "fixedRotation": True, "isSensor": False},
                    "material": {"friction": 0.4, "restitution": 0.2},
                    "collision": {"enabled": True, "group": "default"},
                    "visual": {"color": "#1e293b", "label": "Ground", "showLabel": False}
                }
            ],
            "controls": {
                "parameters": [
                    {"id": "vel_x", "type": "slider", "label": "Launch Vx", "symbol": "vx", "bind": "objects[0].velocity.x", "min": 0.0, "max": 30.0, "step": 1.0},
                    {"id": "vel_y", "type": "slider", "label": "Launch Vy", "symbol": "vy", "bind": "objects[0].velocity.y", "min": -30.0, "max": 0.0, "step": 1.0}
                ],
                "actions": [
                    {"id": "reset_btn", "type": "button", "label": "Launch Again", "action": "resetSimulation"}
                ]
            },
            "observables": [
                {"id": "obs_vx", "label": "Horizontal Vel (Vx)", "source": "objects[0].velocity.x", "unit": "m/s", "precision": 1},
                {"id": "obs_vy", "label": "Vertical Vel (Vy)", "source": "objects[0].velocity.y", "unit": "m/s", "precision": 1}
            ],
            "runtime": {
                "engine": "matter-js",
                "renderer": "pixi-js",
                "fps": 60,
                "paused": False
            }
        },
        "knowledge": {
            "relevant_formulas": ["R = (u^2 * sin(2*theta)) / g", "H_max = (u^2 * sin^2(theta)) / (2*g)", "T = (2*u*sin(theta)) / g"],
            "related_concepts": ["Parabolic Trajectory", "Independence of Motions", "Horizontal Range", "Maximum Height"],
            "learningObjectives": ["Analyze horizontal and vertical velocity components", "Determine angle for maximum range"]
        },
        "metadata": {
            "subject": "physics",
            "chapter": "Motion in a Plane",
            "difficulty": "medium",
            "curriculum": "CBSE / NCERT",
            "simulationCategory": "Mechanics",
            "tags": ["Projectile", "2D Motion", "Range", "Height"]
        }
    },
    "pendulum": {
        "dsl": {
            "meta": {
                "id": "sim_pendulum_oscillation",
                "title": "Simple Harmonic Motion: Pendulum",
                "topic": "Oscillations & Pendulum",
                "simulationType": "Mechanics",
                "difficulty": "Class 10-11",
                "version": "2.0"
            },
            "environment": {
                "gravity": {"x": 0.0, "y": 9.8},
                "airResistance": 0.001,
                "world": {"width": 800, "height": 600, "unitSystem": "normalized"},
                "background": {"color": "#0f172a"},
                "camera": {"mode": "auto-fit", "padding": 0.15, "allowZoom": True, "allowPan": True},
                "boundaries": {"enabled": True, "type": "solid"}
            },
            "objects": [
                {
                    "id": "pivot",
                    "category": "environment",
                    "bodyType": "static",
                    "shape": {"type": "circle", "radius": 0.8},
                    "position": {"x": 40, "y": 15},
                    "physics": {"mass": 0.0, "density": 1.0, "affectedByGravity": False, "fixedRotation": True, "isSensor": True},
                    "visual": {"color": "#64748b", "label": "Pivot", "showLabel": True}
                },
                {
                    "id": "bob",
                    "category": "physics-object",
                    "bodyType": "dynamic",
                    "shape": {"type": "circle", "radius": 1.5},
                    "position": {"x": 55, "y": 25},
                    "physics": {"mass": 1.0, "density": 1.0, "affectedByGravity": True, "fixedRotation": False, "isSensor": False},
                    "material": {"friction": 0.01, "restitution": 0.8},
                    "collision": {"enabled": True, "group": "default"},
                    "visual": {"color": "#8b5cf6", "label": "Bob", "showLabel": True, "showVelocityVector": True, "showTrail": True}
                }
            ],
            "constraints": [
                {
                    "id": "rope_1",
                    "type": "rope",
                    "bodyA": "pivot",
                    "bodyB": "bob",
                    "length": 20.0,
                    "stiffness": 1.0,
                    "visual": {"color": "#cbd5e1", "lineWidth": 2}
                }
            ],
            "controls": {
                "parameters": [
                    {"id": "gravity_ctrl", "type": "slider", "label": "Gravity", "symbol": "g", "bind": "environment.gravity.y", "min": 1.0, "max": 25.0, "step": 0.5},
                    {"id": "length_ctrl", "type": "slider", "label": "String Length", "symbol": "L", "bind": "constraints[0].length", "min": 5.0, "max": 35.0, "step": 1.0}
                ],
                "actions": [
                    {"id": "reset_btn", "type": "button", "label": "Release from Rest", "action": "resetSimulation"}
                ]
            },
            "observables": [
                {"id": "obs_period", "label": "Approx. Period (T)", "source": "runtime.calculated.period", "unit": "s", "precision": 2}
            ],
            "formulaBindings": [
                {
                    "id": "pendulum_period_formula",
                    "formula": "T = 2 * pi * sqrt(L / g)",
                    "variables": {
                        "L": {"path": "constraints[0].length", "role": "independent"},
                        "g": {"path": "environment.gravity.y", "role": "independent"}
                    }
                }
            ],
            "runtime": {
                "engine": "matter-js",
                "renderer": "pixi-js",
                "fps": 60,
                "paused": False
            }
        },
        "knowledge": {
            "relevant_formulas": ["T = 2 * \\pi * \\sqrt{L / g}", "f = 1 / T"],
            "related_concepts": ["Simple Harmonic Motion", "Restoring Force", "Period & Frequency", "Energy Conservation"],
            "learningObjectives": ["Understand that period depends on length and gravity, independent of mass for small angles"]
        },
        "metadata": {
            "subject": "physics",
            "chapter": "Oscillations",
            "difficulty": "medium",
            "curriculum": "CBSE / NCERT",
            "simulationCategory": "Mechanics",
            "tags": ["Pendulum", "SHM", "Period", "Oscillation"]
        }
    }
}


def get_precompiled_template(topic_or_prompt: str) -> dict | None:
    """
    Check if a fast, verified precompiled Physics simulation template exists for the given topic or prompt.
    Returns the valid EduSimResponse dictionary or None if LLM synthesis is needed.
    """
    if not topic_or_prompt:
        return None
    lowered = topic_or_prompt.lower()
    
    if any(kw in lowered for kw in ["projectile", "trajectory", "launch angle", "parabolic"]):
        return PRECOMPILED_PHYSICS_TEMPLATES["projectile"]
    if any(kw in lowered for kw in ["pendulum", "oscillation", "harmonic", "shm", "bob", "string length"]):
        return PRECOMPILED_PHYSICS_TEMPLATES["pendulum"]
    if any(kw in lowered for kw in ["newton", "force", "acceleration", "f=ma", "f = ma", "mass", "motion", "inertia", "cart", "speed", "velocity", "friction"]):
        return PRECOMPILED_PHYSICS_TEMPLATES["newton"]
        
    return None
