#!/usr/bin/env python3
"""
Topic Content Generator for EduSim
Generates TutorScript, FormulaLab, and SimulationConfig using a local Ollama model.
Validates against Pydantic models with strict 1-retry fallback before failing loudly.
Saves validated output to a 'pending_review' folder for human inspection.
"""

import os
import sys
import json
import re
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from pydantic import ValidationError

# Set up module path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from app.src.models.topic_content_models import TopicContent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("EduSim.ContentGenerator")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b").strip() or "gemma3:4b"
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "300"))
DEFAULT_OUTPUT_DIR = BASE_DIR / "pending_review"


# ============================================================================
# Strict Prompts & Few-Shot Examples
# ============================================================================

SYSTEM_PROMPT = """You are an expert STEM curriculum and interactive simulation AI engine for EduSim.
Your task is to generate complete structured educational content for a given topic across three stages:

1. tutorScript:
   - explanation (string): Clear, age-appropriate conceptual breakdown of the topic.
   - keyPoints (array of strings): Core takeaways and principles.
   - followUpPrompts (array of strings): Socratic questions and reflection prompts.

2. formulaLab:
   - Include ONLY if the topic involves quantitative/mathematical equations or formulas.
   - If the topic is conceptual/qualitative with no formulas, set formulaLab to null or omit it.
   - If present:
     - formulas: Array of { expression: string, description: string }
     - variables: Array of { name: string, unit: string, min: number, max: number, default: number }
     - computeExpression: Evaluable mathematical formula string (e.g. "m * a" or "(m * v**2) / r")

3. simulationConfig:
   - mode: "static" | "dynamic"
   - rendererType: "mechanics-2d" | "chart" | "circuit" | "chemical-reaction" | "bio-process"
   - entities: Array of { name: string, properties: object, adjustable: boolean }
     (Any property that can be tweaked via interactive sliders MUST be in an entity with adjustable=true)
   - rules: Array of string constraints, physical laws, or governing equations.

STRICT FORMATTING RULE:
You must output ONLY valid, parseable JSON matching the schema. No conversational prose, no greetings, and no markdown formatting before or after the JSON.
"""

FEW_SHOT_EXAMPLES = """
--- EXAMPLE 1 (Physics topic with formulas and dynamic 2D mechanics):
Input:
Topic: Kinematic Equations for Uniform Acceleration
Subject: Physics
Chapter: Motion in a Straight Line
Grade: Class 11

Output:
{
  "topicId": "kinematic-equations-uniform-acceleration",
  "topicName": "Kinematic Equations for Uniform Acceleration",
  "tutorScript": {
    "explanation": "Uniformly accelerated motion occurs when an object's velocity changes at a constant rate over time. The fundamental kinematic equations link initial velocity (u), final velocity (v), acceleration (a), time elapsed (t), and displacement (s).",
    "keyPoints": [
      "Acceleration is constant throughout the motion (a = constant)",
      "v = u + a * t relates velocity linearly to time",
      "s = u * t + 0.5 * a * t^2 calculates position under constant acceleration",
      "v^2 = u^2 + 2 * a * s relates velocities and displacement independently of time"
    ],
    "followUpPrompts": [
      "If acceleration is zero, what happens to the displacement equation?",
      "How does doubling the initial velocity affect the stopping distance under constant deceleration?"
    ]
  },
  "formulaLab": {
    "formulas": [
      {
        "expression": "s = u * t + 0.5 * a * t^2",
        "description": "Displacement under uniform acceleration"
      },
      {
        "expression": "v = u + a * t",
        "description": "Final velocity after time t"
      }
    ],
    "variables": [
      { "name": "u", "unit": "m/s", "min": 0, "max": 50, "default": 10 },
      { "name": "a", "unit": "m/s²", "min": -10, "max": 20, "default": 2 },
      { "name": "t", "unit": "s", "min": 0, "max": 30, "default": 5 }
    ],
    "computeExpression": "(u * t) + (0.5 * a * (t ** 2))"
  },
  "simulationConfig": {
    "mode": "dynamic",
    "rendererType": "mechanics-2d",
    "entities": [
      {
        "name": "cart",
        "properties": { "mass": 2, "x": 100, "y": 350, "width": 60, "height": 30, "color": "#3B82F6", "initialVelocity": 10, "acceleration": 2 },
        "adjustable": true
      },
      {
        "name": "track",
        "properties": { "isStatic": true, "width": 800, "height": 20, "y": 380, "color": "#475569" },
        "adjustable": false
      }
    ],
    "rules": [
      "velocity += acceleration * dt",
      "position += velocity * dt",
      "collision with boundary stops motion"
    ]
  }
}

--- EXAMPLE 2 (Biology / Qualitative topic with no formula):
Input:
Topic: Cell Structure and Function: Mitochondria
Subject: Biology
Chapter: Cell: The Unit of Life
Grade: Class 11

Output:
{
  "topicId": "cell-structure-mitochondria",
  "topicName": "Cell Structure and Function: Mitochondria",
  "tutorScript": {
    "explanation": "Mitochondria are double-membrane-bound cellular organelles known as the powerhouses of the cell. They generate adenosine triphosphate (ATP) through cellular aerobic respiration and possess their own circular DNA and ribosomes.",
    "keyPoints": [
      "Double membrane: smooth outer membrane and folded inner membrane (cristae)",
      "Cristae increase surface area for ATP synthase complexes",
      "Matrix contains enzymes for Krebs cycle, 70S ribosomes, and circular DNA",
      "Semi-autonomous organelle replicating by fission"
    ],
    "followUpPrompts": [
      "Why do muscle cells contain significantly more mitochondria than skin cells?",
      "How does the endosymbiotic theory explain the origin of mitochondria?"
    ]
  },
  "formulaLab": null,
  "simulationConfig": {
    "mode": "static",
    "rendererType": "bio-process",
    "entities": [
      {
        "name": "outer_membrane",
        "properties": { "permeability": 1.0, "color": "#10B981" },
        "adjustable": false
      },
      {
        "name": "cristae_density",
        "properties": { "folds": 8, "surfaceAreaMultiplier": 3.5 },
        "adjustable": true
      },
      {
        "name": "atp_production_rate",
        "properties": { "glucoseInput": 50, "atpOutput": 36 },
        "adjustable": true
      }
    ],
    "rules": [
      "ATP output scales proportionally with cristae surface area and substrate availability",
      "Proton gradient across inner membrane drives ATP synthase rotation"
    ]
  }
}
"""


