# hongik-food

홍익대 학식 페이지(`apps.hongik.ac.kr/food/food_m.php`)를 매일 새벽 긁어
정적 JSON 으로 낸다. Garmin 워치 앱 `학식` 이 이 파일을 읽는다.

- `https://minheokchoi.github.io/hongik-food/menu.json` — 오늘부터 이번 주 금요일까지 (최대 4일)
- `menu.min.json` — 키를 줄인 같은 내용 (`u`,`d`,`t`,`m`,`s`,`p`,`e`,`i`)

```bash
python3 scrape.py            # menu.json 갱신
python3 tests/test_scrape.py # 파서 검사
```

GitHub Actions 가 KST 05:30 에 돌고, 바뀐 날만 커밋한다.
