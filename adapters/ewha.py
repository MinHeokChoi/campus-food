"""이화여대 — www.ewha.ac.kr/ewha/life/restaurant.do

식당이 다섯 곳이고 **한 곳이 게시글 하나**다 (`articleNo`). 사용자가 고르는 단위가
식당이라 식당을 place 로 둔다. 그래서 한 번 긁을 때 요청이 다섯 번 나간다.

게시글 하나에 그 주 월~일이 통째로 들어 있다 — `<div id="go-menu">` 안의
`<li class="b-menu-day">` 일곱 개, 각 요일 안에 조식/중식/석식 div. `srDt=YYYY-MM-DD`
로 임의 주를 부를 수 있다 (페이지의 이전/다음 링크가 이 파라미터를 쓴다).

거르는 데가 두 군데 있다.

1. 안 하는 끼니가 **빈 div 로** 렌더된다 (`<div class="b-menu b-menu-b breakfast"></div>`).
   끼니 div 를 `</div>` 로 끊으면 빈 조식이 뒤따르는 중식 메뉴를 삼켜서 중식이 조식으로
   찍힌다 (진·선·미관이 실제로 이렇다). 그래서 **끼니 div 의 시작 위치로 잘라서** 조각마다
   첫 <pre> 만 본다.
2. 메뉴 칸에 안내문이 섞여 들어온다 — `아점:10시30-1시30분`, `휴    무` 같은 줄.
   parse_items() 에서 턴다.
"""
import datetime as dt
import re
import sys

from . import base

VENUE = {
    "id": "ewha",
    "name": "이화여대",
    "region": "서울",
    "region_id": "seoul",
    "country": "KR",
    "tz": "Asia/Seoul",
    "calendar": "kr",
    "places": [
        {"id": "ihouse", "name": "I-House"},
        {"id": "jinsunmi", "name": "진선미관"},
        {"id": "enguni", "name": "공대식당"},
        {"id": "hanuri", "name": "한우리집"},
        {"id": "ehouse", "name": "E-House"},
    ],
}

URL = "https://www.ewha.ac.kr/ewha/life/restaurant.do?mode=view&articleNo={no}"

# 게시글 번호 -> place_id. VENUE["places"] 의 순서가 곧 같은 끼니 안의 표시 순서다.
ARTICLES = [
    (339841, "ihouse"),      # I-House 학생식당
    (903, "jinsunmi"),       # 진·선·미관 식당
    (905, "enguni"),         # 공대식당
    (899, "hanuri"),         # 한우리집 식당
    (900, "ehouse"),         # E-House 식당(201동)
]
PLACE_NAME = {p["id"]: p["name"] for p in VENUE["places"]}
PLACE_RANK = {p["id"]: i for i, p in enumerate(VENUE["places"])}

# 끼니 div 의 class 글자 -> 화면에 찍을 이름. 홍익대/상명대와 같은 말을 쓴다.
SLOTS = {"b": "아침", "l": "점심", "d": "저녁"}
SLOT_RANK = {"아침": 0, "점심": 1, "저녁": 2}

# 이용안내 문구의 끼니 이름 -> class 글자. 식당마다 말이 달라서 둘 다 받는다.
HOURS_NAMES = {"조식": "b", "아침": "b", "중식": "l", "점심": "l", "석식": "d", "저녁": "d"}

MAX_ITEM_LEN = 40            # run.check() 와 같은 값. 넘으면 메뉴가 아니라 안내문이다

RE_MENU_BOX = re.compile(r'id="go-menu"(.*)', re.S)
RE_DAY = re.compile(r'<li class="b-menu-day[^"]*">(.*?)</li>', re.S)
RE_DAY_DATE = re.compile(r"\((\d{1,2})\.(\d{1,2})\)")
RE_SLOT_DIV = re.compile(r'<div class="b-menu b-menu-([bld])[\s"]')
RE_PRE = re.compile(r"<pre>(.*?)</pre>", re.S)

# 이용안내는 go-menu 앞의 b-info-wrap 안에 <pre> 자유 텍스트로 한 덩어리 들어 있다
RE_HOURS_BOX = re.compile(r'class="b-info-wrap".*?<pre>(.*?)</pre>', re.S)
RE_HOURS = re.compile(
    r"(조식|중식|석식|아침|점심|저녁)\s*[:：]?\s*(\d{1,2}):(\d{2})\s*[-~–]\s*(\d{1,2}):(\d{2})")

# 메뉴 칸에 섞여 들어오는 줄들
RE_TIME_NOTE = re.compile(r"\d{1,2}\s*[:시]\s*\d{0,2}\s*분?\s*[-~–]")   # "11:30-14:00", "10시30-1시30분"
RE_NOISE = re.compile(r"원산지|알레르기|알러지")
CLOSED = {"휴무", "휴관", "미운영", "운영없음", "운영안함"}


