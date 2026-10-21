from typing import Any

from googleapiclient.discovery import build

from lifeos.shared.google.auth import GoogleAuthManager


class DriveConnector:
    """Connector for Google Drive API with mock fallback when unauthenticated."""

    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.auth_manager = GoogleAuthManager(service_name="google_drive")

    async def _get_service(self):
        creds = await self.auth_manager.get_credentials(self.user_id)
        if not creds:
            return None
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    async def list_files(
        self,
        folder_id: str = "root",
        max_results: int = 20
    ) -> list[dict[str, Any]]:
        service = await self._get_service()
        if not service:
            return [
                {
                    "id": "file_mock_001",
                    "name": "LifeOS_Architecture_V1.pdf",
                    "mime_type": "application/pdf",
                    "modified_time": "2026-10-18T12:00:00Z",
                    "size": "245000",
                    "is_mock": True
                },
                {
                    "id": "file_mock_002",
                    "name": "Q4_Financial_Projections.xlsx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "modified_time": "2026-10-19T16:20:00Z",
                    "size": "112000",
                    "is_mock": True
                }
            ]

        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime, size)"
        ).execute()

        files = results.get("files", [])
        return [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "mime_type": f.get("mimeType"),
                "modified_time": f.get("modifiedTime"),
                "size": f.get("size")
            }
            for f in files
        ]

    async def rename_file(self, file_id: str, new_name: str) -> dict[str, Any]:
        service = await self._get_service()
        if not service:
            return {
                "id": file_id,
                "name": new_name,
                "status": "renamed_mock",
                "is_mock": True
            }

        updated = service.files().update(
            fileId=file_id,
            body={"name": new_name},
            fields="id, name"
        ).execute()
        return updated

    async def move_file(self, file_id: str, target_folder_id: str) -> dict[str, Any]:
        service = await self._get_service()
        if not service:
            return {
                "id": file_id,
                "target_folder_id": target_folder_id,
                "status": "moved_mock",
                "is_mock": True
            }

        # Retrieve current parents
        file = service.files().get(fileId=file_id, fields="parents").execute()
        previous_parents = ",".join(file.get("parents", []))

        updated = service.files().update(
            fileId=file_id,
            addParents=target_folder_id,
            removeParents=previous_parents,
            fields="id, parents"
        ).execute()
        return updated

    async def create_folder(self, folder_name: str, parent_id: str = "root") -> dict[str, Any]:
        service = await self._get_service()
        if not service:
            return {
                "id": f"folder_mock_{folder_name}",
                "name": folder_name,
                "mime_type": "application/vnd.google-apps.folder",
                "is_mock": True
            }

        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id]
        }
        folder = service.files().create(body=metadata, fields="id, name").execute()
        return folder
