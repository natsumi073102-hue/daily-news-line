"""
毎日のニュースをNewsAPIから取得し、LINEに配信するスクリプト。

必要な環境変数:
  NEWSAPI_KEY            - newsapi.org で取得したAPIキー
  LINE_CHANNEL_TOKEN     - LINE Messaging APIのチャネルアクセストークン
  LINE_USER_ID           - 送信先のLINEユーザーID(自分のID)

使い方:
  python fetch_news.py
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

import requests

NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")
LINE_CHANNEL_TOKEN = os.environ.get("LINE_CHANNEL_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# 取得するニュースの設定
COUNTRY = "jp"       # 日本のトップニュース。海外も混ぜたい場合は下のfetch_world_newsも使う
PAGE_SIZE = 6         # 1回の配信で何件表示するか
LANGUAGE_WORLD = "en"  # 海外ニュース欄の言語


def fetch_japan_headlines():
    """日本のトップヘッドラインを取得"""
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": COUNTRY,
        "pageSize": PAGE_SIZE,
        "apiKey": NEWSAPI_KEY,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("articles", [])


def fetch_world_headlines():
    """海外(英語圏)のトップヘッドラインを取得"""
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "language": LANGUAGE_WORLD,
        "category": "general",
        "pageSize": PAGE_SIZE,
        "apiKey": NEWSAPI_KEY,
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("articles", [])


JST = timezone(timedelta(hours=9))


def format_message(jp_articles, world_articles):
    """LINEに送るテキストメッセージを組み立てる"""
    today = datetime.now(JST).strftime("%Y年%m月%d日")

    lines = [f"📰 {today}の朝刊まとめ\n"]

    if jp_articles:
        lines.append("【国内】")
        for i, a in enumerate(jp_articles, 1):
            title = a.get("title", "").split(" - ")[0]  # 末尾のメディア名を除去
            lines.append(f"{i}. {title}\n{a.get('url', '')}")
        lines.append("")

    if world_articles:
        lines.append("【海外】")
        for i, a in enumerate(world_articles, 1):
            title = a.get("title", "").split(" - ")[0]
            lines.append(f"{i}. {title}\n{a.get('url', '')}")

    return "\n".join(lines)


def save_news_json(jp_articles, world_articles, path="docs/news.json"):
    """Web版が読み込む news.json を書き出す"""

    def slim(a):
        return {
            "title": (a.get("title") or "").split(" - ")[0],
            "url": a.get("url", ""),
            "source": (a.get("source") or {}).get("name", ""),
            "publishedAt": a.get("publishedAt", ""),
            "image": a.get("urlToImage") or None,
        }

    data = {
        "updatedAt": datetime.now(JST).isoformat(),
        "domestic": [slim(a) for a in jp_articles],
        "world": [slim(a) for a in world_articles],
    }

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"news.json を書き出しました: {path}")


def send_line_message(text):
    """LINE Messaging APIでpushメッセージを送信"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}",
    }
    # LINEのテキストメッセージは1通5000文字までなので念のため切る
    text = text[:4900]
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.status_code


def main():
    missing = [
        name
        for name, val in [
            ("NEWSAPI_KEY", NEWSAPI_KEY),
            ("LINE_CHANNEL_TOKEN", LINE_CHANNEL_TOKEN),
            ("LINE_USER_ID", LINE_USER_ID),
        ]
        if not val
    ]
    if missing:
        print(f"環境変数が設定されていません: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    jp_articles = fetch_japan_headlines()
    world_articles = fetch_world_headlines()

    if not jp_articles and not world_articles:
        print("ニュースが取得できませんでした。APIキーやリクエスト上限を確認してください。")
        sys.exit(1)

    save_news_json(jp_articles, world_articles)

    message = format_message(jp_articles, world_articles)
    status = send_line_message(message)
    print(f"LINE送信完了 (status={status})")


if __name__ == "__main__":
    main()
