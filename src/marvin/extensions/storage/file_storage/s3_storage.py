import io
import tempfile

import boto3
from botocore.exceptions import ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

from marvin.extensions.settings import extension_settings
from marvin.extensions.storage.file_storage.local_file_storage import BaseFileStorage
from marvin.extensions.utilities.logging import logger


class BucketConfig(BaseSettings):
    bucket_name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_endpoint_url_s3: str
    aws_region: str

    model_config = SettingsConfigDict(env_prefix="AWS_")

    @classmethod
    def from_env(cls):
        return cls(
            bucket_name=extension_settings.s3.bucket_name,
            aws_access_key_id=extension_settings.s3.aws_access_key_id,
            aws_secret_access_key=extension_settings.s3.aws_secret_access_key,
            aws_endpoint_url_s3=extension_settings.s3.aws_endpoint_url_s3,
            aws_region=extension_settings.s3.aws_region,
        )

    @classmethod
    def from_django_settings(cls):
        try:
            from django.conf import settings

            return cls(
                bucket_name=settings.S3_BUCKET_NAME,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                aws_endpoint_url_s3=settings.S3_ENDPOINT_URL,
                aws_region=settings.S3_REGION,
            )
        except ImportError as e:
            logger.error(
                f"""
                         Error getting S3 config from django settings: {e}. Make sure you are running in a django project 
                         and have the django setting for S3_BUCKET_NAME, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, 
                         S3_ENDPOINT_URL, and S3_REGION set."""
            )
            return None
        except Exception as e:
            print(f"Error getting S3 config from django settings: {e}")
            return None


class S3Storage(BaseFileStorage):
    def __init__(self, config: BucketConfig = None):
        if config is None:
            config = BucketConfig.from_env()

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=config.aws_endpoint_url_s3,
            region_name=config.aws_region,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
        )
        self.bucket_name = config.bucket_name

    def exists(self, object_name):
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError:
            return False

    def upload_file(self, file_object: io.BytesIO, file_name):
        try:
            # check if open
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_object.read())
            self.s3_client.upload_file(temp_file.name, self.bucket_name, file_name)
            return True
        except ClientError:
            return False

    def download_file(self, object_name, file_path):
        try:
            local_file_path = file_path.split("/")[-1]
            with open(local_file_path, "wb") as f:
                self.s3_client.download_fileobj(self.bucket_name, object_name, f)
                return local_file_path
        except ClientError:
            return None

    def generate_presigned_url(
        self,
        object_name,
        expiration=3600,
        http_method="get",
        content_type=None,
        as_attachment=True,
    ):
        try:
            params = {
                "Bucket": self.bucket_name,
                "Key": object_name,
            }
            if content_type:
                params["ResponseContentType"] = content_type
            if not as_attachment:
                params["ResponseContentDisposition"] = "inline"

            url = self.s3_client.generate_presigned_url(
                f"{http_method}_object", Params=params, ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"Error generating presigned URL: {e}")
            return None

    def list_objects(self, prefix=""):
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name, Prefix=prefix
            )
            return [obj["Key"] for obj in response.get("Contents", [])]
        except ClientError as e:
            print(f"Error listing objects: {e}")
            return []

    def delete_object(self, object_name):
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            print(f"Error deleting object: {e}")
            return False

    def generate_streaming_url(self, object_name, expiration=3600):
        try:
            params = {
                "Bucket": self.bucket_name,
                "Key": object_name,
                "ResponseContentType": "audio/mpeg",  # Adjust based on your file type
                "ResponseContentDisposition": "inline",
            }

            url = self.s3_client.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"Error generating streaming URL: {e}")
            return None

    def stream_to_file(self, object_name, chunk_iterator):
        try:
            # Initiate multipart upload
            mpu = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name, Key=object_name
            )
            upload_id = mpu["UploadId"]

            parts = []
            part_number = 1

            for chunk in chunk_iterator:
                # Upload part
                part = self.s3_client.upload_part(
                    Body=chunk,
                    Bucket=self.bucket_name,
                    Key=object_name,
                    PartNumber=part_number,
                    UploadId=upload_id,
                )

                parts.append({"PartNumber": part_number, "ETag": part["ETag"]})
                part_number += 1

            # Complete multipart upload
            self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_name,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            return True

        except Exception:
            # Abort the multipart upload if it was initiated
            if "upload_id" in locals():
                self.s3_client.abort_multipart_upload(
                    Bucket=self.bucket_name, Key=object_name, UploadId=upload_id
                )
            return False

    def save_file(self, file_object: io.BytesIO, file_name):
        return self.upload_file(file_object, file_name)

    def get_file(self, file_id):
        return self.download_file(file_id, file_path=None)

    def delete_file(self, file_id):
        return self.delete_object(file_id)
