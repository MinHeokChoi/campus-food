"""서울교대 — www.snue.ac.kr/snue/mm/menu/userMenuList.do?mi=1275

학생회관 1층 구내식당 한 곳인데, 페이지가 **학생 / 교직원 두 탭**으로 갈린다.
사용자가 고르는 단위가 그거라서 탭을 place 로 둔다 (학생식당 / 교직원식당).
같은 날 두 탭의 메뉴가 겹치는 날도 있고 (09.15) 다른 날도 있다 (09.14) — 그냥 둘 다 낸다.

두 탭이 **전부 초기 HTML 에 들어 있다.** 교직원 쪽은 `display:none` 으로 숨겨져 있을 뿐이라
탭을 누르는 흉내를 낼 필요가 없다. 마크업은

    <div class="meal_list sd">   학생      <div class="meal_list tl">   교직원
      <h3>중식</h3>                          <h3>중식</h3>
        <li><strong>09.14</strong><p>메뉴<br>메뉴</p></li>

꼴이고, 탭 / 끼니 제목 / 날짜칸이 문서 순서로 섞여 있다. 홍익대처럼 위치 순으로 훑는다.

**주차 이동이 없다.** `mi=1275` 뿐이고 폼의 hidden 은 `tlVal`(빈 값) 하나다.
`regDate`·`tlVal`·`date` 를 GET·POST 어느 쪽으로 넣어도 응답이 이번 주 그대로다 (확인함).
그래서 상명대처럼 다음 주를 부를 방법이 없다 — **주말에는 이번 주가 통째로 과거라 낼 게 없고,
그때는 예외를 던진다.** 러너가 옛 파일을 그대로 두는 쪽이 빈 파일보다 낫다.
"""
import re
import sys

from . import base

VENUE = {
    "id": "snue",
    "name": "서울교대",
    "region": "서울",
    "country": "KR",
    "tz": "Asia/Seoul",
    "calendar": "kr",
    "places": [
        {"id": "student", "name": "학생식당"},
        {"id": "faculty", "name": "교직원식당"},
    ],
}

URL = "https://www.snue.ac.kr/snue/mm/menu/userMenuList.do?mi=1275"

# 탭 div 의 class -> (화면에 찍을 이름, place_id)
PLACES = {
    "sd": ("학생식당", "student"),
    "tl": ("교직원식당", "faculty"),
}

# 페이지의 끼니 제목 -> 화면에 찍을 이름. 홍익대/상명대와 같은 말을 쓴다.
SLOTS = {"조식": "아침", "중식": "점심", "석식": "저녁"}

# 하루 안의 표시 순서. 끼니 순, 같은 끼니면 학생식당 먼저.
SLOT_RANK = {"아침": 0, "점심": 1, "저녁": 2}
PLACE_RANK = {"student": 0, "faculty": 1}

# 마감시각. **식단 페이지에는 시간이 없다.** 편의시설 페이지
#   https://www.snue.ac.kr/snue/cm/cntnts/cntntsView.do?mi=1336&cntntsId=1194
# 의 "이용시간" 표(학생식당 중식 11:20~13:20, 5,500원)에서 값을 옮겨 상수로 박았다.
# **학교가 시간을 바꾸면 여기를 고쳐야 한다.** 페이지를 한 번 더 받지 않는 건, 그 표가
# 일 년에 한 번 바뀔까 말까 한 값이라 매 실행마다 요청 한 번을 더 쓸 이유가 없어서다.
#
# 그 표에 있는 건 **학생식당 중식뿐**이다. 석식과 교직원 중식은 어디에도 안 적혀 있어서
# None 으로 둔다 — 워치가 "마감 지남" 판정을 못 하고 늘 열린 것으로 보이지만,
# 없는 시각을 지어내는 것보다 낫다.
ENDS = {("student", "점심"): "13:20"}

