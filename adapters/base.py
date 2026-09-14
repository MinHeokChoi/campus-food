"""어댑터가 공통으로 쓰는 것들. 표준 라이브러리만 쓴다.

어댑터 하나 = 장소(venue) 하나. 규약은 두 가지뿐이다.

    VENUE = { "id", "name", "region", "country", "tz", "calendar", "places" }
    def fetch(today: datetime.date) -> list[Day]

`fetch` 는 받아서 파싱만 한다. 정렬·검증·기록은 러너(run.py)가 한다.
실패하면 예외를 던진다 — 빈 리스트로 조용히 넘기지 않는다. 러너가 구분해야 하기 때문이다.
"""
import datetime as dt
import html
import re
import urllib.request
from dataclasses import dataclass, field

RE_TAG = re.compile(r"<[^>]+>")

USER_AGENT = "campus-food/1.0 (+https://github.com/MinHeokChoi/campus-food)"


@dataclass
class Meal:
    """화면 하나. 끼니 하나, 메뉴 전부."""
    slot: str                       # "점심A" — 화면에 그대로 찍힌다
    place: str                      # "학식" — 화면에 그대로 찍힌다
    place_id: str                   # "haksik" — 사용자가 고른 식당을 거를 때 쓴다
    items: list                     # ["백미밥", ...]
    end: str = None                 # "14:00" 로컬. 마감이 공개돼 있지 않으면 None

    def as_json(self):
        out = {"slot": self.slot, "place": self.place, "end": self.end,
               "items": list(self.items)}
        return out


@dataclass
class Day:
    date: str                       # "2026-09-14"
    meals: list = field(default_factory=list)


def clean(text):
    """HTML 엔티티 복원 + &nbsp; 제거 + 앞뒤 공백 제거."""
    return html.unescape(text).replace("\xa0", " ").strip()


def text_lines(fragment):
    """HTML 조각 -> 줄 목록. <br> 과 태그를 줄바꿈으로 보고 빈 줄은 버린다."""
    blob = clean(RE_TAG.sub("\n", fragment.replace("<br", "\n<br")))
    return [line.strip() for line in blob.split("\n") if line.strip()]


def resolve_year(month, day, today):
    """페이지에 연도가 없을 때. 오늘과 가장 가까운 연도를 고른다.

    12월 말/1월 초에 해가 넘어가는 걸 이걸로 처리한다.
    """
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            cand = dt.date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    return best


def http_get(url, timeout=20, tries=3, headers=None, data=None, encoding="utf-8"):
    """한 번 실패해도 바로 버리지 않는다. 러너에서 한 페이지가 빠진 적이 있다."""
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, data=data)
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode(encoding, "replace")
        except Exception as e:  # noqa: BLE001
            last = e
    raise last
