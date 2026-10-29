<p align="center">
  <img src="assets/banner.png" alt="Fitness First Germany - Hermes Agent Skill & MCP Server" width="100%">
</p>

# Fitness First Germany MCP & Hermes Skill

MCP server and Hermes Agent skill for your Fitness First Germany membership powered by the Netpulse brand API (`https://fitnessfirst.netpulse.com`).

It can list upcoming courses, show your bookings, book and cancel classes, join or leave waitlists, search clubs, view the club leaderboard and member rankings, track gym check-ins, view activity levels, read EGYM body measurements / BioAge, check announcements, and monitor live studio workouts.

---

## Installation & Quick Start

You can use Fitness First Germany either as a **Hermes Agent Skill** (one-liner install with conversational zero-CLI onboarding) or as a **Model Context Protocol (MCP) Server** (Claude Desktop, Cursor, Antigravity).

### Option 1: Install as a Hermes Agent Skill (Recommended)

Install the skill directly into Hermes from GitHub:

```bash
hermes skills install danielmain/fitness-first-germany-mcp/skills/fitness-first-germany
```

#### Zero-CLI Conversational Setup
Once installed, no config editing or terminal commands are needed:
1. Start chatting with Hermes: *"Show me upcoming spinning classes tomorrow"*
2. If unauthenticated, Hermes will ask conversationally for your Fitness First account email and password directly in the chat.
3. Hermes tests your credentials against the API and saves them securely to `~/.config/fitness-first-germany/auth.json` (chmod 600).
4. That's it! You can now manage bookings, inspect BioAge stats, and track visits conversationally.

---

### Option 2: Run as an MCP Server (Claude Desktop, Cursor, Antigravity)

#### Local Setup & Dependencies

```bash
cd fitness-first-germany-mcp
cp .env.example .env
# Edit FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD
uv sync
```

#### MCP Client Configuration

Add to your MCP client config (`claude_desktop_config.json`, Cursor MCP settings, or `~/.gemini/config/mcp_config.json`):

```json
{
  "mcpServers": {
    "fitness-first-germany": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/fitness-first-germany-mcp", "fitness-first-germany-mcp"],
      "env": {
        "FITNESS_FIRST_EMAIL": "you@example.com",
        "FITNESS_FIRST_PASSWORD": "your-password"
      }
    }
  }
}
```

Or run directly via stdio:
```bash
uv run fitness-first-germany-mcp
```

#### Running as an MCP Server in Hermes Agent

If you prefer native tool calling over MCP inside Hermes instead of the standalone skill:

```yaml
# Add to ~/.hermes/config.yaml
mcp_servers:
  fitness-first-germany:
    command: "uv"
    args: ["run", "--directory", "/path/to/fitness-first-germany-mcp", "fitness-first-germany-mcp"]
    env:
      FITNESS_FIRST_EMAIL: "you@example.com"
      FITNESS_FIRST_PASSWORD: "your-password"
```

---

### Live Studio Activity Monitor (`tail -f`)

Stream real-time workout completions and studio activity from members at your home club (with unmasked full names and avatar photos):

```bash
# Continuous live tail (default: polls every 60s)
python scripts/tail_members.py

# Or via uv package script
uv run fitness-first-tail

# Options
python scripts/tail_members.py -i 120        # Poll every 120 seconds (or set FITNESS_FIRST_POLL_INTERVAL=120)
python scripts/tail_members.py --reset       # Reset baseline snapshot
python scripts/tail_members.py --once        # Single check and exit
python scripts/tail_members.py --json        # Output newline-delimited JSON (ndjson)

# Forward live stream directly into Mattermost
python scripts/tail_members.py --mattermost-webhook "https://mattermost.funktional.dev/hooks/YOUR_TOKEN"
# Or with a Bot/Personal Token
python scripts/tail_members.py --mattermost-token "YOUR_TOKEN"
```

> [!NOTE]
> Netpulse sessions expire periodically and return `403: Access is denied`. The client automatically re-authenticates and refreshes the session without interrupting the stream. If an API error persists, the tail monitor automatically applies exponential backoff (up to 5 minutes) instead of spamming retries.

## Available Tools

| Tool | What it does |
| --- | --- |
| `ff_account` | Signed-in member and home club |
| `ff_upcoming_classes` | Courses from today for `days` (default 14, max 60). Optional `club_uuid` or `club_name` |
| `ff_class_details` | One course. The id contains a colon |
| `ff_my_schedule` | Courses you already booked |
| `ff_book_class` | Book. Requires `confirm=true`. Optional `spot` |
| `ff_cancel_class` | Cancel a booking. Requires `confirm=true` |
| `ff_join_waitlist` / `ff_leave_waitlist` | Waitlist. Require `confirm=true` |
| `ff_clubs` | Search clubs by name or city |
| `ff_membership` | Membership type and contract dates |
| `ff_leaderboard` | Club ranking of members with points, UUIDs, and CDN avatars. Optional `size` (1-100) and `next_page_token` |
| `ff_ranking` | Signed-in member's personal rank, points, and total club members |
| `ff_member_info` | Lookup public profile of a club member by UUID (resolves unmasked full name, club, and avatar) |
| `ff_active_trainers` | Real-time detection of members actively training in your studio using leaderboard point deltas |
| `ff_check_ins` | Gym visits / check-in history (date, club name, address). Optional `limit` (default 30) and `end_date` |
| `ff_latest_check_in` | Most recent gym check-in timestamp and timezone |
| `ff_activity_level` | EGYM activity level, points, days remaining in cycle, and maintenance points |
| `ff_body_measurements` | Weight (kg), height (cm), and EGYM Fitness Hub / bioimpedance stats (body fat %, BMI, metabolic age, BioAge, VO2 max, blood pressure) |
| `ff_notifications` | Gym notifications and system messages |
| `ff_profile` | Profile. Login passcodes are removed |
| `ff_update_profile` | Update the fields you pass. Requires `confirm=true` |
| `ff_change_password` | Change the password. Requires `confirm=true` |

`birthday` is `MM/DD/YYYY`. `measurement_unit` is `M` or `I`. `privacy` is `Public` or `Private`.

Profile saves POST the whole profile to `/np/exerciser/{uuid}`. A partial body clears the home club, and the API then assigns a different club. Every save sends `homeClub` with the current UUID unless you pass `home_club_uuid`.

## Real-Time Presence & Member Intelligence

Fitness First does not expose a direct "who is in the gym right now" attendance endpoint, and individual check-in histories (`/check-ins/history`) for other members return `403 Forbidden`. However, near real-time presence detection is possible via **EGYM Leaderboard Point Deltas**:

1. **Live Points Updating**: When members log workouts, use smart EGYM strength machines, or check into the gym, their points on `/analysis/api/v1.0/exercisers/{uuid}/ranking/leaderboard` update within minutes.
2. **Snapshot Comparison (`ff_active_trainers`)**: The tool caches current leaderboard scores. When called again, any member whose points increased is identified as actively training in the studio.
3. **Identity Resolution (`ff_member_info`)**: While the leaderboard only shows truncated names (`Alex M.`), calling `/np/exercisers/{exerciser_id}/brief-info` unmasks the member's full first and last name (`Alex Mustermann`), home club, and direct high-resolution CDN profile picture.

See [AGENTS.md](AGENTS.md) for full reverse-engineering notes and API route references.

## Tests

```bash
uv run pytest
```
