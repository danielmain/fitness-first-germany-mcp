import json

import pytest

from fitness_first_germany_mcp.client import (
    FitnessFirstClient,
    FitnessFirstError,
    profile_form,
    public_profile,
    summarize_classes,
)


CURRENT = {
    "firstname": "Ada",
    "lastname": "Lovelace",
    "email": "ada@example.com",
    "birthday": "03/08/1980",
    "gender": "F",
    "height": 170.0,
    "weight": 60.0,
    "measurementUnit": "M",
    "phoneNumber": "",
    "aboutMe": "",
    "privacy": "Public",
    "timezone": "Europe/Berlin",
    "homeClubUuid": "fellbach-uuid",
    "clientLoginPasscode": "secret",
    "picturePassword": "secret",
    "emailPreference": {"emailGoalNotice": True, "emailChallengeNotice": False},
    "address": {"street1": None, "city": "Fellbach", "postalCode": "70734"},
}


def test_profile_form_keeps_home_club_when_only_about_me_changes():
    form = profile_form(CURRENT, {"aboutMe": "runs"})
    assert form["homeClub"] == "fellbach-uuid"
    assert form["aboutMe"] == "runs"
    assert form["firstname"] == "Ada"
    assert form["emailGoalNotice"] == "true"
    assert form["emailChallengeNotice"] == "false"
    assert form["city"] == "Fellbach"
    assert "clientLoginPasscode" not in form


def test_profile_form_changes_home_club_with_home_club_field():
    form = profile_form(CURRENT, {"homeClubUuid": "other-club"})
    assert form["homeClub"] == "other-club"


def test_profile_form_refuses_a_missing_home_club():
    current = dict(CURRENT)
    current["homeClubUuid"] = None
    with pytest.raises(FitnessFirstError):
        profile_form(current, {"aboutMe": "runs"})


def test_public_profile_drops_secrets():
    shown = public_profile(CURRENT)
    assert "clientLoginPasscode" not in shown
    assert shown["firstname"] == "Ada"


def test_summarize_classes_dedupes_and_formats_berlin_time():
    items = [
        {
            "brief": {
                "id": "1:2",
                "name": "Hyrox",
                "clubUuid": "club",
                "startDateTime": 1791907200000,
                "endDateTime": 1791910800000,
                "maxCapacity": 16,
                "totalBooked": 13,
                "instructor": {"fullName": "Coach"},
                "activity": {"description": "intervals"},
            },
            "attendeeDetails": {"booked": False, "availableActions": ["ADD_TO_CLASS"]},
        },
        {"brief": {"id": "1:2", "name": "Hyrox duplicate", "startDateTime": 1791907200000, "endDateTime": 1791910800000}},
    ]
    classes = summarize_classes(items, "Europe/Berlin")
    assert len(classes) == 1
    assert classes[0]["starts_at"].endswith("+02:00") or classes[0]["starts_at"].endswith("+01:00")
    assert classes[0]["spots_free"] == 3
    assert classes[0]["available_actions"] == ["ADD_TO_CLASS"]