def slugify(text: str) -> str:
    """Creates a URL-safe slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def extract_json_payload(raw_text: str) -> str:
    """Extracts clean JSON substring from model output."""
    raw_text = raw_text.strip()
    # Remove markdown code block fences if present
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
        raw_text = re.sub(r"\s*```$", "", raw_text)
    
    # Try finding outermost { ... }
    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return raw_text[first_brace:last_brace + 1]
    return raw_text


class OllamaContentGenerator:
    def __init__(
        self,
        model: str = OLLAMA_DEFAULT_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        timeout: float = OLLAMA_TIMEOUT_SECONDS,
    ):
        self.model = model
        self.base_url = base_url
        self.generate_url = f"{self.base_url}/api/generate"
        self.timeout = timeout

    def call_ollama(self, prompt: str, system: str) -> str:
        """Sends request to Ollama with format=json."""
        payload = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            }
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.generate_url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"[Ollama Timeout] Request timed out after {self.timeout}s at {self.generate_url}. "
                f"Consider increasing OLLAMA_TIMEOUT_SECONDS (currently {self.timeout}s) or checking model compute load. Error: {e}"
            ) from e
        except httpx.ConnectError as e:
            raise ConnectionError(
                f"[Ollama Connection Error] Could not connect to Ollama at {self.generate_url}. Is Ollama running? Error: {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Ollama generation request failed: {e}") from e

    def generate_and_validate(self, topic: str, subject: str, chapter: str, grade: str) -> TopicContent:
        """
        Generates content for a topic and validates against TopicContent Pydantic model.
        Retries once on validation failure with error feedback before failing loudly.
        """
        user_prompt = f"""Generate full EduSim topic content for:
Topic: {topic}
Subject: {subject}
Chapter: {chapter}
Grade: {grade}
"""
        full_system = f"{SYSTEM_PROMPT}\n{FEW_SHOT_EXAMPLES}"

        logger.info(f"Generating content for '{topic}' ({grade} - {subject})...")
        raw_response = self.call_ollama(prompt=user_prompt, system=full_system)

        # First attempt parsing & validation
        try:
            json_str = extract_json_payload(raw_response)
            parsed_json = json.loads(json_str)
            validated_model = TopicContent.model_validate(parsed_json)
            logger.info(f"Successfully validated content for '{topic}' on 1st attempt.")
            return validated_model
        except (json.JSONDecodeError, ValidationError) as first_err:
            logger.warning(f"Validation failed on 1st attempt for '{topic}': {first_err}. Retrying with error feedback...")

            # Retry with explicit error feedback
            retry_prompt = f"""{user_prompt}

CRITICAL ERROR IN PREVIOUS ATTEMPT:
Your previous output failed validation with error:
{str(first_err)}

Previous invalid output:
{raw_response}

