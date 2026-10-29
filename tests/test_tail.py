import json
from unittest.mock import MagicMock, patch

from fitness_first_germany_mcp.tail import MemberTailer, MattermostNotifier, format_event_terminal


def test_member_tailer_poll_once_detects_activity(tmp_path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(json.dumps({
        "timestamp": "2026-10-29T12:00:00",
        "club_uuid": "club-1",
        "scores": {
            "user-1": 100,
            "user-2": 200,
        },
    }))

    mock_client = MagicMock()
    mock_client.timezone = "Europe/Berlin"
    mock_client.home_club_uuid = "club-1"
    mock_client.leaderboard.return_value = {
        "items": [
            {"exerciser_id": "user-1", "name": "User One", "points": 150, "avatar_url": None},
            {"exerciser_id": "user-2", "name": "User Two", "points": 200, "avatar_url": None},
        ]
    }
    mock_client.member_info.return_value = {
        "exerciser_id": "user-1",
        "full_name": "User One Full",
        "first_name": "User",
        "last_name": "One",
        "home_club_name": "Club 1 Studio",
        "home_club_uuid": "club-1",
        "nickname": "Tester",
        "avatar_url": "https://example.com/avatar.jpg",
    }

    mock_notifier = MagicMock()
    mock_notifier.is_configured = True

    tailer = MemberTailer(client=mock_client, cache_path=str(cache_file), notifier=mock_notifier)
    tailer.load_baseline()

    events = tailer.poll_once()

    assert len(events) == 1
    ev = events[0]
    assert ev["exerciser_id"] == "user-1"
    assert ev["points_gained"] == 50
    assert ev["current_points"] == 150
    assert ev["previous_points"] == 100
    assert ev["name"] == "User One Full"
    assert ev["avatar_url"] == "https://example.com/avatar.jpg"
    assert ev["nickname"] == "Tester"

    # Verify cached lookup
    assert "user-1" in tailer.member_cache
    mock_client.member_info.assert_called_once_with("user-1")

    # Formatted terminal string
    formatted = format_event_terminal(ev)
    assert "User One Full" in formatted
    assert "+50 pts" in formatted
    assert "Club 1 Studio" in formatted

    # Verify notifier was called
    mock_notifier.send_event.assert_called_once_with(ev)


def test_mattermost_notifier_webhook():
    notifier = MattermostNotifier(
        webhook_url="https://mattermost.funktional.dev/hooks/test-token",
        channel_name="fitness-first---bad-cannstatt",
    )
    assert notifier.is_configured is True

    event = {
        "timestamp_local": "12:30:00",
        "name": "Alex Gymmer",
        "leaderboard_name": "Alex G.",
        "points_gained": 35,
        "current_points": 5000,
        "home_club_name": "Stuttgart – Bad Cannstatt",
        "exerciser_id": "uuid-123",
        "avatar_url": "https://example.com/photo.jpg",
    }

    with patch.object(notifier, "_post_json", return_value=True) as mock_post:
        success = notifier.send_event(event)
        assert success is True
        mock_post.assert_called_once()
        url, payload = mock_post.call_args[0][:2]
        assert url == "https://mattermost.funktional.dev/hooks/test-token"
        assert payload["channel"] == "fitness-first---bad-cannstatt"
        assert "Alex Gymmer" in payload["text"]
        assert "+35" in payload["text"]
        assert payload["attachments"][0]["thumb_url"] == "https://example.com/photo.jpg"


def test_mattermost_notifier_api_token():
    notifier = MattermostNotifier(
        server_url="https://mattermost.funktional.dev",
        bot_token="token-xyz",
        channel_id="aised4nnkbnoug1h4khytwqbce",
    )
    assert notifier.is_configured is True

    event = {
        "name": "Alex Gymmer",
        "points_gained": 35,
        "current_points": 5000,
        "home_club_name": "Stuttgart – Bad Cannstatt",
        "exerciser_id": "uuid-123",
    }

    with patch.object(notifier, "_post_json", return_value=True) as mock_post:
        success = notifier.send_event(event)
        assert success is True
        url, payload = mock_post.call_args[0][:2]
        headers = mock_post.call_args[1].get("headers")
        assert url == "https://mattermost.funktional.dev/api/v4/posts"
        assert payload["channel_id"] == "aised4nnkbnoug1h4khytwqbce"
        assert headers == {"Authorization": "Bearer token-xyz"}
