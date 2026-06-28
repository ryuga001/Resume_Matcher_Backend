import os
import tempfile
import uuid
from contextlib import contextmanager

import boto3

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    BotoCoreError = Exception
    ClientError = Exception


class S3Service:
    """Application-wide S3/MinIO client. Import and instantiate where needed."""

    def __init__(self):
        self._bucket   = os.getenv("AWS_S3_BUCKET", "")
        self._region   = os.getenv("AWS_REGION", "us-east-1")
        self._endpoint = os.getenv("S3_ENDPOINT_URL", "")  # empty = real AWS

    def _client(self):
        kwargs = dict(
            region_name=self._region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        if self._endpoint:
            kwargs["endpoint_url"] = self._endpoint
        return boto3.client("s3", **kwargs)

    # ── Upload ────────────────────────────────────────────────────────────────

    def presign_put(self, filename: str, content_type: str, folder: str) -> dict:
        """
        Generate a presigned PUT URL for a browser-direct upload.

        Args:
            filename:     Original file name (used for extension only).
            content_type: MIME type of the file.
            folder:       S3 key prefix, e.g. "courses/thumbnail".

        Returns:
            {"url": <presigned PUT URL>, "key": <object key>}

        Raises:
            ValueError if filename is empty.
            RuntimeError if the S3 call fails.
        """
        if not filename:
            raise ValueError("filename is required.")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        key = f"{folder.strip('/')}/{uuid.uuid4()}.{ext}"

        try:
            url = self._client().generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=3600,
            )
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Could not generate upload URL: {exc}") from exc

        return {"url": url, "key": key}

    # ── Download ──────────────────────────────────────────────────────────────

    def presign_get(self, key: str, expiry: int = 300) -> str:
        """
        Return a presigned GET URL valid for `expiry` seconds (default 5 min).
        Returns empty string for empty/missing keys — never raises.
        """
        if not key:
            return ""
        try:
            return self._client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expiry,
            )
        except (BotoCoreError, ClientError):
            return ""

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, key: str) -> None:
        """Delete a single object. Silently ignores empty keys or S3 errors."""
        if not key:
            return
        try:
            self._client().delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError):
            pass

    @contextmanager
    def stream_to_temp(self, key: str):
        """
        Stream an S3 object to a named temp file in 8 MB chunks — never loads
        the whole file into Python memory.  Yields the temp file path; deletes
        the file when the context exits.
        """
        obj  = self._client().get_object(Bucket=self._bucket, Key=key)
        body = obj["Body"]
        ext  = key.rsplit(".", 1)[-1] if "." in key else "bin"
        tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        try:
            for chunk in body.iter_chunks(chunk_size=8 * 1024 * 1024):
                tmp.write(chunk)
            tmp.flush()
            tmp.close()
            yield tmp.name
        finally:
            tmp.close()
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    def delete_many(self, keys: list[str]) -> None:
        """Batch-delete up to 1 000 objects in a single S3 request."""
        keys = [k for k in keys if k]
        if not keys:
            return
        try:
            self._client().delete_objects(
                Bucket=self._bucket,
                Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
            )
        except (BotoCoreError, ClientError):
            pass
