---
name: fitness-first-germany
description: Fitness First Germany gym bookings, schedule, and metrics.
version: 1.0.0
author: Daniel Main (danielmain), Hermes Agent
license: MIT
platforms:
  - linux
  - macos
  - windows
metadata:
  hermes:
    tags:
      - Fitness
      - Gym
      - Netpulse
      - EGYM
      - Booking
    related_skills: []
---

# Fitness First Germany Skill

Manage Fitness First Germany studio memberships, book group fitness courses, view gym check-in visits, inspect EGYM BioAge metrics, and detect members working out in real time via the Netpulse brand API. Works both as a standalone Hermes skill via bundled scripts and as native MCP tools.

## When to Use

- User asks to view upcoming gym classes or check their class schedule.
- User wants to book a class, cancel an existing booking, or manage course waitlists.
- User asks about gym visits, past check-ins, or latest check-in timestamp.
- User wants to inspect EGYM body metrics (BioAge, body fat %, BMI, metabolic age, VO2 max).
- User asks for club leaderboards, member ranking, or real-time active trainers.
- Don't use for: gyms outside the Fitness First Germany network or generic fitness calculations without account access.

## Prerequisites

Authentication requires the user's Fitness First Germany account email and password:
- `FITNESS_FIRST_EMAIL`
- `FITNESS_FIRST_PASSWORD`

These may be set as environment variables or saved locally via the in-chat onboarding flow below.

## Conversational Onboarding (Zero CLI for Users)

If the credentials are not yet configured or an authentication error occurs:

1. **Do not display technical errors or ask the user to run CLI commands.**
2. Ask the user conversationally in chat:
   > "To manage your Fitness First schedule and bookings, I need your Fitness First account email and password. What are your login details?"
3. Once the user replies with their credentials, run the auth helper using the `terminal` tool:
   ```bash
   python3 scripts/ff_cli.py auth-save --email "<user_email>" --password "<user_password>"
   ```
   *(Note: when running from the repo root, prefix with `skills/fitness-first-germany/scripts/ff_cli.py`)*.
4. If authentication fails, politely ask the user to double-check their credentials.
5. If successful, confirm to the user and immediately proceed with their original request.

## Safety & Confirmation Rules

All write actions require explicit user confirmation before applying changes:
- Class bookings (`book`)
- Booking cancellations (`cancel`)
- Joining or leaving waitlists (`waitlist-join`, `waitlist-leave`)

Always present class title, instructor, date, and start time to the user, and ask for confirmation. Never pass `--confirm` (or `confirm=true` in MCP mode) without explicit user approval.

## Quick Reference

| Action | Skill Script Command | MCP Equivalent |
|---|---|---|
| Check Auth Status | `python3 scripts/ff_cli.py auth-status` | `ff_account` |
| Upcoming Classes | `python3 scripts/ff_cli.py classes --days 14` | `ff_upcoming_classes` |
| Class Details | `python3 scripts/ff_cli.py class-details <class_id>` | `ff_class_details` |
| My Booked Classes | `python3 scripts/ff_cli.py schedule` | `ff_my_schedule` |
| Book a Class | `python3 scripts/ff_cli.py book <class_id> --confirm` | `ff_book_class` |
| Cancel Booking | `python3 scripts/ff_cli.py cancel <class_id> --confirm` | `ff_cancel_class` |
| Join Waitlist | `python3 scripts/ff_cli.py waitlist-join <class_id> --confirm` | `ff_join_waitlist` |
| Leave Waitlist | `python3 scripts/ff_cli.py waitlist-leave <class_id> --confirm` | `ff_leave_waitlist` |
| Check-in History | `python3 scripts/ff_cli.py check-ins --limit 20` | `ff_check_ins` |
| Latest Check-in | `python3 scripts/ff_cli.py latest-check-in` | `ff_latest_check_in` |
| EGYM BioAge & Body | `python3 scripts/ff_cli.py bioage` | `ff_body_measurements` |
| EGYM Activity Points | `python3 scripts/ff_cli.py activity` | `ff_activity_level` |
| Club Leaderboard | `python3 scripts/ff_cli.py leaderboard --limit 50` | `ff_leaderboard` |
| Member Profile Info | `python3 scripts/ff_cli.py member-info <uuid>` | `ff_member_info` |
| Active Trainers Delta | `python3 scripts/ff_cli.py active-trainers` | `ff_active_trainers` |

## How to Run

When running in Hermes Agent, execute commands via the `terminal` tool.
Locate the helper script relative to the installed skill path (`scripts/ff_cli.py`):

```python
terminal(command="python3 scripts/ff_cli.py classes --days 7")
```

If the MCP server is configured and active in Hermes, the agent can call `ff_*` native tools directly instead of executing terminal commands.

## Procedure

1. **Check or Establish Auth**:
   Call `auth-status`. If unauthenticated, trigger the Conversational Onboarding flow.
2. **Search Classes**:
   Call `classes --days 7`. Filter results by requested name, time, or location.
3. **Confirm Write Operations**:
   Before booking or cancelling, summarize class information and prompt the user.
4. **Execute Booking**:
   After confirmation, invoke `book <class_id> --confirm`.
5. **Report Result**:
   Confirm the booking and show the updated schedule.

## Pitfalls

- **Class IDs**: Netpulse class identifiers contain colons (e.g., `course:12345`). Always pass the full identifier string as returned by the classes query.
- **Session Expiry**: Sessions expire after prolonged inactivity. The client automatically re-authenticates using stored credentials on session expiration.
- **Home Club Reassignment**: Updating profiles requires sending the existing `homeClub` UUID, which the client handles automatically.

## Verification

To verify the skill installation and credentials:
```bash
python3 scripts/ff_cli.py auth-status
```
Expected output: JSON object with `"authenticated": true`, member name, and home club name.
