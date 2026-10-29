# Fitness First Germany API — Agent & Developer Reference

> [!IMPORTANT]
> **Documentation Maintenance Rule**: All relevant changes to code, architecture, CLI tools, MCP tools, or configuration options **must always be updated in the documentation** (`README.md`, `AGENTS.md`, and `skills/fitness-first-germany/SKILL.md`) whenever modifications are made. Never leave documentation out of sync with code changes.

This document provides deep technical reference, API reverse-engineering findings, and platform architecture details for AI agents (Claude, Hermes, Antigravity) working with the `fitness-first-germany-mcp` server.

---

## 1. Platform Architecture

The Fitness First Germany mobile app (`com.netpulse.mobile.fitnessfirst`) is powered by the **Netpulse / EGYM white-label mobile backend**.

- **Brand Host**: `https://fitnessfirst.netpulse.com`
- **Global Netpulse Host**: `https://api.netpulse.com` *(Note: European brand memberships authenticate against the brand-specific host, not the global host).*
- **Authentication**: Stateful session cookie (`JSESSIONID`) acquired via form-encoded credentials at `POST /np/exerciser/login`.
  - *Session Expiry & Access Denied*: When the `JSESSIONID` expires (typically after 15–30 minutes of inactivity), Netpulse's Spring Security layer responds with `403: Access is denied` (rather than standard 401). The MCP client intercepts both `401` and `403` status codes, automatically clears invalid session cookies, executes a fresh login, and transparently retries the request once before escalating any genuine authorization failure.
- **Required Request Headers**:
  - `User-Agent`: `okhttp/4.12.0` (or `okhttp/3.12.3`)
  - `Accept`: `application/json`
  - `X-NP-API-Version`: `1.5`
  - `X-NP-APP-Version`: `3.1` (or `9999` to bypass client version deprecation checks)
  - `X-NP-User-Agent`: `clientType=MOBILE_DEVICE; devicePlatform=ANDROID; deviceUid=fitness-first-germany-mcp; applicationName=Fitness First; applicationVersion=3.1; applicationVersionCode=328`

---

## 2. API Endpoints & Capabilities

### Member & Authentication
- `POST /np/exerciser/login`: Authenticate with `username` and `password`. Returns session payload containing `uuid`, `homeClubUuid`, `chainUuid`, `egymAccountId`, and sets `JSESSIONID`.
- `GET /np/exerciser/{uuid}/profile`: Full account profile (sanitized to remove internal passcodes `clientLoginPasscode`, `picturePassword`).
- `POST /np/exerciser/{uuid}`: Update profile fields. **Caution**: A partial POST without `homeClub` causes Netpulse to reassign or wipe the member's home club. Always resend `homeClub=<uuid>`.
- `GET /np/exerciser/{uuid}/membership`: Contract details, start/end dates, agreement number, remaining days.

### Classes & Bookings (GroupX)
- `GET /np/company/{club_uuid}/classes?startDateTime={epoch_ms}&endDateTime={epoch_ms}&exerciserUuid={uuid}`: Returns bookable course list.
- `GET /np/company/{club_uuid}/class/{class_id}`: Course details, instructor, capacity, and current bookings.
- `GET /np/exerciser/{uuid}/schedule?startDateTime={epoch_ms}&endDateTime={epoch_ms}`: Member's booked courses.
- `POST /np/company/{club_uuid}/class/{class_id}/addExerciser`: Book course (`exerciserUuid={uuid}`, optional `spot={num}`).
- `POST /np/company/{club_uuid}/class/{class_id}/removeExerciser`: Cancel booking.
- `POST /np/company/{club_uuid}/class/{class_id}/waitlist/addExerciser`: Join course waitlist.
- `POST /np/company/{club_uuid}/class/{class_id}/waitlist/removeExerciser`: Leave course waitlist.

### Check-in History & Visits
- `GET /np/exercisers/{uuid}/check-ins/history?endDate={iso_timestamp}`: Historical gym check-in records with studio location and duration (in milliseconds).
- `GET /np/exercisers/{uuid}/latest-check-in`: Most recent check-in timestamp and timezone.

### EGYM BioAge & Body Metrics
- `GET /analysis/api/v1.0/exercisers/{uuid}/bioage`: EGYM Fitness Hub / bioimpedance analysis data:
  - Total BioAge (`totalDetails.totalBioAge.value`)
  - Metabolic BioAge, BMI, Body Fat % (`metabolicDetails`)
  - Cardio BioAge, Resting Heart Rate, Blood Pressure, VO2 Max (`cardioDetails`)
- `GET /analysis/api/v1.0/exercisers/{uuid}/activitylevels`: Current EGYM tier (wood, silver, gold, etc.), points, and maintenance target.

---

## 3. Member Visibility & Real-Time Presence Findings

### Privacy & Access Control Boundaries
| Target Endpoint | Querying Own UUID | Querying Another Member's UUID |
| :--- | :--- | :--- |
| `/np/exercisers/{uuid}/check-ins/history` | `200 OK` (Full visit log) | `403 Forbidden` (Access denied) |
| `/np/exercisers/{uuid}/latest-check-in` | `200 OK` (Timestamp) | `403 Forbidden` (Access denied) |
| `/np/exerciser/{uuid}/profile` | `200 OK` (Profile fields) | `403 Forbidden` (Access denied) |
| `/analysis/api/v1.0/exercisers/{uuid}/bioage` | `200 OK` (Health stats) | `403 Forbidden` (Access denied) |
| `/analysis/api/v1.0/exercisers/{uuid}/ranking` | `200 OK` (Rank & points) | `403 Forbidden` (Access denied) |
| `/np/exercisers/{uuid}/brief-info` | `200 OK` | **`200 OK` (Public directory)** |
| `/analysis/api/v1.0/exercisers/{own_uuid}/ranking/leaderboard` | `200 OK` | **`200 OK` (All club members)** |

