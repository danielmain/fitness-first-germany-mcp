"""MCP tools for Fitness First Germany."""

from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from fitness_first_germany_mcp.client import FitnessFirstClient, FitnessFirstError

load_dotenv()

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)

mcp = FastMCP(
    "fitness-first-germany",
    instructions=(
        "Fitness First Germany member tools: upcoming courses, your schedule, "
        "booking, waitlist, clubs, membership, check-ins, activity level, "
        "body measurements, notifications, club leaderboard, and profile edits. "
        "Write tools do nothing until confirm is true. "
        "Profile saves always resend the current home club. "
        "Use the class id and club_uuid returned by ff_upcoming_classes when booking. "
        "Credentials come from FITNESS_FIRST_EMAIL and FITNESS_FIRST_PASSWORD."
    ),
)

_client: FitnessFirstClient | None = None


def get_client() -> FitnessFirstClient:
    global _client
    if _client is None:
        _client = FitnessFirstClient.from_env()
    return _client


def set_client(client: FitnessFirstClient | None) -> None:
    global _client
    _client = client


def _run(func) -> dict[str, Any]:
    try:
        return func()
    except FitnessFirstError as error:
        payload: dict[str, Any] = {"error": str(error)}
        if error.status is not None:
            payload["status"] = error.status
        return payload


def _needs_confirm(confirm: bool, action: str) -> dict[str, Any] | None:
    if confirm:
        return None
    return {
        "confirmed": False,
        "applied": False,
        "message": f"Not applied. Call again with confirm=true to {action}.",
    }


@mcp.tool(annotations=READ)
def ff_account() -> dict[str, Any]:
    """Show the signed-in member, home club, and membership type."""
    return _run(lambda: get_client().account())


@mcp.tool(annotations=READ)
def ff_upcoming_classes(
    days: int = 14,
    club_uuid: str | None = None,
    club_name: str | None = None,
) -> dict[str, Any]:
    """List bookable courses from today through the next days (1-60).

    Defaults to the home club. Pass club_uuid or a club name such as "Fellbach".
    Times are in the member's club timezone.
    """
    return _run(lambda: get_client().upcoming_classes(days, club_uuid, club_name))


@mcp.tool(annotations=READ)
def ff_class_details(class_id: str, club_uuid: str | None = None) -> dict[str, Any]:
    """Get one course. class_id comes from ff_upcoming_classes and includes a colon."""
    return _run(lambda: get_client().class_details(class_id, club_uuid))


@mcp.tool(annotations=READ)
def ff_my_schedule(days: int = 14) -> dict[str, Any]:
    """List courses already booked by the signed-in member."""
    return _run(lambda: get_client().my_schedule(days))


@mcp.tool(annotations=WRITE)
def ff_book_class(
    class_id: str,
    confirm: bool = False,
    club_uuid: str | None = None,
    spot: str | None = None,
) -> dict[str, Any]:
    """Book a course. Does nothing unless confirm is true. spot is optional."""
    pending = _needs_confirm(confirm, f"book class {class_id}")
    if pending:
        return pending
    return _run(lambda: get_client().book_class(class_id, club_uuid, spot))


@mcp.tool(annotations=WRITE)
def ff_cancel_class(class_id: str, confirm: bool = False, club_uuid: str | None = None) -> dict[str, Any]:
    """Cancel a booked course. Does nothing unless confirm is true."""
    pending = _needs_confirm(confirm, f"cancel class {class_id}")
    if pending:
        return pending
    return _run(lambda: get_client().cancel_class(class_id, club_uuid))


@mcp.tool(annotations=WRITE)
def ff_join_waitlist(class_id: str, confirm: bool = False, club_uuid: str | None = None) -> dict[str, Any]:
    """Join a course waitlist. Does nothing unless confirm is true."""
    pending = _needs_confirm(confirm, f"join the waitlist for class {class_id}")
    if pending:
        return pending
    return _run(lambda: get_client().join_waitlist(class_id, club_uuid))


@mcp.tool(annotations=WRITE)
def ff_leave_waitlist(class_id: str, confirm: bool = False, club_uuid: str | None = None) -> dict[str, Any]:
    """Leave a course waitlist. Does nothing unless confirm is true."""
    pending = _needs_confirm(confirm, f"leave the waitlist for class {class_id}")
    if pending:
        return pending
    return _run(lambda: get_client().leave_waitlist(class_id, club_uuid))


@mcp.tool(annotations=READ)
def ff_clubs(query: str | None = None, limit: int = 30) -> dict[str, Any]:
    """Search Fitness First clubs by name or city. Returns uuid, name, city, and address."""
    return _run(lambda: get_client().clubs(query, limit))


@mcp.tool(annotations=READ)
def ff_membership() -> dict[str, Any]:
    """Show the membership type and contract dates."""
    return _run(lambda: get_client().membership())