def parse_hours(head):
    """이용안내 자유 텍스트 -> {class 글자: "HH:MM"}. 못 찾은 끼니는 아예 안 담는다.

    다섯 곳 다 '학기 중 평일' 을 먼저 적고 '주말·공휴일/방학' 을 뒤에 적는다.
    그래서 **먼저 나온 것을 쓴다** (setdefault). 학기 중을 기본으로 보겠다는 뜻이다.

    I-House 는 '11시~19시 (쉬는시간 14시30분~16시30분)' 이라 끼니 구분이 없다 —
    그 집은 전부 None 으로 나간다. 지어내지 않는다.
    """
    m = RE_HOURS_BOX.search(head)
    if not m:
        return {}
    out = {}
    for hm in RE_HOURS.finditer(base.clean(m.group(1))):
        out.setdefault(HOURS_NAMES[hm.group(1)],
                       "%02d:%02d" % (int(hm.group(4)), int(hm.group(5))))
    return out


def parse_items(pre, where):
    """<pre> 한 덩어리 -> 메뉴 줄. 휴무면 빈 리스트.

    섹션 머리글은 그대로 항목으로 남긴다. 식당마다 표기가 달라서
    ((정품)/(일품) · [한식]/[일품] · *일품식) 규칙 하나로 못 묶고,
    지우면 두 벌의 메뉴가 한 줄기로 붙어 버려 무엇이 세트인지 안 보인다.
    """
    out = []
    for raw in base.clean(pre).split("\n"):
        item = re.sub(r"\s+", " ", raw).strip()
        if not item:
            continue
        if item.replace(" ", "") in CLOSED:
            return []                       # "휴    무" 한 줄이면 그날 그 끼니는 없는 것이다
        if RE_TIME_NOTE.search(item) or RE_NOISE.search(item):
            continue
        if len(item) > MAX_ITEM_LEN:
            print("ewha: %s 항목이 너무 길다 — 버린다: %r" % (where, item[:50]), file=sys.stderr)
            continue
        out.append(item)
    return out


def parse_page(page, today, place_id):
    """게시글 한 장 -> {datetime.date: [Meal]}. 그 주에 메뉴가 없으면 빈 dict."""
    box = RE_MENU_BOX.search(page)
    if not box:
        return {}
    ends = parse_hours(page[:box.start()])

    out = {}
    for dm in RE_DAY.finditer(box.group(1)):
        block = dm.group(1)
        dd = RE_DAY_DATE.search(block)
        if not dd:
            continue
        date = base.resolve_year(int(dd.group(1)), int(dd.group(2)), today)
        if date is None:
            continue
        # 끼니 div 는 시작 위치로만 자른다 — 위 주석 1번 참고
        cuts = [(sm.start(), sm.group(1)) for sm in RE_SLOT_DIV.finditer(block)]
        for i, (pos, code) in enumerate(cuts):
            end_pos = cuts[i + 1][0] if i + 1 < len(cuts) else len(block)
            pm = RE_PRE.search(block[pos:end_pos])
            if not pm:
                continue                    # 안 하는 끼니는 빈 div 로 온다
            items = parse_items(pm.group(1), "%s %s" % (place_id, date))
            if not items:
                continue
            out.setdefault(date, []).append(
                base.Meal(slot=SLOTS[code], place=PLACE_NAME[place_id], place_id=place_id,
                          end=ends.get(code), items=items))
    return out


def collect(today, week):
    """다섯 곳을 한 주 긁는다 -> ({date: [Meal]}, 실패한 곳 설명).

    한 곳이 비거나 터져도 나머지는 낸다. 이번 주 메뉴를 아직 안 올린 식당이 늘 하나쯤 있다.
    """
    by_date, errors = {}, []
    for no, pid in ARTICLES:
        url = URL.format(no=no)
        if week is not None:
            url += "&srDt=" + week.isoformat()
        try:
            page = base.http_get(url)
        except Exception as e:  # noqa: BLE001
            errors.append("%s: %s" % (pid, e))
            continue
        found = parse_page(page, today, pid)
        found = {d: ms for d, ms in found.items() if d >= today}
        if not found:
            errors.append("%s: 메뉴 없음" % pid)
            continue
        for date, meals in found.items():
            by_date.setdefault(date, []).extend(meals)
    return by_date, errors


def fetch(today):
    """오늘 이후의 날들. 다섯 곳이 전부 비었을 때만 예외를 던진다."""
    by_date, errors = collect(today, None)
    if not by_date:
        # 일요일이면 이번 주에 남은 날이 오늘 하루뿐이고, 그날이 휴무면 아무것도 안 남는다.
        # 페이지가 다음 주를 갖고 있으니 한 번 더 본다.
        by_date, errors = collect(today, today + dt.timedelta(days=7 - today.weekday()))
    if not by_date:
        raise RuntimeError("식당 다섯 곳 모두 메뉴가 없다: " + "; ".join(errors))

    days = []
    for date in sorted(by_date):
        meals = by_date[date]
        # 끼니 순(아침→점심→저녁), 같은 끼니면 VENUE["places"] 순. 워치는 정렬하지 않는다.
        meals.sort(key=lambda m: (SLOT_RANK.get(m.slot, 9), PLACE_RANK.get(m.place_id, 9)))
        days.append(base.Day(date=date.isoformat(), meals=meals))
    return days
