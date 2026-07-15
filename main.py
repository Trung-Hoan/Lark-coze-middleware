import json
import hmac
import hashlib
import base64
import binascii

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
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


def decrypt_lark_payload(encrypt_b64: str, encrypt_key: str) -> str:
    """Giải mã payload webhook của Lark bằng AES-256-CBC."""
    if not encrypt_key:
        raise ValueError("LARK_ENCRYPT_KEY is not set")

    key = hashlib.sha256(encrypt_key.encode("utf-8")).digest()
    encrypted = base64.b64decode(encrypt_b64)

    iv = encrypted[:16]
    ciphertext = encrypted[16:]

    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = cipher.decrypt(ciphertext)
    decrypted = unpad(decrypted, AES.block_size)
    return decrypted.decode("utf-8")


def verify_lark_signature(signature: str, timestamp: str, nonce: str, body: str) -> bool:
    """Xác thực webhook signature của Lark."""
    key = settings.LARK_ENCRYPT_KEY
    if not key:
        return True

    if not all(isinstance(v, str) for v in [signature, timestamp, nonce, body]):
        print("[WEBHOOK] Signature verification skipped: missing values")
        return False

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
            key = m.get("key") or ""
            text = text.replace(key, "").strip()
    return text


def process_message(event: dict):
    try:
        _process_message(event)
    except Exception as e:
        print(f"[ERROR] process_message exception: {e}")
        import traceback
        traceback.print_exc()


def _process_message(event: dict):
    message = event.get("message", {})
    sender = event.get("sender", {}).get("sender_id", {})

    lark_user_id = sender.get("user_id")
    chat_id = message.get("chat_id")
    message_id = message.get("message_id")
    msg_type = message.get("message_type")
    chat_type = message.get("chat_type")

    print(f"[PROCESS] user={lark_user_id}, chat={chat_id}, msg_type={msg_type}, chat_type={chat_type}")

    if not lark_user_id or not chat_id or not message_id:
        print("[PROCESS] Missing required fields, skip")
        return

    # Group chat: chỉ phản hồi khi bot bị @mention
    if chat_type == "group":
        mentions = message.get("mentions") or []
        if not any(m.get("name") == settings.LARK_BOT_NAME for m in mentions):
            print("[PROCESS] Group message without mention, skip")
            return

    # Lấy hoặc tạo Coze conversation cho user
    conversation_id = db.get_conversation_id(lark_user_id)
    if not conversation_id:
        conversation_id = coze_client.create_conversation()
        db.save_conversation_id(lark_user_id, conversation_id)
        print(f"[PROCESS] Created conversation: {conversation_id}")

    messages = []

    if msg_type == "text":
        try:
            content = json.loads(message.get("content", "{}"))
        except json.JSONDecodeError:
            print(f"[PROCESS] Failed to parse text content")
            return
        text = remove_mention(content.get("text", ""), message)
        if not text:
            print("[PROCESS] Empty text after mention removal, skip")
            return
        messages.append({"role": "user", "content_type": "text", "content": text})
        db.save_message(lark_user_id, "user", text, "text")

    elif msg_type == "image":
        try:
            content = json.loads(message.get("content", "{}"))
        except json.JSONDecodeError:
            print(f"[PROCESS] Failed to parse image content")
            return
        image_key = content.get("image_key")
        if not image_key:
            print("[PROCESS] Missing image_key, skip")
            return
        file_content = lark_client.download_resource(message_id, image_key, "image")
        file_id = coze_client.upload_file(file_content, "image.png")
        messages.append({"role": "user", "content_type": "image", "content": file_id})
        db.save_message(lark_user_id, "user", file_id, "image")

    elif msg_type == "file":
        try:
            content = json.loads(message.get("content", "{}"))
        except json.JSONDecodeError:
            print(f"[PROCESS] Failed to parse file content")
            return
        file_key = content.get("file_key")
        file_name = content.get("file_name", "file")
        if not file_key:
            print("[PROCESS] Missing file_key, skip")
            return
        file_content = lark_client.download_resource(message_id, file_key, "file")
        file_id = coze_client.upload_file(file_content, file_name)
        messages.append({"role": "user", "content_type": "file", "content": file_id})
        db.save_message(lark_user_id, "user", file_id, "file")

    else:
        print(f"[PROCESS] Unsupported message type: {msg_type}")
        return

    try:
        print(f"[PROCESS] Calling Coze chat with {len(messages)} messages")
        reply = coze_client.chat(conversation_id, lark_user_id, messages, stream=True)
        print(f"[PROCESS] Coze reply: {reply[:200]}")
        db.save_message(lark_user_id, "assistant", reply, "text")
        lark_client.send_text_message(chat_id, reply)
        print("[PROCESS] Reply sent to Lark")
    except Exception as e:
        print(f"[ERROR] Coze chat failed: {e}")
        try:
            lark_client.send_text_message(chat_id, settings.FALLBACK_MESSAGE)
        except Exception as e2:
            print(f"[ERROR] Failed to send fallback message: {e2}")


@app.post(settings.WEBHOOK_PATH)
async def lark_webhook(request: Request):
    body = await request.body()
    body_str = body.decode("utf-8")

    print(f"[WEBHOOK] Raw request: {body_str[:500]}")
    print(f"[WEBHOOK] Headers: {dict(request.headers)}")

    try:
        data = json.loads(body_str)
    except json.JSONDecodeError as e:
        print(f"[WEBHOOK] JSON parse error: {e}")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    # Nếu Lark gửi payload đã mã hóa, giải mã trước
    if "encrypt" in data:
        try:
            body_str = decrypt_lark_payload(data["encrypt"], settings.LARK_ENCRYPT_KEY)
            print(f"[WEBHOOK] Decrypted: {body_str[:500]}")
            data = json.loads(body_str)
        except Exception as e:
            print(f"[WEBHOOK] Decryption failed: {e}")
            return JSONResponse(status_code=400, content={"error": "decryption failed"})

    # URL verification challenge: ưu tiên trả về ngay, không check signature
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        print(f"[WEBHOOK] URL verification challenge: {challenge}")
        return {"challenge": challenge}

    # Xác thực signature cho các event thật
    signature = request.headers.get("X-Lark-Signature")
    timestamp = request.headers.get("X-Lark-Timestamp")
    nonce = request.headers.get("X-Lark-Nonce")

    print(f"[WEBHOOK] Signature: {signature}, Timestamp: {timestamp}, Nonce: {nonce}")

    if signature and timestamp and nonce:
        if not verify_lark_signature(signature, timestamp, nonce, body_str):
            print("[WEBHOOK] Signature verification failed")
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
    else:
        print("[WEBHOOK] Missing signature headers, skipping verification")

    event = data.get("event")
    if event:
        try:
            process_message(event)
        except Exception as e:
            print(f"[ERROR] Process message failed: {e}")

    return {"code": 0}


@app.on_event("startup")
async def startup_event():
    print("[STARTUP] Lark - Coze.cn Middleware started")
    print(f"[STARTUP] Webhook path: {settings.WEBHOOK_PATH}")
    print(f"[STARTUP] Coze base URL: {settings.COZE_BASE_URL}")
    print(f"[STARTUP] Bot name: {settings.LARK_BOT_NAME}")


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
