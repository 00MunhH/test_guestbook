"""파일 저장소 — S3 (운영) / MinIO (로컬 테스트) 추상화."""
import boto3
from botocore.config import Config

from .config import settings


def _client():
    kwargs = {"region_name": settings.aws_region, "config": Config(signature_version="s3v4")}
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **kwargs)


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """바이트를 S3 객체로 업로드한다."""
    _client().put_object(
        Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type
    )


def presigned_download_url(key: str, filename: str, expires: int = 300) -> str:
    """다운로드용 presigned URL 발급 (원본 파일명으로 저장되게 Content-Disposition 지정)."""
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expires,
    )