@mcp.tool(annotations=READ)
def ff_leaderboard(size: int = 50, next_page_token: str | None = None) -> dict[str, Any]:
    """Get the club ranking leaderboard of members with points and profile pictures.

    Returns member names (first name + last initial), exerciser UUIDs, points, and CDN avatar URLs.
    size: Number of members to return (1-100, default 50).
    next_page_token: Optional token for the next page of results.
    """
    return _run(lambda: get_client().leaderboard(size, next_page_token))


@mcp.tool(annotations=READ)
def ff_ranking() -> dict[str, Any]:
    """Show the signed-in member's personal rank, points, and total club members."""
    return _run(lambda: get_client().ranking())


@mcp.tool(annotations=READ)
def ff_check_ins(limit: int = 30, end_date: str | None = None) -> dict[str, Any]:
    """Get the member's gym visits / check-in history.

    Returns the visit date, club name, and address.
    limit: Max number of check-ins to return (1-100, default 30).
    end_date: Optional ISO date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) to retrieve history before.
    """
    return _run(lambda: get_client().check_ins(limit, end_date))


@mcp.tool(annotations=READ)
def ff_latest_check_in() -> dict[str, Any]:
    """Show the signed-in member's most recent gym check-in date and timezone."""
    return _run(lambda: get_client().latest_check_in())


@mcp.tool(annotations=READ)
def ff_activity_level() -> dict[str, Any]:
    """Show the member's current EGYM activity level, points, days left, and maintenance target."""
    return _run(lambda: get_client().activity_level())


@mcp.tool(annotations=READ)
def ff_body_measurements() -> dict[str, Any]:
    """Show the member's body weight and EGYM Fitness Hub / bioimpedance scale measurements.

    Returns weight (kg), height (cm), body fat percentage, BMI, metabolic age,
    total BioAge, cardio age, resting heart rate, blood pressure, and VO2 max.
    """
    return _run(lambda: get_client().body_measurements())


@mcp.tool(annotations=READ)
def ff_notifications() -> dict[str, Any]:
    """Get notifications and announcements from Fitness First."""
    return _run(lambda: get_client().notifications())


@mcp.tool(annotations=READ)
def ff_profile() -> dict[str, Any]:
    """Show the editable profile. Login passcodes are removed."""
    return _run(lambda: get_client().profile())


@mcp.tool(annotations=WRITE)
def ff_update_profile(
    confirm: bool = False,
    firstname: str | None = None,
    lastname: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    about_me: str | None = None,
    birthday: str | None = None,
    gender: str | None = None,
    height: float | None = None,
    weight: float | None = None,
    measurement_unit: str | None = None,
    home_club_uuid: str | None = None,
    privacy: str | None = None,
    timezone: str | None = None,
    street1: str | None = None,
    street2: str | None = None,
    city: str | None = None,
    country: str | None = None,
    state_or_province: str | None = None,
    postal_code: str | None = None,
    email_goal_notice: bool | None = None,
    email_challenge_notice: bool | None = None,
    email_system_message: bool | None = None,
    email_reward_update_notice: bool | None = None,
    email_workout_tracking_notice: bool | None = None,
) -> dict[str, Any]:
    """Update profile fields that are provided. Does nothing unless confirm is true.

    birthday uses MM/DD/YYYY. measurement_unit is M or I. privacy is Public or Private.
    home_club_uuid changes the home club. Other omitted fields stay as they are.
    """
    updates = {
        key: value
        for key, value in {
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "phone_number": phone_number,
            "about_me": about_me,
            "birthday": birthday,
            "gender": gender,
            "height": height,
            "weight": weight,
            "measurement_unit": measurement_unit,
            "home_club_uuid": home_club_uuid,
            "privacy": privacy,
            "timezone": timezone,
            "street1": street1,
            "street2": street2,
            "city": city,
            "country": country,
            "state_or_province": state_or_province,
            "postal_code": postal_code,
            "email_goal_notice": email_goal_notice,
            "email_challenge_notice": email_challenge_notice,
            "email_system_message": email_system_message,
            "email_reward_update_notice": email_reward_update_notice,
            "email_workout_tracking_notice": email_workout_tracking_notice,
        }.items()
        if value is not None
    }
    if not updates:
        return {"error": "Pass at least one field to change."}
    pending = _needs_confirm(confirm, f"update profile fields: {', '.join(updates)}")
    if pending:
        pending["fields"] = updates
        return pending
    return _run(lambda: get_client().update_profile(updates))


@mcp.tool(annotations=WRITE)
def ff_change_password(old_password: str, new_password: str, confirm: bool = False) -> dict[str, Any]:
    """Change the Fitness First password. Does nothing unless confirm is true."""
    pending = _needs_confirm(confirm, "change the password")
    if pending:
        return pending
    return _run(lambda: get_client().change_password(old_password, new_password))


def main() -> None:
    mcp.run()
