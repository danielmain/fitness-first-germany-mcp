---
name: fitness-first-germany
description: Manage Fitness First Germany memberships, view and book group classes, manage waitlists, check gym visit history, rankings, and inspect EGYM body measurements / BioAge using Netpulse API.
version: 1.0.0
metadata:
  hermes:
    tags: [fitness, gym, booking, mcp, egym]
prerequisites:
  env:
    - FITNESS_FIRST_EMAIL
    - FITNESS_FIRST_PASSWORD
---

# Fitness First Germany

Procedural guide for managing your Fitness First Germany account, bookings, check-in history, and EGYM body metrics via the Netpulse brand API tools.

## When to Use
Activate this skill when the user wants to:
- Check gym schedule or upcoming fitness classes.
- Book, cancel, or join/leave waitlists for classes.
- View gym check-in history or verify their latest visit.
- Check club leaderboards, personal rank, or EGYM activity points.
- View BioAge, weight, BMI, body fat, or metabolic measurements.
- Inspect or update profile settings and home club.
- Configure or troubleshoot Fitness First credentials in Hermes.

Command: `/fitness-first <instruction>`

---

## Prerequisites & Credential Configuration

This skill requires the `fitness-first-germany` MCP server running with valid credentials.

### If credentials or tools are missing:
If tools (`ff_*`) are not available or return `Set FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD before starting the server`, guide the user with these 3 options:

1. **Hermes CLI (Recommended):**
   ```bash
   hermes config set FITNESS_FIRST_EMAIL "you@example.com"
   hermes config set FITNESS_FIRST_PASSWORD "your-password"
   ```
   *(Hermes stores UPPER_CASE variables directly in `~/.hermes/.env`)*.

2. **Hermes MCP config (`~/.hermes/config.yaml`):**
   ```yaml
   mcp_servers:
     fitness-first-germany:
       command: "uv"
       args: ["run", "--directory", "/path/to/fitness-first-germany-mcp", "fitness-first-germany-mcp"]
       env:
         FITNESS_FIRST_EMAIL: ${FITNESS_FIRST_EMAIL}
         FITNESS_FIRST_PASSWORD: ${FITNESS_FIRST_PASSWORD}
   ```

3. **Local repository `.env`:**
   In the cloned repository directory:
   ```bash
   cp .env.example .env
   # Edit FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD
   ```

You can also run the bundled interactive setup script:
```bash
./scripts/setup.sh
```

---

## Safety & Confirmation Rules

> [!IMPORTANT]
> All write actions require explicit user confirmation before executing:
> - `ff_book_class`
> - `ff_cancel_class`
> - `ff_join_waitlist` / `ff_leave_waitlist`
> - `ff_update_profile`
> - `ff_change_password`
> 
> Never pass `confirm=true` unless the user explicitly approved the action with the specific details (class title, date, time, or profile fields).

---

## Available Tools

| Tool | Purpose |
| --- | --- |
| `ff_account` | Signed-in member and home club info |
| `ff_upcoming_classes` | Courses from today for `days` (default 14, max 60). Optional `club_uuid` or `club_name` |
| `ff_class_details` | Detailed info for a class ID (note: IDs contain colons, e.g. `course:12345`) |
| `ff_my_schedule` | List courses currently booked by the user |
| `ff_book_class` | Book a class (`confirm=true`, optional `spot`) |
| `ff_cancel_class` | Cancel a booking (`confirm=true`) |
| `ff_join_waitlist` / `ff_leave_waitlist` | Join or leave a waitlist (`confirm=true`) |
| `ff_clubs` | Search clubs by name or city |
| `ff_membership` | Membership type and contract start/end dates |
| `ff_leaderboard` | Club member rankings with points, UUIDs, and avatars |
| `ff_ranking` | Personal member ranking and club totals |
| `ff_member_info` | Lookup full name, home club, and CDN avatar for an exerciser UUID |
| `ff_active_trainers` | Real-time detection of members currently training based on leaderboard point deltas |
| `ff_check_ins` | Gym visits / check-in history (dates, club names, addresses) |
| `ff_latest_check_in` | Most recent gym check-in timestamp and timezone |
| `ff_activity_level` | EGYM activity points, tier, and days left in cycle |
| `ff_body_measurements` | Weight, height, BMI, body fat %, BioAge, metabolic age, VO2 max |
| `ff_notifications` | Gym notifications and system messages |
| `ff_profile` | Full profile details (passwords omitted) |
| `ff_update_profile` | Update profile fields (`confirm=true`) |
| `ff_change_password` | Change account password (`confirm=true`) |

---

## Workflows

### 1. Searching & Booking a Class
1. Call `ff_upcoming_classes(days=...)` optionally filtering by `club_name` or `club_uuid`.
2. Present the available classes clearly (title, date/time, instructor, available spots).
3. If the user picks a class, summarize the details and ask for explicit confirmation.
4. When confirmed, call `ff_book_class(class_id=..., confirm=true, spot=...)`.
   - If the class is full, offer to join the waitlist with `ff_join_waitlist(class_id=..., confirm=true)`.

### 2. Viewing Bookings & Cancellations
1. Call `ff_my_schedule` to display upcoming reservations.
2. If the user requests a cancellation, verify the class details and confirm before calling `ff_cancel_class(class_id=..., confirm=true)`.

### 3. Check-ins & Gym Activity
- Call `ff_latest_check_in` to verify the latest visit timestamp and gym location.
- Call `ff_check_ins(limit=...)` for visit frequency analysis and past visit history.
- Call `ff_activity_level` to check EGYM progress towards point thresholds.

### 4. Health & Body Measurements
- Call `ff_body_measurements` to display health and body composition stats (BioAge vs. chronological age, body fat %, metabolic age, VO2 max).

### 5. Profile Management
- `birthday` format is `MM/DD/YYYY`.
- `measurement_unit` is `M` (metric) or `I` (imperial).
- Saving profile sends the entire payload to the Netpulse API. The tool automatically preserves `homeClub` UUID to prevent accidental club resets.

### 6. Live Activity Stream & Mattermost Notifications
- Run `python scripts/tail_members.py` or `uv run fitness-first-tail` to monitor members training in real time.
- The stream can forward live updates to Mattermost via `--mattermost-webhook` or `MATTERMOST_WEBHOOK_URL`.

---

## Common Pitfalls
- **Session renewal**: The client automatically maintains `JSESSIONID` and re-authenticates on 401 using `FITNESS_FIRST_EMAIL` and `FITNESS_FIRST_PASSWORD`.
- **Class IDs**: Netpulse class identifiers contain a colon `:` (e.g., `course:12345`). Always pass the full ID string as returned by `ff_upcoming_classes`.
