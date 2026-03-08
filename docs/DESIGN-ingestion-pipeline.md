# DESIGN — Ingestion Pipeline (Capture → Inbox → Vault)

> **Phase:** 2 (Capture Layer & Inbox System)
> **Depends on:** Sprint 2.5 refactor (note_pipeline, async queue)
> **Files affected:** `capture_service.py`, `scraper_service.py`, `capture.py`, `inbox.py`

---

## 1. Tổng quan

Pipeline chuyển raw capture → inbox entry → reviewed note → vault.

```
Capture Source (Telegram / Browser / Web UI)
    ↓
POST /api/capture
    ↓
capture_service.parse_entry()
    ↓
Append to knowledge/inbox/YYYY-MM-DD.md
    ↓
Watcher detect → reindex (optional for inbox)
    ↓
User opens Inbox UI → Review
    ↓
Convert to Note / Archive / Delete
    ↓
knowledge/{folder}/slug.md (organized note)
    ↓
note_pipeline() → tags, links, index, (future: embed)
```

---

## 2. Capture Stage

### 2.1 API Endpoint

```python
# backend/api/capture.py

@router.post("/capture", status_code=201)
async def capture(body: CaptureRequest):
    """
    Accept raw text/URL from any source.
    Auto-parse metadata, append to inbox file.
    """
    entry = capture_service.create_entry(
        content=body.content,
        source=body.source,  # "telegram" | "browser" | "manual" | "quick-capture"
        url=body.url,        # optional
    )
    await capture_service.append_to_inbox(entry)
    return {"id": entry.id, "date": entry.date}
```

### 2.2 CaptureRequest Schema

```python
class CaptureRequest(BaseModel):
    content: str           # raw text hoặc URL + notes
    source: str = "manual" # telegram/browser/manual/quick-capture
    url: str | None = None # optional URL
```

### 2.3 Entry Generation

```python
from datetime import datetime

def create_entry(content: str, source: str, url: str | None) -> InboxEntry:
    now = datetime.now()
    entry = InboxEntry(
        id=now.strftime("%Y%m%d-%H%M%S"),
        time=now.strftime("%H:%M"),
        source=source,
        type=detect_type(content, url),  # auto-detect
        url=url,
        content=content,
        date=now.strftime("%Y-%m-%d"),
    )
    return entry
```

### 2.4 Type Auto-detection

```python
def detect_type(content: str, url: str | None) -> str:
    """Detect entry type. Simple rules, type is UI hint only."""
    if url:
        return "link"
    if content.startswith((">", '"', "'")):
        return "quote"
    return "note"
```

> **Note:** `type` chỉ là UI hint (icon, filter). AI đọc `content`, không dùng `type`.
> Types giữ minimal: `link`, `quote`, `note`. Không cần `idea` (dễ misclassify).

---

## 3. Inbox File Format

### 3.1 File Convention

```
knowledge/inbox/YYYY-MM-DD.md
```

**Một file per ngày.** Tất cả entries trong ngày append vào cùng file.

### 3.2 File Structure

```markdown
# Inbox — 2026-03-08

---

id: 20260308-142135
time: 14:21
source: telegram
type: link

---

bài này giải thích RAG pipeline khá rõ

https://example.com

---

id: 20260308-183022
time: 18:30
source: telegram
type: note

---

Động lực không đến từ cảm xúc nhất thời.
Nó đến từ việc hiểu rõ mục tiêu của bạn.
```

### 3.3 Append Logic

⚠️ **Concurrent write protection:** Telegram có thể gửi nhiều message cùng lúc.
Dùng `asyncio.Lock()` per-file để tránh markdown bị hỏng.

```python
from asyncio import Lock
from collections import defaultdict

# Per-file lock — không lock global, chỉ lock theo ngày
_inbox_locks: dict[str, Lock] = defaultdict(Lock)

async def append_to_inbox(entry: InboxEntry):
    inbox_dir = settings.KNOWLEDGE_DIR / "inbox"
    inbox_dir.mkdir(exist_ok=True)

    file_path = inbox_dir / f"{entry.date}.md"

    async with _inbox_locks[str(file_path)]:
        if not file_path.exists():
            # Create with header
            header = f"# Inbox — {entry.date}\n"
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(header)

        # Append entry (inside lock)
        entry_text = format_entry(entry)
        async with aiofiles.open(file_path, "a", encoding="utf-8") as f:
            await f.write(entry_text)
```

### 3.4 Entry Formatting

