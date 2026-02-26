"""Pattern database for efficient prompts."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class PatternDB:
    """Database for storing and retrieving prompt patterns."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize pattern database.

        Args:
            db_path: Path to database file (default: patterns/patterns.jsonl)
        """
        if db_path is None:
            db_path = Path(__file__).parent / "patterns.jsonl"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def add_pattern(
        self,
        pattern_type: str,
        original_prompt: str,
        optimized_prompt: str,
        rounds: int,
        success: bool,
        metadata: Optional[Dict] = None
    ):
        """Add a pattern to the database.

        Args:
            pattern_type: Type of pattern (bug_fix, feature_add, etc.)
            original_prompt: Original user prompt
            optimized_prompt: Optimized version
            rounds: Number of conversation rounds
            success: Whether it succeeded
            metadata: Additional metadata
        """
        pattern = {
            "timestamp": datetime.now().isoformat(),
            "type": pattern_type,
            "original": original_prompt,
            "optimized": optimized_prompt,
            "rounds": rounds,
            "success": success,
            "original_tokens": len(original_prompt.split()),
            "optimized_tokens": len(optimized_prompt.split()),
            "metadata": metadata or {}
        }

        # Append to JSONL file
        with open(self.db_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(pattern, ensure_ascii=False) + '\n')

    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_rounds: Optional[int] = None,
        max_rounds: Optional[int] = None,
        success_only: bool = False
    ) -> List[Dict]:
        """Retrieve patterns from database.

        Args:
            pattern_type: Filter by pattern type
            min_rounds: Minimum number of rounds
            max_rounds: Maximum number of rounds
            success_only: Only return successful patterns

        Returns:
            List of matching patterns
        """
        if not self.db_path.exists():
            return []

        patterns = []
        with open(self.db_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                pattern = json.loads(line)

                # Apply filters
                if pattern_type and pattern.get("type") != pattern_type:
                    continue
                if min_rounds and pattern.get("rounds", 0) < min_rounds:
                    continue
                if max_rounds and pattern.get("rounds", 0) > max_rounds:
                    continue
                if success_only and not pattern.get("success"):
                    continue

                patterns.append(pattern)

        return patterns

    def get_efficient_patterns(self, pattern_type: Optional[str] = None) -> List[Dict]:
        """Get efficient patterns (1-2 rounds, successful).

        Args:
            pattern_type: Filter by pattern type

        Returns:
            List of efficient patterns
        """
        return self.get_patterns(
            pattern_type=pattern_type,
            max_rounds=2,
            success_only=True
        )

    def get_inefficient_patterns(self, pattern_type: Optional[str] = None) -> List[Dict]:
        """Get inefficient patterns (4+ rounds).

        Args:
            pattern_type: Filter by pattern type

        Returns:
            List of inefficient patterns
        """
        return self.get_patterns(
            pattern_type=pattern_type,
            min_rounds=4
        )

    def get_statistics(self) -> Dict:
        """Get database statistics.

        Returns:
            Statistics dictionary
        """
        patterns = self.get_patterns()

        if not patterns:
            return {
                "total": 0,
                "by_type": {},
                "avg_rounds": 0,
                "success_rate": 0,
                "avg_token_reduction": 0
            }

        by_type = {}
        total_rounds = 0
        successful = 0
        total_reduction = 0

        for pattern in patterns:
            p_type = pattern.get("type", "unknown")
            by_type[p_type] = by_type.get(p_type, 0) + 1

            total_rounds += pattern.get("rounds", 0)
            if pattern.get("success"):
                successful += 1

            original = pattern.get("original_tokens", 0)
            optimized = pattern.get("optimized_tokens", 0)
            if original > 0:
                reduction = ((original - optimized) / original) * 100
                total_reduction += reduction

        return {
            "total": len(patterns),
            "by_type": by_type,
            "avg_rounds": total_rounds / len(patterns),
            "success_rate": (successful / len(patterns)) * 100,
            "avg_token_reduction": total_reduction / len(patterns) if patterns else 0
        }
