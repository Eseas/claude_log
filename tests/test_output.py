"""Tests for OutputWriter (user-facing terminal output)."""

import io
import sys

from claude_log_organizer.output import OutputWriter


class TestOutputWriterPrint:
    def test_print_to_configured_stream(self):
        buf = io.StringIO()
        ow = OutputWriter(stream=buf)
        ow.print("hello")
        assert buf.getvalue() == "hello\n"

    def test_print_is_drop_in_for_builtin(self):
        buf = io.StringIO()
        ow = OutputWriter(stream=buf)
        ow.print("a", "b", sep="-", end="!")
        assert buf.getvalue() == "a-b!"

    def test_print_multiline(self):
        buf = io.StringIO()
        ow = OutputWriter(stream=buf)
        ow.print("\n" + "=" * 5)
        assert buf.getvalue() == "\n=====\n"

    def test_stderr_routes_to_err_stream(self):
        out_buf, err_buf = io.StringIO(), io.StringIO()
        ow = OutputWriter(stream=out_buf, err_stream=err_buf)
        ow.print("oops", file=sys.stderr)
        assert err_buf.getvalue() == "oops\n"
        assert out_buf.getvalue() == ""


class TestOutputWriterSemanticHelpers:
    def test_blank(self):
        buf = io.StringIO()
        OutputWriter(stream=buf).blank()
        assert buf.getvalue() == "\n"

    def test_success_prefix(self):
        buf = io.StringIO()
        OutputWriter(stream=buf).success("done")
        assert buf.getvalue() == "✓ done\n"

    def test_error_goes_to_err_stream(self):
        out_buf, err_buf = io.StringIO(), io.StringIO()
        OutputWriter(stream=out_buf, err_stream=err_buf).error("bad")
        assert "❌ bad" in err_buf.getvalue()
        assert out_buf.getvalue() == ""

    def test_warning_prefix(self):
        buf = io.StringIO()
        OutputWriter(stream=buf).warning("careful")
        assert "careful" in buf.getvalue()
        assert "⚠" in buf.getvalue()


class TestRichStructuredOutput:
    def test_table_renders_columns_and_rows(self):
        buf = io.StringIO()
        ow = OutputWriter(stream=buf)
        ow.table(["Session", "Tokens"], [["abc123", "5,700"]], title="Usage")
        result = buf.getvalue()
        assert "Session" in result
        assert "abc123" in result
        assert "5,700" in result

    def test_panel_includes_content(self):
        buf = io.StringIO()
        ow = OutputWriter(stream=buf)
        ow.panel("important message", title="Note")
        assert "important message" in buf.getvalue()

    def test_rule_emits_something(self):
        buf = io.StringIO()
        ow = OutputWriter(stream=buf)
        ow.rule("Section")
        assert buf.getvalue().strip() != ""

    def test_markdown_renders_heading_text(self):
        buf = io.StringIO()
        ow = OutputWriter(stream=buf)
        ow.markdown("# Title\n\nsome body text")
        result = buf.getvalue()
        assert "Title" in result
        assert "some body text" in result


class TestSetStreams:
    def test_set_streams_redirects(self):
        ow = OutputWriter()
        buf = io.StringIO()
        ow.set_streams(buf)
        ow.print("redirected")
        assert buf.getvalue() == "redirected\n"

    def test_shared_instance_capture(self):
        # Simulates how tests can capture the shared module-level `out`.
        from claude_log_organizer import output
        original = output.out._stream
        buf = io.StringIO()
        try:
            output.out.set_streams(buf)
            output.out.print("captured")
            assert buf.getvalue() == "captured\n"
        finally:
            output.out.set_streams(original)
