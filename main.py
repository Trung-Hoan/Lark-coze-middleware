import json
import hmac
import hashlib
import base64
import binascii

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from config import settings
from database import Database
from lark_client import LarkClient
from coze_client import CozeClient

app = FastAPI(title="Lark - Coze.cn Middleware")
db = Database(settings.DATABASE_PATH)
lark_client = LarkClient()
coze_client = CozeClient()


def verify_lark_signature(signature: str, timestamp: str, nonce: str, body: str) -> bool:
    """Xác thực webhook signature của Lark."""
    key = settings.LARK_ENCRYPT_KEY
    if not key:
        return True

    try:
        bytes_b = "".join([timestamp, nonce, key, body]).encode("utf-8")
        hmac_code = hmac.new(key.encode("utf-8"), bytes_b, hashlib.sha256).digest()
        expected = base64.b64encode(hmac_code).decode("utf-8")
        return hmac.compare_digest(expected, signature)
    except (binascii.Error, UnicodeEncodeError):
        return False


def remove_mention(text: str, message: dict) -> str:
    """Loại bỏ @mention tới bot trong group chat."""
    mentions = message.get("mentions") or []
    for m in mentions:
        if m.get("name") == settings.LARK_BOT_NAME:
            key = m.get("key", "")
            text = text.replace(key, "").strip()
    return text


def process_message(event: dict):
    message = event.get("message", {})
    sender = event.get("sender", {}).get("sender_id", {})

    lark_user_id = sender.get("user_id")
    chat_id = message.get("chat_id")
    message_id = message.get("message_id")
    msg_type = message.get("message_type")
    chat_type = message.get("chat_type")

    if not lark_user_id or not chat_id or not message_id:
        return

    # Group chat: chỉ phản hồi khi bot bị @mention
    if chat_type == "group":
        mentions = message.get("mentions") or []
        if not any(m.get("name") == settings.LARK_BOT_NAME for m in mentions):
            return

    # Lấy hoặc tạo Coze conversation cho user
    conversation_id = db.get_conversation_id(lark_user_id)
    if not conversation_id:
        conversation_id = coze_client.create_conversation()
        db.save_conversation_id(lark_user_id, conversation_id)

    messages = []

    if msg_type == "text":
        content = json.loads(message.get("content", "{}"))
        text = remove_mention(content.get("text", ""), message)
        if not text:
            return
        messages.append({"role": "user", "content_type": "text", "content": text})
        db.save_message(lark_user_id, "user", text, "text")

    elif msg_type == "image":
        content = json.loads(message.get("content", "{}"))
        image_key = content.get("image_key")
        if not image_key:
            return
        file_content = lark_client.download_resource(message_id, image_key, "image")
        file_id = coze_client.upload_file(file_content, "image.png")
        messages.append({"role": "user", "content_type": "image", "content": file_id})
        db.save_message(lark_user_id, "user", file_id, "image")

    elif msg_type == "file":
        content = json.loads(message.get("content", "{}"))
        file_key = content.get("file_key")
        file_name = content.get("file_name", "file")
        if not file_key:
            return
        file_content = lark_client.download_resource(message_id, file_key, "file")
        file_id = coze_client.upload_file(file_content, file_name)
        messages.append({"role": "user", "content_type": "file", "content": file_id})
        db.save_message(lark_user_id, "user", file_id, "file")

    else:
        # Các loại tin nhắn khác chưa hỗ trợ
        return

    try:
        reply = coze_client.chat(conversation_id, lark_user_id, messages, stream=True)
        db.save_message(lark_user_id, "assistant", reply, "text")
        lark_client.send_text_message(chat_id, reply)
    except Exception as e:
        print(f"[ERROR] Coze chat failed: {e}")
        lark_client.send_text_message(chat_id, settings.FALLBACK_MESSAGE)


@app.post(settings.WEBHOOK_PATH)
async def lark_webhook(request: Request):
    body = await request.body()
    body_str = body.decode("utf-8")

    data = json.loads(body_str)

    # URL verification challenge
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # Xác thực signature
    signature = request.headers.get("X-Lark-Signature")
    timestamp = request.headers.get("X-Lark-Timestamp")
    nonce = request.headers.get("X-Lark-Nonce")

    if signature and not verify_lark_signature(signature, timestamp, nonce, body_str):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    event = data.get("event")
    if event:
        try:
            process_message(event)
        except Exception as e:
            print(f"[ERROR] Process message failed: {e}")

    return {"code": 0}


@app.get("/")
async def root():
    return {
        "service": "Lark - Coze.cn Middleware",
        "status": "running",
        "health_endpoint": "/health",
        "webhook_endpoint": "/webhook"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