```python
def format_entry(entry: InboxEntry) -> str:
    meta_lines = [
        f"\n---\n",
        f"id: {entry.id}",
        f"time: {entry.time}",
        f"source: {entry.source}",
    ]
    if entry.type != "note":
        meta_lines.append(f"type: {entry.type}")
    if entry.url:
        meta_lines.append(f"url: {entry.url}")

    meta_block = "\n".join(meta_lines) + "\n\n---\n\n"
    return meta_block + entry.content + "\n"
```

---

## 4. URL Scraping

### 4.1 Scraper Service

```python
# backend/services/scraper_service.py

import asyncio
import trafilatura
import httpx

async def scrape_url(url: str) -> ScrapedArticle | None:
    """Fetch URL → extract article → return structured content."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, follow_redirects=True)
            html = response.text
    except httpx.HTTPError:
        return None

    # ⚠️ trafilatura.extract() is CPU-heavy sync function.
    # MUST run in thread to avoid blocking FastAPI event loop.
    extracted = await asyncio.to_thread(
        trafilatura.extract,
        html,
        include_comments=False,
        include_tables=True,
        output_format="markdown",
    )

    if not extracted:
        return None

    metadata = await asyncio.to_thread(trafilatura.extract_metadata, html)
    return ScrapedArticle(
        title=metadata.title if metadata else "",
        author=metadata.author if metadata else "",
        content=extracted,
        url=url,
        reading_time=len(extracted.split()) // 200,  # WPM
    )
```

### 4.2 ScrapedArticle Schema

```python
class ScrapedArticle(BaseModel):
    title: str
    author: str
    content: str
    url: str
    reading_time: int  # minutes
```

### 4.3 Scraping trong Capture Flow

```python
async def capture_with_scrape(body: CaptureRequest):
    entry = create_entry(body.content, body.source, body.url)

    # If URL present, try to scrape
    if body.url:
        article = await scraper_service.scrape_url(body.url)
        if article:
            entry.scraped_title = article.title
            entry.scraped_content = article.content[:2000]  # limit

    await append_to_inbox(entry)
```

### 4.4 Scraping Failures

| Trường hợp | Xử lý |
|------------|--------|
| Paywall | Lưu URL + user context, không scrape |
| JS-only render | Fallback: lưu meta tags từ HTML |
| Timeout | Lưu URL only |
| 404 | Lưu URL + "page not found" note |

---

## 5. Inbox API

### 5.1 Endpoints

```python
# backend/api/inbox.py

@router.get("/inbox")
async def list_inbox_dates():
    """Return list of inbox dates with entry count."""
    # Scan knowledge/inbox/*.md files
    return [{"date": "2026-03-08", "count": 5}, ...]

@router.get("/inbox/{date}")
async def get_inbox_entries(date: str):
    """Parse inbox file → return structured entries."""
    entries = inbox_service.parse_inbox_file(date)
    return entries

@router.post("/inbox/{date}/{entry_id}/convert")
async def convert_entry(date: str, entry_id: str, body: ConvertRequest):
    """Convert inbox entry → organized note in vault."""

@router.delete("/inbox/{date}/{entry_id}")
async def delete_entry(date: str, entry_id: str):
    """Remove entry from inbox file."""

@router.post("/inbox/{date}/{entry_id}/archive")
async def archive_entry(date: str, entry_id: str):
    """Mark entry as archived (remove from active inbox)."""
```

### 5.2 Inbox Parser

```python
def parse_inbox_file(date: str) -> list[InboxEntry]:
    """Parse markdown inbox file → structured entries."""
    file_path = settings.KNOWLEDGE_DIR / "inbox" / f"{date}.md"
    content = file_path.read_text(encoding="utf-8")

    entries = []
    # Split by "---" separator blocks
    blocks = re.split(r'\n---\n', content)

    for i in range(1, len(blocks), 2):  # metadata blocks at odd indices
        metadata = parse_metadata_block(blocks[i])
        content_block = blocks[i+1] if i+1 < len(blocks) else ""
        entries.append(InboxEntry(
            **metadata,
            content=content_block.strip(),
        ))

    return entries
```

---

## 6. Convert Entry → Vault Note

### 6.1 Convert Flow

```
User clicks "Convert" on inbox entry
    ↓
ConvertRequest: { folder, title, tags }
    ↓
Generate slug: slugify(title)
    ↓
Create organized note with schema
    ↓
Save to knowledge/{folder}/{slug}.md
    ↓
note_pipeline() → tags, links, index
    ↓
Remove entry from inbox file
```

