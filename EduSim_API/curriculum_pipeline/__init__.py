# EduSim Curriculum Pipeline
# Use lazy imports to avoid runpy circular-import warnings.
# Programmatic use:
#   from curriculum_pipeline.scan_textbooks import scan

__all__ = ["scan"]


def __getattr__(name: str):
    if name == "scan":
        from curriculum_pipeline.scan_textbooks import scan
        return scan
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

