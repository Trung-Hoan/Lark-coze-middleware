# Lark Global → Coze.cn Middleware

Bot middleware kết nối **Lark Global** với **Coze.cn API v3**, hỗ trợ chat 1-1, group chat, file và ảnh.

## Cấu trúc

```
.
├── config.py         # Đọc biến môi trường
├── database.py       # SQLite lưu session và lịch sử chat
├── lark_client.py    # Gọi Lark API
├── coze_client.py    # Gọi Coze.cn API v3
├── main.py           # FastAPI webhook server
├── requirements.txt  # Python dependencies
├── .env.example      # Mẫu file môi trường
└── README.md         # Hướng dẫn này
```

## Cài đặt local (Windows + PowerShell)

```powershell
# 1. Vào thư mục dự án
cd C:\Users\Hoan\Desktop\lark-coze-middleware

# 2. Tạo virtual environment (khuyến nghị)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Tạo file .env từ mẫu
copy .env.example .env

# 5. Mở .env bằng Notepad và điền thông tin thật
notepad .env

# 6. Chạy local
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Triển khai lên Render

### Bước 1: Đẩy code lên GitHub

Tạo repository GitHub, sau đó:

```powershell
git init
git add .
git commit -m "initial"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/lark-coze-middleware.git
git push -u origin main
```

> **Lưu ý bảo mật**: Không commit file `.env` chứa credentials thật. Repository này đã bao gồm `.env.example`.

### Bước 2: Tạo Web Service trên Render

1. Vào dashboard Render: https://dashboard.render.com/project/prj-d9bifb6cjfls738etbo0
2. Click **New +** → **Web Service**
3. Chọn repository GitHub vừa đẩy
4. Cấu hình:
   - **Name**: `lark-coze-middleware` (hoặc tên bạn muốn)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port 8000`
5. Thêm **Environment Variables** từ file `.env` (trừ `WEBHOOK_PATH` nếu để mặc định `/webhook`)
6. Click **Create Web Service**

### Bước 3: Lấy URL webhook

Sau khi deploy thành công, URL sẽ có dạng:

```
https://lark-coze-middleware-xxx.onrender.com/webhook
```

Copy URL này và dán vào **Lark Developer Console → Event Subscription → Request URL**.

## Cấu hình Lark Developer Console

1. **Event Subscription**:
   - Request URL: `https://your-service.onrender.com/webhook`
   - Event: `im.message.receive_v1`
   - Verification Token: điền vào `LARK_VERIFICATION_TOKEN`
   - Encrypt Key: điền vào `LARK_ENCRYPT_KEY` (nếu bật)

2. **Permissions**:
   - `im:chat:readonly`
   - `im:message:send`
   - `im:message:send_as_bot`
   - `im:message.group_msg`

3. **Event Subscriptions**:
   - `im.message.receive_v1`

## Cấu hình Coze.cn

1. Bot đã được publish và có API access.
2. Tạo **Personal Access Token** trên Coze.cn.
3. Lấy **Bot ID** từ bot settings.
4. Đảm bảo bot hỗ trợ `stream` response.

## Kiểm tra

1. Gửi tin nhắn đến bot trong Lark (chat 1-1 hoặc @mention trong group).
2. Logs trên Render sẽ hiển thị request và response.
3. Nếu bot không phản hồi, kiểm tra logs để xem lỗi.

## Lưu ý

- **Bot ID trong Excel bị làm tròn** — đã sửa thành `7659443401871550000` trong `.env.example`.
- **Lark webhook yêu cầu HTTPS** — Render tự động cung cấp HTTPS.
- **Session riêng user**: mỗi `user_id` Lark được map sang một `conversation_id` Coze.cn.
- **Lịch sử chat**: lưu vào SQLite file `lark_coze.db`.

## Troubleshooting

| Lỗi | Nguyên nhân | Cách sửa |
|---|---|---|
| 401 Unauthorized | Signature sai hoặc thiếu Encrypt Key | Kiểm tra `LARK_ENCRYPT_KEY` và Verification Token |
| 403 Forbidden | Thiếu permission | Add đủ scope trong Lark Developer Console |
| Coze không trả lời | Token hết hạn hoặc Bot ID sai | Kiểm tra `COZE_TOKEN` và `COZE_BOT_ID` |
| Bot không phản hồi trong group | Không bị @mention | Nhớ @bot hoặc kiểm tra `LARK_BOT_NAME` |
