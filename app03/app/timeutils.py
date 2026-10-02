"""시간 변환 유틸: UTC 저장값을 KST(한국 시간)로 표시."""
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def to_kst(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """datetime을 KST로 변환해 포맷팅한다.

    tz 정보가 없는(naive) 값은 UTC로 간주한다 (DB에 UTC로 저장되기 때문).
    """
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(KST).strftime(fmt)
