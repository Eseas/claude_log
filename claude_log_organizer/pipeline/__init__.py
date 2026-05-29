"""Extensible processing pipeline: .log file → parsed → markdown.

Replaces the procedural `_process_new_file` flow with a sequence of named,
testable PipelineStep objects. Steps can be added/reordered without editing
the core flow, enabling optional stages (analysis, notifications) as plugins.
"""

from claude_log_organizer.pipeline.base import Pipeline, PipelineContext, PipelineStep
from claude_log_organizer.pipeline.steps import build_default_pipeline

__all__ = [
    "Pipeline",
    "PipelineContext",
    "PipelineStep",
    "build_default_pipeline",
]