RE_BODY = re.compile(r'<div class="meal_list\s+sd".*?(?=<form name="pagingForm")', re.S)
RE_TAB = re.compile(r'<div class="meal_list\s+(sd|tl)"')
RE_HEAD = re.compile(r"<h3>\s*([^<]+?)\s*</h3>")
RE_CELL = re.compile(r"<strong>(\d{1,2})\.(\d{1,2})</strong>\s*<p>(.*?)</p>", re.S)

# 메뉴 칸에 섞여 들어오는 안내문. 원산지·알레르기·운영시간 줄은 메뉴가 아니다.
RE_NOISE = re.compile(r"원산지|알레르기|알러지|\d{1,2}:\d{2}\s*~")
MAX_ITEM_LEN = 40          # run.check() 가 막는 길이. 넘으면 안내문이라고 본다


def cell_items(fragment):
    """메뉴 칸 한 개 -> 항목 목록. 안내문 줄은 버린다.

    '휴무' 같은 줄은 남긴다 — 문 닫은 날이라는 게 사용자에게 필요한 정보다.
    """
    items = []
    for line in base.text_lines(fragment):
        if line == "-" or RE_NOISE.search(line):
            continue
        if len(line) > MAX_ITEM_LEN:
            print("snue: 너무 긴 줄 — 버린다 %r" % line[:50], file=sys.stderr)
            continue
        items.append(line)
    return items


def parse_page(page, today):
    """HTML 한 장 -> [Day]. 메뉴 칸을 하나도 못 찾으면 빈 리스트."""
    # 머리글·꼬리말에도 <h3> 가 있다. 학생 탭부터 페이징 폼까지로 잘라 놓고 본다.
    bm = RE_BODY.search(page)
    if not bm:
        return []
    body = bm.group(0)

    # 탭 / 끼니 제목 / 날짜칸이 문서 순서로 섞여 있다. 위치 순으로 훑으며 상태를 물고 간다.
    events = []
    for tm in RE_TAB.finditer(body):
        events.append((tm.start(), "tab", tm.group(1)))
    for hm in RE_HEAD.finditer(body):
        events.append((hm.start(), "slot", base.clean(hm.group(1))))
    for cm in RE_CELL.finditer(body):
        events.append((cm.start(), "cell", cm.groups()))
    events.sort(key=lambda e: e[0])

    place = None
    slot = None
    by_date = {}
    for _, kind, payload in events:
        if kind == "tab":
            place = PLACES[payload]
            slot = None                 # 탭이 바뀌면 끼니 제목도 다시 나온다
            continue
        if place is None:
            continue                    # 탭 시작 전의 <h3> 는 머리글이다 (예: "학생")
        if kind == "slot":
            if payload not in SLOTS:
                print("snue: 모르는 끼니 %r — 건너뛴다" % payload, file=sys.stderr)
                slot = None
            else:
                slot = SLOTS[payload]
            continue
        if slot is None:
            continue
        month, day, cell = payload
        date = base.resolve_year(int(month), int(day), today)
        if date is None:
            continue
        items = cell_items(cell)
        if not items:
            continue
        by_date.setdefault(date, []).append(
            base.Meal(slot=slot, place=place[0], place_id=place[1],
                      end=ENDS.get((place[1], slot)), items=items))

    days = []
    for date in sorted(by_date):
        meals = by_date[date]
        meals.sort(key=lambda m: (SLOT_RANK.get(m.slot, 9), PLACE_RANK.get(m.place_id, 9)))
        days.append(base.Day(date=date.isoformat(), meals=meals))
    return days


def fetch(today):
    """이번 주에서 오늘 이후의 날들.

    낼 게 없으면 예외다. 주말이면 이번 주가 전부 과거라 여기로 떨어지는데,
    다음 주를 부를 방법이 페이지에 없어서 그대로 실패로 둔다 (모듈 주석 참고).
    """
    page = base.http_get(URL)
    days = [d for d in parse_page(page, today) if d.date >= today.isoformat()]
    if not days:
        raise RuntimeError("오늘 이후 메뉴가 없다 (주차 이동이 없어 이번 주만 보인다)")
    return days
