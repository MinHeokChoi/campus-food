"""상명대 서울캠퍼스 — www.smu.ac.kr/kor/life/restaurantView.do

미래백년관 학생식당 한 곳이고, 그 안에서 코너가 갈린다 (한식 / 푸드코트).
사용자가 고르는 단위는 코너라서 코너를 place 로 둔다.

한 페이지에 그 주 월~금이 표로 들어 있다. `srDt=YYYY-MM-DD` 로 임의 주를 부를 수 있고,
페이지 안의 hidden input `#next` 에 다음 주 월요일 날짜가 들어 있다.

끼니는 조식/중식/석식/간식 탭이 있는데 **선택된 것 하나만 렌더된다.** 어느 것이 선택됐는지는
`<li class="on selBtn">` 로 알 수 있다. `srCategory` 파라미터는 넣어도 응답이 안 바뀐다 (확인함) —
그래서 등록된 끼니만 가져온다. 지금은 중식만 올라온다.
"""
import re
import sys

from . import base

VENUE = {
    "id": "smu",
    "name": "상명대",
    "region": "서울",
    "region_id": "seoul",
    "country": "KR",
    "tz": "Asia/Seoul",
    "calendar": "kr",
    "places": [
        {"id": "hansik", "name": "한식"},
        {"id": "foodcourt", "name": "푸드코트"},
    ],
}

URL = "https://www.smu.ac.kr/kor/life/restaurantView.do"

# 페이지의 코너 이름 -> (화면에 찍을 이름, place_id)
PLACES = {
    "한식(식판)": ("한식", "hansik"),
    "한식": ("한식", "hansik"),
    "푸드코트": ("푸드코트", "foodcourt"),
}

# 탭의 data-value -> 화면에 찍을 끼니 이름. 홍익대와 같은 말을 쓴다.
SLOTS = {"B": "아침", "L": "점심", "D": "저녁", "S": "간식"}
SLOT_RANK = {"아침": 0, "점심": 1, "간식": 2, "저녁": 3}
PLACE_RANK = {"hansik": 0, "foodcourt": 1}

# 이용시간 안내문의 끼니 이름 -> 탭 코드
HOURS_NAMES = {"조식": "B", "중식": "L", "석식": "D", "간식": "S"}

RE_TABLE = re.compile(r'<table[^>]*class="[^"]*smu-table[^"]*"[^>]*>(.*?)</table>', re.S)
RE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
RE_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
RE_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
RE_HEAD_DATE = re.compile(r"\((\d{1,2})\.(\d{1,2})\)")
RE_SELECTED = re.compile(r'<li class="on selBtn"[^>]*>\s*<a[^>]*data-value="([BLDS])"', re.S)
RE_NEXT = re.compile(r'id="next"[^>]*value="(\d{4}-\d{2}-\d{2})"')
RE_HOURS = re.compile(r"(조식|중식|석식|간식)\s*:\s*\d{1,2}시\s*\d{1,2}분\s*~\s*(\d{1,2})시\s*(\d{1,2})분")


def parse_hours(page):
    """이용시간 안내문에서 끼니별 마감시각. 안 적힌 끼니는 None 이다."""
    out = {}
    for m in RE_HOURS.finditer(page):
        code = HOURS_NAMES[m.group(1)]
        out[code] = "%02d:%02d" % (int(m.group(2)), int(m.group(3)))
    return out


def parse_page(page, today):
    """HTML 한 장 -> [Day]. 표가 없으면 빈 리스트."""
    # 페이지에 smu-table 이 여럿이다 (공지 표 등). 머리줄에 "월(09.14)" 꼴 날짜가 있는 게 메뉴 표다.
    body = None
    for tm in RE_TABLE.finditer(page):
        head = RE_ROW.search(tm.group(1))
        if head and RE_HEAD_DATE.search(head.group(1)):
            body = tm.group(1)
            break
    if body is None:
        return []
    sm = RE_SELECTED.search(page)
    if not sm:
        return []
    slot = SLOTS[sm.group(1)]
    end = parse_hours(page).get(sm.group(1))

    rows = RE_ROW.findall(body)
    if not rows:
        return []

    # 첫 행의 th 가 "월(09.14)" 꼴. 첫 칸은 코너 이름 자리라 비어 있다.
    dates = []
    for th in RE_TH.findall(rows[0]):
        dm = RE_HEAD_DATE.search(th)
        d = base.resolve_year(int(dm.group(1)), int(dm.group(2)), today) if dm else None
        dates.append(d)
    if not any(dates):
        return []

    by_date = {}
    for row in rows[1:]:
        ths = RE_TH.findall(row)
        tds = RE_TD.findall(row)
        if not ths or not tds:
            continue
        corner = base.clean(base.RE_TAG.sub("", ths[0]))
        if corner not in PLACES:
            print("smu: 모르는 코너 %r — 건너뛴다" % corner, file=sys.stderr)
            continue
        name, pid = PLACES[corner]
        # 날짜 칸은 첫 th(코너 이름) 다음부터라, 헤더 날짜도 한 칸 밀려 있다
        for i, cell in enumerate(tds):
            date = dates[i + 1] if i + 1 < len(dates) else None
            if date is None:
                continue
            items = [x for x in base.text_lines(cell) if x != "-"]
            if not items:
                continue
            by_date.setdefault(date, []).append(
                base.Meal(slot=slot, place=name, place_id=pid, end=end, items=items))

    days = []
    for date in sorted(by_date):
        meals = by_date[date]
        meals.sort(key=lambda m: (SLOT_RANK.get(m.slot, 9), PLACE_RANK.get(m.place_id, 9)))
        days.append(base.Day(date=date.isoformat(), meals=meals))
    return days


def fetch(today):
    page = base.http_get(URL)
    days = [d for d in parse_page(page, today) if d.date >= today.isoformat()]
    if days:
        return days

    # 주말이면 이번 주가 통째로 과거다. 페이지가 알려 주는 다음 주를 한 번 더 본다.
    nm = RE_NEXT.search(page)
    if nm:
        page = base.http_get(URL + "?srDt=" + nm.group(1))
        days = [d for d in parse_page(page, today) if d.date >= today.isoformat()]
    if not days:
        raise RuntimeError("오늘 이후 메뉴가 없다")
    return days
