from fitness_first_germany_mcp import server


class _FakeClient:
    def __init__(self):
        self.calls = []

    def book_class(self, class_id, club_uuid=None, spot=None):
        self.calls.append(("book", class_id, club_uuid, spot))
        return {"status": "ok", "class_id": class_id}

    def update_profile(self, updates):
        self.calls.append(("profile", updates))
        return {"firstname": updates.get("firstname", "Ada")}

    def leaderboard(self, size=50, next_page_token=None):
        self.calls.append(("leaderboard", size, next_page_token))
        return {"total_users": 10, "count": 1, "items": [{"name": "Test User"}]}

    def ranking(self):
        self.calls.append(("ranking",))
        return {"rank": 1, "points": 500}

    def check_ins(self, limit=30, end_date=None):
        self.calls.append(("check_ins", limit, end_date))
        return {"count": 1, "check_ins": []}

    def latest_check_in(self):
        self.calls.append(("latest_check_in",))
        return {"date": "2026-10-12T10:00:00"}

    def activity_level(self):
        self.calls.append(("activity_level",))
        return {"level": "gold"}

    def body_measurements(self):
        self.calls.append(("body_measurements",))
        return {"weight_kg": 70.0}

    def notifications(self):
        self.calls.append(("notifications",))
        return {"count": 0, "notifications": []}

    def member_info(self, exerciser_id):
        self.calls.append(("member_info", exerciser_id))
        return {"exerciser_id": exerciser_id, "full_name": "Ada Lovelace"}

    def active_trainers(self, limit=50, reset_cache=False):
        self.calls.append(("active_trainers", limit, reset_cache))
        return {"active_count": 1, "active_trainers": []}


def test_book_does_not_call_the_api_without_confirm():
    fake = _FakeClient()
    server.set_client(fake)
    result = server.ff_book_class("10:20", confirm=False)
    assert result["applied"] is False
    assert fake.calls == []


def test_book_calls_the_api_when_confirmed():
    fake = _FakeClient()
    server.set_client(fake)
    result = server.ff_book_class("10:20", confirm=True, spot="4")
    assert result["status"] == "ok"
    assert fake.calls == [("book", "10:20", None, "4")]


def test_profile_update_previews_fields_until_confirmed():
    fake = _FakeClient()
    server.set_client(fake)
    preview = server.ff_update_profile(confirm=False, about_me="hello")
    assert preview["applied"] is False
    assert preview["fields"]["about_me"] == "hello"
    assert fake.calls == []
    applied = server.ff_update_profile(confirm=True, firstname="Ada")
    assert applied["firstname"] == "Ada"
    assert fake.calls == [("profile", {"firstname": "Ada"})]


def test_profile_update_requires_a_field():
    server.set_client(_FakeClient())
    assert "error" in server.ff_update_profile(confirm=True)


def test_leaderboard_and_ranking_forward_to_client():
    fake = _FakeClient()
    server.set_client(fake)
    lb = server.ff_leaderboard(size=25, next_page_token="tok123")
    assert lb["total_users"] == 10
    assert fake.calls[-1] == ("leaderboard", 25, "tok123")

    rk = server.ff_ranking()
    assert rk["rank"] == 1
    assert fake.calls[-1] == ("ranking",)


def test_health_and_activity_tools_forward_to_client():
    fake = _FakeClient()
    server.set_client(fake)
    c_ins = server.ff_check_ins(limit=15, end_date="2026-10-10")
    assert c_ins["count"] == 1
    assert fake.calls[-1] == ("check_ins", 15, "2026-10-10")

    lat = server.ff_latest_check_in()
    assert lat["date"] == "2026-10-12T10:00:00"
    assert fake.calls[-1] == ("latest_check_in",)

    act = server.ff_activity_level()
    assert act["level"] == "gold"
    assert fake.calls[-1] == ("activity_level",)

    meas = server.ff_body_measurements()
    assert meas["weight_kg"] == 70.0
    assert fake.calls[-1] == ("body_measurements",)

    notifs = server.ff_notifications()
    assert notifs["count"] == 0
    assert fake.calls[-1] == ("notifications",)


def test_member_info_and_active_trainers_forward_to_client():
    fake = _FakeClient()
    server.set_client(fake)

    info = server.ff_member_info("user-123")
    assert info["full_name"] == "Ada Lovelace"
    assert fake.calls[-1] == ("member_info", "user-123")

    act = server.ff_active_trainers(limit=20, reset_cache=True)
    assert act["active_count"] == 1
    assert fake.calls[-1] == ("active_trainers", 20, True)
