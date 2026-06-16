#!/usr/bin/env python3
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

FORUM_RSS_URL = "https://forums.warframe.com/forum/113-livestreams.xml"

TITLE_DEVSTREAM_PATTERN = re.compile(r"devstream", re.IGNORECASE)
# 掉寶活動帖：標題本身就點明 Twitch Drops / Drops Campaign
TITLE_DROP_PATTERN = re.compile(r"twitch\s*drops?|drops?\s+campaign", re.IGNORECASE)
# 每週例行週播表：內文常順帶提到 drops，但不是要推的活動，依標題整類排除
SCHEDULE_PATTERN = re.compile(r"community\s+stream\s+schedule", re.IGNORECASE)
TOPIC_ID_PATTERN = re.compile(r"/topic/(\d+)-")

# drop 偵測只用來「標註」訊息，不決定要不要發（每篇新 Devstream 都會通知）
KEYWORD_PATTERN = re.compile(r"twitch\s*drops?", re.IGNORECASE)
DROPS_PATTERN = re.compile(r"there will be drops", re.IGNORECASE)
# 只認領獎勵的句型（to earn / earn yourself / earn a|an|數字），避免吃到 "earned your trust" 之類
EARN_PATTERN = re.compile(r"to\s+earn|earn\s+yourself|earn\s+(?:an?\b|\d)", re.IGNORECASE)
NO_DROP_PATTERN = re.compile(r"\bno\s+(?:twitch\s*)?drops?\b", re.IGNORECASE)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36"
)

SEEN_PATH = os.environ.get("SEEN_PATH", os.path.join(os.path.dirname(__file__), "seen.json"))
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
HTTP_TIMEOUT = 30
SEND_ATTEMPTS = 3
SEND_BACKOFF_SECONDS = 3


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return resp.read()


def load_seen():
    if not os.path.exists(SEEN_PATH):
        return set()
    try:
        with open(SEEN_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(str(x) for x in data.get("seen_ids", []))
    except (json.JSONDecodeError, OSError) as e:
        log(f"⚠ 無法讀取 {SEEN_PATH}（{e}），視為空清單")
        return set()


def save_seen(seen_ids):
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump({"seen_ids": sorted(seen_ids, key=int)}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def strip_html(raw):
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = item.findtext("description") or ""
        m = TOPIC_ID_PATTERN.search(link)
        if not m:
            continue
        items.append(
            {
                "title": title,
                "link": link,
                "topic_id": m.group(1),
                "description_text": strip_html(description),
            }
        )
    return items


def select_kind(title):
    if SCHEDULE_PATTERN.search(title):
        return None
    if TITLE_DEVSTREAM_PATTERN.search(title):
        return "devstream"
    if TITLE_DROP_PATTERN.search(title):
        return "drop"
    return None


def classify_drop(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    hits = [ln for ln in lines if KEYWORD_PATTERN.search(ln)
            or DROPS_PATTERN.search(ln) or EARN_PATTERN.search(ln)]
    if hits:
        status = "no" if any(NO_DROP_PATTERN.search(ln) for ln in hits) else "yes"
        return status, hits
    return "unknown", []


def build_message(title, link, status, lines, kind="devstream"):
    if kind == "drop":
        # DE 的掉寶公告標題/內文格式很隨便、歷年模板多變，硬解獎勵與時間易出錯，
        # 因此不解析內文，直接通知並導流到原文。
        section = "🎁 這是 Twitch Drop 活動，獎勵與時間請點進公告確認。"
    elif status == "unknown":
        section = "❓ 無法自動判斷是否有 Twitch Drop，請點進公告確認。"
    else:
        head = {
            "yes": "🎁 偵測到 Twitch Drop：",
            "no": "❌ 公告說明這次沒有 Twitch Drop：",
        }[status]
        body = "\n".join(f"> {s[:500]}" for s in lines) if lines else "> （無內文）"
        section = f"{head}\n{body}"
    heading = {
        "devstream": "🎮 **新 Devstream 公告**",
        "drop": "📣 **新 Twitch Drop 活動公告**",
    }[kind]
    content = (
        f"{heading}\n"
        f"**{title}**\n"
        f"{section}\n"
        f"🔗 {link}"
    )
    return content[:1900]


def send_discord(content):
    payload = json.dumps({"content": content}).encode("utf-8")

    last_err = None
    for attempt in range(1, SEND_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(
                DISCORD_WEBHOOK_URL,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                resp.read()
            return
        except Exception as e:
            last_err = e
            log(f"    · 發送第 {attempt}/{SEND_ATTEMPTS} 次失敗：{e}")
            if attempt < SEND_ATTEMPTS:
                time.sleep(SEND_BACKOFF_SECONDS * attempt)
    raise last_err


def main():
    seen = load_seen()

    log(f"抓取 RSS：{FORUM_RSS_URL}")
    items = parse_feed(http_get(FORUM_RSS_URL))
    candidates = [it for it in items if select_kind(it["title"])]
    log(f"RSS 共 {len(items)} 篇，其中要追蹤 {len(candidates)} 篇（Devstream + Twitch Drop 活動）")

    # 首次部署時 seen 為空 → 目前 feed 的所有候選都會推送一次
    new_items = sorted(
        (it for it in candidates if it["topic_id"] not in seen),
        key=lambda it: int(it["topic_id"]),
    )
    if not new_items:
        log("沒有新的公告。")
        return

    if not DISCORD_WEBHOOK_URL:
        log("⚠ 未設定 DISCORD_WEBHOOK_URL，無法發送通知。")

    feed_ids = {it["topic_id"] for it in candidates}
    failures = 0
    try:
        for it in new_items:
            kind = select_kind(it["title"])
            log(f"新公告[{kind}]：{it['title']}（id={it['topic_id']}）")
            status, lines = classify_drop(it["description_text"])

            if not DISCORD_WEBHOOK_URL:
                # 不標記，等設好 webhook 後仍會補送
                log(f"  · [{status}] 未設 webhook，保留待設定後再通知")
                continue

            try:
                send_discord(build_message(it["title"], it["link"], status, lines, kind))
                log(f"  · 已發送 Discord（{kind}/{status}）")
            except Exception as e:
                failures += 1
                log(f"  · {SEND_ATTEMPTS} 次都失敗，放棄這篇：{e}")
            seen.add(it["topic_id"])
    finally:
        # 只留仍在 feed 的 ID；放 finally 確保中途出錯也寫回進度
        save_seen(seen & feed_ids)

    log("完成。")
    if failures:
        log(f"⚠ 有 {failures} 篇發送失敗（已放棄），以非零結束碼回報以便收到通知。")
        sys.exit(1)


if __name__ == "__main__":
    main()
