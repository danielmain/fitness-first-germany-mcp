import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add skills scripts to path
SKILLS_SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "fitness-first-germany" / "scripts"
if str(SKILLS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILLS_SCRIPTS))

import ff_cli


def test_cmd_auth_save():
    with patch.object(ff_cli, "FitnessFirstClient") as mock_cls, \
         patch.object(ff_cli, "save_auth_config") as mock_save:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.login.return_value = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "uuid": "u-123",
            "homeClubName": "Club A",
            "homeClubUuid": "c-123",
        }

        parser = ff_cli.build_parser()
        args = parser.parse_args(["auth-save", "--email", "jane@example.com", "--password", "secret"])
        ret = ff_cli.cmd_auth_save(args)

        assert ret == 0
        mock_client.login.assert_called_once()
        mock_save.assert_called_once_with("jane@example.com", "secret")


def test_cmd_auth_status():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client._session = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "uuid": "u-123",
            "homeClubName": "Club A",
            "homeClubUuid": "c-123",
        }

        parser = ff_cli.build_parser()
        args = parser.parse_args(["auth-status"])
        ret = ff_cli.cmd_auth_status(args)

        assert ret == 0
        mock_client._ensure_session.assert_called_once()


def test_cmd_classes():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.upcoming_classes.return_value = {"classes": []}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["classes", "--days", "7", "--club", "Fellbach"])
        ret = ff_cli.cmd_classes(args)

        assert ret == 0
        mock_client.upcoming_classes.assert_called_once_with(days=7, club_name="Fellbach")


def test_cmd_class_details():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.class_details.return_value = {"id": "cls-1"}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["class-details", "cls-1"])
        ret = ff_cli.cmd_class_details(args)

        assert ret == 0
        mock_client.class_details.assert_called_once_with("cls-1")


def test_cmd_schedule():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.my_schedule.return_value = {"classes": []}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["schedule", "--days", "5"])
        ret = ff_cli.cmd_schedule(args)

        assert ret == 0
        mock_client.my_schedule.assert_called_once_with(days=5)


def test_cmd_check_ins():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.check_ins.return_value = {"check_ins": []}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["check-ins", "--limit", "15"])
        ret = ff_cli.cmd_check_ins(args)

        assert ret == 0
        mock_client.check_ins.assert_called_once_with(limit=15)


def test_cmd_latest_check_in():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.latest_check_in.return_value = {"date": "2026-10-29"}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["latest-check-in"])
        ret = ff_cli.cmd_latest_check_in(args)

        assert ret == 0
        mock_client.latest_check_in.assert_called_once()


def test_cmd_bioage():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.body_measurements.return_value = {"total_bio_age": 28}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["bioage"])
        ret = ff_cli.cmd_bioage(args)

        assert ret == 0
        mock_client.body_measurements.assert_called_once()


def test_cmd_activity():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.activity_level.return_value = {"level": "gold"}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["activity"])
        ret = ff_cli.cmd_activity(args)

        assert ret == 0
        mock_client.activity_level.assert_called_once()


def test_cmd_ranking():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.ranking.return_value = {"rank": 5}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["ranking"])
        ret = ff_cli.cmd_ranking(args)

        assert ret == 0
        mock_client.ranking.assert_called_once()


def test_cmd_leaderboard():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.leaderboard.return_value = {"items": []}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["leaderboard", "--limit", "25"])
        ret = ff_cli.cmd_leaderboard(args)

        assert ret == 0
        mock_client.leaderboard.assert_called_once_with(size=25)


def test_cmd_member_info():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.member_info.return_value = {"first_name": "Ada"}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["member-info", "uid-123"])
        ret = ff_cli.cmd_member_info(args)

        assert ret == 0
        mock_client.member_info.assert_called_once_with("uid-123")


def test_cmd_profile():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.profile.return_value = {"firstname": "Ada"}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["profile"])
        ret = ff_cli.cmd_profile(args)

        assert ret == 0
        mock_client.profile.assert_called_once()


def test_cmd_active_trainers():
    with patch.object(ff_cli, "get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.active_trainers.return_value = {"active_trainers": []}

        parser = ff_cli.build_parser()
        args = parser.parse_args(["active-trainers", "--limit", "30", "--reset-cache"])
        ret = ff_cli.cmd_active_trainers(args)

        assert ret == 0
        mock_client.active_trainers.assert_called_once_with(limit=30, reset_cache=True)

