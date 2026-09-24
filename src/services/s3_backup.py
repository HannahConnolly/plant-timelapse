import logging
import mimetypes
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


def upload_to_s3(file_path: str | Path, bucket: str, prefix: str, client=None) -> str | None:
    """Uploads a file to s3://bucket/prefix/<filename>. Returns the object key, or None on failure."""
    file_path = Path(file_path)
    key = f"{prefix.strip('/')}/{file_path.name}"
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

    # Credentials and region come from ~/.aws (set up with `aws configure`)
    s3 = client or boto3.client("s3")
    try:
        s3.upload_file(str(file_path), bucket, key, ExtraArgs={"ContentType": content_type})
    except (BotoCoreError, ClientError, OSError) as e:
        # A failed backup shouldn't stop the Discord report, so log and carry on
        logger.error(f"S3 upload of '{file_path}' failed: {e}")
        return None

    logger.info(f"Backed up {file_path} to s3://{bucket}/{key}")
    return key
