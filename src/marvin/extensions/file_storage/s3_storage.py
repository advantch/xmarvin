import tempfile
import uuid
import warnings

import boto3
from botocore.exceptions import ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

from marvin.extensions.file_storage.base import BaseBlobStorage
from marvin.extensions.settings import s3_settings
from marvin.extensions.types.data_source import FileStoreMetadata
from marvin.extensions.utilities.file_utilities import (
    ContentFile,
    File,
    SimpleUploadedFile,
)
from marvin.extensions.utilities.logging import logger
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class BucketConfig(BaseSettings):
    bucket_name: str
    access_key_id: str
    secret_access_key: str
    endpoint_url: str
    region: str

    model_config = SettingsConfigDict(env_prefix="MARVIN_S3_")

    @classmethod
    def from_env(cls):
        return cls(
            bucket_name=s3_settings.bucket_name,
            access_key_id=s3_settings.access_key_id,
            secret_access_key=s3_settings.secret_access_key,
            endpoint_url=s3_settings.endpoint_url,
            region=s3_settings.region,
        )

    @classmethod
    def from_django_settings(cls):
        try:
            from django.conf import settings

            return cls(
                bucket_name=settings.S3_BUCKET_NAME,
                access_key_id=settings.S3_ACCESS_KEY_ID,
                secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                endpoint_url=settings.S3_ENDPOINT_URL,
                region=settings.S3_REGION,
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


class S3Storage(BaseBlobStorage, ExposeSyncMethodsMixin):
    location: str | None = "files"
    prefix: str | None = None
    acl: str | None = "private"

    def __init__(self, config: BucketConfig | None = None):
        if config is None:
            config = BucketConfig.from_env()

        self.s3_client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            region_name=config.region,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
        )
        self.bucket_name = config.bucket_name

    def exists(self, object_name):
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError:
            return False

    def get_file_path(self, file_id: str | uuid.UUID, prefix: str | None = None) -> str:
        prefix = prefix or self.prefix
        if prefix is None:
            return f"{self.location}/{file_id}"
        else:
            return f"{self.location}/{prefix}/{file_id}"

    def upload_file(
        self,
        file: ContentFile | SimpleUploadedFile | File,
        file_name=None,
        file_id=None,
        prefix=None,
    ) -> FileStoreMetadata:
        """
        Upload a file to S3.
        """

        path = self.get_file_path(file_id, prefix)
        try:
            self.s3_client.upload_fileobj(
                file, self.bucket_name, path, ExtraArgs={"ACL": self.acl}
            )
        except ClientError as e:
            raise Exception(f"Error uploading file to S3: {e}")

        s3_object = self.s3_client.head_object(Bucket=self.bucket_name, Key=path)

        return FileStoreMetadata(
            file_id=file_id,
            file_size=getattr(file, "size", None),
            file_name=file_name,
            file_type=getattr(file, "content_type", None),
            file_path=path,
            created=s3_object["LastModified"],
            modified=s3_object["LastModified"],
            storage_type="s3",
            bucket=self.bucket_name,
        )

    def download_file(
        self, file_id, file_path: str | None = None, prefix: str | None = None
    ) -> File | ContentFile | str:
        """
        Download a file from S3 to a local file path.
        If file_path is None, return a ContentFile.
        """
        try:
            s3_path = self.get_file_path(file_id, prefix)
            local_file_path = file_path or s3_path

            # create a temp file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                self.s3_client.download_fileobj(self.bucket_name, s3_path, temp_file)
                temp_file.flush()
                temp_file.seek(0)
                if file_path is None:
                    return ContentFile(temp_file.read(), name=file_id)
                else:
                    with open(local_file_path, "wb") as f:
                        f.write(temp_file.read())
                    return local_file_path

        except ClientError as e:
            raise Exception(f"Error downloading file from S3: {e}")

    def generate_presigned_url(
        self,
        file_metadata: FileStoreMetadata | str,
        expiration=3600,
        method="get",
        http_method=None,
        content_type=None,
        as_attachment=True,
    ) -> str | None:
        """
        Generate a presigned URL for a file.
        Method can be get or put.
        """
        if http_method is not None:
            warnings.warn(
                "http_method is deprecated. Use method instead.", DeprecationWarning
            )
            method = http_method
        try:
            file_id = (
                file_metadata
                if isinstance(file_metadata, str)
                else file_metadata.file_id
            )
            params = {
                "Bucket": self.bucket_name,
                "Key": file_id,
            }
            if content_type:
                params["ResponseContentType"] = content_type
            if not as_attachment:
                params["ResponseContentDisposition"] = "inline"

            url = self.s3_client.generate_presigned_url(
                f"{method}_object", Params=params, ExpiresIn=expiration
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

    async def get_file_async(self, file_metadata: FileStoreMetadata):
        """
        Get a file from S3.
        """
        return self.download_file(file_metadata.file_id, file_path=None)

    async def delete_file_async(self, file_metadata: FileStoreMetadata):
        """
        Delete a file from S3.
        """
        return self.delete_object(file_metadata.file_id)

    @expose_sync_method("save_file")
    async def save_file_async(
        self,
        file: File | ContentFile,
        file_id: str | uuid.UUID | None = None,
        file_name: str = None,
    ) -> FileStoreMetadata:
        """
        Save a file to S3.
        """

        file_id = str(file_id or uuid.uuid4())
        file_name = file_name or getattr(file, "name", str(file_id))
        file_metadata = self.upload_file(file, file_name, file_id)
        presigned_url = self.generate_presigned_url(file_metadata)
        url = presigned_url.split("?")[0]
        file_metadata.presigned_url = presigned_url
        file_metadata.url = url
        return file_metadata

    @expose_sync_method("request_presigned_url")
    async def request_presigned_url_async(
        self, file_id: str, private: bool = True
    ) -> dict:
        """
        Request a presigned URL for a file.
        """
        return {
            "id": file_id,
            "upload_url": self.generate_presigned_url(file_id, method="put"),
        }
