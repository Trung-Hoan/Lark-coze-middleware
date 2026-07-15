import requests
import json
import re
from config import settings

class CozeClient:
    def __init__(self):
        self.base_url = settings.COZE_BASE_URL.rstrip("/")
        self.token = settings.COZE_TOKEN
        self.bot_id = settings.COZE_BOT_ID
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def create_conversation(self) -> str:
        url = f"{self.base_url}/v3/conversation/create"
        resp = requests.post(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Coze create conversation failed: {data}")
        return data["data"]["id"]

    def upload_file(self, file_content: bytes, file_name: str) -> str:
        url = f"{self.base_url}/v3/files/upload"
        files = {"file": (file_name, file_content)}
        headers = {"Authorization": f"Bearer {self.token}"}
        resp = requests.post(url, headers=headers, files=files, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Coze upload file failed: {data}")
        return data["data"]["id"]

    def chat(self, conversation_id: str, user_id: str, messages: list, stream: bool = True) -> str:
        url = f"{self.base_url}/v3/chat"
        payload = {
            "bot_id": self.bot_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "additional_messages": messages,
            "stream": stream
        }
        resp = requests.post(
            url,
            headers=self.headers,
            json=payload,
            stream=stream,
            timeout=120
        )
        resp.raise_for_status()

        if stream:
            return self._parse_stream(resp)
        else:
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Coze chat failed: {data}")
            return self._extract_answer(data)

    def _parse_stream(self, resp) -> str:
        full_text = ""
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            line = raw_line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            try:
                data = json.loads(line[5:])
            except json.JSONDecodeError:
                continue
            event = data.get("event")
            msg = data.get("message", {})
            if event == "conversation.message.completed" and msg.get("role") == "assistant":
                content = msg.get("content", "")
                if content:
                    full_text += content
        return full_text or "(Không có phản hồi)"

    def _extract_answer(self, data: dict) -> str:
        messages = data.get("data", {}).get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("type") == "answer":
                return msg.get("content", "")
        return "(Không có phản hồi)"