class _Response:
    def __init__(self, payload, status=200):
        self.status = status
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Opener:
    def __init__(self):
        self.urls = []

    def open(self, request, timeout=30):
        self.urls.append((request.get_method(), request.full_url, request.data))
        path = request.full_url
        if path.endswith("/np/exerciser/login"):
            return _Response({"uuid": "user-1", "homeClubUuid": "club-1", "timezone": "Europe/Berlin", "firstName": "Ada", "homeClubName": "Fellbach"})
        if "/classes?" in path:
            assert "1%3A2" not in path
            assert "exerciserUuid=user-1" in path
            return _Response([
                {"brief": {"id": "10:20", "name": "PowerCore", "startDateTime": 1791907200000, "endDateTime": 1791910800000, "maxCapacity": 10, "totalBooked": 1, "clubUuid": "club-1"}}
            ])
        if "/class/10%3A20/addExerciser" in path:
            body = request.data.decode()
            assert "exerciserUuid=user-1" in body
            return _Response({"status": "ok"})
        if "/ranking/leaderboard?" in path:
            assert "exerciserUuid" not in path  # in url path
            assert "user-1" in path
            return _Response({
                "items": [
                    {
                        "exerciserId": "user-2",
                        "exerciserName": "Kristina D.",
                        "points": 100,
                        "exerciserIconUrl": "https://cdn.example.com/pic.jpg",
                    }
                ],
                "totalNumberOfUsers": 50,
                "nextPageToken": "tok-1",
            })
        if path.endswith("/ranking"):
            return _Response({
                "exerciserId": "user-1",
                "exerciserName": "Ada L.",
                "rank": {"value": 2},
                "points": {"value": 11867},
                "averageRank": 2,
                "totalNumberOfUsers": 50,
                "exerciserIconUrl": "https://cdn.example.com/ada.jpg",
            })
        if "/check-ins/history?" in path:
            return _Response({
                "checkIns": [
                    {
                        "gymLocationName": "Fellbach",
                        "gymLocationAddress": "Stuttgarter Str. 1",
                        "checkInDate": "2026-10-12T10:00:00",
                        "timezone": "Europe/Berlin",
                    }
                ]
            })
        if path.endswith("/latest-check-in"):
            return _Response({
                "checkInDate": "2026-10-12T10:00:00",
                "timezone": "Europe/Berlin",
            })
        if path.endswith("/activitylevels"):
            return _Response({
                "level": "gold",
                "points": 5000,
                "maintainPoints": 3000,
                "daysLeft": 10,
                "goal": 10000,
            })
        if path.endswith("/profile"):
            return _Response({
                "weight": 70.0,
                "height": 175.0,
                "firstname": "Ada",
                "homeClubUuid": "club-1",
            })
        if path.endswith("/bioage"):
            return _Response({
                "totalDetails": {
                    "totalBioAge": {"value": 30, "createdAt": "2026-10-12T12:00:00Z"}
                },
                "metabolicDetails": {
                    "bmi": {"value": 22.5},
                    "bodyFat": {"value": 15.0},
                    "metabolicAge": {"value": 28},
                },
                "cardioDetails": {
                    "cardioAge": {"value": 29},
                    "restingHeartRate": {"value": 60},
                    "systolicPressure": {"value": 115},
                    "diastolicPressure": {"value": 75},
                    "vo2max": {"value": 42.0},
                },
            })
        if path.endswith("/brief-info"):
            return _Response({
                "uuid": "user-2",
                "firstName": "Kristina",
                "lastName": "Dittrich",
                "homeGymLocationId": "club-1",
                "homeGymLocationName": "Fellbach",
                "nickname": "Krissi",
                "imageUrl": "https://cdn.example.com/pic-hires.jpg",
            })
        if path.endswith("/notifications"):
            return _Response({
                "data": {
                    "notifications": [{"id": 1, "text": "Gym closed on Sunday"}]
                }
            })
        raise AssertionError(path)


def test_client_logs_in_and_encodes_class_ids():
    opener = _Opener()
    client = FitnessFirstClient("ada@example.com", "secret", opener=opener)
    listed = client.upcoming_classes(days=7)
    assert listed["count"] == 1
    assert listed["classes"][0]["name"] == "PowerCore"
    booked = client.book_class("10:20")
    assert booked["status"] == "ok"
    methods = [item[0] for item in opener.urls]
    assert methods[0] == "POST"
    assert any("/class/10%3A20/addExerciser" in url for _, url, _ in opener.urls)


