# Fitness First Germany MCP

MCP server for a Fitness First Germany membership on the Netpulse brand API (`https://fitnessfirst.netpulse.com`).

It can list upcoming courses, show your bookings, book and cancel, join or leave a waitlist, search clubs, view the club leaderboard and member rankings, track gym check-ins, view activity levels, read EGYM body measurements / BioAge, check announcements, and edit your profile. Write tools do nothing until `confirm` is true.

Sign-in is `POST /np/exerciser/login` on the Fitness First host. `https://api.netpulse.com/np/login` does not see this membership. The server keeps the `JSESSIONID` cookie and signs in again if a call returns 401.

## Setup

```bash
cd fitness-first-germany-mcp
cp .env.example .env
# edit FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD
uv sync
```

stdio entry point:

```bash
uv run fitness-first-germany-mcp
```

### MCP Client Config (Claude Desktop, Cursor, etc.)

```json
{
  "mcpServers": {
    "fitness-first-germany": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/daniel/Workspace/mcp/fitness-first-germany-mcp", "fitness-first-germany-mcp"],
      "env": {
        "FITNESS_FIRST_EMAIL": "you@example.com",
        "FITNESS_FIRST_PASSWORD": "your-password"
      }
    }
  }
}
```

### Hermes Agent Setup

This repository works natively with [Hermes Agent](https://hermes-agent.nousresearch.com) both as an MCP server and as a procedural skill ([`agentskills.io`](https://agentskills.io) format).

#### 1. Link or install the Skill

Link the bundled skill to your Hermes skills directory:

```bash
mkdir -p ~/.hermes/skills
ln -s "$(pwd)/skills/fitness-first-germany" ~/.hermes/skills/fitness-first-germany
```

*(Alternatively, add this repository's `skills/` path to `skills.external_dirs` in `~/.hermes/config.yaml`)*.

#### 2. Choose how to configure your credentials

You have three options to provide your Fitness First credentials:

- **Option A: Via Hermes CLI (Recommended)**
  Hermes automatically saves `UPPER_SNAKE_CASE` environment variables into `~/.hermes/.env`:
  ```bash
  hermes config set FITNESS_FIRST_EMAIL "you@example.com"
  hermes config set FITNESS_FIRST_PASSWORD "your-password"
  ```
  Then in `~/.hermes/config.yaml`, reference them using `${VAR}`:
  ```yaml
  mcp_servers:
    fitness-first-germany:
      command: "uv"
      args: ["run", "--directory", "/path/to/fitness-first-germany-mcp", "fitness-first-germany-mcp"]
      env:
        FITNESS_FIRST_EMAIL: ${FITNESS_FIRST_EMAIL}
        FITNESS_FIRST_PASSWORD: ${FITNESS_FIRST_PASSWORD}
  ```

- **Option B: Directly in `~/.hermes/config.yaml`**
  ```yaml
  mcp_servers:
    fitness-first-germany:
      command: "uv"
      args: ["run", "--directory", "/path/to/fitness-first-germany-mcp", "fitness-first-germany-mcp"]
      env:
        FITNESS_FIRST_EMAIL: "you@example.com"
        FITNESS_FIRST_PASSWORD: "your-password"
  ```

- **Option C: In the local repository `.env`**
  Create `.env` in the repository root:
  ```bash
  cp .env.example .env
  # edit FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD
  ```
  The server loads `.env` automatically via `python-dotenv` when launched.

#### Quick Setup Script

You can also run the interactive setup helper:
```bash
./skills/fitness-first-germany/scripts/setup.sh
```

Now you can invoke `/fitness-first` or ask Hermes naturally about upcoming classes, check-ins, or EGYM BioAge metrics.

## Tools

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

## Tests

```bash
uv run pytest
```
