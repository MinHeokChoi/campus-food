"""장소 하나에 어댑터 하나. 여기 등록하면 러너가 집어 간다.

새 장소를 붙이는 순서:
  1. `adapters/<id>.py` 에 VENUE 와 fetch(today) 를 쓴다 (smu.py 가 제일 단순한 본보기다)
  2. 응답 한 장을 `tests/fixtures/<id>_YYYYMMDD.html` 로 저장하고 테스트를 붙인다
  3. 여기 REGISTRY 에 넣는다
"""
from . import ewha, hongik, smu, snue, syu

REGISTRY = {
    m.VENUE["id"]: m
    for m in (ewha, hongik, smu, snue, syu)
}
