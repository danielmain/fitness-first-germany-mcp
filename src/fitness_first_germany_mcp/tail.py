"""Live tail CLI script to monitor member activity in Fitness First clubs.

Fitness First / Netpulse does not expose turnstile checkout events or direct
check-in history of other members (which returns 403 Forbidden). Instead,
members logging workouts, finishing sets on EGYM machines, or checking in earn
activity points in real-time. This CLI streams these events as a live feed
and resolves full member identities (unmasked name, avatar, club) via brief-info,
enriching the feed with club rank, leaderboard standing, and workout estimates.

Optionally forwards live activity alerts to a Mattermost channel via
an Incoming Webhook or Bot Access Token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from fitness_first_germany_mcp.client import FitnessFirstClient, FitnessFirstError, _zone


# ANSI escape sequences for pretty terminal styling
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
BRIGHT_GREEN = "\033[92m"
CYAN = "\033[36m"
BRIGHT_CYAN = "\033[96m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"


def estimate_activity(delta: int) -> str:
    """Categorize workout intensity based on EGYM point-scoring heuristics."""
    if delta >= 200:
        return "Extended Workout / Multi-Circuit"
    elif delta >= 100:
        return "Full EGYM Circuit / High-Intensity Set"
    elif delta >= 50:
        return "Smart Strength Rotation / Cardio Block"
    elif delta >= 20:
        return "Smart Strength Machine Set"
    elif delta >= 10:
        return "Single Machine Set / Check-in Badge"
    else:
        return "Activity Points Increment"


def format_event_terminal(event: dict[str, Any]) -> str:
    """Format an activity event for human-readable terminal display."""
    ts = event.get("timestamp_local") or event.get("timestamp")
    name = event.get("name") or "Unknown Member"
    lb_name = event.get("leaderboard_name")
    name_str = f"{BOLD}{BRIGHT_GREEN}{name}{RESET}"
    if lb_name and lb_name != name:
        name_str += f" {DIM}({lb_name}){RESET}"

    delta = event.get("points_gained", 0)
    pts_str = f"{BOLD}{YELLOW}+{delta} pts{RESET} {DIM}(total: {event.get('current_points', 0):,}){RESET}"

    rank = event.get("rank")
    total_users = event.get("total_users")
    percentile = event.get("percentile")
    rank_str = f"#{rank} of {total_users}" if rank and total_users else "N/A"
    if percentile is not None:
        rank_str += f" (Top {percentile}%)"

    lines = [
        f"{DIM}[{ts}]{RESET} ⚡ {name_str} gained {pts_str}",
        f"       {DIM}├─ Club Standing:{RESET} {CYAN}{rank_str}{RESET}",
        f"       {DIM}├─ Activity Est :{RESET} {MAGENTA}{event.get('activity_estimate', 'N/A')}{RESET}",
    ]
    if event.get("gap_above"):
        gap = event["gap_above"]
        lines.append(f"       {DIM}├─ Leaderboard  :{RESET} {gap['gap_points']:,} pts behind {gap['ahead_name']} (#{gap['ahead_rank']})")

    lines.extend([
        f"       {DIM}├─ Home Studio  :{RESET} {event.get('home_club_name') or 'N/A'}",
        f"       {DIM}├─ Exerciser ID :{RESET} {CYAN}{event.get('exerciser_id')}{RESET}",
    ])
    if event.get("nickname"):
        lines.append(f"       {DIM}├─ Nickname     :{RESET} {event.get('nickname')}")
    if event.get("avatar_url"):
        lines.append(f"       {DIM}└─ Avatar Photo :{RESET} {BLUE}{event.get('avatar_url')}{RESET}")
    else:
        lines.append(f"       {DIM}└─ Avatar Photo :{RESET} {DIM}None{RESET}")

    return "\n".join(lines)


class MattermostNotifier:
    """Sends activity notifications to a Mattermost channel."""

    def __init__(
        self,
        webhook_url: str | None = None,
        server_url: str | None = None,
        bot_token: str | None = None,
        channel_id: str | None = None,
        channel_name: str | None = None,
    ):
        self.webhook_url = webhook_url
        self.server_url = server_url.rstrip("/") if server_url else None
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.channel_name = channel_name

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url or (self.server_url and self.bot_token and self.channel_id))

    def send_event(self, event: dict[str, Any]) -> bool:
        if not self.is_configured:
            return False

        name = event.get("name") or "Unknown Member"
        lb_name = event.get("leaderboard_name")
        display_name = f"{name} ({lb_name})" if lb_name and lb_name != name else name
        delta = event.get("points_gained", 0)
        current_points = event.get("current_points", 0)
        studio = event.get("home_club_name") or "Home Studio"
        uid = event.get("exerciser_id")
        avatar = event.get("avatar_url")
        nickname = event.get("nickname")
        rank = event.get("rank")
        total_users = event.get("total_users")
        percentile = event.get("percentile")
        activity_type = event.get("activity_estimate") or "Workout Activity"

        rank_str = f"#{rank} of {total_users}" if rank and total_users else "N/A"
        if percentile is not None:
            rank_str += f" (Top {percentile}%)"

        lines = [
            f"### ⚡ Fitness First Activity: **{display_name}**",
            f"**+{delta} Activity Points** earned (Total: **{current_points:,} pts**)",
            f"- **Estimated Activity:** {activity_type}",
            f"- **Club Standing:** Rank {rank_str}",
            f"- **Studio:** {studio}",
            f"- **Member UUID:** `{uid}`",
        ]
        if nickname:
            lines.append(f"- **Nickname:** {nickname}")

        text = "\n".join(lines)

        fields = [
            {"title": "Club Standing", "value": rank_str, "short": True},
            {"title": "Activity Type", "value": activity_type, "short": True},
            {"title": "Points Gained", "value": f"+{delta:,} pts", "short": True},
            {"title": "Total Score", "value": f"{current_points:,} pts", "short": True},
            {"title": "Home Studio", "value": studio, "short": True},
            {"title": "Exerciser UUID", "value": f"`{uid}`", "short": True},
        ]

        attachment: dict[str, Any] = {
            "color": "#00C853",
            "author_name": display_name,
            "title": f"+{delta} pts gained at {studio}",
            "text": f"Current Total: **{current_points:,} pts** | Rank **{rank_str}**",
            "fields": fields,
        }
        if avatar:
            attachment["thumb_url"] = avatar
            attachment["author_icon"] = avatar

        # Flow A: Incoming Webhook (Recommended)
        if self.webhook_url:
            payload: dict[str, Any] = {
                "username": "Fitness First Monitor",
                "text": text,
                "attachments": [attachment],
            }
            if self.channel_name:
                payload["channel"] = self.channel_name
            return self._post_json(self.webhook_url, payload)

        # Flow B: Bot Access Token / Personal Access Token via REST API v4
        if self.server_url and self.bot_token and self.channel_id:
            api_url = f"{self.server_url}/api/v4/posts"
            payload = {
                "channel_id": self.channel_id,
                "message": text,
                "props": {
                    "attachments": [attachment],
                },
            }
            headers = {"Authorization": f"Bearer {self.bot_token}"}
            return self._post_json(api_url, payload, headers=headers)

        return False

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> bool:
        req_headers = {
            "Content-Type": "application/json",
            "User-Agent": "fitness-first-germany-mcp/0.1.0",
        }
        if headers:
            req_headers.update(headers)
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 201)
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            print(f"[Mattermost Error] HTTP {err.code}: {err_body}", file=sys.stderr)
            return False
        except Exception as err:
            print(f"[Mattermost Error] {err}", file=sys.stderr)
            return False


class MemberTailer:
    def __init__(
        self,
        client: FitnessFirstClient,
        cache_path: str | None = None,
        poll_interval: float = 60.0,
        json_output: bool = False,
        notifier: MattermostNotifier | None = None,
    ):
        self.client = client
        self.poll_interval = max(5.0, poll_interval)
        self.json_output = json_output
        self.timezone_str = client.timezone
        self.home_club_uuid = client.home_club_uuid
        self.notifier = notifier

        if not cache_path:
            cache_dir = os.path.expanduser("~/.cache/fitness_first_germany")
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"leaderboard_snapshot_{self.home_club_uuid}.json")
        self.cache_path = cache_path

        # In-memory member brief-info cache to avoid repeated network lookups
        self.member_cache: dict[str, dict[str, Any]] = {}
        # Current known scores: {exerciser_id: points}
        self.scores: dict[str, int] = {}
        self.last_check_time: str | None = None

    def load_baseline(self, reset: bool = False) -> None:
        """Load baseline scores from file or fetch fresh baseline."""
        if not reset and os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.scores = data.get("scores") or {}
                    self.last_check_time = data.get("timestamp")
            except Exception:
                self.scores = {}

    def save_snapshot(self) -> None:
        """Persist current scores to cache file."""
        now_iso = datetime.now(_zone(self.timezone_str)).isoformat(timespec="seconds")
        try:
            cache_dir = os.path.dirname(self.cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": now_iso,
                    "club_uuid": self.home_club_uuid,
                    "scores": self.scores,
                }, f, indent=2)
            self.last_check_time = now_iso
        except Exception:
            pass

    def get_member_details(self, exerciser_id: str) -> dict[str, Any]:
        """Fetch and cache unmasked member details."""
        if exerciser_id in self.member_cache:
            return self.member_cache[exerciser_id]

        try:
            info = self.client.member_info(exerciser_id)
            self.member_cache[exerciser_id] = info
            return info
        except Exception:
            return {
                "exerciser_id": exerciser_id,
                "full_name": None,
                "first_name": None,
                "last_name": None,
                "home_club_uuid": self.home_club_uuid,
                "home_club_name": None,
                "nickname": None,
                "avatar_url": None,
            }

    def poll_once(self) -> list[dict[str, Any]]:
        """Poll the leaderboard once and detect members with increased points."""
        lb = self.client.leaderboard(size=100)
        items = lb.get("items") or []
        total_users = lb.get("total_users") or len(items)

        now_dt = datetime.now(_zone(self.timezone_str))
        now_iso = now_dt.isoformat(timespec="seconds")
        now_local = now_dt.strftime("%H:%M:%S")

        events: list[dict[str, Any]] = []
        is_first_sync = len(self.scores) == 0

        current_batch: dict[str, int] = {}
        for idx, item in enumerate(items):
            uid = item.get("exerciser_id")
            pts = item.get("points")
            if not uid or not isinstance(pts, int):
                continue
            current_batch[uid] = pts

            if not is_first_sync and uid in self.scores:
                old_pts = self.scores[uid]
                delta = pts - old_pts
                if delta > 0:
                    details = self.get_member_details(uid)
                    full_name = details.get("full_name") or item.get("name")
                    avatar = details.get("avatar_url") or item.get("avatar_url")
                    rank = idx + 1
                    percentile = round((rank / total_users) * 100, 1) if total_users else None

                    gap_above = None
                    if idx > 0:
                        prev_item = items[idx - 1]
                        ahead_pts = prev_item.get("points", 0)
                        gap_above = {
                            "ahead_name": prev_item.get("name"),
                            "ahead_rank": idx,
                            "gap_points": ahead_pts - pts,
                        }

                    ev = {
                        "timestamp": now_iso,
                        "timestamp_local": now_local,
                        "exerciser_id": uid,
                        "name": full_name,
                        "leaderboard_name": item.get("name"),
                        "first_name": details.get("first_name"),
                        "last_name": details.get("last_name"),
                        "nickname": details.get("nickname"),
                        "home_club_name": details.get("home_club_name"),
                        "home_club_uuid": details.get("home_club_uuid"),
                        "points_gained": delta,
                        "current_points": pts,
                        "previous_points": old_pts,
                        "avatar_url": avatar,
                        "rank": rank,
                        "total_users": total_users,
                        "percentile": percentile,
                        "activity_estimate": estimate_activity(delta),
                        "gap_above": gap_above,
                    }
                    events.append(ev)

                    # Forward to Mattermost if configured
                    if self.notifier and self.notifier.is_configured:
                        self.notifier.send_event(ev)

        self.scores.update(current_batch)
        self.save_snapshot()
        return events

    def run(self, once: bool = False, reset: bool = False) -> None:
        """Run the continuous tail loop."""
        self.load_baseline(reset=reset)

        if not self.json_output:
            # Print friendly startup banner
            print(f"{BOLD}{CYAN}=== Fitness First Germany Live Studio Activity Stream ==={RESET}")
            print(f"{DIM}Home Club UUID  :{RESET} {self.home_club_uuid}")
            print(f"{DIM}Polling Interval:{RESET} {self.poll_interval:.1f}s")
            print(f"{DIM}Cache Snapshot  :{RESET} {self.cache_path}")
            if self.notifier and self.notifier.is_configured:
                target_str = (
                    f"Incoming Webhook ({self.notifier.channel_name or 'channel default'})"
                    if self.notifier.webhook_url
                    else f"API -> Channel ID {self.notifier.channel_id}"
                )
                print(f"{DIM}Mattermost Dest :{RESET} {GREEN}{target_str}{RESET}")
            else:
                print(f"{DIM}Mattermost Dest :{RESET} {DIM}Disabled (no webhook or token configured){RESET}")
            print(f"{DIM}Note            :{RESET} Netpulse does not log checkout events. This tails real-time")
            print(f"                  member workout completions, machine sets & point increases.")
            print(f"{DIM}------------------------------------------------------------{RESET}")

        # Initial check / sync
        if not self.scores:
            if not self.json_output:
                print(f"{DIM}[{datetime.now().strftime('%H:%M:%S')}]{RESET} Fetching initial studio baseline...", end="", flush=True)
            self.poll_once()
            if not self.json_output:
                print(f" {GREEN}Done ({len(self.scores)} ranked members loaded).{RESET}")
                if once:
                    print(f"{YELLOW}Baseline established. Run without --once to stream live events.{RESET}")
                    return
                print(f"{CYAN}Streaming live events (Ctrl+C to stop)...{RESET}\n")
        else:
            if not self.json_output:
                print(f"{GREEN}Loaded existing baseline ({len(self.scores)} members) from {self.last_check_time}.{RESET}")
                if not once:
                    print(f"{CYAN}Streaming live events (Ctrl+C to stop)...{RESET}\n")

            # Check immediately for deltas since snapshot
            events = self.poll_once()
            for ev in events:
                if self.json_output:
                    print(json.dumps(ev, ensure_ascii=False), flush=True)
                else:
                    print(format_event_terminal(ev), flush=True)

            if once:
                if not events and not self.json_output:
                    print(f"{DIM}No member activity detected since last check.{RESET}")
                return

        # Continuous tail loop
        consecutive_errors = 0
        while True:
            sleep_time = (
                self.poll_interval
                if consecutive_errors == 0
                else min(300.0, max(self.poll_interval, 30.0) * (2 ** min(consecutive_errors - 1, 4)))
            )
            try:
                time.sleep(sleep_time)
                events = self.poll_once()
                consecutive_errors = 0
                for ev in events:
                    if self.json_output:
                        print(json.dumps(ev, ensure_ascii=False), flush=True)
                    else:
                        print(format_event_terminal(ev), flush=True)
            except KeyboardInterrupt:
                if not self.json_output:
                    print(f"\n{YELLOW}Tail interrupted by user. Stopping.{RESET}")
                break
            except FitnessFirstError as err:
                consecutive_errors += 1
                next_delay = int(min(300.0, max(self.poll_interval, 30.0) * (2 ** min(consecutive_errors - 1, 4))))
                if not self.json_output:
                    print(
                        f"{DIM}[{datetime.now().strftime('%H:%M:%S')}]{RESET} {YELLOW}API error (retrying in {next_delay}s): {err}{RESET}",
                        file=sys.stderr,
                    )
            except Exception as err:
                consecutive_errors += 1
                next_delay = int(min(300.0, max(self.poll_interval, 30.0) * (2 ** min(consecutive_errors - 1, 4))))
                if not self.json_output:
                    print(
                        f"{DIM}[{datetime.now().strftime('%H:%M:%S')}]{RESET} {YELLOW}Unexpected error (retrying in {next_delay}s): {err}{RESET}",
                        file=sys.stderr,
                    )


def main() -> None:
    load_dotenv()

    env_interval = os.environ.get("FITNESS_FIRST_POLL_INTERVAL")
    default_interval = float(env_interval) if env_interval else 60.0

    parser = argparse.ArgumentParser(
        prog="fitness-first-tail",
        description=(
            "Live 'tail -f' monitor for member workout activity and check-ins at your Fitness First home studio. "
            "Resolves full member identity details (unmasked name, avatar photo, home club) in real time."
        ),
    )
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=default_interval,
        help="Polling interval in seconds (default: 60s, or FITNESS_FIRST_POLL_INTERVAL; minimum: 5s)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset/ignore previous baseline and start tracking fresh from now",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once, print any detected activity since the last check, and exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output detected events as newline-delimited JSON (ndjson)",
    )
    parser.add_argument(
        "--cache-path",
        type=str,
        default=None,
        help="Custom path to snapshot cache JSON file",
    )
    parser.add_argument(
        "-m", "--mattermost-webhook",
        type=str,
        default=os.environ.get("MATTERMOST_WEBHOOK_URL"),
        help="Mattermost Incoming Webhook URL (or set MATTERMOST_WEBHOOK_URL)",
    )
    parser.add_argument(
        "--mattermost-url",
        type=str,
        default=os.environ.get("MATTERMOST_URL", "https://mattermost.funktional.dev"),
        help="Mattermost server URL (default: https://mattermost.funktional.dev)",
    )
    parser.add_argument(
        "--mattermost-token",
        type=str,
        default=os.environ.get("MATTERMOST_TOKEN"),
        help="Mattermost bot / personal access token (or set MATTERMOST_TOKEN)",
    )
    parser.add_argument(
        "--mattermost-channel-id",
        type=str,
        default=os.environ.get("MATTERMOST_CHANNEL_ID", "aised4nnkbnoug1h4khytwqbce"),
        help="Mattermost Channel ID (default: aised4nnkbnoug1h4khytwqbce)",
    )
    parser.add_argument(
        "--mattermost-channel",
        type=str,
        default=os.environ.get("MATTERMOST_CHANNEL", "fitness-first---bad-cannstatt"),
        help="Mattermost Channel handle (default: fitness-first---bad-cannstatt)",
    )

    args = parser.parse_args()

    try:
        client = FitnessFirstClient.from_env()
    except Exception as err:
        print(f"Error initializing Fitness First client: {err}", file=sys.stderr)
        print("Ensure FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD are set in your .env or environment.", file=sys.stderr)
        sys.exit(1)

    notifier = MattermostNotifier(
        webhook_url=args.mattermost_webhook,
        server_url=args.mattermost_url,
        bot_token=args.mattermost_token,
        channel_id=args.mattermost_channel_id,
        channel_name=args.mattermost_channel,
    )

    tailer = MemberTailer(
        client=client,
        cache_path=args.cache_path,
        poll_interval=args.interval,
        json_output=args.json,
        notifier=notifier,
    )
    tailer.run(once=args.once, reset=args.reset)


if __name__ == "__main__":
    main()
