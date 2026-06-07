"""Tests for SINGLE_EPISODE_ONLY — the single-episode safety brake that skips
whole-season / "all episodes" / multi-episode issues instead of acting on them."""

import asyncio

import pytest

from app.webhooks import handlers

# A TV issue with a season but no specific episode -> resolves to the all-episodes
# sentinel (episode=0) inside _tv_episode_from_payload.
PAYLOAD = {
    "issue": {"issue_id": 901},
    "media": {"mediaType": "tv", "tvdbId": 350665},
}


@pytest.fixture
def whole_season_env(monkeypatch):
    """Wire handle_jellyseerr so PAYLOAD resolves to a whole-season TV issue, with
    the season/specific-episode handlers stubbed to record whether they ran."""
    calls = {"season": 0, "specific": 0}

    async def fake_fetch_issue(issue_id):
        return {"issue_type": "audio", "problemSeason": 4, "problemEpisode": None}

    async def fake_last_comment(issue_id):
        return ""

    async def fake_series(tvdb, **kw):
        return {"id": 267, "title": "The Rookie", "tvdbId": tvdb}

    async def fake_season(issue_id, series, season, bucket, **kw):
        calls["season"] += 1

    async def fake_specific(issue_id, series, season, episodes, bucket, **kw):
        calls["specific"] += 1

    monkeypatch.setattr(handlers, "jelly_fetch_issue", fake_fetch_issue)
    monkeypatch.setattr(handlers, "jelly_last_human_comment", fake_last_comment)
    monkeypatch.setattr(handlers.S, "get_series_by_tvdb", fake_series)
    monkeypatch.setattr(handlers, "_handle_tv_season", fake_season)
    monkeypatch.setattr(handlers, "_handle_tv_specific_episodes", fake_specific)
    monkeypatch.setattr(handlers.cfg, "ISSUE_TYPE_AS_BUCKET", True)
    handlers._COOLDOWN.clear()
    return calls


def test_single_episode_only_skips_whole_season(whole_season_env, monkeypatch):
    monkeypatch.setattr(handlers.cfg, "SINGLE_EPISODE_ONLY", True)
    res = asyncio.run(handlers.handle_jellyseerr(PAYLOAD))
    assert res["detail"] == "ignored: single-episode-only (no specific episode)"
    assert whole_season_env["season"] == 0    # whole-season handler NOT called
    assert whole_season_env["specific"] == 0   # specific-episodes handler NOT called


def test_default_still_handles_whole_season(whole_season_env, monkeypatch):
    # Flag off (default) = v0.2.4 behavior preserved: the whole-season handler runs.
    monkeypatch.setattr(handlers.cfg, "SINGLE_EPISODE_ONLY", False)
    res = asyncio.run(handlers.handle_jellyseerr(PAYLOAD))
    assert res["detail"].startswith("tv season handled")
    assert whole_season_env["season"] == 1
