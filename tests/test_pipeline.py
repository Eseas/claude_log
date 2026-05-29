"""Tests for the processing pipeline (base machinery + default steps)."""

from pathlib import Path

import pytest
import yaml

from claude_log_organizer.config import Config
from claude_log_organizer.parsers.parser_factory import ParserFactory
from claude_log_organizer.generators.markdown_generator import MarkdownGenerator
from claude_log_organizer.storage.processed_tracker import ProcessedTracker
from claude_log_organizer.pipeline import (
    Pipeline,
    PipelineContext,
    PipelineStep,
    build_default_pipeline,
)
from claude_log_organizer.pipeline.steps import extract_task_id, get_output_path

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


# --- Test doubles ---

class RecordingStep(PipelineStep):
    def __init__(self, name, log):
        self.name = name
        self._log = log

    def execute(self, ctx):
        self._log.append(self.name)


class HaltingStep(PipelineStep):
    name = "halter"

    def execute(self, ctx):
        ctx.halt()


def _ctx(file_path=Path("x.log")):
    return PipelineContext(file_path, config=None, parser_factory=None,
                           generator=None, tracker=None)


class TestPipelineMachinery:
    def test_runs_steps_in_order(self):
        log = []
        pipe = Pipeline([RecordingStep("a", log), RecordingStep("b", log)])
        pipe.execute(_ctx())
        assert log == ["a", "b"]

    def test_add_step_chains(self):
        log = []
        pipe = Pipeline().add_step(RecordingStep("a", log)).add_step(RecordingStep("b", log))
        pipe.execute(_ctx())
        assert log == ["a", "b"]

    def test_halt_stops_remaining_steps(self):
        log = []
        pipe = Pipeline([RecordingStep("a", log), HaltingStep(), RecordingStep("c", log)])
        pipe.execute(_ctx())
        assert log == ["a"]  # "c" never runs

    def test_should_run_gate(self):
        log = []

        class Skipped(RecordingStep):
            def should_run(self, ctx):
                return False

        pipe = Pipeline([Skipped("skip", log), RecordingStep("run", log)])
        pipe.execute(_ctx())
        assert log == ["run"]

    def test_execute_returns_context(self):
        ctx = _ctx()
        assert Pipeline([]).execute(ctx) is ctx


class TestHelpers:
    def test_extract_task_id_conversation(self):
        assert extract_task_id(Path("conversation-task-20260212-130624.log")) == "20260212-130624"

    def test_extract_task_id_task_pattern(self):
        assert extract_task_id(Path("task-abc.def.log")) == "abc"

    def test_extract_task_id_fallback_stem(self):
        assert extract_task_id(Path("randomname.log")) == "randomname"

    def test_get_output_path_with_project(self):
        cfg = Config(None)
        path = get_output_path(cfg, "abc", project_path="/proj")
        assert path == Path("/proj/tasks/task-abc.md")

    def test_get_output_path_uses_config_dir(self):
        cfg = Config(None)
        path = get_output_path(cfg, "abc")
        assert path == Path("./tasks/task-abc.md")


class TestDefaultPipeline:
    def test_default_step_order(self):
        names = [s.name for s in build_default_pipeline().steps]
        assert names == ["validate", "dedup", "task-id", "parse",
                         "output-path", "generate", "track"]


def _make_deps(tmp_path):
    """Build real config/factory/generator/tracker writing into tmp_path."""
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump({"output": {"directory": str(tmp_path / "out")}}),
                        encoding="utf-8")
    config = Config(cfg_file)
    return (
        config,
        ParserFactory(),
        MarkdownGenerator(TEMPLATE_DIR, config),
        ProcessedTracker(tmp_path / ".processed.json"),
    )


def _session_log(session_id="deadbeef-1234"):
    # No Project-Root-Path header → output goes to config output.directory.
    return (
        "=== Claude Code Session Log ===\n"
        f"Session ID: {session_id}\n\n"
        "[USER]\nmain.py 파일을 수정해줘\n\n"
        "[ASSISTANT]\n수정했습니다 완료\n\n"
        "[TOOL] Edit → /proj/main.py\n\n"
    )


class TestDefaultPipelineEndToEnd:
    def test_full_run_generates_and_tracks(self, tmp_path):
        config, factory, generator, tracker = _make_deps(tmp_path)
        log_file = tmp_path / "2026-05-28_143000_deadbeef-1234.log"
        log_file.write_text(_session_log(), encoding="utf-8")

        ctx = PipelineContext(log_file, config, factory, generator, tracker)
        build_default_pipeline().execute(ctx)

        assert ctx.task_data is not None
        assert ctx.output_path.exists()
        assert tracker.is_processed(log_file)

    def test_dedup_halts_second_run(self, tmp_path):
        config, factory, generator, tracker = _make_deps(tmp_path)
        log_file = tmp_path / "2026-05-28_143000_deadbeef-1234.log"
        log_file.write_text(_session_log(), encoding="utf-8")

        build_default_pipeline().execute(
            PipelineContext(log_file, config, factory, generator, tracker))

        # Second run: dedup step should halt before parsing
        ctx2 = PipelineContext(log_file, config, factory, generator, tracker)
        build_default_pipeline().execute(ctx2)
        assert ctx2.halted
        assert ctx2.task_data is None  # never parsed

    def test_too_small_file_halts(self, tmp_path):
        config, factory, generator, tracker = _make_deps(tmp_path)
        tiny = tmp_path / "2026-05-28_143000_deadbeef-1234.log"
        tiny.write_text("x", encoding="utf-8")  # < 10 bytes
        ctx = PipelineContext(tiny, config, factory, generator, tracker)
        build_default_pipeline().execute(ctx)
        assert ctx.halted
        assert ctx.task_data is None

    def test_output_exists_no_overwrite_marks_processed(self, tmp_path):
        config, factory, generator, tracker = _make_deps(tmp_path)
        log_file = tmp_path / "2026-05-28_143000_deadbeef-1234.log"
        log_file.write_text(_session_log(), encoding="utf-8")

        # First run creates the output
        build_default_pipeline().execute(
            PipelineContext(log_file, config, factory, generator, tracker))
        # Reset tracker so dedup doesn't short-circuit; output file still exists
        tracker.clear()

        ctx = PipelineContext(log_file, config, factory, generator, tracker)
        build_default_pipeline().execute(ctx)
        # overwrite disabled → halted at output-path AND marked processed
        assert ctx.halted
        assert tracker.is_processed(log_file)
