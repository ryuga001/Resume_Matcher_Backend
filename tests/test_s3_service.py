"""Unit tests — S3Service (boto3 fully mocked)."""

import unittest
from unittest.mock import MagicMock, patch, mock_open

from common.s3 import S3Service

try:
    from botocore.exceptions import ClientError
    def _client_error():
        return ClientError({"Error": {"Code": "NoSuchKey", "Message": "not found"}}, "GetObject")
except ImportError:
    def _client_error():
        return Exception("botocore unavailable")


def _mock_client():
    return MagicMock()


class TestS3PresignGet(unittest.TestCase):

    def test_returns_empty_string_for_empty_key(self):
        svc = S3Service()
        self.assertEqual(svc.presign_get(""), "")

    def test_returns_empty_string_for_none_key(self):
        svc = S3Service()
        self.assertEqual(svc.presign_get(None), "")

    def test_calls_generate_presigned_url_get_object(self):
        svc = S3Service()
        svc._bucket = "mybucket"
        mock_client = _mock_client()
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/signed"
        with patch.object(svc, "_client", return_value=mock_client):
            result = svc.presign_get("resumes/abc.pdf", expiry=300)
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "mybucket", "Key": "resumes/abc.pdf"},
            ExpiresIn=300,
        )
        self.assertEqual(result, "https://s3.example.com/signed")

    def test_returns_empty_string_on_client_error(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.generate_presigned_url.side_effect = _client_error()
        with patch.object(svc, "_client", return_value=mock_client):
            result = svc.presign_get("resumes/abc.pdf")
        self.assertEqual(result, "")

    def test_does_not_raise_on_any_error(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.generate_presigned_url.side_effect = _client_error()
        with patch.object(svc, "_client", return_value=mock_client):
            try:
                svc.presign_get("some/key.pdf")
            except Exception:
                self.fail("presign_get must never raise")

    def test_default_expiry_is_300(self):
        svc = S3Service()
        svc._bucket = "b"
        mock_client = _mock_client()
        mock_client.generate_presigned_url.return_value = "url"
        with patch.object(svc, "_client", return_value=mock_client):
            svc.presign_get("key.pdf")
        _, kwargs = mock_client.generate_presigned_url.call_args
        self.assertEqual(kwargs.get("ExpiresIn", mock_client.generate_presigned_url.call_args[0]), 300)


class TestS3PresignPut(unittest.TestCase):

    def test_raises_value_error_for_empty_filename(self):
        svc = S3Service()
        with self.assertRaises(ValueError):
            svc.presign_put("", "application/pdf", "resumes")

    def test_returns_url_and_key_dict(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.generate_presigned_url.return_value = "https://put-url"
        with patch.object(svc, "_client", return_value=mock_client):
            result = svc.presign_put("resume.pdf", "application/pdf", "resumes")
        self.assertIn("url", result)
        self.assertIn("key", result)
        self.assertEqual(result["url"], "https://put-url")

    def test_key_starts_with_folder(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.generate_presigned_url.return_value = "https://put-url"
        with patch.object(svc, "_client", return_value=mock_client):
            result = svc.presign_put("myresume.pdf", "application/pdf", "uploads/resumes")
        self.assertTrue(result["key"].startswith("uploads/resumes/"))

    def test_key_preserves_file_extension(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.generate_presigned_url.return_value = "https://put-url"
        with patch.object(svc, "_client", return_value=mock_client):
            result = svc.presign_put("myresume.pdf", "application/pdf", "resumes")
        self.assertTrue(result["key"].endswith(".pdf"))

    def test_raises_runtime_error_on_s3_error(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.generate_presigned_url.side_effect = _client_error()
        with patch.object(svc, "_client", return_value=mock_client):
            with self.assertRaises(RuntimeError):
                svc.presign_put("file.pdf", "application/pdf", "folder")


class TestS3Delete(unittest.TestCase):

    def test_ignores_empty_key(self):
        svc = S3Service()
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            svc.delete("")
        mock_client.delete_object.assert_not_called()

    def test_ignores_none_key(self):
        svc = S3Service()
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            svc.delete(None)
        mock_client.delete_object.assert_not_called()

    def test_calls_delete_object_with_bucket_and_key(self):
        svc = S3Service()
        svc._bucket = "mybucket"
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            svc.delete("resumes/abc.pdf")
        mock_client.delete_object.assert_called_once_with(Bucket="mybucket", Key="resumes/abc.pdf")

    def test_does_not_raise_on_s3_error(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.delete_object.side_effect = _client_error()
        with patch.object(svc, "_client", return_value=mock_client):
            try:
                svc.delete("some/key")
            except Exception:
                self.fail("delete() must never raise")


class TestS3DeleteMany(unittest.TestCase):

    def test_ignores_empty_list(self):
        svc = S3Service()
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            svc.delete_many([])
        mock_client.delete_objects.assert_not_called()

    def test_ignores_list_of_empty_strings(self):
        svc = S3Service()
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            svc.delete_many(["", "", ""])
        mock_client.delete_objects.assert_not_called()

    def test_calls_delete_objects_with_valid_keys(self):
        svc = S3Service()
        svc._bucket = "mybucket"
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            svc.delete_many(["key1.pdf", "key2.pdf"])
        _, kwargs = mock_client.delete_objects.call_args
        objects = kwargs["Delete"]["Objects"]
        keys = [o["Key"] for o in objects]
        self.assertIn("key1.pdf", keys)
        self.assertIn("key2.pdf", keys)

    def test_does_not_raise_on_s3_error(self):
        svc = S3Service()
        mock_client = _mock_client()
        mock_client.delete_objects.side_effect = _client_error()
        with patch.object(svc, "_client", return_value=mock_client):
            try:
                svc.delete_many(["key1.pdf"])
            except Exception:
                self.fail("delete_many() must never raise")


class TestS3UploadFile(unittest.TestCase):

    def test_calls_put_object_with_key_and_content_type(self):
        svc = S3Service()
        svc._bucket = "mybucket"
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            with patch("builtins.open", mock_open(read_data=b"PDF content")):
                svc.upload_file("/tmp/fake.pdf", "resumes/fake.pdf", "application/pdf")
        _, kwargs = mock_client.put_object.call_args
        self.assertEqual(kwargs["Bucket"], "mybucket")
        self.assertEqual(kwargs["Key"], "resumes/fake.pdf")
        self.assertEqual(kwargs["ContentType"], "application/pdf")

    def test_default_content_type_is_octet_stream(self):
        svc = S3Service()
        svc._bucket = "b"
        mock_client = _mock_client()
        with patch.object(svc, "_client", return_value=mock_client):
            with patch("builtins.open", mock_open(read_data=b"data")):
                svc.upload_file("/tmp/file.bin", "some/key")
        _, kwargs = mock_client.put_object.call_args
        self.assertEqual(kwargs["ContentType"], "application/octet-stream")


if __name__ == "__main__":
    unittest.main()
