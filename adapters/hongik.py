"""홍익대 서울캠퍼스 — apps.hongik.ac.kr/food/food_m.php

`p` 는 이번 주 요일 번호다 (1=월 … 5=금, 0=오늘). 6 이상은 5 와 같다.
그래서 보이는 날 수가 월요일엔 5일, 금요일엔 1일이다. 주말은 페이지가 비어 있다.

`food.php`(PC) 는 UA 를 바꿔도 403 이라 쓰지 않는다.
"""
import datetime as dt
import re

from . import base

VENUE = {
    "id": "hongik",
    "name": "홍익대",
    "region": "서울",
    "country": "KR",
    "tz": "Asia/Seoul",
    "calendar": "kr",
    "places": [
        {"id": "haksik", "name": "학식"},    # 제2기숙사
        {"id": "gyosik", "name": "교식"},    # 교직원식당
    ],
}

URL = "https://apps.hongik.ac.kr/food/food_m.php?p={p}"
PAGES = (1, 2, 3, 4, 5)

# 페이지에 적힌 식당 이름 -> (화면에 찍을 이름, place_id)
PLACES = {
    "제2기숙사": ("학식", "haksik"),
    "교직원식당": ("교식", "gyosik"),
}

# 하루 안의 표시 순서. 끼니 슬롯 순, 같은 슬롯이면 학식 먼저.
# 마감시간 순이 아니다 — 사람은 "저녁"을 슬롯으로 생각한다.
SLOT_RANK = {"아침": 0, "아침 간편식": 1, "점심A": 2, "점심B": 2, "점심": 2, "저녁": 3}
PLACE_RANK = {"haksik": 0, "gyosik": 1}
SIMPLE = "간편식"

RE_DATE = re.compile(r"\((\d{1,2})월\s*(\d{1,2})일\)")
RE_PLACE = re.compile(r'class="time"[^>]*>\s*<strong>([^<]+)</strong>')
RE_MEAL = re.compile(r"<th(?:\s[^>]*)?>(.*?)</th>\s*<td(?:\s[^>]*)?>(.*?)</td>", re.S)
RE_SLOT = re.compile(r"^\s*(?:<!--.*?-->\s*)?([^<\s][^<]*?)\s*<br", re.S)
RE_END = re.compile(r"\(\d{1,2}:\d{2}\s*~\s*(\d{1,2}:\d{2})\)")


def split_simple(slot, items):
    """아침의 '간편식' 뒤 항목은 별도 끼니 '아침 간편식' 으로 쪼갠다."""
    if SIMPLE not in items:
        return [(slot, items)]
    i = items.index(SIMPLE)
    out = []
    if items[:i]:
        out.append((slot, items[:i]))
    if items[i + 1:]:
        out.append((slot + " " + SIMPLE, items[i + 1:]))
    return out


def parse_page(page_html, today):
    """HTML 한 장 -> Day 또는 None."""
    m = RE_DATE.search(page_html)
    if not m:
        return None
    date = base.resolve_year(int(m.group(1)), int(m.group(2)), today)
    if date is None:
        return None

    meals = []
    # 식당 제목과 끼니 행이 문서 순서로 섞여 있다. 위치 순으로 훑는다.
    events = []
    for pm in RE_PLACE.finditer(page_html):
        events.append((pm.start(), "place", base.clean(pm.group(1))))
    for mm in RE_MEAL.finditer(page_html):
        events.append((mm.start(), "meal", (mm.group(1), mm.group(2))))
    events.sort(key=lambda e: e[0])

    place = None
    for _, kind, payload in events:
        if kind == "place":
            place = PLACES.get(payload, (payload, payload))
            continue
        if place is None:
            continue
        head, cell = payload
        sm = RE_SLOT.search(head)
        em = RE_END.search(head)
        if not sm or not em:
            continue
        slot = base.clean(sm.group(1))
        end = em.group(1)
        if len(end) == 4:
            end = "0" + end
        for s, items in split_simple(slot, base.text_lines(cell)):
            if items:
                meals.append(base.Meal(slot=s, place=place[0], place_id=place[1],
                                       end=end, items=items))

    if not meals:
        return None

    meals.sort(key=lambda m: (SLOT_RANK.get(m.slot, 99), PLACE_RANK.get(m.place_id, 9)))
    return base.Day(date=date.isoformat(), meals=meals)


def fetch(today):
    """오늘부터의 날들. 파싱 실패한 날은 건너뛰고 나머지를 낸다.

    전부 실패하면 예외를 던진다 — 러너가 기존 파일을 건드리지 않게 하려는 것이다.
    """
    days = {}
    errors = []
    for p in PAGES:
        try:
            page = base.http_get(URL.format(p=p))
        except Exception as e:  # noqa: BLE001
            errors.append(f"p={p}: {e}")
            continue
        day = parse_page(page, today)
        if day is None:
            errors.append(f"p={p}: no menu")
            continue
        if day.date < today.isoformat():
            errors.append(f"p={p}: stale date {day.date}")
            continue
        days.setdefault(day.date, day)

    if not days:
        raise RuntimeError("모든 페이지 실패: " + "; ".join(errors))
    return [days[k] for k in sorted(days)][:4]