Please fix the error and output ONLY the valid JSON matching the TopicContent schema.
"""
            raw_retry_response = self.call_ollama(prompt=retry_prompt, system=full_system)

            try:
                retry_json_str = extract_json_payload(raw_retry_response)
                retry_parsed = json.loads(retry_json_str)
                validated_model = TopicContent.model_validate(retry_parsed)
                logger.info(f"Successfully validated content for '{topic}' on 2nd attempt (retry).")
                return validated_model
            except Exception as final_err:
                logger.error(f"FATAL: Generation failed validation after retry for '{topic}'. Failing loudly.")
                logger.error(f"Raw Model Output on Retry:\n{raw_retry_response}")
                raise RuntimeError(
                    f"Topic content validation failed for '{topic}' after retry: {final_err}"
                ) from final_err


def save_to_pending_review(
    content: TopicContent,
    topic_meta: Dict[str, str],
    output_dir: Path,
    model_name: str
) -> Path:
    """Saves validated topic content to the pending_review directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    grade_slug = slugify(topic_meta.get("grade", "general"))
    subject_slug = slugify(topic_meta.get("subject", "general"))
    topic_slug = slugify(topic_meta.get("name", "untitled-topic"))

    target_subdir = output_dir / grade_slug / subject_slug
    target_subdir.mkdir(parents=True, exist_ok=True)

    filename = f"{topic_slug}.json"
    target_file = target_subdir / filename

    payload = {
        "metadata": {
            "topic_name": topic_meta.get("name"),
            "subject": topic_meta.get("subject"),
            "chapter": topic_meta.get("chapter"),
            "grade": topic_meta.get("grade"),
            "model_used": model_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending_review",
        },
        "content": content.model_dump(by_alias=True, exclude_none=False)
    }

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    logger.info(f"Saved validated topic content to: {target_file}")
    return target_file


def parse_batch_input(batch_path: Path) -> List[Dict[str, str]]:
    """Loads a list of topics from a JSON or JSONL file."""
    if not batch_path.exists():
        raise FileNotFoundError(f"Batch file not found at: {batch_path}")

    with open(batch_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    if batch_path.suffix.lower() == ".jsonl":
        topics = []
        for line in content.splitlines():
            if line.strip():
                topics.append(json.loads(line))
        return topics

    data = json.loads(content)
    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "topics" in data:
        return data["topics"]
    else:
        raise ValueError("Batch file must be a JSON array or object with a 'topics' array.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate EduSim Topic Content (TutorScript, FormulaLab, SimulationConfig) with Ollama."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--topic", type=str, help="Single topic name to generate content for")
    group.add_argument("--batch", type=str, help="Path to JSON or JSONL file containing batch topic definitions")

    parser.add_argument("--subject", type=str, default="Physics", help="Subject name (for single topic mode)")
    parser.add_argument("--chapter", type=str, default="General", help="Chapter name (for single topic mode)")
    parser.add_argument("--grade", type=str, default="Class 11", help="Grade or Class level (for single topic mode)")
    parser.add_argument("--model", type=str, default=OLLAMA_DEFAULT_MODEL, help="Ollama model identifier")
    parser.add_argument("--ollama-url", type=str, default=OLLAMA_BASE_URL, help="Ollama base API URL")
    parser.add_argument("--timeout", type=float, default=OLLAMA_TIMEOUT_SECONDS, help=f"Ollama request timeout in seconds (default: {int(OLLAMA_TIMEOUT_SECONDS)}s)")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR), help="Directory to save pending review JSONs")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    generator = OllamaContentGenerator(model=args.model, base_url=args.ollama_url, timeout=args.timeout)

    if args.topic:
        topics_to_process = [{
            "name": args.topic,
            "subject": args.subject,
            "chapter": args.chapter,
            "grade": args.grade,
        }]
    else:
        topics_to_process = parse_batch_input(Path(args.batch))

    total = len(topics_to_process)
    logger.info(f"Starting generation for {total} topic(s) using model '{args.model}'...")

    success_count = 0
    failure_count = 0

    for idx, item in enumerate(topics_to_process, 1):
        name = item.get("name") or item.get("topic") or "Untitled Topic"
        subject = item.get("subject", "General")
        chapter = item.get("chapter", "General")
        grade = item.get("grade") or item.get("class") or "General"

        logger.info(f"[{idx}/{total}] Processing: '{name}' ({grade} - {subject})")
        try:
            validated_content = generator.generate_and_validate(
                topic=name,
                subject=subject,
                chapter=chapter,
                grade=grade
            )
            save_to_pending_review(
                content=validated_content,
                topic_meta={"name": name, "subject": subject, "chapter": chapter, "grade": grade},
                output_dir=output_dir,
                model_name=args.model
            )
            success_count += 1
        except Exception as e:
            logger.error(f"[{idx}/{total}] FAILED for '{name}': {e}")
            failure_count += 1

    logger.info(f"Batch generation completed: {success_count} succeeded, {failure_count} failed.")
    if failure_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
