"""python3 tests/test_adapters.py 또는 python3 -m pytest 로 돈다.

어댑터마다 실제 응답 하나를 tests/fixtures/ 에 저장해 두고 기대 결과와 비교한다.
네트워크를 타지 않으므로 학교 사이트가 죽어 있어도 돈다.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adapters import REGISTRY, base, hongik  # noqa: E402
from calendars import kr  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return f.read()


# --- 공통 -----------------------------------------------------------------

def test_registry_shape():
    """어댑터 규약: VENUE 키가 다 있고, id 가 등록 키와 같고, places 가 비어 있지 않다."""
    for vid, mod in REGISTRY.items():
        v = mod.VENUE
        for key in ("id", "name", "region", "country", "tz", "calendar", "places"):
            assert key in v, (vid, key)
        assert v["id"] == vid
        assert v["places"], vid
        ids = [p["id"] for p in v["places"]]
        assert len(ids) == len(set(ids)), vid
        assert hasattr(mod, "fetch"), vid


def test_text_lines():
    assert base.text_lines("가<br>나&amp;다<br/>\xa0") == ["가", "나&다"]
    assert base.text_lines("") == []


def test_resolve_year():
    assert base.resolve_year(1, 2, dt.date(2026, 12, 30)) == dt.date(2027, 1, 2)
    assert base.resolve_year(12, 30, dt.date(2027, 1, 2)) == dt.date(2026, 12, 30)
    assert base.resolve_year(2, 30, dt.date(2026, 3, 1)) is None   # 없는 날짜


def test_holidays():
    hs = kr.upcoming(dt.date(2026, 9, 9))
    assert hs[0] == "2026-09-24" and "2026-10-09" in hs and "2026-12-25" not in hs
    assert all(hs[i] < hs[i + 1] for i in range(len(hs) - 1))


# --- 홍익대 ---------------------------------------------------------------

def test_hongik_sample():
    day = hongik.parse_page(fixture("hongik_0908.html"), dt.date(2026, 9, 8))
    assert day.date == "2026-09-08"
    meals = day.meals
    keys = [(m.slot, m.place) for m in meals]
    assert keys == [
        ("아침", "학식"), ("아침 간편식", "학식"),
        ("점심A", "학식"), ("점심B", "학식"), ("점심", "교식"),
        ("저녁", "학식"), ("저녁", "교식"),
    ], keys
    assert [m.place_id for m in meals] == ["haksik"] * 4 + ["gyosik", "haksik", "gyosik"]

    lunch_a = meals[2]
    assert lunch_a.end == "14:00"
    assert lunch_a.items == ["백미밥", "사골파국", "불맛제육볶음", "감자고로케&케찹",
                             "흑임자연근무침", "실곤약무침", "야채샐러드&배추김치"]
    assert meals[1].items == ["더커진참치마요삼각김밥", "빅스위트데니쉬빵", "애사비소다(체리)"]
    assert "간편식" not in meals[0].items
    assert meals[5].end == "18:50" and meals[6].end == "18:30"
    for m in meals:
        assert all("&amp;" not in i and "\xa0" not in i for i in m.items)


def test_hongik_empty_page():
    assert hongik.parse_page("<html>(09월 08일)</html>", dt.date(2026, 9, 8)) is None
    assert hongik.parse_page("<html>nothing</html>", dt.date(2026, 9, 8)) is None


def test_hongik_places_match_venue():
    """어댑터가 내는 place_id 가 VENUE.places 에 선언된 것들 안에 있어야 한다."""
    declared = {p["id"] for p in hongik.VENUE["places"]}
    day = hongik.parse_page(fixture("hongik_0908.html"), dt.date(2026, 9, 8))
    assert {m.place_id for m in day.meals} <= declared


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
