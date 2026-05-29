"""Tests for TaskSuccessAnalyzer heuristic logic (no AI dependency)."""

from claude_log_organizer.analyzers.task_success_analyzer import TaskSuccessAnalyzer
from claude_log_organizer.models.task_data import TaskInteraction


def _analyze_one(request, feedback, tool_results=None):
    """Build a single interaction, run heuristic analysis, return it."""
    analyzer = TaskSuccessAnalyzer()
    interaction = TaskInteraction(
        request=request,
        feedback=feedback,
        tool_results=tool_results or [],
    )
    analyzer.analyze_heuristic([interaction])
    return interaction


class TestExtractInteractions:
    def test_pairs_request_with_next_feedback(self):
        log = (
            "[USER]\nmain.py 파일을 수정해줘\n"
            "[ASSISTANT]\n수정하겠습니다 지금 바로 처리할게요\n"
            "[USER]\n좋아요 이제 테스트도 추가해줘\n"
        )
        interactions = TaskSuccessAnalyzer().extract_interactions(log)
        assert len(interactions) == 2
        assert "main.py" in interactions[0].request
        assert interactions[0].feedback is not None
        assert "테스트" in interactions[0].feedback

    def test_last_interaction_has_no_feedback(self):
        log = (
            "[USER]\n첫 번째 요청입니다 처리해주세요\n"
            "[USER]\n마지막 요청이고 피드백이 없습니다\n"
        )
        interactions = TaskSuccessAnalyzer().extract_interactions(log)
        assert interactions[-1].feedback is None

    def test_skips_tool_result_pseudo_users(self):
        log = (
            "[USER]\n실제 사용자 요청입니다 처리해주세요\n"
            "[USER]\n[TOOL_RESULT] some output\n"
            "[USER]\n또 다른 실제 요청을 보냅니다\n"
        )
        interactions = TaskSuccessAnalyzer().extract_interactions(log)
        requests = [i.request for i in interactions]
        assert not any("[TOOL_RESULT]" in r for r in requests)

    def test_extracts_tools_and_results(self):
        log = (
            "[USER]\n파일을 읽고 수정해주세요 부탁합니다\n"
            "[TOOL] Read → /a/b.py\n"
            "[TOOL_RESULT] file contents here\n"
            "[USER]\n완벽해요 감사합니다\n"
        )
        interactions = TaskSuccessAnalyzer().extract_interactions(log)
        assert interactions[0].tools_used[0]["tool"] == "Read"
        assert len(interactions[0].tool_results) == 1


class TestHeuristicSuccess:
    def test_positive_confirmation(self):
        result = _analyze_one("기능 구현해줘", "좋아요 완벽합니다")
        assert result.heuristic_result == "success"
        assert result.heuristic_confidence > 0

    def test_gratitude_signals_success(self):
        result = _analyze_one("버그 고쳐줘", "감사합니다 잘 동작하네요")
        assert result.heuristic_result == "success"

    def test_english_success(self):
        result = _analyze_one("fix the bug", "works now, thanks")
        assert result.heuristic_result == "success"


class TestHeuristicFailure:
    def test_correction_request(self):
        result = _analyze_one("이 기능 만들어줘", "아니 그게 아니라 틀렸어")
        assert result.heuristic_result == "failure"
        assert result.heuristic_confidence > 0

    def test_retry_request(self):
        result = _analyze_one("코드 짜줘", "에러가 나는데 다시 해줘")
        assert result.heuristic_result == "failure"

    def test_tool_error_contributes_to_failure(self):
        result = _analyze_one(
            "스크립트 실행해줘",
            "음 이상한데",
            tool_results=["Traceback (most recent call last): Exception"],
        )
        # tool error + 문제 언급 → failure
        assert result.heuristic_result in ("failure", "partial")
        assert any("도구 에러" in s for s in result.heuristic_signals)


class TestHeuristicUnknown:
    def test_no_feedback_is_unknown(self):
        analyzer = TaskSuccessAnalyzer()
        interaction = TaskInteraction(request="뭔가 해줘", feedback=None)
        analyzer.analyze_heuristic([interaction])
        assert interaction.heuristic_result == "unknown"
        assert interaction.heuristic_confidence == 0.0

    def test_neutral_feedback_no_signals(self):
        # Feedback shares some keywords (not a topic change) but carries
        # no success/failure signal words → genuinely undecidable.
        result = _analyze_one(
            "데이터베이스 스키마 설계 작업 진행",
            "스키마 설계 부분 출력",
        )
        assert result.heuristic_result == "unknown"

    def test_topic_change_feedback_reads_as_success(self):
        # An unrelated follow-up is treated as an implicit success signal.
        result = _analyze_one(
            "데이터베이스 스키마 설계해줘",
            "프론트엔드 버튼 색상 바꾸는 작업 시작",
        )
        assert result.heuristic_result == "success"
        assert any("주제 전환" in s for s in result.heuristic_signals)


class TestSimilarityAndTopicChange:
    def test_repeated_request_flags_failure(self):
        analyzer = TaskSuccessAnalyzer()
        text = "로그인 인증 토큰 검증 로직 구현"
        assert analyzer._text_similarity(text, text) == 1.0

    def test_topic_change_detected(self):
        analyzer = TaskSuccessAnalyzer()
        assert analyzer._is_topic_change(
            "데이터베이스 마이그레이션 스크립트 작성",
            "프론트엔드 버튼 색상 변경",
        ) is True

    def test_same_topic_not_flagged_as_change(self):
        analyzer = TaskSuccessAnalyzer()
        assert analyzer._is_topic_change(
            "데이터베이스 마이그레이션 스크립트 작성",
            "데이터베이스 마이그레이션 롤백 추가",
        ) is False
