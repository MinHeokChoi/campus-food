#!/usr/bin/env python3
"""홍익대 학식 페이지(food_m.php)를 긁어 menu.json 을 쓴다.

표준 라이브러리만 쓴다. `python3 scrape.py` 로 오늘부터 나흘(p=2~5)을 받는다.
파싱에 실패한 날은 건너뛰고 나머지를 낸다. 전부 실패하면 기존 파일을 건드리지
않고 종료 코드 1 로 끝난다.

JSON 계약은 garmin/SPEC-학식.md 의 "JSON 계약" 절이 기준이다. 표시 순서까지
여기서 정한다. 워치는 정렬하지 않는다.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

URL = "https://apps.hongik.ac.kr/food/food_m.php?p={p}"
PAGES = (2, 3, 4, 5)          # 오늘, 내일, 모레, 글피
KST = dt.timezone(dt.timedelta(hours=9))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu.json")
OUT_MIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "menu.min.json")

PLACES = {"교직원식당": "교식", "제2기숙사": "학식"}
# 하루 안의 표시 순서. 끼니 슬롯 순, 같은 슬롯이면 학식 먼저.
SLOT_RANK = {"아침": 0, "아침 간편식": 1, "점심A": 2, "점심B": 2, "점심": 2, "저녁": 3}
PLACE_RANK = {"학식": 0, "교식": 1}
SIMPLE = "간편식"

RE_DATE = re.compile(r"\((\d{1,2})월\s*(\d{1,2})일\)")
RE_PLACE = re.compile(r'class="time"[^>]*>\s*<strong>([^<]+)</strong>')
RE_MEAL = re.compile(
    r"<th(?:\s[^>]*)?>(.*?)</th>\s*<td(?:\s[^>]*)?>(.*?)</td>", re.S)
RE_SLOT = re.compile(r"^\s*(?:<!--.*?-->\s*)?([^<\s][^<]*?)\s*<br", re.S)
RE_END = re.compile(r"\(\d{1,2}:\d{2}\s*~\s*(\d{1,2}:\d{2})\)")
RE_TAG = re.compile(r"<[^>]+>")


def clean(text):
    text = html.unescape(text).replace("\xa0", " ")
    return text.strip()


def resolve_year(month, day, today):
    """페이지에는 연도가 없다. 오늘과 가장 가까운 연도를 고른다."""
    best = None
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            cand = dt.date(year, month, day)
        except ValueError:
            continue
        if best is None or abs((cand - today).days) < abs((best - today).days):
            best = cand
    return best


def parse_items(cell):
    lines = [clean(RE_TAG.sub("\n", cell.replace("<br", "\n<br")))]
    items = []
    for line in lines[0].split("\n"):
        line = line.strip()
        if line:
            items.append(line)
    return items


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
    """HTML 한 장 -> {"date": "YYYY-MM-DD", "meals": [...]} 또는 None."""
    m = RE_DATE.search(page_html)
    if not m:
        return None
    date = resolve_year(int(m.group(1)), int(m.group(2)), today)
    if date is None:
        return None

    meals = []
    # 식당 제목과 끼니 행이 문서 순서로 섞여 있다. 위치 순으로 훑는다.
    events = []
    for pm in RE_PLACE.finditer(page_html):
        events.append((pm.start(), "place", clean(pm.group(1))))
    for mm in RE_MEAL.finditer(page_html):
        events.append((mm.start(), "meal", (mm.group(1), mm.group(2))))
    events.sort(key=lambda e: e[0])

    place = None
    for _, kind, payload in events:
        if kind == "place":
            place = PLACES.get(payload, payload)
            continue
        if place is None:
            continue
        head, cell = payload
        sm = RE_SLOT.search(head)
        em = RE_END.search(head)
        if not sm or not em:
            continue
        slot = clean(sm.group(1))
        end = em.group(1)
        if len(end) == 4:
            end = "0" + end
        for s, items in split_simple(slot, parse_items(cell)):
            if items:
                meals.append({"slot": s, "place": place, "end": end, "items": items})

    if not meals:
        return None

    meals.sort(key=lambda x: (SLOT_RANK.get(x["slot"], 99), PLACE_RANK.get(x["place"], 9)))
    return {"date": date.isoformat(), "meals": meals}


def fetch(p, timeout=20, tries=3):
    """한 번 실패해도 바로 버리지 않는다. 러너에서 p=5 가 한 번 빠진 적이 있다."""
    req = urllib.request.Request(URL.format(p=p), headers={"User-Agent": "hongik-food/1.0"})
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            last = e
    raise last


def minify(doc):
    return {
        "u": doc["updated"],
        "d": [{"t": d["date"],
               "m": [{"s": m["slot"], "p": m["place"], "e": m["end"], "i": m["items"]}
                     for m in d["meals"]]} for d in doc["days"]],
    }


def main():
    now = dt.datetime.now(KST)
    today = now.date()
    days = {}
    for p in PAGES:
        try:
            day = parse_page(fetch(p), today)
        except Exception as e:  # 네트워크·파싱 실패는 그 날만 버린다
            print(f"p={p}: {e}", file=sys.stderr)
            continue
        if day is None:
            print(f"p={p}: no menu", file=sys.stderr)
            continue
        if day["date"] < today.isoformat():
            print(f"p={p}: stale date {day['date']}", file=sys.stderr)
            continue
        days.setdefault(day["date"], day)

    if not days:
        print("all pages failed; leaving menu.json untouched", file=sys.stderr)
        return 1

    doc = {
        "updated": now.replace(microsecond=0).isoformat(),
        "days": [days[k] for k in sorted(days)][:4],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(OUT_MIN, "w", encoding="utf-8") as f:
        json.dump(minify(doc), f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"wrote {len(doc['days'])} day(s): {[d['date'] for d in doc['days']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
