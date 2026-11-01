"""
sandbox_initializer.py
=======================
Main Initialization Orchestrator for the EduSim Backend.
...
"""


from __future__ import annotations
import logging
logger = logging.getLogger("EduSim.sandbox.initializer")

import traceback
from typing import Any, Dict, Callable

from app.src.modules.sandbox.schemas.sandbox_schema import SandboxSchema
from app.src.modules.sandbox.initialization.pipeline import InitializationPipeline
from app.src.modules.sandbox.initialization.runtime_builder import RuntimeBuilder


class SandboxInitializer:
    """
    Coordinator class exposing orchestration hooks and pipeline execution.
    Allows injecting custom pre-processing or post-processing hooks.
    """
    def __init__(self) -> None:
        self.pipeline = InitializationPipeline()
        self._pre_hooks: list[Callable[[Dict[str, Any]], Dict[str, Any]]] = []
        self._post_hooks: list[Callable[[SandboxSchema], SandboxSchema]] = []

    def register_pre_hook(self, hook: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Registers a function to inspect or alter raw payloads before compilation starts."""
        self._pre_hooks.append(hook)

    def register_post_hook(self, hook: Callable[[SandboxSchema], SandboxSchema]) -> None:
        """Registers a function to process or enrich the hydrated SandboxSchema before serialization."""
        self._post_hooks.append(hook)

    def initialize_sandbox(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main orchestration entry point.
        Processes untrusted raw input, compiles the simulation contract, 
        and outputs a finalized frontend payload.
        """
        # 1. Run pre-hooks
        payload = dict(raw_payload)
        for hook in self._pre_hooks:
            try:
                payload = hook(payload)
            except Exception as e:
                logger.info(f"Pre-hook failure: {e}")

        # 2. Run initialization pipeline
        sandbox = self.pipeline.execute(payload)

        # 3. Run post-hooks
        for hook in self._post_hooks:
            try:
                sandbox = hook(sandbox)
            except Exception as e:
                logger.info(f"Post-hook failure: {e}")

        # 4. Serialize to final Matter.js / PixiJS contract format
        runtime_payload = RuntimeBuilder.build_runtime_payload(sandbox)
        return runtime_payload


# Central orchestrator singleton instance for simple system-wide imports
initializer = SandboxInitializer()


def initialize_sandbox(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenient wrapper function for the global initializer singleton.
    Converts raw specs into production-ready frontend contracts.
    """
    try:
        return initializer.initialize_sandbox(raw_payload)
    except Exception as e:
        # Wrap in standardized initialization errors for tutor and API layers
        error_msg = f"Failed to compile sandbox scenario: {e}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        raise ValueError(error_msg) from e
