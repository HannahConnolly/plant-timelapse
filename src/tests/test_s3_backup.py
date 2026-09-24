import unittest
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from src.services.s3_backup import upload_to_s3


class TestS3Backup(unittest.TestCase):
    def test_upload_uses_prefix_filename_and_content_type(self):
        client = MagicMock()

        key = upload_to_s3("data/photos/09-24-2026.jpg", "my-bucket", "photos/", client=client)

        self.assertEqual(key, "photos/09-24-2026.jpg")
        client.upload_file.assert_called_once_with(
            "data/photos/09-24-2026.jpg",
            "my-bucket",
            "photos/09-24-2026.jpg",
            ExtraArgs={"ContentType": "image/jpeg"},
        )

    def test_upload_failure_returns_none(self):
        client = MagicMock()
        client.upload_file.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
        )

        self.assertIsNone(upload_to_s3("growth.gif", "my-bucket", "animations", client=client))


if __name__ == "__main__":
    unittest.main()
