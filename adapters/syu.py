"""삼육대 — www.syu.ac.kr/school-life/facility-information/cafeteria/

온라인 텍스트로 나오는 식당은 SU Lounge(학생회관 1층) 한 곳이다.
생활관 "만나의 집" 은 이미지로만 올라와서 여기서 다루지 않는다.

한 페이지에 그 주 월~금이 표 하나로 들어 있다. `?week_start=YYYYMMDD` 로 임의 주를 부른다
(월요일 날짜를 넣는다). 아직 안 올라온 주는 표 대신 `weekly-menu-empty` 만 온다.

중식이 A코너·B코너로 갈리는데, **코너를 place 가 아니라 slot 으로 뒀다** — 식당은 한 곳이고
두 코너가 같은 시간대에 같은 카운터에서 나오니, 사용자가 "여기 밥 먹는다" 로 고르는 단위는
SU Lounge 쪽이다. 코너는 그날 점심 안에서 고르는 것이라 홍익대의 점심A/점심B 와 같은 모양이 맞다.

끼니 행 헤더에 `조식<br>(08:00~09:30)` 꼴로 시간이 붙어 나온다 — 마감시각은 거기서 뽑는다.
위쪽 운영시간 표(학기중/방학중)는 쓰지 않는다. 행 헤더가 그 주에 실제로 적용된 시간이다.

금요일 석식은 `weekly-menu-table__no-dinner` 셀("운영 없음")로, 휴일은 빈 셀로 온다.
"""
import datetime as dt
import re

from . import base

VENUE = {
    "id": "syu",
    "name": "삼육대",
    "region": "서울",
    "region_id": "seoul",
    "country": "KR",
    "tz": "Asia/Seoul",
    "calendar": "kr",
    "places": [
        {"id": "su_lounge", "name": "SU Lounge"},   # 학생회관 1층
    ],
}

URL = "https://www.syu.ac.kr/school-life/facility-information/cafeteria/?week_start={week}"

PLACE_NAME = "SU Lounge"
PLACE_ID = "su_lounge"

# 행 헤더의 끼니 이름 -> 화면에 찍을 이름. 홍익대/상명대와 같은 말을 쓴다.
SLOTS = {"조식": "아침", "중식": "점심", "석식": "저녁"}

# 하루 안의 표시 순서. 아침 -> 점심A -> 점심B -> 저녁.
SLOT_RANK = {"아침": 0, "점심": 1, "점심A": 1, "점심B": 2, "저녁": 3}

# 메뉴 칸에 섞여 들어올 수 있는 안내문. 지금 페이지엔 안 보이지만
# 학식 페이지는 원산지·알레르기 줄이 갑자기 붙는 일이 잦아 미리 막는다.
RE_NOISE = re.compile(r"^[※*·•]?\s*(원산지|알레르기|알러지|공지|안내)")
CLOSED = {"운영 없음", "미운영", "휴무", "-", "*"}

RE_TABLE = re.compile(r'<table[^>]*class="[^"]*weekly-menu-table[^"]*"[^>]*>(.*?)</table>', re.S)
RE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
RE_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
RE_TD = re.compile(r"<td([^>]*)>(.*?)</td>", re.S)
RE_HEAD_DATE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")
RE_SLOT = re.compile(r"(조식|중식|석식)")
RE_CORNER = re.compile(r"([A-Z])코너")
RE_END = re.compile(r"~\s*(\d{1,2}):(\d{2})")


def parse_row_head(head):
    """끼니 행 헤더 -> (끼니 이름, 마감시각). 모르는 헤더면 (None, None)."""
    text = base.clean(base.RE_TAG.sub(" ", head))
    sm = RE_SLOT.search(text)
    if not sm:
        return None, None
    em = RE_END.search(text)
    end = "%02d:%02d" % (int(em.group(1)), int(em.group(2))) if em else None
    return SLOTS[sm.group(1)], end


def parse_page(page, today):
    """HTML 한 장 -> [Day]. 아직 안 올라온 주면 표가 없어서 빈 리스트."""
    tm = RE_TABLE.search(page)
    if not tm:
        return []
    rows = RE_ROW.findall(tm.group(1))
    if not rows:
        return []

    # 머리줄: "구분" th 하나 + "9월 14일 (월)" 5개. 날짜 th 만 세면 본문의 날짜 칸과 1:1 이다.
    dates = []
    for th in RE_TH.findall(rows[0]):
        dm = RE_HEAD_DATE.search(base.clean(th))
        if dm:
            dates.append(base.resolve_year(int(dm.group(1)), int(dm.group(2)), today))
    if not dates:
        return []

    by_date = {}
    slot, end = None, None          # B코너 행엔 th 가 없다 (위 행에서 rowspan). 직전 값을 이어 쓴다.
    for row in rows[1:]:
        ths = RE_TH.findall(row)
        if ths:
            slot, end = parse_row_head(ths[0])
        if slot is None:
            continue

        # 중식 행은 첫 칸이 코너 이름이고 날짜 칸은 그 다음부터다.
        corner = None
        cells = []
        for attrs, cell in RE_TD.findall(row):
            if "corner-label" in attrs:
                cm = RE_CORNER.search(base.clean(base.RE_TAG.sub("", cell)))
                corner = cm.group(1) if cm else None
                continue
            cells.append(cell)

        name = slot + corner if corner else slot
        for i, cell in enumerate(cells):
            if i >= len(dates) or dates[i] is None:
                continue
            items = [x for x in base.text_lines(cell)
                     if x not in CLOSED and not RE_NOISE.match(x)]
            if not items:                       # 빈 칸(휴일) · "운영 없음"(금요일 석식)
                continue
            by_date.setdefault(dates[i], []).append(
                base.Meal(slot=name, place=PLACE_NAME, place_id=PLACE_ID,
                          end=end, items=items))

    days = []
    for date in sorted(by_date):
        meals = by_date[date]
        meals.sort(key=lambda m: SLOT_RANK.get(m.slot, 99))
        days.append(base.Day(date=date.isoformat(), meals=meals))
    return days


def monday(date):
    return date - dt.timedelta(days=date.weekday())


def fetch(today):
    page = base.http_get(URL.format(week=monday(today).strftime("%Y%m%d")))
    days = [d for d in parse_page(page, today) if d.date >= today.isoformat()]
    if days:
        return days

    # 주말이면 이번 주가 통째로 과거다. 다음 주 월요일로 한 번 더 본다.
    # 다음 주가 아직 안 올라왔으면 표가 없어서 빈 리스트로 돌아온다 -> 예외.
    page = base.http_get(URL.format(week=(monday(today) + dt.timedelta(days=7)).strftime("%Y%m%d")))
    days = [d for d in parse_page(page, today) if d.date >= today.isoformat()]
    if not days:
        raise RuntimeError("오늘 이후 메뉴가 없다")
    return days
