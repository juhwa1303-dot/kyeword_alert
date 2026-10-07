import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ===== 설정 (여기만 수정하면 됩니다) =====
BOARDS = {
    "영화": "https://theqoo.net/movie",
    "스퀘어": "https://theqoo.net/square",
}
KEYWORDS = ["톰", "슾", "스파", "디거"]
# =========================================

SEEN_FILE = Path("seen.json")
MAX_SEEN = 3000
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def fetch_posts(board_url):
    """게시판 목록에서 {글번호: (제목, 링크)} 를 가져옵니다."""
    r = requests.get(board_url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    board = board_url.rstrip("/").split("/")[-1]
    pattern = re.compile(rf"/{board}/(\d+)")
    posts = {}
    for a in soup.find_all("a", href=True):
        m = pattern.search(a["href"])
        if not m:
            continue
        title = a.get_text(" ", strip=True)
        # 빈 텍스트, 댓글 수([3]) 같은 링크는 건너뜀
        if not title or re.fullmatch(r"\[?\d+\]?", title):
            continue
        pid = m.group(1)
        # 말머리 등이 제목 링크 밖에 있어도 잡히도록, 그 글이 속한 줄 전체 텍스트를 검사 대상으로 씁니다
        row = a.find_parent("tr") or a.find_parent("li")
        full_text = row.get_text(" ", strip=True) if row else title
        posts.setdefault(pid, (title, f"https://theqoo.net/{board}/{pid}", full_text))
    return posts


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"},
        timeout=20,
    )
    r.raise_for_status()


def main():
    first_run = not SEEN_FILE.exists()
    seen_list = json.loads(SEEN_FILE.read_text("utf-8")) if not first_run else []
    seen = set(seen_list)

    ok_count = 0
    for name, url in BOARDS.items():
        try:
            posts = fetch_posts(url)
        except Exception as e:
            print(f"[경고] {name} 가져오기 실패: {e}")
            continue
        ok_count += 1

        for pid, (title, link, full_text) in posts.items():
            key = f"{name}:{pid}"
            if key in seen:
                continue
            seen.add(key)
            seen_list.append(key)

            hits = [k for k in KEYWORDS if k in full_text]
            # 첫 실행에는 기존 글로 알림이 쏟아지지 않도록 기록만 합니다
            if hits and not first_run:
                send_telegram(f"🔔 [{name}] {', '.join(hits)}\n{title}\n{link}")
                print(f"알림 전송: {title}")

    SEEN_FILE.write_text(
        json.dumps(seen_list[-MAX_SEEN:], ensure_ascii=False), encoding="utf-8"
    )

    if ok_count == 0:
        print("모든 사이트 접속 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
