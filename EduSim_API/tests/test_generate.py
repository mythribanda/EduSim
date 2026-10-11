import argparse
import sys
import json
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from app.src.modules.simulation_synthesis.service import (
    retrieve_context,
    build_dsl_prompt,
    generate_dsl,
    sanitize_dsl,
    validate_dsl
)

def test_generation_pipeline(prompt: str = "A block sliding down an inclined plane with friction"):
    print(f"Testing Generation Pipeline for prompt: '{prompt}'")
    print("-" * 60)
    
    try:
        print("1. Retrieving RAG Context...")
        context = retrieve_context(prompt)
        print(f"   Context retrieved (length: {len(context)})")
        
        print("\n2. Building DSL Prompt...")
        dsl_prompt = build_dsl_prompt(prompt, context)
        print(f"   Prompt built (length: {len(dsl_prompt)})")
        
        print("\n3. Calling LLM (This may take a few seconds)...")
        raw_text = generate_dsl(dsl_prompt)
        print("   LLM Response received.")
        
        print("\n4. Sanitizing DSL...")
        sanitized_json = sanitize_dsl(raw_text)
        print("   Sanitized successfully.")
        
        print("\n5. Validating DSL...")
        valid_dsl = validate_dsl(sanitized_json)
        print("   Validation PASSED.")
        
        print("\n--- Final Validated Output ---")
        print(json.dumps(valid_dsl, indent=2)[:1000] + "\n... (truncated for brevity) ...\n")
        print("------------------------------")
        print("Successfully completed the generation pipeline.")
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the EduSim simulation synthesis pipeline.")
    parser.add_argument("prompt", type=str, nargs="?", default="A block sliding down an inclined plane with friction", help="The physics prompt to generate.")
    args = parser.parse_args()
    
    test_generation_pipeline(args.prompt)
