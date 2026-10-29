"""HTTP client for the Fitness First Germany Netpulse brand API."""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_BASE_URL = "https://fitnessfirst.netpulse.com"
DEFAULT_TIMEZONE = "Europe/Berlin"


def get_auth_file_path() -> Path:
    return Path.home() / ".config" / "fitness-first-germany" / "auth.json"


def load_auth_config() -> dict[str, str]:
    path = get_auth_file_path()
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_auth_config(email: str, password: str, base_url: str = DEFAULT_BASE_URL) -> None:
    path = get_auth_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"email": email.strip(), "password": password, "base_url": base_url}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass

# Returned by GET /profile. Never send these back, and never show the secrets.
_HIDDEN_PROFILE_KEYS = ("clientLoginPasscode", "picturePassword", "clientLoginId")

_PROFILE_FIELDS = (
    "firstname",
    "lastname",
    "email",
    "birthday",
    "gender",
    "height",
    "weight",
    "measurementUnit",
    "phoneNumber",
    "aboutMe",
    "privacy",
    "timezone",
)

_EMAIL_PREF_FIELDS = (
    "emailGoalNotice",
    "emailChallengeNotice",
    "emailSystemMessage",
    "emailRewardUpdateNotice",
    "emailWorkoutTrackingNotice",
)

_ADDRESS_FIELDS = ("street1", "street2", "city", "country", "stateOrProvince", "postalCode")

# Tool argument names -> profile JSON names.
UPDATE_FIELDS = {
    "firstname": "firstname",
    "lastname": "lastname",
    "email": "email",
    "birthday": "birthday",
    "gender": "gender",
    "height": "height",
    "weight": "weight",
    "measurement_unit": "measurementUnit",
    "phone_number": "phoneNumber",
    "about_me": "aboutMe",
    "privacy": "privacy",
    "timezone": "timezone",
    "home_club_uuid": "homeClubUuid",
    "email_goal_notice": "emailGoalNotice",
    "email_challenge_notice": "emailChallengeNotice",
    "email_system_message": "emailSystemMessage",
    "email_reward_update_notice": "emailRewardUpdateNotice",
    "email_workout_tracking_notice": "emailWorkoutTrackingNotice",
    "street1": "street1",
    "street2": "street2",
    "city": "city",
    "country": "country",
    "state_or_province": "stateOrProvince",
    "postal_code": "postalCode",
}


