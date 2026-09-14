"""장소 하나에 어댑터 하나. 여기 등록하면 러너가 집어 간다."""
from . import hongik

REGISTRY = {
    hongik.VENUE["id"]: hongik,
}
