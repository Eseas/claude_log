"""Concrete pipeline steps for the .log → markdown flow.

Each step mirrors one slice of the original procedural `_process_new_file`,
preserving its behavior exactly (including which conditions mark a file as
processed). Helper functions for task-id extraction, validation, and output
path resolution live here too.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from claude_log_organizer.pipeline.base import (
    InvalidFileFormatError,
    Pipeline,
    PipelineContext,
    PipelineStep,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MIN_FILE_SIZE = 10  # bytes


def extract_task_id(file_path: Path) -> Optional[str]:
    """Extract a task ID from a log filename (None if it can't be derived)."""
    match = re.search(r"conversation-task-(.+?)\.log", file_path.name)
    if match:
        return match.group(1)
    match = re.search(r"task-(.+?)[-.]", file_path.name)
    if match:
        return match.group(1)
    return file_path.stem


def get_output_path(config, task_id: str, project_path: Optional[str] = None) -> Path:
    """Resolve the markdown output path for a task."""
    if project_path:
        output_dir = Path(project_path) / "tasks"
    else:
        output_dir = Path(config.get("output.directory", "./tasks"))
    filename_pattern = config.get("output.filename_pattern", "task-{task_id}.md")
    return output_dir / filename_pattern.format(task_id=task_id)


class FileValidationStep(PipelineStep):
    """Validate existence, type, and size bounds before any work."""

    name = "validate"

    def execute(self, ctx: PipelineContext) -> None:
        path = ctx.file_path
        if not path.exists():
            raise InvalidFileFormatError(f"File does not exist: {path}")
        if not path.is_file():
            raise InvalidFileFormatError(f"Not a regular file: {path}")

        size = path.stat().st_size
        if size < MIN_FILE_SIZE:
            logger.warning(f"File too small: {path}")
            ctx.halt()
            return
        if size > MAX_FILE_SIZE:
            logger.warning(f"File too large: {path}")
            ctx.halt()


class DeduplicationStep(PipelineStep):
    """Skip files whose content hash is already recorded as processed."""

    name = "dedup"

    def execute(self, ctx: PipelineContext) -> None:
        if ctx.tracker.is_processed(ctx.file_path):
            logger.info(f"File already processed: {ctx.file_path}")
            ctx.halt()


class TaskIdStep(PipelineStep):
    """Derive the task ID; halt if it cannot be determined."""

    name = "task-id"

    def execute(self, ctx: PipelineContext) -> None:
        task_id = extract_task_id(ctx.file_path)
        if not task_id:
            logger.error(f"Could not extract task ID from: {ctx.file_path}")
            ctx.halt()
            return
        ctx.task_id = task_id


class ParseStep(PipelineStep):
    """Select a parser and parse the log into a TaskData object."""

    name = "parse"

    def execute(self, ctx: PipelineContext) -> None:
        try:
            parser = ctx.parser_factory.get_parser(ctx.file_path)
        except ValueError as e:
            logger.error(f"No parser available: {e}")
            ctx.halt()
            return

        logger.info(f"Parsing: {ctx.file_path}")
        ctx.task_data = parser.parse(ctx.file_path)


class OutputPathStep(PipelineStep):
    """Resolve the output path; honor the overwrite setting."""

    name = "output-path"

    def execute(self, ctx: PipelineContext) -> None:
        project_path = ctx.task_data.metadata.get("project_path")
        ctx.output_path = get_output_path(ctx.config, ctx.task_id, project_path=project_path)

        if ctx.output_path.exists() and not ctx.config.get("output.overwrite", False):
            logger.warning(
                f"Output file already exists (overwrite disabled): {ctx.output_path}"
            )
            # Still mark as processed to avoid repeated warnings.
            ctx.tracker.mark_processed(ctx.file_path)
            ctx.halt()


class MarkdownGenerationStep(PipelineStep):
    """Render the markdown output file from TaskData."""

    name = "generate"

    def execute(self, ctx: PipelineContext) -> None:
        ctx.generator.generate(ctx.task_data, ctx.output_path)


class TrackingStep(PipelineStep):
    """Record the file as processed after a successful run."""

    name = "track"

    def execute(self, ctx: PipelineContext) -> None:
        ctx.tracker.mark_processed(ctx.file_path)
        logger.info(f"✓ Generated: {ctx.output_path}")


def build_default_pipeline() -> Pipeline:
    """Construct the standard .log → markdown pipeline."""
    return Pipeline([
        FileValidationStep(),
        DeduplicationStep(),
        TaskIdStep(),
        ParseStep(),
        OutputPathStep(),
        MarkdownGenerationStep(),
        TrackingStep(),
    ])
