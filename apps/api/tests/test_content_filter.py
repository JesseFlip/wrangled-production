"""Tests for better-profanity content filtering in ModerationStore."""

from api.moderation import ModerationStore


def test_blocks_profanity(tmp_path):
    store = ModerationStore(db_path=tmp_path / "test.json")
    result = store.check_profanity("fuck you")
    assert result is not None


def test_allows_clean_text(tmp_path):
    store = ModerationStore(db_path=tmp_path / "test.json")
    result = store.check_profanity("hello world")
    assert result is None


def test_blocks_racial_slurs(tmp_path):
    store = ModerationStore(db_path=tmp_path / "test.json")
    result = store.check_profanity("nigger")
    assert result is not None
