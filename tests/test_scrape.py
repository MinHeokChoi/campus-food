"""python3 tests/test_scrape.py 또는 python3 -m pytest 로 돈다."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import scrape  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


def test_sample_0908():
    day = scrape.parse_page(load("sample_0908.html"), dt.date(2026, 9, 8))
    assert day["date"] == "2026-09-08"
    meals = day["meals"]
    keys = [(m["slot"], m["place"]) for m in meals]
    assert keys == [
        ("아침", "학식"), ("아침 간편식", "학식"),
        ("점심A", "학식"), ("점심B", "학식"), ("점심", "교식"),
        ("저녁", "학식"), ("저녁", "교식"),
    ], keys
    lunch_a = meals[2]
    assert lunch_a["end"] == "14:00"
    assert lunch_a["items"] == ["백미밥", "사골파국", "불맛제육볶음", "감자고로케&케찹",
                                "흑임자연근무침", "실곤약무침", "야채샐러드&배추김치"]
    simple = meals[1]
    assert simple["items"] == ["더커진참치마요삼각김밥", "빅스위트데니쉬빵", "애사비소다(체리)"]
    assert "간편식" not in meals[0]["items"]
    assert meals[5]["end"] == "18:50" and meals[6]["end"] == "18:30"
    for m in meals:
        assert all("&amp;" not in i and "\xa0" not in i for i in m["items"])


def test_year_rollover():
    assert scrape.resolve_year(1, 2, dt.date(2026, 12, 30)) == dt.date(2027, 1, 2)
    assert scrape.resolve_year(12, 30, dt.date(2027, 1, 2)) == dt.date(2026, 12, 30)


def test_holidays():
    hs = scrape.upcoming_holidays(dt.date(2026, 9, 9))
    assert hs[0] == "2026-09-24" and "2026-10-09" in hs and "2026-12-25" not in hs
    assert all(hs[i] < hs[i + 1] for i in range(len(hs) - 1))


def test_empty_page():
    assert scrape.parse_page("<html>(09월 08일)</html>", dt.date(2026, 9, 8)) is None
    assert scrape.parse_page("<html>nothing</html>", dt.date(2026, 9, 8)) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