### Discovery: Identity Unmasking via Brief-Info
1. The studio leaderboard endpoint (`/analysis/api/v1.0/exercisers/{own_uuid}/ranking/leaderboard`) exposes the monthly ranking of all club members. By default, it masks last names:
   ```json
   {
     "exerciserId": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
     "exerciserName": "Alex M.",
     "points": 29340,
     "exerciserIconUrl": "https://galaxy.cdn.egym.com/avatar-scaled/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d.jpg"
   }
   ```
2. Calling the undocumented `/np/exercisers/{exerciser_id}/brief-info` endpoint with the member's UUID returns their **unmasked full name** and high-resolution CDN profile photo:
   ```json
   {
     "uuid": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
     "firstName": "Alex",
     "lastName": "Mustermann",
     "homeGymLocationId": "b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e",
     "homeGymLocationName": "Frankfurt – MyZeil",
     "nickname": null,
     "imageUrl": "https://galaxy.cdn.egym.com/avatar-scaled/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d.jpg"
   }
   ```

### Real-Time Workout & Presence Detection via Point Deltas
Since there is no public "who is currently checked in" or "turnstile checkout" endpoint:
1. **Mechanism**: EGYM smart strength machines, studio cardio equipment, and gym check-ins award activity points immediately upon completion.
2. **Algorithm**:
   - Query the club leaderboard (`ff_leaderboard`) and save a point snapshot to local cache.
   - On subsequent checks, compute $\Delta \text{points} = \text{points}_{\text{current}} - \text{points}_{\text{previous}}$ for each member.
   - Any member with $\Delta \text{points} > 0$ has actively exercised or checked into the studio during the interval.
   - Query `brief-info` for detected members to surface their full names and profile photos.
   - Compute club standing (rank # and percentile), activity estimation, and leaderboard gap.
3. **Activity Estimation Model**:
   - `+10 – 19 pts`: Exercise Set / Check-in Badge
   - `+20 – 49 pts`: Smart Strength Machine Set
   - `+50 – 99 pts`: Smart Strength Rotation / Cardio Block
   - `+100 – 199 pts`: Full EGYM Circuit / High-Intensity Set
   - `+200+ pts`: Extended Workout / Multi-Circuit

---

## 4. MCP Tools & CLI Reference

### `ff_member_info(exerciser_id: str)`
- **Purpose**: Look up any member's identity using their UUID.
- **Returns**: `first_name`, `last_name`, `full_name`, `home_club_name`, `home_club_uuid`, `nickname`, `avatar_url`.

### `ff_active_trainers(limit: int = 50, reset_cache: bool = False)`
- **Purpose**: Detect studio members currently training based on point increases since the last snapshot.
- **Parameters**:
  - `limit`: Maximum number of active members to return (default 50).
  - `reset_cache`: Set to `true` to wipe the baseline and start a fresh tracking interval.
- **Returns**:
  - `last_checked`: Timestamp of the prior baseline.
  - `current_check`: Timestamp of the current observation.
  - `active_count`: Total active members detected.
  - `active_trainers`: List of active trainers with `name`, `leaderboard_name`, `points_gained`, `current_points`, `previous_points`, and `avatar_url`.

### CLI Activity Stream (`tail -f`) & Mattermost Integration
The CLI tool `scripts/tail_members.py` (or `uv run fitness-first-tail`) streams member events in real-time and supports optional Mattermost notifications:
- Continuous polling loop defaulting to 60s (configurable via `-i`/`--interval` or `FITNESS_FIRST_POLL_INTERVAL`).
- Exponential error backoff on transient network drops or API errors (60s -> 120s -> 240s -> max 300s) to prevent spamming the backend.
- Automatic re-authentication on 401/403 session expiration so long-running streams continue uninterrupted.
- Terminal styling with ANSI colors and formatted metadata cards.
- Optional newline-delimited JSON (`--json`) output.
- Mattermost incoming webhook (`--mattermost-webhook` / `MATTERMOST_WEBHOOK_URL`) or REST API token forwarding with two-column attachments and CDN avatars.

---

## 5. Hermes Agent Skill Architecture

This repository is dual-packaged as an MCP server and a standalone Hermes Skill conforming to Nous Research Hermes standards.

### Hub Installation
```bash
hermes skills install danielmain/fitness-first-germany-mcp/skills/fitness-first-germany
```

### Self-Contained Execution & Security Compliance
- **Zero-Dependency CLI**: The skill bundles `skills/fitness-first-germany/scripts/ff_cli.py` and `client.py`, using standard Python libraries with no external packages required.
- **Skills Guard Clean**: Strictly adheres to Hermes `skills_guard` security patterns, passing with `Verdict: safe` (no raw secret file accesses or unauthorized path traversals).
- **Conversational Onboarding**: When credentials are missing, Hermes prompts the user conversationally in chat and saves them securely to `~/.config/fitness-first-germany/auth.json` (chmod 600).
- **Dual Support**: Works seamlessly via Hermes `terminal` tool without requiring an MCP server process, or as an MCP server via FastMCP tool calling.
