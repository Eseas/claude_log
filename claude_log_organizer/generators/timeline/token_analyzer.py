"""Token usage analysis — identify high-usage sessions and suggest reductions."""

from typing import List

from claude_log_organizer.models.task_data import TimelineEntry


def analyze_token_usage(entries: List[TimelineEntry]) -> List[str]:
    """Analyze token usage patterns, identify high-usage sessions, and suggest reductions.

    Returns list of markdown lines for the analysis section.
    """
    # Filter entries with token data
    with_tokens = [e for e in entries if e.token_usage and e.token_usage.total_tokens > 0]
    if len(with_tokens) < 2:
        return []

    totals = [e.token_usage.total_tokens for e in with_tokens]
    avg_tokens = sum(totals) / len(totals)
    threshold = avg_tokens * 1.5

    # Identify high-usage sessions
    high_usage = [e for e in with_tokens if e.token_usage.total_tokens >= threshold]
    if not high_usage:
        return []

    high_usage.sort(key=lambda e: e.token_usage.total_tokens, reverse=True)

    lines = [
        "## Token Usage Analysis",
        "",
    ]

    # High usage table
    lines.append("### High Usage Sessions")
    lines.append(f"> 평균 토큰: {avg_tokens:,.0f} / 기준 (1.5x): {threshold:,.0f}")
    lines.append("")
    lines.append("| Session | Task | Total Tokens | Requests | Tokens/Req | Factors |")
    lines.append("|---------|------|-------------|----------|------------|---------|")

    for entry in high_usage:
        tu = entry.token_usage
        tpr = tu.total_tokens // tu.request_count if tu.request_count else 0
        factors = _identify_factors(entry)
        factor_str = ", ".join(factors) if factors else "-"
        label = entry.label[:40] + "..." if len(entry.label) > 40 else entry.label
        lines.append(
            f"| `{entry.session_short}` | {label} "
            f"| {tu.total_tokens:,} | {tu.request_count} | {tpr:,} | {factor_str} |"
        )

    lines.append("")

    # Per-session analysis
    lines.append("### Analysis")
    lines.append("")

    for entry in high_usage:
        tu = entry.token_usage
        label = entry.label[:50] + "..." if len(entry.label) > 50 else entry.label
        lines.append(f"#### `{entry.session_short}` - {label}")
        lines.append("")

        # Causes
        factors = _identify_factors(entry)
        if factors:
            lines.append(f"- **주요 원인**: {', '.join(factors)}")

        # Cache efficiency
        input_side = tu.input_tokens + tu.cache_read_tokens + tu.cache_write_tokens
        if input_side > 0:
            cache_eff = (tu.cache_read_tokens / input_side) * 100
            avg_cache_eff = _avg_cache_efficiency(with_tokens)
            quality = "양호" if cache_eff >= avg_cache_eff else "평균 대비 낮음"
            lines.append(f"- **캐시 효율**: {cache_eff:.0f}% ({quality})")

        # Output ratio
        if tu.total_tokens > 0:
            output_ratio = (tu.output_tokens / tu.total_tokens) * 100
            lines.append(f"- **출력 비율**: {output_ratio:.0f}%")

        lines.append("")

    # Reduction strategies
    strategies = _suggest_strategies(high_usage, with_tokens)
    if strategies:
        lines.append("### Reduction Strategies")
        lines.append("")
        for i, strategy in enumerate(strategies, 1):
            lines.append(f"{i}. {strategy}")
        lines.append("")

    return lines


def _identify_factors(entry: TimelineEntry) -> List[str]:
    """Identify factors that may explain high token usage."""
    factors = []
    if entry.compact_count > 0:
        factors.append(f"compact x{entry.compact_count}")
    if entry.tool_use_count > 15:
        factors.append(f"도구 {entry.tool_use_count}회")
    if entry.thinking_count > 10:
        factors.append(f"thinking {entry.thinking_count}블록")
    if entry.assistant_response_count > 20:
        factors.append(f"응답 {entry.assistant_response_count}회")
    if entry.token_usage and entry.token_usage.request_count > 0:
        tpr = entry.token_usage.total_tokens // entry.token_usage.request_count
        if tpr > 5000:
            factors.append(f"요청당 {tpr:,} tokens")
    return factors


def _avg_cache_efficiency(entries: List[TimelineEntry]) -> float:
    """Calculate average cache efficiency across entries."""
    effs = []
    for e in entries:
        tu = e.token_usage
        input_side = tu.input_tokens + tu.cache_read_tokens + tu.cache_write_tokens
        if input_side > 0:
            effs.append((tu.cache_read_tokens / input_side) * 100)
    return sum(effs) / len(effs) if effs else 0


def _suggest_strategies(
    high_usage: List[TimelineEntry],
    all_entries: List[TimelineEntry],
) -> List[str]:
    """Generate reduction strategies based on patterns found in high-usage sessions."""
    strategies = []

    compact_sessions = [e for e in high_usage if e.compact_count > 0]
    if compact_sessions:
        strategies.append(
            f"대화가 길어지기 전에 새 세션을 시작하세요"
            f" — 컨텍스트 압축이 발생한 세션이 {len(compact_sessions)}개 있습니다"
        )

    heavy_tool = [e for e in high_usage if e.tool_use_count > 15]
    if heavy_tool:
        strategies.append(
            f"구체적인 지시로 불필요한 탐색을 줄이세요"
            f" — 도구 호출이 15회 이상인 세션이 {len(heavy_tool)}개 있습니다"
        )

    heavy_thinking = [e for e in high_usage if e.thinking_count > 10]
    if heavy_thinking:
        strategies.append(
            f"단순 작업에는 thinking 제한을 고려하세요"
            f" — thinking 블록이 10개 이상인 세션이 {len(heavy_thinking)}개 있습니다"
        )

    low_cache = []
    avg_eff = _avg_cache_efficiency(all_entries)
    for e in high_usage:
        tu = e.token_usage
        input_side = tu.input_tokens + tu.cache_read_tokens + tu.cache_write_tokens
        if input_side > 0:
            eff = (tu.cache_read_tokens / input_side) * 100
            if eff < avg_eff * 0.7:
                low_cache.append(e)
    if low_cache:
        strategies.append(
            f"동일 세션 내에서 대화를 이어가 캐시 활용도를 높이세요"
            f" — 캐시 효율이 낮은 세션이 {len(low_cache)}개 있습니다"
        )

    verbose = []
    for e in high_usage:
        tu = e.token_usage
        if tu.total_tokens > 0 and (tu.output_tokens / tu.total_tokens) > 0.25:
            verbose.append(e)
    if verbose:
        strategies.append(
            f"간결한 응답을 요청하세요"
            f" — 출력 비율이 25% 이상인 세션이 {len(verbose)}개 있습니다"
        )

    high_tpr = []
    for e in high_usage:
        tu = e.token_usage
        if tu.request_count > 0 and tu.total_tokens // tu.request_count > 5000:
            high_tpr.append(e)
    if high_tpr:
        strategies.append(
            f"작업을 더 작은 단위로 분할하세요"
            f" — 요청당 5,000+ 토큰을 사용하는 세션이 {len(high_tpr)}개 있습니다"
        )

    return strategies
