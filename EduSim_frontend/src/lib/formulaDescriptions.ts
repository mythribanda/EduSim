/**
 * formulaDescriptions.ts
 * =======================
 * Plain-English, kid-friendly descriptions for formulas returned by static physics simulations.
 */

export const formulaDescriptions: Record<string, string> = {
  // Projectile Motion
  "x = v₀ · cos(θ) · t": "Horizontal distance grows steadily because there is no horizontal force slowing it down.",
  "y = y₀ + v₀ · sin(θ) · t - ½gt²": "Height rises from the initial upward push and curves downward as gravity pulls on it.",
  "v_x = v₀ · cos(θ)": "Horizontal velocity stays constant during the entire flight.",
  "v_y = v₀ · sin(θ) - gt": "Vertical speed drops steadily under gravity until it reaches zero at the peak, then speeds up downward.",
  "t_flight = (v₀ · sin(θ) + √(v₀² · sin²(θ) + 2gy₀)) / g": "Total flight time is how many seconds the projectile remains in the air before landing.",
  "H_max = y₀ + (v₀² · sin²(θ)) / (2g)": "Maximum height is the highest peak reached when upward velocity momentarily becomes zero.",
  "R = v₀ · cos(θ) · t_flight": "Total range is how far forward the projectile travels from launch to touchdown.",
  "v_final = √(v_x² + v_y²)": "Final impact speed combines both horizontal and vertical velocity at the moment of landing.",

  // Pendulum
  "T = 2π√(L/g)": "The longer the pendulum string, the more time it takes to complete one full swing back and forth.",
  "v_max = √(2gL(1-cosθ))": "Top speed happens at the very bottom of the swing, where all height energy has turned into speed.",

  // Free Fall
  "h = h₀ + v₀t - ½gt²": "The falling object accelerates toward the ground, losing height faster and faster every second.",
  "v = v₀ + gt": "Speed increases by 9.81 m/s every second during free fall due to Earth's gravitational pull.",

  // Collision
  "p_total = m₁u₁ + m₂u₂ = m₁v₁ + m₂v₂": "Total momentum before the crash is always equal to total momentum after the crash.",
  "e = (v₂ - v₁) / (u₁ - u₂)": "The restitution coefficient measures bounciness: 1 for perfectly bouncy elastic, 0 for sticky inelastic.",
  "v₁ = (m₁u₁ + m₂u₂ - m₂e(u₁ - u₂)) / (m₁ + m₂)": "Calculates the rebound speed and direction of the first object after impact.",
  "v₂ = (m₁u₁ + m₂u₂ + m₁e(u₁ - u₂)) / (m₁ + m₂)": "Calculates how fast and in what direction the second object gets pushed after the collision.",
  "KE_before = ½m₁u₁² + ½m₂u₂²": "The total energy of motion of both objects before they crash into each other.",
  "KE_after = ½m₁v₁² + ½m₂v₂²": "The total kinetic energy remaining in motion after the objects bounce apart.",
  "ΔE = KE_before - KE_after": "Kinetic energy lost during impact, turned into heat, deformation, or sound vibrations.",

  // Spring Mass
  "ω = √(k/m)": "Natural frequency measures how rapidly the spring vibrates; stiffer springs oscillate faster, heavier masses oscillate slower.",
  "x(t) = A·cos(ωt + φ)": "The bouncing mass follows a smooth cosine wave back and forth between maximum stretch and compression.",
  "F = -kx": "Hooke's Law: The spring pushes or pulls opposite to displacement to return the mass to its resting center.",

  // Inclined Plane
  "a = g(sinθ - μcosθ)": "Acceleration down the ramp equals gravity's downhill pull minus the resistive dragging force of friction.",
  "F_net = mg sinθ - μmg cosθ": "The net sliding force determines whether the block overcomes friction to slide and accelerate down the incline.",
};

/**
 * Returns a kid-friendly description for a given formula string.
 * Falls back to a generalized physics explanation if the exact string isn't mapped.
 */
export function getFormulaDescription(formula: string): string {
  if (formulaDescriptions[formula]) {
    return formulaDescriptions[formula];
  }

  // Normalize potential unicode / spacing differences
  const cleaned = formula.replace(/\s+/g, " ").trim();
  for (const [key, desc] of Object.entries(formulaDescriptions)) {
    if (key.replace(/\s+/g, " ").trim() === cleaned) {
      return desc;
    }
  }

  return "Core physics relationship governing this part of the simulation.";
}