class FitnessFirstError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Drop login secrets that the profile document includes."""
    return {key: value for key, value in profile.items() if key not in _HIDDEN_PROFILE_KEYS}


def profile_form(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, str]:
    """Build a full profile form.

    A partial POST clears the home club. The API then assigns another club.
    Every save resends the current profile and sets ``homeClub`` to the UUID.
    """
    merged = dict(current)
    prefs = dict(merged.get("emailPreference") or {})
    address = dict(merged.get("address") or {})

    for name, value in updates.items():
        if name in _EMAIL_PREF_FIELDS:
            prefs[name] = value
        elif name in _ADDRESS_FIELDS:
            address[name] = value
        else:
            merged[name] = value

    home = merged.get("homeClubUuid")
    if not home:
        raise FitnessFirstError("Profile has no home club, so it cannot be saved safely.")

    form: dict[str, str] = {"homeClub": str(home)}
    for field in _PROFILE_FIELDS:
        value = merged.get(field)
        form[field] = "" if value is None else str(value)
    for field in _EMAIL_PREF_FIELDS:
        form[field] = "true" if prefs.get(field) else "false"
    for field in _ADDRESS_FIELDS:
        value = address.get(field)
        form[field] = "" if value is None else str(value)
    return form


def summarize_class(item: dict[str, Any], timezone: str) -> dict[str, Any]:
    brief = item.get("brief") or item
    attendee = item.get("attendeeDetails") or {}
    zone = _zone(timezone)
    start = _epoch_ms(brief.get("startDateTime"), zone)
    end = _epoch_ms(brief.get("endDateTime"), zone)
    capacity = brief.get("maxCapacity")
    booked = brief.get("totalBooked")
    free = None
    if isinstance(capacity, int) and isinstance(booked, int):
        free = capacity - booked
    instructor = brief.get("instructor") or {}
    activity = brief.get("activity") or {}
    return {
        "id": brief.get("id"),
        "name": brief.get("name"),
        "club_uuid": brief.get("clubUuid"),
        "starts_at": start,
        "ends_at": end,
        "instructor": instructor.get("fullName") or None,
        "description": activity.get("description") or None,
        "booked": booked,
        "capacity": capacity,
        "spots_free": free,
        "waitlist_booked": brief.get("waitlistBooked"),
        "waitlist_capacity": brief.get("waitlistCapacity"),
        "cancelled": bool(brief.get("cancelled")),
        "already_booked": bool(brief.get("booked") or attendee.get("booked")),
        "waitlisted": bool(brief.get("waitlisted") or attendee.get("waitlistBooked")),
        "available_actions": attendee.get("availableActions") or [],
    }


def summarize_classes(items: list[Any], timezone: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    classes: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        summary = summarize_class(item, timezone)
        class_id = summary.get("id")
        if isinstance(class_id, str):
            if class_id in seen:
                continue
            seen.add(class_id)
        classes.append(summary)
    classes.sort(key=lambda row: row.get("starts_at") or "")
    return classes


def compact_club(club: dict[str, Any]) -> dict[str, Any]:
    address = club.get("address") or {}
    line = ", ".join(
        part
        for part in (
            address.get("addressLine1"),
            address.get("postalCode"),
            address.get("city"),
        )
        if part
    )
    return {
        "uuid": club.get("uuid"),
        "name": club.get("name"),
        "city": address.get("city"),
        "address": line or None,
        "phone": club.get("phone"),
        "url": club.get("url"),
        "timezone": club.get("timezone"),
    }


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _epoch_ms(value: Any, zone: ZoneInfo) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value / 1000, zone).isoformat(timespec="minutes")


def _window(timezone: str, days: int) -> tuple[int, int]:
    zone = _zone(timezone)
    start = datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=days)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


class FitnessFirstClient:
    def __init__(
        self,
        email: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        opener: urllib.request.OpenerDirector | None = None,
    ):
        self.email = email
        self.password = password
        self.base_url = base_url.rstrip("/")
        self._cookies = CookieJar()
        self._opener = opener or urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies)
        )
        self._lock = threading.Lock()
        self._session: dict[str, Any] | None = None
        self._clubs: list[dict[str, Any]] | None = None

    @classmethod
    def from_env(cls) -> FitnessFirstClient:
        email = os.environ.get("FITNESS_FIRST_EMAIL", "").strip()
        password = os.environ.get("FITNESS_FIRST_PASSWORD", "")
        base = os.environ.get("FITNESS_FIRST_BASE_URL", "").strip()
        if not email or not password:
            stored = load_auth_config()
            email = email or stored.get("email", "").strip()
            password = password or stored.get("password", "")
            base = base or stored.get("base_url", "").strip()
        if not email or not password:
            raise FitnessFirstError(
                "Set FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD before starting the server."
            )
        return cls(email, password, base or DEFAULT_BASE_URL)

    @property
    def timezone(self) -> str:
        if self._session:
            return self._session.get("timezone") or DEFAULT_TIMEZONE
        return DEFAULT_TIMEZONE

    @property
    def exerciser_uuid(self) -> str:
        self._ensure_session()
        assert self._session is not None
        return self._session["uuid"]

    @property
    def home_club_uuid(self) -> str:
        self._ensure_session()
        assert self._session is not None
        return self._session["homeClubUuid"]

    def account(self) -> dict[str, Any]:
        self._ensure_session()
        assert self._session is not None
        session = self._session
        return {
            "uuid": session.get("uuid"),
            "first_name": session.get("firstName"),
            "last_name": session.get("lastName"),
            "home_club_name": session.get("homeClubName"),
            "home_club_uuid": session.get("homeClubUuid"),
            "chain_name": session.get("chainName"),
            "timezone": session.get("timezone"),
            "membership_type": session.get("membershipType"),
            "verified": session.get("verified"),
        }

    def profile(self) -> dict[str, Any]:
        self._ensure_session()
        body = self._request("GET", f"/np/exerciser/{self.exerciser_uuid}/profile")
        if not isinstance(body, dict):
            raise FitnessFirstError("Profile response was not an object.")
        return public_profile(body)

    def update_profile(self, updates: dict[str, Any]) -> dict[str, Any]:
        unknown = sorted(set(updates) - set(UPDATE_FIELDS.values()) - set(UPDATE_FIELDS))
        if unknown:
            raise FitnessFirstError(f"Unknown profile fields: {', '.join(unknown)}")
        mapped = {UPDATE_FIELDS.get(key, key): value for key, value in updates.items()}
        current = self.profile()
        form = profile_form(current, mapped)
        self._request("POST", f"/np/exerciser/{self.exerciser_uuid}", form=form)
        updated = self.profile()
        if updated.get("homeClubUuid") != form["homeClub"]:
            raise FitnessFirstError(
                "The profile save did not keep the home club. "
                f"Expected {form['homeClub']}, got {updated.get('homeClubUuid')}."
            )
        self._session = None
        self._ensure_session()
        return updated

    def change_password(self, old_password: str, new_password: str) -> dict[str, str]:
        if not old_password or not new_password:
            raise FitnessFirstError("Old and new passwords are required.")
        if old_password == new_password:
            raise FitnessFirstError("The new password is the same as the old password.")
        self._ensure_session()
        self._request(
            "POST",
            "/np/exerciser/changePassword",
            form={
                "email": self.email,
                "oldPassword": old_password,
                "newPassword": new_password,
                "confirmPassword": new_password,
            },
        )
        return {"status": "ok"}

    def clubs(self, query: str | None = None, limit: int = 30) -> dict[str, Any]:
        matches = [compact_club(club) for club in self._club_list()]
        if query:
            needle = query.casefold()
            matches = [
                club
                for club in matches
                if needle in (club.get("name") or "").casefold()
                or needle in (club.get("city") or "").casefold()
            ]
        total = len(matches)
        return {"total": total, "clubs": matches[:limit]}

    def resolve_club(self, club_uuid: str | None, club_name: str | None) -> str:
        if club_uuid:
            return club_uuid
        if not club_name:
            return self.home_club_uuid
        found = self.clubs(club_name, limit=20)["clubs"]
        exact = [club for club in found if (club.get("name") or "").casefold() == club_name.casefold()]
        chosen = exact or found
        if len(chosen) == 1:
            return str(chosen[0]["uuid"])
        if not chosen:
            raise FitnessFirstError(f"No club matches {club_name!r}.")
        names = ", ".join(f"{club['name']} ({club['uuid']})" for club in chosen[:8])
        raise FitnessFirstError(f"Several clubs match {club_name!r}: {names}")

    def upcoming_classes(
        self,
        days: int = 14,
        club_uuid: str | None = None,
        club_name: str | None = None,
    ) -> dict[str, Any]:
        days = _clamp_days(days)
        club = self.resolve_club(club_uuid, club_name)
        start, end = _window(self.timezone, days)
        query = urllib.parse.urlencode(
            {"startDateTime": start, "endDateTime": end, "exerciserUuid": self.exerciser_uuid}
        )
        body = self._request("GET", f"/np/company/{_path(club)}/classes?{query}")
        classes = summarize_classes(body if isinstance(body, list) else [], self.timezone)
        return {"club_uuid": club, "days": days, "count": len(classes), "classes": classes}

    def class_details(self, class_id: str, club_uuid: str | None = None) -> dict[str, Any]:
        club = club_uuid or self.home_club_uuid
        body = self._request("GET", f"/np/company/{_path(club)}/class/{_path(class_id)}")
        if not isinstance(body, dict):
            raise FitnessFirstError("Class response was not an object.")
        return summarize_class(body, self.timezone)

    def my_schedule(self, days: int = 14) -> dict[str, Any]:
        days = _clamp_days(days)
        start, end = _window(self.timezone, days)
        query = urllib.parse.urlencode({"startDateTime": start, "endDateTime": end})
        body = self._request("GET", f"/np/exerciser/{self.exerciser_uuid}/schedule?{query}")
        classes = summarize_classes(body if isinstance(body, list) else [], self.timezone)
        return {"days": days, "count": len(classes), "classes": classes}

    def book_class(self, class_id: str, club_uuid: str | None = None, spot: str | None = None) -> dict[str, Any]:
        return self._class_action(class_id, club_uuid, "addExerciser", spot)

    def cancel_class(self, class_id: str, club_uuid: str | None = None) -> dict[str, Any]:
        return self._class_action(class_id, club_uuid, "removeExerciser")

    def join_waitlist(self, class_id: str, club_uuid: str | None = None) -> dict[str, Any]:
        return self._class_action(class_id, club_uuid, "waitlist/addExerciser")

    def leave_waitlist(self, class_id: str, club_uuid: str | None = None) -> dict[str, Any]:
        return self._class_action(class_id, club_uuid, "waitlist/removeExerciser")

    def membership(self) -> dict[str, Any]:
        body = self._request("GET", f"/np/exerciser/{self.exerciser_uuid}/membership")
        if not isinstance(body, dict):
            raise FitnessFirstError("Membership response was not an object.")
        return {
            "membership_type": body.get("membershipType"),
            "membership_subtype": body.get("membershipSubtype"),
            "contract_signed": body.get("contractSignedDate"),
            "contract_end": body.get("contractEndDate"),
            "expired": body.get("expired"),
            "remaining_days": body.get("remainingDays"),
            "agreement_number": body.get("agreementNumber"),
        }

    def leaderboard(self, size: int = 50, next_page_token: str | None = None) -> dict[str, Any]:
        clamped_size = max(1, min(size, 100))
        params: dict[str, Any] = {"size": clamped_size}
        if next_page_token:
            params["nextPageToken"] = next_page_token
        query = urllib.parse.urlencode(params)
        body = self._request(
            "GET",
            f"/analysis/api/v1.0/exercisers/{self.exerciser_uuid}/ranking/leaderboard?{query}",
        )
        if not isinstance(body, dict):
            raise FitnessFirstError("Leaderboard response was not an object.")
        raw_items = body.get("items")
        items = []
        if isinstance(raw_items, list):
            for item in raw_items:
                if isinstance(item, dict):
                    items.append({
                        "exerciser_id": item.get("exerciserId"),
                        "name": item.get("exerciserName"),
                        "points": item.get("points"),
                        "avatar_url": item.get("exerciserIconUrl") or None,
                    })
        return {
            "total_users": body.get("totalNumberOfUsers"),
            "next_page_token": body.get("nextPageToken"),
            "count": len(items),
            "items": items,
        }

    def ranking(self) -> dict[str, Any]:
        body = self._request("GET", f"/analysis/api/v1.0/exercisers/{self.exerciser_uuid}/ranking")
        if not isinstance(body, dict):
            raise FitnessFirstError("Ranking response was not an object.")
        rank = body.get("rank") if isinstance(body.get("rank"), dict) else {}
        points = body.get("points") if isinstance(body.get("points"), dict) else {}
        return {
            "exerciser_id": body.get("exerciserId"),
            "name": body.get("exerciserName"),
            "rank": rank.get("value"),
            "points": points.get("value"),
            "average_rank": body.get("averageRank"),
            "total_users": body.get("totalNumberOfUsers"),
            "avatar_url": body.get("exerciserIconUrl") or None,
        }

    def member_info(self, exerciser_id: str) -> dict[str, Any]:
        """Look up public/club details of another member by exerciser UUID."""
        if not exerciser_id:
            raise FitnessFirstError("exerciser_id is required.")
        body = self._request("GET", f"/np/exercisers/{_path(exerciser_id)}/brief-info")
        if not isinstance(body, dict):
            raise FitnessFirstError("Member brief-info response was not an object.")
        first = body.get("firstName") or ""
        last = body.get("lastName") or ""
        full = f"{first} {last}".strip() or None
        return {
            "exerciser_id": body.get("uuid") or exerciser_id,
            "first_name": body.get("firstName") or None,
            "last_name": body.get("lastName") or None,
            "full_name": full,
            "home_club_uuid": body.get("homeGymLocationId"),
            "home_club_name": body.get("homeGymLocationName"),
            "nickname": body.get("nickname"),
            "avatar_url": body.get("imageUrl"),
        }

    def active_trainers(
        self,
        limit: int = 50,
        reset_cache: bool = False,
        cache_path: str | None = None,
    ) -> dict[str, Any]:
        """Detect club members who are currently training in the studio.

        Compares current leaderboard points against the previously saved snapshot.
        Members whose points increased since the last check have logged workouts
        or check-in activity. Their full names and profile photos are resolved via brief-info.
        """
        clamped_limit = max(1, min(limit, 100))
        now_dt = datetime.now(_zone(self.timezone))
        now_iso = now_dt.isoformat(timespec="seconds")

        cache_file = cache_path or os.environ.get("FITNESS_FIRST_CACHE_PATH")
        if not cache_file:
            cache_dir = os.path.expanduser("~/.cache/fitness_first_germany")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f"leaderboard_snapshot_{self.home_club_uuid}.json")

        previous_snapshot: dict[str, Any] = {}
        if not reset_cache and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    previous_snapshot = json.load(f)
            except Exception:
                previous_snapshot = {}

        prev_scores: dict[str, int] = previous_snapshot.get("scores") or {}
        prev_time: str | None = previous_snapshot.get("timestamp")

        lb = self.leaderboard(size=100)
        items = lb.get("items") or []

        current_scores: dict[str, int] = {}
        active_list: list[dict[str, Any]] = []

        for item in items:
            uid = item.get("exerciser_id")
            pts = item.get("points")
            if not uid or not isinstance(pts, int):
                continue
            current_scores[uid] = pts

            if prev_scores and uid in prev_scores:
                old_pts = prev_scores[uid]
                delta = pts - old_pts
                if delta > 0:
                    full_name = item.get("name")
                    avatar = item.get("avatar_url")
                    try:
                        info = self.member_info(uid)
                        if info.get("full_name"):
                            full_name = info["full_name"]
                        if info.get("avatar_url"):
                            avatar = info["avatar_url"]
                    except Exception:
                        pass

                    active_list.append({
                        "exerciser_id": uid,
                        "name": full_name,
                        "leaderboard_name": item.get("name"),
                        "points_gained": delta,
                        "current_points": pts,
                        "previous_points": old_pts,
                        "avatar_url": avatar,
                    })

        active_list.sort(key=lambda row: row.get("points_gained") or 0, reverse=True)

        try:
            cache_dir = os.path.dirname(cache_file)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": now_iso,
                    "club_uuid": self.home_club_uuid,
                    "scores": current_scores,
                }, f, indent=2)
        except Exception:
            pass

        msg = None
        if not prev_scores:
            msg = "Initial snapshot created. Run again later to detect members who gained points while training."

        return {
            "last_checked": prev_time,
            "current_check": now_iso,
            "active_count": len(active_list),
            "active_trainers": active_list[:clamped_limit],
            "snapshot_saved": True,
            "message": msg,
        }

    def check_ins(self, limit: int = 30, end_date: str | None = None) -> dict[str, Any]:
        clamped_limit = max(1, min(limit, 100))
        if not end_date:
            end_date = datetime.now(_zone(self.timezone)).strftime("%Y-%m-%dT%H:%M:%S")
        query = urllib.parse.urlencode({"endDate": end_date})
        body = self._request(
            "GET",
            f"/np/exercisers/{self.exerciser_uuid}/check-ins/history?{query}",
        )
        if not isinstance(body, dict):
            raise FitnessFirstError("Check-ins response was not an object.")
        raw_list = body.get("checkIns") if isinstance(body.get("checkIns"), list) else []
        items = [
            {
                "date": entry.get("checkInDate"),
                "club_name": entry.get("gymLocationName"),
                "club_address": entry.get("gymLocationAddress"),
                "timezone": entry.get("timezone"),
            }
            for entry in raw_list[:clamped_limit]
            if isinstance(entry, dict)
        ]
        return {
            "count": len(items),
            "total_returned": len(raw_list),
            "check_ins": items,
        }

    def latest_check_in(self) -> dict[str, Any]:
        body = self._request("GET", f"/np/exercisers/{self.exerciser_uuid}/latest-check-in")
        if not isinstance(body, dict):
            raise FitnessFirstError("Latest check-in response was not an object.")
        return {
            "date": body.get("checkInDate"),
            "timezone": body.get("timezone"),
        }

    def activity_level(self) -> dict[str, Any]:
        body = self._request(
            "GET",
            f"/analysis/api/v1.0/exercisers/{self.exerciser_uuid}/activitylevels",
        )
        if not isinstance(body, dict):
            raise FitnessFirstError("Activity level response was not an object.")
        return {
            "level": body.get("level"),
            "points": body.get("points"),
            "maintain_points": body.get("maintainPoints"),
            "days_left": body.get("daysLeft"),
            "goal": body.get("goal"),
        }

    def body_measurements(self) -> dict[str, Any]:
        profile = self.profile()
        bio = self._request("GET", f"/analysis/api/v1.0/exercisers/{self.exerciser_uuid}/bioage")
        if not isinstance(bio, dict):
            bio = {}
        tot = bio.get("totalDetails") if isinstance(bio.get("totalDetails"), dict) else {}
        meta = bio.get("metabolicDetails") if isinstance(bio.get("metabolicDetails"), dict) else {}
        card = bio.get("cardioDetails") if isinstance(bio.get("cardioDetails"), dict) else {}

        def _val(d: dict[str, Any], key: str) -> Any:
            obj = d.get(key)
            if isinstance(obj, dict):
                return obj.get("value")
            return None

        systolic = _val(card, "systolicPressure")
        diastolic = _val(card, "diastolicPressure")
        bp = f"{systolic}/{diastolic}" if systolic is not None and diastolic is not None else None
        tot_age = tot.get("totalBioAge") if isinstance(tot.get("totalBioAge"), dict) else {}

        return {
            "weight_kg": profile.get("weight"),
            "height_cm": profile.get("height"),
            "bmi": _val(meta, "bmi"),
            "body_fat_percentage": _val(meta, "bodyFat"),
            "metabolic_age": _val(meta, "metabolicAge"),
            "total_bio_age": _val(tot, "totalBioAge"),
            "cardio_age": _val(card, "cardioAge"),
            "resting_heart_rate": _val(card, "restingHeartRate"),
            "blood_pressure": bp,
            "vo2_max": _val(card, "vo2max"),
            "last_measured": tot_age.get("createdAt"),
        }

    def notifications(self) -> dict[str, Any]:
        body = self._request("GET", f"/np/exerciser/{self.exerciser_uuid}/notifications")
        if not isinstance(body, dict):
            raise FitnessFirstError("Notifications response was not an object.")
        data = body.get("data") if isinstance(body.get("data"), dict) else {}
        notifs = data.get("notifications") if isinstance(data.get("notifications"), list) else []
        return {
            "count": len(notifs),
            "notifications": notifs,
        }

    def _class_action(
        self,
        class_id: str,
        club_uuid: str | None,
        action: str,
        spot: str | None = None,
    ) -> dict[str, Any]:
        club = club_uuid or self.home_club_uuid
        form = {"exerciserUuid": self.exerciser_uuid}
        if spot:
            form["spot"] = spot
        body = self._request(
            "POST",
            f"/np/company/{_path(club)}/class/{_path(class_id)}/{action}",
            form=form,
        )
        if isinstance(body, dict) and "brief" in body:
            return summarize_class(body, self.timezone)
        if isinstance(body, dict):
            return {"status": body.get("status", "ok"), "class_id": class_id, "club_uuid": club}
        return {"status": "ok", "class_id": class_id, "club_uuid": club}

    def _club_list(self) -> list[dict[str, Any]]:
        if self._clubs is None:
            body = self._request("GET", "/np/company/children")
            if not isinstance(body, list):
                raise FitnessFirstError("Club list response was not a list.")
            self._clubs = [club for club in body if isinstance(club, dict)]
        return self._clubs

    def _ensure_session(self) -> None:
        if self._session is None:
            self.login()

    def login(self) -> dict[str, Any]:
        body = self._request(
            "POST",
            "/np/exerciser/login",
            form={"username": self.email, "password": self.password},
            retry=False,
            authenticated=False,
        )
        if not isinstance(body, dict) or not body.get("uuid") or not body.get("homeClubUuid"):
            raise FitnessFirstError("Login succeeded but did not return an exerciser or home club.")
        self._session = body
        return body

    def _request(
        self,
        method: str,
        path: str,
        form: dict[str, str] | None = None,
        retry: bool = True,
        authenticated: bool = True,
    ) -> Any:
        if authenticated and self._session is None and path != "/np/exerciser/login":
            self.login()
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "okhttp/4.12.0",
            "X-NP-API-Version": "1.5",
            "X-NP-APP-Version": "3.1",
            "X-NP-User-Agent": (
                "clientType=MOBILE_DEVICE; devicePlatform=ANDROID; "
                "deviceUid=fitness-first-germany-mcp; applicationName=Fitness First; "
                "applicationVersion=3.1; applicationVersionCode=328"
            ),
        }
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._lock:
                with self._opener.open(request, timeout=30) as response:
                    raw = response.read()
        except urllib.error.HTTPError as error:
            detail = _error_message(error)
            if error.code == 401 and retry and path != "/np/exerciser/login":
                self._session = None
                self.login()
                return self._request(method, path, form, retry=False, authenticated=False)
            raise FitnessFirstError(detail, error.code) from error
        except urllib.error.URLError as error:
            raise FitnessFirstError(f"Could not reach Fitness First: {error.reason}") from error
        if not raw:
            return {"status": "ok"}
        try:
            return json.loads(raw.decode())
        except json.JSONDecodeError as error:
            raise FitnessFirstError("Fitness First returned a non-JSON response.") from error


def _path(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _clamp_days(days: int) -> int:
    if days < 1 or days > 60:
        raise FitnessFirstError("days must be between 1 and 60.")
    return days


def _error_message(error: urllib.error.HTTPError) -> str:
    raw = error.read()
    try:
        body = json.loads(raw.decode())
    except Exception:
        body = None
    if isinstance(body, dict):
        message = body.get("message") or body.get("error")
        if message:
            return f"{error.code}: {message}"
    return f"Fitness First returned HTTP {error.code}."
