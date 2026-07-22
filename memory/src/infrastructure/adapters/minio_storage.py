import asyncio
import io
import os
import uuid

from minio import Minio

from memory.src.application.ports.storage import StoragePort


class MinioStorage(StoragePort):
    """
    Implementación real de StoragePort (F3-T6) sobre MinIO/S3. Preferible a `LocalFsStorage`
    cuando el servicio corre en varias réplicas o se quiere el almacenamiento desacoplado del host.
    """
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False):
        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket
        if not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)

    async def save(self, file_path: str, content: bytes) -> str:
        return await asyncio.to_thread(self._save_sync, file_path, content)

    def _save_sync(self, file_path: str, content: bytes) -> str:
        object_name = f"{uuid.uuid4().hex}_{os.path.basename(file_path)}"
        self.client.put_object(self.bucket, object_name, io.BytesIO(content), length=len(content))
        return f"minio://{self.bucket}/{object_name}"

    async def get(self, uri: str) -> bytes:
        return await asyncio.to_thread(self._get_sync, uri)

    def _get_sync(self, uri: str) -> bytes:
        response = self.client.get_object(self.bucket, self._uri_to_object_name(uri))
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    async def delete(self, uri: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, uri)

    def _delete_sync(self, uri: str) -> bool:
        self.client.remove_object(self.bucket, self._uri_to_object_name(uri))
        return True

    def _uri_to_object_name(self, uri: str) -> str:
        prefix = f"minio://{self.bucket}/"
        if not uri.startswith(prefix):
            raise ValueError(f"URI no reconocida por MinioStorage (bucket '{self.bucket}'): {uri}")
        return uri[len(prefix):]