### 6.2 ConvertRequest

```python
class ConvertRequest(BaseModel):
    title: str
    folder: str = ""          # "ai", "backend", etc.
    tags: list[str] = []
    include_scraped: bool = True  # include scraped article content
```

### 6.3 Note Generation

```python
def generate_note(entry: InboxEntry, request: ConvertRequest) -> str:
    frontmatter = {
        "title": request.title,
        "captured": entry.date,
        "tags": request.tags,
    }
    if entry.url:
        frontmatter["source"] = entry.url

    yaml_block = "---\n" + yaml.dump(frontmatter) + "---\n\n"

    body = "## Summary\n\n\n\n## Notes\n\n"
    body += entry.content + "\n"

    if entry.scraped_content and request.include_scraped:
        body += "\n## Content\n\n" + entry.scraped_content

    return yaml_block + body
```

### 6.4 Slug Generation

```python
import re
import unicodedata

def slugify(title: str) -> str:
    """Convert title to file-safe slug."""
    # Normalize unicode
    text = unicodedata.normalize("NFKD", title)
    # Remove non-ASCII
    text = text.encode("ascii", "ignore").decode()
    # Replace spaces with hyphens
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80]  # max length
```

---

## 7. Dedup Detection

### 7.1 Trước khi tạo note

```python
def check_duplicate(url: str | None, title: str) -> list[str]:
    """Check if similar note already exists."""
    duplicates = []

    # URL match (exact)
    if url:
        for note in all_notes:
            if note.frontmatter.get("source") == url:
                duplicates.append(note.path)

    # Title similarity (basic)
    if title:
        slug = slugify(title)
        for note in all_notes:
            if slugify(note.title) == slug:
                duplicates.append(note.path)

    # Future: embedding similarity (Phase 3)
    return duplicates
```

### 7.2 UI Warning

```
⚠️ This article may already exist:
  → ai/rag-pipeline.md

[Convert anyway] [Open existing] [Cancel]
```

---

## 8. Telegram Bot

### 8.1 Architecture

```
Telegram → Bot → POST /api/capture → inbox
```

Bot chạy trong lifespan startup:
```python
# backend/main.py lifespan()

from bot.telegram_bot import start_bot
bot_task = asyncio.create_task(start_bot())
```

### 8.2 Bot Implementation

```python
# bot/telegram_bot.py

from telegram.ext import Application, MessageHandler, filters

async def handle_message(update, context):
    text = update.message.text
    urls = extract_urls(text)

    async with httpx.AsyncClient() as client:
        await client.post("http://localhost:8000/api/capture", json={
            "content": text,
            "source": "telegram",
            "url": urls[0] if urls else None,
        })

    await update.message.reply_text("✅ Captured!")

async def start_bot():
    app = Application.builder().token(settings.TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    await app.run_polling()
```

### 8.3 Config

```python
# backend/config.py
class Settings(BaseSettings):
    TELEGRAM_TOKEN: str = ""  # SB_TELEGRAM_TOKEN env var
```

---

## 9. Browser Bookmarklet

```javascript
javascript:(function(){
  var url = window.location.href;
  var text = window.getSelection().toString() || document.title;
  fetch('http://YOUR_SERVER:8000/api/capture', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content: text, source: 'browser', url: url})
  }).then(function(){alert('✅ Captured!')});
})();
```

---

## 10. Inbox Retention

| Rule | Xử lý |
|------|--------|
| Entry converted | Remove from inbox file |
| Entry archived | Move to `inbox/archive/YYYY-MM-DD.md` |
| Entry deleted | Remove from inbox file |
| Inbox > 30 days old | Auto-archive unchecked entries |

---

## 11. Keyboard Shortcuts (Inbox UI)

| Key | Action |
|-----|--------|
| `Enter` | Convert to note |
| `A` | Archive |
| `D` | Delete |
| `↑/↓` | Navigate entries |
| `Space` | Toggle preview |

---

## 12. File Structure

```
backend/
  api/
    capture.py          # POST /api/capture
    inbox.py            # GET /api/inbox, convert, delete, archive
  services/
    capture_service.py  # entry creation, append to inbox
    scraper_service.py  # URL → article extraction
    inbox_service.py    # inbox file parsing, entry management

bot/
  telegram_bot.py       # Telegram bot polling

frontend/js/
  inbox.js              # Inbox UI panel

tests/
  test_capture_service.py
  test_inbox_service.py
  test_scraper_service.py
```
