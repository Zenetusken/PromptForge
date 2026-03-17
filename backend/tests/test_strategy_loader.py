
import pytest

from app.services.strategy_loader import StrategyLoader


@pytest.fixture
def tmp_strategies(tmp_path):
    strat_dir = tmp_path / "strategies"
    strat_dir.mkdir()
    (strat_dir / "chain-of-thought.md").write_text(
        "---\ntagline: reasoning\ndescription: Step-by-step reasoning.\n---\n"
        "# Chain of Thought\nThink step by step."
    )
    (strat_dir / "few-shot.md").write_text(
        "---\ntagline: examples\ndescription: Example-driven.\n---\n"
        "# Few-Shot\nProvide examples."
    )
    (strat_dir / "auto.md").write_text(
        "---\ntagline: adaptive\ndescription: Best approach.\n---\n"
        "# Auto\nSelect the best approach."
    )
    return strat_dir


class TestStrategyLoader:
    def test_list_strategies(self, tmp_strategies):
        loader = StrategyLoader(tmp_strategies)
        strategies = loader.list_strategies()
        assert "chain-of-thought" in strategies
        assert "few-shot" in strategies
        assert "auto" in strategies

    def test_load_strategy(self, tmp_strategies):
        loader = StrategyLoader(tmp_strategies)
        content = loader.load("chain-of-thought")
        assert "Think step by step" in content

    def test_load_strips_frontmatter(self, tmp_strategies):
        loader = StrategyLoader(tmp_strategies)
        content = loader.load("chain-of-thought")
        assert "tagline:" not in content
        assert "---" not in content

    def test_load_unknown_returns_fallback(self, tmp_strategies):
        """Unknown strategy returns graceful fallback instead of crashing."""
        loader = StrategyLoader(tmp_strategies)
        content = loader.load("nonexistent")
        assert "No specific strategy" in content

    def test_load_metadata(self, tmp_strategies):
        loader = StrategyLoader(tmp_strategies)
        meta = loader.load_metadata("chain-of-thought")
        assert meta["name"] == "chain-of-thought"
        assert meta["tagline"] == "reasoning"
        assert meta["description"] == "Step-by-step reasoning."

    def test_list_with_metadata(self, tmp_strategies):
        loader = StrategyLoader(tmp_strategies)
        all_meta = loader.list_with_metadata()
        assert len(all_meta) == 3
        names = {m["name"] for m in all_meta}
        assert "chain-of-thought" in names
        assert "auto" in names

    def test_format_available_strategies(self, tmp_strategies):
        loader = StrategyLoader(tmp_strategies)
        formatted = loader.format_available()
        assert "chain-of-thought (reasoning)" in formatted
        assert "few-shot (examples)" in formatted

    def test_empty_directory(self, tmp_path):
        strat_dir = tmp_path / "strategies"
        strat_dir.mkdir()
        loader = StrategyLoader(strat_dir)
        assert loader.list_strategies() == []

    def test_empty_directory_load_returns_fallback(self, tmp_path):
        """When no strategy files exist, load() returns fallback."""
        strat_dir = tmp_path / "strategies"
        strat_dir.mkdir()
        loader = StrategyLoader(strat_dir)
        content = loader.load("auto")
        assert "No specific strategy" in content

    def test_validate_passes(self, tmp_strategies):
        loader = StrategyLoader(tmp_strategies)
        loader.validate()  # should not raise

    def test_validate_empty_warns_not_crashes(self, tmp_path):
        """Empty directory warns but does not crash."""
        empty = tmp_path / "strategies"
        empty.mkdir()
        loader = StrategyLoader(empty)
        loader.validate()  # should not raise (warns instead)

    def test_format_available_empty(self, tmp_path):
        strat_dir = tmp_path / "strategies"
        strat_dir.mkdir()
        loader = StrategyLoader(strat_dir)
        assert loader.format_available() == "No strategies available."
