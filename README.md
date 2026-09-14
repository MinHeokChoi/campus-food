# campus-food

대학 학식 페이지를 매일 새벽 긁어 정적 JSON 으로 낸다.
Garmin 워치 앱 **Campus Food** 가 이 파일을 읽는다.

지금 등록된 장소는 **홍익대(서울) 한 곳**이다. 서울 25곳까지 늘릴 수 있다는 걸
조사로 확인했다 — 워치 앱 저장소의 `SURVEY-서울학식.md`, `PLAN-다학교.md` 참고.

## 쓰기

```bash
python3 run.py                 # 등록된 장소 전부
python3 run.py hongik          # 한 곳만
python3 tests/test_adapters.py # 파서 검사 (네트워크 안 탐)
```

GitHub Actions 가 KST 05:30 / 08:00 에 돌고, 바뀐 날만 커밋한다.

## 구조

```
adapters/
  base.py      Meal/Day, HTML 헬퍼, http_get. 표준 라이브러리만
  hongik.py    장소 하나 = 어댑터 하나
  __init__.py  REGISTRY — 여기 등록하면 러너가 집어 간다
calendars/
  kr.py        나라별 공휴일
run.py         받기·검증·기록. 한 곳이 터져도 나머지는 계속한다
tests/
  fixtures/    어댑터마다 실제 응답 1개
```

**어댑터 규약은 둘뿐이다.**

```python
VENUE = {"id", "name", "region", "country", "tz", "calendar", "places"}
def fetch(today: datetime.date) -> list[base.Day]
```

`fetch` 는 받아서 파싱만 한다. 정렬·검증·기록은 러너가 한다.
실패하면 **예외를 던진다** — 빈 리스트로 조용히 넘기면 러너가 "메뉴 없는 날"과 구분하지 못한다.

## 내는 것

- `https://minheokchoi.github.io/campus-food/menu.json` — 오늘부터 최대 4일
- `menu.min.json` — 키를 줄인 같은 내용 (`u`,`h`,`d`,`t`,`m`,`s`,`p`,`e`,`i`)
- `holidays` — 오늘부터 60일 안의 공휴일. 시계는 요일만 알아서 여기서 실어 준다

**이 두 경로는 이제 옮기면 안 된다.** 설치된 시계가 이 URL 을 상수로 들고 있다.
장소별 파일(`menu/<id>.json`)과 목록(`venues.json`)은 1단계에서 **추가로** 낸다.

저장소 이름은 2026-09-14 에 `hongik-food` → `campus-food` 로 바꿨다. 그때 설치자가 개발자 본인
하나뿐이라 옛 주소를 지킬 필요가 없었다. **지금은 다르다** — 스토어에 v1.1 이 올라간 뒤로는
이 주소가 남의 시계 안에 박혀 있다.
