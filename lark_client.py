import requests
import json
from config import settings

class LarkClient:
    BASE_URL = "https://open.larksuite.com"

    def __init__(self):
        self.app_id = settings.LARK_APP_ID
        self.app_secret = settings.LARK_APP_SECRET
        self._tenant_access_token = None

    def get_tenant_access_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token

        resp = requests.post(
            f"{self.BASE_URL}/open-apis/auth/v3/app_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark auth failed: {data}")
        self._tenant_access_token = data["tenant_access_token"]
        return self._tenant_access_token

    def send_text_message(self, receive_id: str, text: str, receive_id_type: str = "chat_id"):
        token = self.get_tenant_access_token()
        resp = requests.post(
            f"{self.BASE_URL}/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text})
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Lark send message failed: {data}")
        return data

    def download_resource(self, message_id: str, file_key: str, resource_type: str = "image") -> bytes:
        token = self.get_tenant_access_token()
        url = f"{self.BASE_URL}/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"type": resource_type},
            stream=True,
            timeout=60
        )
        resp.raise_for_status()
        return resp.content
