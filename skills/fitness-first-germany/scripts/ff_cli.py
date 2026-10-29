#!/usr/bin/env python3
"""Fitness First Germany CLI helper for Hermes Agent."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Support relative import when run as a standalone script inside skills/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from client import FitnessFirstClient, FitnessFirstError, save_auth_config, load_auth_config  # type: ignore


def get_client() -> FitnessFirstClient:
    return FitnessFirstClient.from_env()


def cmd_auth_save(args: argparse.Namespace) -> int:
    client = FitnessFirstClient(args.email, args.password)
    try:
        session = client.login()
        save_auth_config(args.email, args.password)
        info = {
            "status": "success",
            "message": f"Successfully authenticated as {session.get('name')} ({session.get('homeClubName')})",
            "user": {
                "name": session.get("name"),
                "email": session.get("email"),
                "uuid": session.get("uuid"),
                "home_club": session.get("homeClubName"),
                "home_club_uuid": session.get("homeClubUuid"),
            },
        }
        print(json.dumps(info, indent=2))
        return 0
    except FitnessFirstError as exc:
        print(json.dumps({"status": "error", "message": f"Authentication failed: {exc}"}, indent=2), file=sys.stderr)
        return 1


def cmd_auth_status(args: argparse.Namespace) -> int:
    try:
        client = get_client()
        client._ensure_session()
        session = client._session
        info = {
            "authenticated": True,
            "name": session.get("name") if session else None,
            "email": session.get("email") if session else None,
            "uuid": session.get("uuid") if session else None,
            "home_club": session.get("homeClubName") if session else None,
            "home_club_uuid": session.get("homeClubUuid") if session else None,
        }
        print(json.dumps(info, indent=2))
        return 0
    except FitnessFirstError as exc:
        print(json.dumps({"authenticated": False, "error": str(exc)}, indent=2))
        return 1


def cmd_classes(args: argparse.Namespace) -> int:
    client = get_client()
    classes = client.upcoming_classes(days=args.days, club_name=args.club)
    print(json.dumps(classes, indent=2))
    return 0


def cmd_class_details(args: argparse.Namespace) -> int:
    client = get_client()
    details = client.class_details(args.class_id)
    print(json.dumps(details, indent=2))
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    client = get_client()
    schedule = client.my_schedule(days=args.days)
    print(json.dumps(schedule, indent=2))
    return 0


def cmd_book(args: argparse.Namespace) -> int:
    if not args.confirm:
        print(json.dumps({
            "status": "confirmation_required",
            "message": f"Confirmation required to book class {args.class_id}. Re-run with --confirm."
        }, indent=2))
        return 2
    client = get_client()
    res = client.book_class(args.class_id, spot=args.spot)
    print(json.dumps(res, indent=2))
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    if not args.confirm:
        print(json.dumps({
            "status": "confirmation_required",
            "message": f"Confirmation required to cancel class {args.class_id}. Re-run with --confirm."
        }, indent=2))
        return 2
    client = get_client()
    res = client.cancel_class(args.class_id)
    print(json.dumps(res, indent=2))
    return 0


def cmd_waitlist_join(args: argparse.Namespace) -> int:
    if not args.confirm:
        print(json.dumps({
            "status": "confirmation_required",
            "message": f"Confirmation required to join waitlist for class {args.class_id}. Re-run with --confirm."
        }, indent=2))
        return 2
    client = get_client()
    res = client.join_waitlist(args.class_id)
    print(json.dumps(res, indent=2))
    return 0


def cmd_waitlist_leave(args: argparse.Namespace) -> int:
    if not args.confirm:
        print(json.dumps({
            "status": "confirmation_required",
            "message": f"Confirmation required to leave waitlist for class {args.class_id}. Re-run with --confirm."
        }, indent=2))
        return 2
    client = get_client()
    res = client.leave_waitlist(args.class_id)
    print(json.dumps(res, indent=2))
    return 0


def cmd_check_ins(args: argparse.Namespace) -> int:
    client = get_client()
    visits = client.check_ins(limit=args.limit)
    print(json.dumps(visits, indent=2))
    return 0


def cmd_latest_check_in(args: argparse.Namespace) -> int:
    client = get_client()
    latest = client.latest_check_in()
    print(json.dumps(latest, indent=2))
    return 0


def cmd_bioage(args: argparse.Namespace) -> int:
    client = get_client()
    bioage = client.body_measurements()
    print(json.dumps(bioage, indent=2))
    return 0


def cmd_activity(args: argparse.Namespace) -> int:
    client = get_client()
    activity = client.activity_level()
    print(json.dumps(activity, indent=2))
    return 0


def cmd_ranking(args: argparse.Namespace) -> int:
    client = get_client()
    ranking = client.ranking()
    print(json.dumps(ranking, indent=2))
    return 0


def cmd_leaderboard(args: argparse.Namespace) -> int:
    client = get_client()
    lb = client.leaderboard(size=args.limit)
    print(json.dumps(lb, indent=2))
    return 0


def cmd_member_info(args: argparse.Namespace) -> int:
    client = get_client()
    info = client.member_info(args.uuid)
    print(json.dumps(info, indent=2))
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    client = get_client()
    profile = client.profile()
    print(json.dumps(profile, indent=2))
    return 0


def cmd_active_trainers(args: argparse.Namespace) -> int:
    client = get_client()
    res = client.active_trainers(limit=args.limit, reset_cache=args.reset_cache)
    print(json.dumps(res, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fitness First Germany CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # auth save
    p_auth = subparsers.add_parser("auth-save", help="Verify and save Fitness First credentials")
    p_auth.add_argument("--email", required=True, help="Fitness First email")
    p_auth.add_argument("--password", required=True, help="Fitness First password")
    p_auth.set_defaults(func=cmd_auth_save)

    # auth status
    p_status = subparsers.add_parser("auth-status", help="Check authentication status")
    p_status.set_defaults(func=cmd_auth_status)

    # classes
    p_classes = subparsers.add_parser("classes", help="List upcoming courses")
    p_classes.add_argument("--days", type=int, default=14, help="Days ahead (default 14)")
    p_classes.add_argument("--club", default="", help="Optional club name filter")
    p_classes.set_defaults(func=cmd_classes)

    # class details
    p_cd = subparsers.add_parser("class-details", help="Get class details")
    p_cd.add_argument("class_id", help="Class ID")
    p_cd.set_defaults(func=cmd_class_details)

    # schedule
    p_sched = subparsers.add_parser("schedule", help="List booked courses")
    p_sched.add_argument("--days", type=int, default=14, help="Days ahead (default 14)")
    p_sched.set_defaults(func=cmd_schedule)

    # book
    p_book = subparsers.add_parser("book", help="Book a class")
    p_book.add_argument("class_id", help="Class ID")
    p_book.add_argument("--spot", type=int, default=None, help="Spot number")
    p_book.add_argument("--confirm", action="store_true", help="Explicit user confirmation")
    p_book.set_defaults(func=cmd_book)

    # cancel
    p_cancel = subparsers.add_parser("cancel", help="Cancel a booked class")
    p_cancel.add_argument("class_id", help="Class ID")
    p_cancel.add_argument("--confirm", action="store_true", help="Explicit user confirmation")
    p_cancel.set_defaults(func=cmd_cancel)

    # waitlist
    p_wl_join = subparsers.add_parser("waitlist-join", help="Join a class waitlist")
    p_wl_join.add_argument("class_id", help="Class ID")
    p_wl_join.add_argument("--confirm", action="store_true", help="Explicit user confirmation")
    p_wl_join.set_defaults(func=cmd_waitlist_join)

    p_wl_leave = subparsers.add_parser("waitlist-leave", help="Leave a class waitlist")
    p_wl_leave.add_argument("class_id", help="Class ID")
    p_wl_leave.add_argument("--confirm", action="store_true", help="Explicit user confirmation")
    p_wl_leave.set_defaults(func=cmd_waitlist_leave)

    # check-ins
    p_ci = subparsers.add_parser("check-ins", help="Visit history")
    p_ci.add_argument("--limit", type=int, default=20, help="Max visits")
    p_ci.set_defaults(func=cmd_check_ins)

    # latest-check-in
    p_latest = subparsers.add_parser("latest-check-in", help="Most recent check-in")
    p_latest.set_defaults(func=cmd_latest_check_in)

    # bioage
    p_bio = subparsers.add_parser("bioage", help="EGYM BioAge & measurements")
    p_bio.set_defaults(func=cmd_bioage)

    # activity
    p_act = subparsers.add_parser("activity", help="EGYM points and level")
    p_act.set_defaults(func=cmd_activity)

    # ranking
    p_rank = subparsers.add_parser("ranking", help="Personal member ranking")
    p_rank.set_defaults(func=cmd_ranking)

    # leaderboard
    p_lb = subparsers.add_parser("leaderboard", help="Club member leaderboard")
    p_lb.add_argument("--limit", type=int, default=50, help="Max members")
    p_lb.set_defaults(func=cmd_leaderboard)

    # member-info
    p_mi = subparsers.add_parser("member-info", help="Lookup exerciser identity")
    p_mi.add_argument("uuid", help="Exerciser UUID")
    p_mi.set_defaults(func=cmd_member_info)

    # profile
    p_prof = subparsers.add_parser("profile", help="Exerciser profile info")
    p_prof.set_defaults(func=cmd_profile)

    # active-trainers
    p_at = subparsers.add_parser("active-trainers", help="Real-time workout detection")
    p_at.add_argument("--limit", type=int, default=50, help="Max active members")
    p_at.add_argument("--reset-cache", action="store_true", help="Reset tracking baseline")
    p_at.set_defaults(func=cmd_active_trainers)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        sys.exit(args.func(args))
    except FitnessFirstError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

