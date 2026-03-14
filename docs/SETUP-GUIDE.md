# HƯỚNG DẪN SETUP TỪ A → Z — AI Knowledge OS (Second Brain)

> **Version:** v0.8.0
> **Cập nhật:** 2026-03-14
> **Mục đích:** Dành cho người mới, cài trên máy trống

---

## Mục lục

1. [Tổng quan hệ thống hoạt động như thế nào](#1-tổng-quan-hệ-thống-hoạt-động-như-thế-nào)
2. [Yêu cầu phần cứng](#2-yêu-cầu-phần-cứng)
3. [Cài đặt phần mềm cần thiết](#3-cài-đặt-phần-mềm-cần-thiết)
4. [Setup dự án](#4-setup-dự-án)
5. [Cài đặt & cấu hình Ollama (AI Model)](#5-cài-đặt--cấu-hình-ollama-ai-model)
6. [Cài đặt & cấu hình Qdrant (Vector DB)](#6-cài-đặt--cấu-hình-qdrant-vector-db)
7. [Cấu hình Embedding Model (BGE-M3)](#7-cấu-hình-embedding-model-bge-m3)
8. [Khởi động ứng dụng](#8-khởi-động-ứng-dụng)
9. [Thay đổi model & cấu hình](#9-thay-đổi-model--cấu-hình)
10. [Setup Telegram Bot](#10-setup-telegram-bot)
11. [Deploy trên server](#11-deploy-trên-server)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Tổng quan hệ thống hoạt động như thế nào

### Hệ thống gồm 4 thành phần chính:

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   FastAPI     │     │   Qdrant      │     │   Ollama      │     │  BGE-M3      │
│   (Backend)   │     │ (Vector DB)   │     │ (LLM Server)  │     │ (Embedding)  │
│   Port 8000   │     │   Port 6333   │     │  Port 11434   │     │  In-process  │
│               │◄───►│               │     │               │     │              │
│  Python app   │     │  Chứa vectors │     │  Chạy AI model│     │  Chuyển text  │
│  + Frontend   │     │  tìm tương tự │     │  trả lời chat │     │  → vector    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
       │                                         │                      │
       │                                         │                      │
       ▼                                         ▼                      ▼
  Bạn mở browser                          Ollama download         sentence-transformers
  http://localhost:8000                    model từ Ollama Hub      download model từ
  → giao diện web                         vào ~/.ollama/           HuggingFace vào cache
```

### Luồng hoạt động khi bạn chat với AI:

```
1. Bạn gõ câu hỏi trên web UI
2. Backend nhận câu hỏi
3. BGE-M3 (embedding model) chuyển câu hỏi → vector số
4. Qdrant tìm các đoạn note tương tự nhất
5. Backend mở rộng tìm kiếm qua [[wiki-links]] (graph expansion)
6. Chọn top chunks phù hợp nhất (≤ 2000 tokens)
7. Gửi context + câu hỏi → Ollama (LLM)
8. Ollama trả lời từng token → stream về browser
9. UI hiện câu trả lời + link đến note nguồn
```

### Luồng hoạt động khi bạn save note:

```
1. Bạn chỉnh sửa note trong editor
2. Auto-save gửi nội dung lên backend
3. Backend lưu file .md vào ổ đĩa
4. Cập nhật tags, links, search index (tức thì)
5. Sau 2 giây: chunking → embedding → lưu vector vào Qdrant
```

---

## 2. Yêu cầu phần cứng

### Tối thiểu (keyword search only, không AI):
- RAM: 4GB
- CPU: bất kỳ
- GPU: không cần
- Disk: 1GB

### Khuyến nghị (full AI features):
- RAM: 16GB+ (32GB tốt nhất)
- GPU: NVIDIA với ≥ 8GB VRAM (RTX 3060+)
- Disk: 20GB (models + data)

### Budget VRAM thực tế (RTX 4060 Ti 16GB):
| Component | VRAM |
|-----------|------|
| BGE-M3 (embedding) | ~2.5GB |
| Qwen2.5 7B Q4 (LLM) | ~5GB |
| CUDA overhead | ~1GB |
| **Tổng** | **~8.5GB** |
| **Còn trống** | **~7.5GB** |

> **Không có GPU?** Vẫn chạy được — Ollama sẽ dùng CPU (chậm hơn 5-10x).
> BGE-M3 cũng fallback về CPU.

---

## 3. Cài đặt phần mềm cần thiết

### 3.1 Python 3.11+

**Windows:**
1. Tải từ https://www.python.org/downloads/
2. ✅ Tick "Add Python to PATH" khi cài
3. Kiểm tra: `python --version`

**Ubuntu:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

### 3.2 Git

**Windows:** Tải từ https://git-scm.com/download/win
**Ubuntu:** `sudo apt install git`

### 3.3 Docker (cho Qdrant)

**Windows:**
1. Tải Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Cài → khởi động Docker Desktop
3. Kiểm tra: `docker --version`

**Ubuntu:**
```bash
sudo apt install docker.io docker-compose
sudo usermod -aG docker $USER  # để chạy docker không cần sudo
# Log out + log in lại
```

### 3.4 Ollama (cho AI chat)

**Windows:**
1. Tải từ https://ollama.com/download/windows
2. Cài → Ollama chạy nền (system tray)
3. Kiểm tra: `ollama --version`

**Ubuntu:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
# Ollama service tự khởi động
```

**macOS:**
```bash
brew install ollama
ollama serve  # chạy service
```

---

## 4. Setup dự án

### 4.1 Clone repository

```bash
git clone <repo-url> second-brain
cd second-brain
```

### 4.2 Tạo virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Linux/macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4.3 Cài dependencies

```bash
pip install -r requirements.txt
```

**Cài gì:** FastAPI, uvicorn, aiofiles, httpx, trafilatura, watchdog, markdown-it-py, sentence-transformers, qdrant-client, pydantic.

> ⚠️ `sentence-transformers` sẽ kéo theo PyTorch (~2GB download). Đây là bình thường.

### 4.4 Cấu trúc thư mục sau setup

```
second-brain/
├── .venv/              ← Python virtual environment
├── backend/            ← FastAPI backend code
├── frontend/           ← HTML/CSS/JS (không cần build)
├── knowledge/          ← TẠO TỰ ĐỘNG khi chạy lần đầu
│   ├── inbox/          ← Captured entries
│   ├── daily/          ← Daily notes
│   ├── template/       ← Note templates
│   ├── _assets/        ← Uploaded images
│   └── *.md            ← Notes của bạn
├── requirements.txt
└── README.md
```

---

## 5. Cài đặt & cấu hình Ollama (AI Model)

### 5.1 Ollama là gì?

Ollama là **runtime để chạy LLM local** (giống docker cho AI models). Nó:
- Quản lý download model
- Chạy model trên GPU/CPU
- Cung cấp API HTTP tại `http://localhost:11434`

### 5.2 Download model (BẮT BUỘC cho AI chat)

Mở terminal, chạy:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
```

**Giải thích tên model:**
- `qwen2.5` — tên model (Alibaba Qwen2.5)
- `7b` — 7 tỷ parameters
- `instruct` — fine-tuned cho chat/instruction
- `q4_K_M` — lượng tử hóa 4-bit (tiết kiệm VRAM)

**Model download vào đâu?**
| OS | Đường dẫn |
|----|-----------|
| Windows | `C:\Users\{username}\.ollama\models\` |
| Linux | `~/.ollama/models/` |
| macOS | `~/.ollama/models/` |

**Dung lượng:** ~4.7GB

### 5.3 Kiểm tra Ollama hoạt động

```bash
# Ping Ollama API
curl http://localhost:11434/api/tags

# Test chat nhanh
ollama run qwen2.5:7b-instruct-q4_K_M "Xin chào"
# → Nên trả lời bằng tiếng Việt
```

> ⚠️ **Nếu Ollama chưa chạy:** Windows → mở Ollama từ Start Menu. Linux → `ollama serve &`

### 5.4 File nào trong code kết nối Ollama?

```
backend/config/__init__.py   ← OLLAMA_URL, LLM_MODEL (cấu hình)
backend/services/llm_service.py  ← Code kết nối Ollama API
```

`llm_service.py` kết nối qua HTTP:
```python
# Gửi request tới Ollama API
POST http://localhost:11434/api/chat
{
    "model": "qwen2.5:7b-instruct-q4_K_M",
    "messages": [...],
    "stream": true
}
```

---

## 6. Cài đặt & cấu hình Qdrant (Vector DB)

### 6.1 Qdrant là gì?

Qdrant là **vector database** — lưu trữ embedding vectors và tìm kiếm tương tự. Nó:
- Nhận vectors (mảng 1024 số) từ BGE-M3
- Tìm vectors gần nhất khi bạn search/chat
- Chạy trong Docker container

### 6.2 Khởi động Qdrant

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v qdrant_data:/qdrant/storage \
  qdrant/qdrant
```

**Giải thích:**
- `-d` — chạy nền
- `--name qdrant` — đặt tên container
- `-p 6333:6333` — map port
- `-v qdrant_data:/qdrant/storage` — lưu data persistent (không mất khi restart)

**Data lưu ở đâu?**
- Docker volume: `qdrant_data` (quản lý bởi Docker)
- Xem đường dẫn: `docker volume inspect qdrant_data`

### 6.3 Kiểm tra Qdrant

```bash
curl http://localhost:6333/collections
# → Nên trả về JSON: {"result":{"collections":[]},"status":"ok"}
```

### 6.4 Tùy chọn: KHÔNG dùng Qdrant

> **Qdrant là OPTIONAL.** App vẫn chạy bình thường không có Qdrant:
> - Search fallback về keyword only (SQLite FTS5)
> - AI chat fallback về keyword retrieval
> - Related notes không hiển thị
> - Log sẽ ghi: "Qdrant unavailable — running without vector search"

---

## 7. Cấu hình Embedding Model (BGE-M3)

### 7.1 BGE-M3 là gì?

BGE-M3 là **embedding model** — chuyển text thành vector số (1024 chiều). Dùng để:
- Tìm note tương tự về ngữ nghĩa
- Hỗ trợ RAG retrieval

### 7.2 Download xảy ra tự động

**Bạn KHÔNG cần download thủ công.** Khi app chạy lần đầu:

1. `embedding_service.py` gọi `SentenceTransformer("BAAI/bge-m3")`
2. `sentence-transformers` tự download từ HuggingFace Hub
3. Lưu vào cache

**Model download vào đâu?**
| OS | Đường dẫn |
|----|-----------|
| Windows | `C:\Users\{username}\.cache\huggingface\hub\` |
| Linux | `~/.cache/huggingface/hub/` |
| macOS | `~/.cache/huggingface/hub/` |

**Dung lượng:** ~2.3GB (download 1 lần, cache vĩnh viễn)

### 7.3 Lần đầu chạy sẽ lâu

```
Lần 1: 2-5 phút (download model từ HuggingFace)
Lần 2+: 5-15 giây (load từ cache)
```

> Log sẽ hiện: `INFO Loading embedding model: BAAI/bge-m3 ...`
> Sau đó: `INFO Embedding model loaded: dim=1024, device=cuda`
> (hoặc `device=cpu` nếu không có GPU)

### 7.4 File nào trong code quản lý embedding?

```
backend/services/embedding_service.py   ← Load model, embed text
backend/services/chunker_service.py     ← Cắt note thành chunks
backend/services/vector_service.py      ← Lưu/tìm vectors trong Qdrant
backend/config/retrieval.py             ← Batch size, debounce, weights
```

---

## 8. Khởi động ứng dụng

### 8.1 Checklist trước khi chạy

| # | Bước | Cần thiết? | Kiểm tra |
|---|------|-----------|----------|
| 1 | Python + venv activated | ✅ Bắt buộc | `python --version` |
| 2 | Dependencies installed | ✅ Bắt buộc | `pip list` |
| 3 | Docker chạy | ⬜ Tùy chọn | `docker ps` |
| 4 | Qdrant chạy | ⬜ Tùy chọn | `curl localhost:6333` |
| 5 | Ollama chạy | ⬜ Tùy chọn | `curl localhost:11434/api/tags` |
| 6 | Model downloaded | ⬜ Tùy chọn | `ollama list` |

> **Minimum:** Chỉ cần #1 + #2 là app đã chạy được (keyword search, editor, graph).
> **Full AI:** Cần tất cả 6 bước.

### 8.2 Khởi động

```bash
# Từ thư mục second-brain/
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 8.3 Mở trình duyệt

```
http://localhost:8000
```

### 8.4 Thứ tự khởi động trong code (lifespan)

Khi app start, `backend/main.py` chạy theo thứ tự:

```
1. Tạo thư mục knowledge/, template/, inbox/
2. Tạo Welcome.md nếu lần đầu
3. Build FTS5 search index (scan tất cả .md files)
4. Build wiki-link graph (in-memory)
5. [Phase 3] Load BGE-M3 model (2-15 giây)
6. [Phase 3] Connect Qdrant (nếu có)
7. [Phase 3] Warm embedding model
8. Start file watcher (detect external changes)
9. → Sẵn sàng nhận request
```

Nếu Qdrant/Ollama chưa chạy → app vẫn start, chỉ log warning.

---

## 9. Thay đổi model & cấu hình

### 9.1 Thay đổi LLM model

**Bước 1:** Download model mới qua Ollama:

```bash
# Ví dụ: dùng model nhỏ hơn
ollama pull qwen2.5:3b

# Hoặc model lớn hơn
ollama pull qwen2.5:14b-instruct-q4_K_M

# Hoặc model khác
ollama pull llama3.1:8b
ollama pull mistral:7b
ollama pull gemma2:9b
```

> Xem tất cả model có sẵn: https://ollama.com/library

**Bước 2:** Cấu hình dự án dùng model mới. Có 2 cách:

**Cách 1 — Environment variable (khuyên dùng):**
```bash
# Windows PowerShell
$env:SB_LLM_MODEL = "llama3.1:8b"
python -m uvicorn backend.main:app --reload

# Linux/macOS
SB_LLM_MODEL="llama3.1:8b" python -m uvicorn backend.main:app --reload
```

**Cách 2 — Sửa file config:**

File: **`backend/config/__init__.py`** (dòng 18)
```python
# Sửa dòng này:
LLM_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"

# Thành:
LLM_MODEL: str = "llama3.1:8b"
```

### 9.2 Thay đổi Ollama URL

Nếu Ollama chạy trên máy khác:

```bash
$env:SB_OLLAMA_URL = "http://192.168.1.100:11434"
```

Hoặc sửa **`backend/config/__init__.py`** dòng 17:
```python
OLLAMA_URL: str = "http://192.168.1.100:11434"
```

### 9.3 Thay đổi Embedding Model

File: **`backend/services/embedding_service.py`** (dòng 26-27)
```python
# Mặc định:
_DEFAULT_MODEL = "BAAI/bge-m3"       # 1024-dim, multilingual
_EMBEDDING_DIM = 1024

# Thay thế (ví dụ):
_DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"  # 768-dim, English only, nhẹ hơn
_EMBEDDING_DIM = 768
```

> ⚠️ **CẢNH BÁO:** Thay embedding model = phải XÓA collection Qdrant cũ và re-embed toàn bộ vault. Vì dimension khác nhau.
>
> ```bash
> # Xóa Qdrant data
> docker stop qdrant
> docker rm qdrant
> docker volume rm qdrant_data
> # Khởi động lại Qdrant
> docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
> ```

### 9.4 Thay đổi RAG / Search weights

File: **`backend/config/retrieval.py`**

```python
# --- RAG Chat scoring weights ---
VECTOR_WEIGHT = 0.6     # Trọng số semantic similarity (0-1)
GRAPH_WEIGHT  = 0.3     # Trọng số graph proximity     (0-1)
KEYWORD_WEIGHT = 0.1    # Trọng số keyword overlap      (0-1)

# --- Hybrid Search weights (search bar, không phải chat) ---
HYBRID_VECTOR_WEIGHT = 0.7   # Vector search weight
HYBRID_KEYWORD_WEIGHT = 0.3  # Keyword search weight

# --- Chunking ---
MAX_TOKENS = 450        # Chunk lớn nhất (tokens)
TARGET_TOKENS = 300     # Chunk lý tưởng
MIN_TOKENS = 120        # Chunk nhỏ nhất (dưới mức này sẽ merge)

# --- Embedding ---
EMBED_DEBOUNCE_SECONDS = 2.0  # Chờ bao lâu sau save để embed
EMBED_BATCH_SIZE = 32         # Số chunks embed 1 lần (GPU)
```

### 9.5 Tóm tắt file cấu hình

| File | Cấu hình gì | Cách override |
|------|-------------|---------------|
| `backend/config/__init__.py` | Ollama URL, LLM model, port, paths | Env var `SB_*` |
| `backend/config/retrieval.py` | Weights, chunk sizes, batch size | Sửa trực tiếp |
| `backend/services/embedding_service.py` | Embedding model name | Sửa trực tiếp |

### 9.6 Tất cả environment variables

| Variable | Default | Mô tả |
|----------|---------|-------|
| `SB_OLLAMA_URL` | `http://localhost:11434` | Ollama API URL |
| `SB_LLM_MODEL` | `qwen2.5:7b-instruct-q4_K_M` | LLM model name |
| `SB_HOST` | `127.0.0.1` | Server host |
| `SB_PORT` | `8000` | Server port |
| `SB_KNOWLEDGE_DIR` | `./knowledge` | Thư mục chứa notes |

---

## 10. Setup Telegram Bot

> **⚠️ Status:** Telegram Bot (T17) hiện đang ở trạng thái **deferred** — code chưa implement trong main codebase. Dưới đây là cách setup khi feature hoàn thành.

### 10.1 Tạo Bot trên Telegram

1. Mở Telegram → tìm **@BotFather**
2. Gửi `/newbot`
3. Đặt tên bot: `My Second Brain`
4. Đặt username: `my_second_brain_bot`
5. BotFather trả về **BOT TOKEN** (dạng `1234567890:ABCDEFGH...`)
6. **LƯU LẠI token này**

### 10.2 Cấu hình token

```bash
# Environment variable
$env:SB_TELEGRAM_TOKEN = "1234567890:ABCDEFGHijklmnop..."
```

### 10.3 Cách Telegram Bot hoạt động (khi implement)

```
Bạn gửi message trên Telegram
    ↓
Bot nhận message
    ↓
Bot gọi POST http://localhost:8000/api/capture
    body: { content: "message text", source: "telegram", url: null }
    ↓
Capture service tạo entry
    ↓
Entry lưu vào knowledge/inbox/YYYY-MM-DD.md
    ↓
Bạn mở web UI → Inbox tab → thấy entry → Convert thành note
```

### 10.4 Hiện tại có thể dùng gì thay thế?

**Browser Bookmarklet** — hoạt động ngay:
1. Mở `http://localhost:8000/bookmarklet.html`
2. Kéo nút bookmarklet lên thanh bookmarks
3. Khi đọc web → click bookmarklet → URL + selected text → inbox

**Quick Capture** — trên web UI:
- `Ctrl+Shift+N` → nhập nhanh → lưu vào inbox

**Direct API call:**
```bash
curl -X POST http://localhost:8000/api/capture \
  -H "Content-Type: application/json" \
  -d '{"content": "Ghi chú nhanh", "source": "manual"}'
```

---

## 11. Deploy trên server

### 11.1 Deploy cơ bản (Ubuntu server)

**Bước 1: Cài prerequisites trên server**

```bash
# SSH vào server
ssh user@your-server

# Cài đặt tất cả
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git docker.io

# Cài Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download LLM model
ollama pull qwen2.5:7b-instruct-q4_K_M
```

**Bước 2: Clone và setup project**

```bash
git clone <repo-url> ~/second-brain
cd ~/second-brain

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Bước 3: Start Qdrant**

```bash
docker run -d \
  --name qdrant \
  --restart unless-stopped \
  -p 6333:6333 \
  -v qdrant_data:/qdrant/storage \
  qdrant/qdrant
```

**Bước 4: Tạo systemd service cho app**

```bash
sudo nano /etc/systemd/system/second-brain.service
```

Nội dung:
```ini
[Unit]
Description=Second Brain Knowledge OS
After=network.target docker.service

[Service]
Type=simple
User=your-username
WorkingDirectory=/home/your-username/second-brain
Environment="PATH=/home/your-username/second-brain/.venv/bin:$PATH"
Environment="SB_HOST=0.0.0.0"
Environment="SB_KNOWLEDGE_DIR=/home/your-username/knowledge"
ExecStart=/home/your-username/second-brain/.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable second-brain
sudo systemctl start second-brain
sudo systemctl status second-brain  # kiểm tra
```

**Bước 5: Truy cập từ mạng LAN**

```
http://server-ip:8000
```

### 11.2 HTTPS với Cloudflare Tunnel (truy cập từ internet)

```bash
# Cài cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Login
cloudflared tunnel login

# Tạo tunnel
cloudflared tunnel create second-brain

# Config
nano ~/.cloudflared/config.yml
```

Nội dung `config.yml`:
```yaml
tunnel: <tunnel-id>
credentials-file: /home/user/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: brain.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

```bash
# Thêm DNS record
cloudflared tunnel route dns second-brain brain.yourdomain.com

# Start tunnel
cloudflared tunnel run second-brain

# Hoặc cài service để chạy ngầm:
sudo cloudflared service install
```

Bây giờ truy cập: `https://brain.yourdomain.com` — HTTPS, từ bất kỳ đâu.

### 11.3 Docker Compose (Phase 6 — khi implement)

```yaml
# docker-compose.yml (planned)
version: "3.8"
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./knowledge:/app/knowledge
    environment:
      - SB_OLLAMA_URL=http://ollama:11434
    depends_on:
      - qdrant
      - ollama

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  qdrant_data:
  ollama_data:
```

> ⚠️ Docker Compose chưa có Dockerfile trong repo — đây là plan cho Phase 6.

---

## 12. Troubleshooting

### Ollama không connect

```
Lỗi: "Ollama is not available. Start Ollama and try again."
```

**Fix:**
```bash
# Kiểm tra Ollama chạy chưa
curl http://localhost:11434/api/tags

# Nếu chưa chạy:
# Windows: mở Ollama từ Start Menu
# Linux: ollama serve
# macOS: ollama serve

# Kiểm tra model đã download:
ollama list
# → Nên thấy qwen2.5:7b-instruct-q4_K_M
```

### Qdrant không connect

```
Log: "Qdrant unavailable — running without vector search"
```

**Fix:**
```bash
# Kiểm tra Docker chạy chưa
docker ps

# Nếu container bị stop:
docker start qdrant

# Nếu chưa tạo container:
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
```

### Embedding model lâu load

```
Log: "Loading embedding model: BAAI/bge-m3 ..."
(đợi rất lâu)
```

**Lý do:** Lần đầu download ~2.3GB từ HuggingFace.
**Fix:** Kiểm tra internet. Chờ đợi. Lần sau sẽ nhanh (<15s).

### GPU không được sử dụng

```
Log: "Embedding model loaded: dim=1024, device=cpu"
```

**Fix:**
```bash
# Kiểm tra PyTorch có thấy GPU
python -c "import torch; print(torch.cuda.is_available())"

# Nếu False → cài lại PyTorch với CUDA:
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### Port 8000 bị chiếm

```bash
# Dùng port khác:
python -m uvicorn backend.main:app --port 9000

# Hoặc set env:
$env:SB_PORT = "9000"
```

### Notes không hiện trong search/graph

**Lý do:** File `.md` phải nằm trong thư mục `knowledge/` (không phải `inbox/`, `template/`, `_assets/` — các thư mục này bị exclude).

---

## Tóm tắt nhanh — Setup từ zero

```bash
# 1. Cài Python 3.11, Git, Docker, Ollama

# 2. Clone + setup
git clone <repo> second-brain && cd second-brain
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt

# 3. Start services
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
ollama pull qwen2.5:7b-instruct-q4_K_M

# 4. Run app
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 5. Open browser
# http://localhost:8000
```

**Xong!** 🎉
