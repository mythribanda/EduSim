from .schema import EduSimResponse

def validate_simulation(data: dict) -> dict:
    """
    Validate AI-generated EduSimResponse JSON with strict runtime constraints (v2.0).
    """
    try:
        # Pass 0: Deprecation Check
        deprecated_fields = ["movable", "groundFriction"]
        def find_deprecated(d, path=""):
            errors = []
            if isinstance(d, dict):
                for k, v in d.items():
                    current_path = f"{path}.{k}" if path else k
                    if k in deprecated_fields:
                        errors.append(f"Deprecated field '{k}' found at '{current_path}'")
                    errors.extend(find_deprecated(v, current_path))
            elif isinstance(d, list):
                for i, item in enumerate(d):
                    errors.extend(find_deprecated(item, f"{path}[{i}]"))
            return errors

        deprecation_errors = find_deprecated(data)
        if deprecation_errors:
            return {
                "success": False,
                "data": None,
                "errors": "; ".join(deprecation_errors)
            }

        # Pass 1: Structural Validation via Pydantic
        validated_model = EduSimResponse(**data)
        validated_dict = validated_model.dict()
        dsl = validated_dict.get("dsl", {})

        semantic_errors = []
        valid_roots = [
            "objects", "forces", "environment", "constraints", 
            "behaviors", "formulaBindings", "controls", 
            "observables", "events", "runtime"
        ]
        
        # Pass 2: Semantic Path Validation (for controls.parameters and observables)
        # Check parameters
        controls = dsl.get("controls", {})
        for i, param in enumerate(controls.get("parameters", [])):
            path = param.get("bind", "")
            if not any(path.startswith(root) for root in valid_roots):
                semantic_errors.append(
                    f"ControlParameter[{i}] has invalid bind path '{path}'. "
                    f"Must start with one of: {valid_roots}"
                )

        # Check observables
        for i, obs in enumerate(dsl.get("observables", [])):
            path = obs.get("source", "")
            if not any(path.startswith(root) for root in valid_roots):
                semantic_errors.append(
                    f"Observable[{i}] has invalid source path '{path}'. "
                    f"Must start with one of: {valid_roots}"
                )

        # Check formula bindings
        for i, binding in enumerate(dsl.get("formulaBindings", [])):
            for var_name, var_info in binding.get("variables", {}).items():
                path = var_info.get("path", "")
                if not any(path.startswith(root) for root in valid_roots):
                    semantic_errors.append(
                        f"FormulaBinding[{i}] variable '{var_name}' has invalid path '{path}'. "
                        f"Must start with one of: {valid_roots}"
                    )

        # Pass 3: Physics Logic Validation
        object_ids = {obj["id"] for obj in dsl.get("objects", [])}
        all_ids = (
            [obj["id"] for obj in dsl.get("objects", [])] + 
            [force["id"] for force in dsl.get("forces", [])] +
            [c["id"] for c in dsl.get("constraints", [])] +
            [b["id"] for b in dsl.get("behaviors", [])]
        )
        
        from collections import Counter
        duplicates = [item for item, count in Counter(all_ids).items() if count > 1]
        if duplicates:
            semantic_errors.append(f"Duplicate IDs found across objects/forces/constraints/behaviors: {duplicates}")

        # Check for static body mass
        for i, obj in enumerate(dsl.get("objects", [])):
            if obj.get("bodyType") == "static":
                if obj["physics"]["mass"] != 0.0:
                    semantic_errors.append(f"Static body '{obj['id']}' must have mass: 0.0")

        # Check if force targets exist
        for i, force in enumerate(dsl.get("forces", [])):
            if force["target"] not in object_ids:
                semantic_errors.append(f"Force[{i}] ('{force['id']}') targets unknown object '{force['target']}'")

        # Check if constraints targets exist
        for i, constraint in enumerate(dsl.get("constraints", [])):
            if constraint.get("bodyA") and constraint["bodyA"] not in object_ids:
                semantic_errors.append(f"Constraint[{i}] ('{constraint['id']}') bodyA targets unknown object '{constraint['bodyA']}'")
            if constraint.get("bodyB") and constraint["bodyB"] not in object_ids:
                semantic_errors.append(f"Constraint[{i}] ('{constraint['id']}') bodyB targets unknown object '{constraint['bodyB']}'")

        # Check if behavior targets exist
        for i, behavior in enumerate(dsl.get("behaviors", [])):
            for target in behavior.get("targets", []):
                if target not in object_ids:
                    semantic_errors.append(f"Behavior[{i}] ('{behavior['id']}') targets unknown object '{target}'")

        # Check if interaction targets exist
        for i, interaction in enumerate(dsl.get("interactions", [])):
            for target in interaction.get("targets", []):
                if target not in object_ids:
                    semantic_errors.append(f"Interaction[{i}] ('{interaction['id']}') targets unknown object '{target}'")

        # Check if event targets exist
        for i, event in enumerate(dsl.get("events", [])):
            for target in event.get("targets", []):
                if target not in object_ids:
                    semantic_errors.append(f"Event[{i}] ('{event['id']}') targets unknown object '{target}'")

        # Pass 4: SI Unit and Normalization Sanity Check
        env = dsl.get("environment", {})
        gravity = env.get("gravity", {})
        if abs(gravity.get("y", 0)) > 20.0: # Relaxed slightly for v2.0
            semantic_errors.append(f"Gravity Y ({gravity.get('y')}) seems too high. Please use scaled values.")

        for i, obj in enumerate(dsl.get("objects", [])):
            pos = obj.get("position", {})
            if abs(pos.get("x", 0)) > 1000 or abs(pos.get("y", 0)) > 1000:
                semantic_errors.append(f"Object[{i}] ('{obj['id']}') position seems to use pixels. Please use SI meters.")

        if semantic_errors:
            return {
                "success": False,
                "data": None,
                "errors": "; ".join(semantic_errors)
            }

        return {
            "success": True,
            "data": validated_dict,
            "errors": None
        }

    except Exception as e:
        return {
            "success": False,
            "data": None,
            "errors": str(e)
        }