def test_client_leaderboard_and_ranking():
    opener = _Opener()
    client = FitnessFirstClient("ada@example.com", "secret", opener=opener)
    lb = client.leaderboard(size=20)
    assert lb["total_users"] == 50
    assert lb["count"] == 1
    assert lb["items"][0]["name"] == "Kristina D."
    assert lb["items"][0]["avatar_url"] == "https://cdn.example.com/pic.jpg"
    assert lb["next_page_token"] == "tok-1"

    rk = client.ranking()
    assert rk["rank"] == 2
    assert rk["points"] == 11867
    assert rk["total_users"] == 50
    assert rk["avatar_url"] == "https://cdn.example.com/ada.jpg"


def test_days_out_of_range():
    client = FitnessFirstClient("ada@example.com", "secret", opener=_Opener())
    with pytest.raises(FitnessFirstError):
        client.upcoming_classes(days=0)


def test_client_check_ins_and_latest():
    client = FitnessFirstClient("ada@example.com", "secret", opener=_Opener())
    history = client.check_ins(limit=10)
    assert history["count"] == 1
    assert history["check_ins"][0]["club_name"] == "Fellbach"

    latest = client.latest_check_in()
    assert latest["date"] == "2026-10-12T10:00:00"
    assert latest["timezone"] == "Europe/Berlin"


def test_client_activity_level():
    client = FitnessFirstClient("ada@example.com", "secret", opener=_Opener())
    act = client.activity_level()
    assert act["level"] == "gold"
    assert act["points"] == 5000
    assert act["maintain_points"] == 3000
    assert act["days_left"] == 10


def test_client_body_measurements():
    client = FitnessFirstClient("ada@example.com", "secret", opener=_Opener())
    meas = client.body_measurements()
    assert meas["weight_kg"] == 70.0
    assert meas["height_cm"] == 175.0
    assert meas["bmi"] == 22.5
    assert meas["body_fat_percentage"] == 15.0
    assert meas["metabolic_age"] == 28
    assert meas["total_bio_age"] == 30
    assert meas["cardio_age"] == 29
    assert meas["blood_pressure"] == "115/75"
    assert meas["resting_heart_rate"] == 60
    assert meas["vo2_max"] == 42.0
    assert meas["last_measured"] == "2026-10-12T12:00:00Z"


def test_client_notifications():
    client = FitnessFirstClient("ada@example.com", "secret", opener=_Opener())
    notifs = client.notifications()
    assert notifs["count"] == 1
    assert notifs["notifications"][0]["text"] == "Gym closed on Sunday"


def test_client_member_info_and_active_trainers(tmp_path):
    opener = _Opener()
    client = FitnessFirstClient("ada@example.com", "secret", opener=opener)

    info = client.member_info("user-2")
    assert info["first_name"] == "Kristina"
    assert info["last_name"] == "Dittrich"
    assert info["full_name"] == "Kristina Dittrich"
    assert info["home_club_name"] == "Fellbach"
    assert info["avatar_url"] == "https://cdn.example.com/pic-hires.jpg"

    cache_file = str(tmp_path / "snapshot.json")

    # First run: sets baseline snapshot
    first_run = client.active_trainers(cache_path=cache_file)
    assert first_run["active_count"] == 0
    assert first_run["snapshot_saved"] is True
    assert "Initial snapshot" in first_run["message"]

    # Simulate leaderboard score increase: user-2 went from 100 -> 250 (+150 pts)
    with open(cache_file, "r") as f:
        data = json.load(f)
    data["scores"]["user-2"] = 100  # old score was 100
    # In opener, user-2 currently has 100 points. Let's make old score 50:
    data["scores"]["user-2"] = 50
    with open(cache_file, "w") as f:
        json.dump(data, f)

    second_run = client.active_trainers(cache_path=cache_file)
    assert second_run["active_count"] == 1
    trainer = second_run["active_trainers"][0]
    assert trainer["exerciser_id"] == "user-2"
    assert trainer["name"] == "Kristina Dittrich"
    assert trainer["points_gained"] == 50
    assert trainer["current_points"] == 100
    assert trainer["previous_points"] == 50
    assert trainer["avatar_url"] == "https://cdn.example.com/pic-hires.jpg"

