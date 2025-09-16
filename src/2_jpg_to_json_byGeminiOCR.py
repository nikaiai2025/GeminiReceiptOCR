# GEMINI_API_KEY = "[REDACTED]"  # 固定値として設定
# MODEL_NAME = "gemini-2.5-pro"  
# MODEL_NAME = "gemini-2.5-flash"  
# MODEL_NAME = "gemini-2.5-flash-lite"
# MODEL_NAME = "gemini-2.0-flash-lite"
# -*- coding: utf-8 -*-
"""
GeminiOCR.py
- google-genai (google.genai) を使用
- スクリプト所在フォルダを基準に inputPicture / OutputJSON を参照
- MIMEは自動判定（mimetypes）または files.upload を使用
- 1分あたり最大 4 リクエスト（タイムスタンプ方式）
- サーバ側429等のレート上限を検知したら途中までを保存して即終了
- 出力は配列形式、各要素は OrderedDict で "ファイル名" を先頭キーにする
- 出力ファイル名: YYYYMMDD_hhmm.json
"""

import os
import json
import time
import mimetypes
from pathlib import Path
from collections import OrderedDict, deque
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

try:
    # 新SDK（推奨）
    from google import genai
except Exception as e:
    raise RuntimeError("google-genai がインストールされていないか import に失敗しました。pip install google-genai を確認してください.") from e

# ===== 設定（.env: ルートのみ） =====
# リポジトリルートを決定
REPO_ROOT = Path(__file__).resolve().parent.parent
# ルートの .env を読み込み（既存環境変数は優先）
load_dotenv(REPO_ROOT / ".env", override=False)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY が未設定です。.env か環境変数に設定してください。")

MODEL_NAME = "gemini-2.5-pro"  
# MODEL_NAME = "gemini-2.5-flash"  
#MODEL_NAME = "gemini-2.5-flash-lite"
#MODEL_NAME = "gemini-2.0-flash-lite"
#MODEL_NAME = "gemini-1.5-flash"
#MODEL_NAME = "gemini-1.5-flash-8b"


PROMPT_TEXT = """これは日本語のレシートです。以下をJSON形式で出力して。
１：日付
２：店名
３：合計金額
４：登録番号
<出力要件>
読み取れない項目は「不明」とする。日付はYYYY-MM-DD形式とする。合計金額は数字のみでカンマや円記号は含めない。合計金額が日本円でない場合は「外国通貨」とする。項目名（日付・店名・合計金額・登録番号）は日本語に統一する。
"""

# プロジェクトルート配下の data ディレクトリを使用
DATA_DIR = REPO_ROOT / "data"
INPUT_DIR = DATA_DIR / "jpg"
OUTPUT_DIR = DATA_DIR / "json"

# RPM 制御
MAX_RPM = 4
WINDOW_SECONDS = 60
request_times = deque()

# 出力エラー時の再試行回数
MAX_RETRIES = 3

# クライアント初期化
client = genai.Client(api_key=GEMINI_API_KEY)


# ===== ユーティリティ =====
def log(level: str, msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def ensure_folders():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_text_from_response(resp) -> Optional[str]:
    """
    SDKの戻り方差異に対応してテキストを抽出するヘルパー。
    - 優先: resp.text
    - 次: resp.candidates[0].content.parts[0].text (SDKの別形式)
    - 次: str(resp)
    """
    if resp is None:
        return None
    # 直接 .text がある場合
    text = getattr(resp, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    # candidates パターン（SDKによってはここにある）
    try:
        cand = getattr(resp, "candidates", None)
        if cand and len(cand) > 0:
            # candidate の中の text を探す
            first = cand[0]
            # さまざまな構造に対応（保険的に）
            if hasattr(first, "content"):
                parts = getattr(first.content, "parts", None)
                if parts and len(parts) > 0:
                    p0 = parts[0]
                    t = getattr(p0, "text", None)
                    if isinstance(t, str):
                        return t.strip()
            # 文字列化して返す（最終手段）
            return str(first)
    except Exception:
        pass
    # 最終的に文字列化
    try:
        s = str(resp)
        return s.strip()
    except Exception:
        return None


def extract_json_loose(text: str):
    """
    緩い判定でJSON部分を抜き出してパースする。
    - まず json.loads で試す
    - 次に ```json``` や ``` ... ``` ブロックの中身を抽出して試す
    - 次に最初の { ... } または [ ... ] を抜いて試す
    - 末尾カンマの除去も試みる
    """
    import re
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        snippet = m.group(1).strip()
        snippet = re.sub(r",\s*}", "}", snippet)
        try:
            return json.loads(snippet)
        except Exception:
            pass

    # 最初の { ... } または [ ... ]
    start_obj = text.find("{")
    end_obj = text.rfind("}")
    start_arr = text.find("[")
    end_arr = text.rfind("]")

    candidate = None
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        candidate = text[start_obj:end_obj+1]
    elif start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        candidate = text[start_arr:end_arr+1]

    if candidate:
        candidate = re.sub(r",\s*}", "}", candidate)
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None


def is_rate_limit_error(exc: Exception) -> bool:
    """
    レート上限かどうか判定する（google.api_core がなくても文字列で検出）。
    """
    text = str(exc).lower()
    markers = ["429", "rate limit", "quota", "resource_exhausted", "too many requests"]
    return any(m in text for m in markers)


# ===== レート制御（タイムスタンプ方式） =====
def wait_for_rate_slot():
    now = time.time()
    # 古い履歴を破棄（WINDOW_SECONDSより古いもの）
    while request_times and now - request_times[0] > WINDOW_SECONDS:
        request_times.popleft()
    if len(request_times) >= MAX_RPM:
        wait_time = WINDOW_SECONDS - (now - request_times[0])
        if wait_time > 0:
            log("INFO", f"レート制限のため {wait_time:.1f} 秒待機します...")
            time.sleep(wait_time)
        # 再度古い履歴を削除
        now2 = time.time()
        while request_times and now2 - request_times[0] > WINDOW_SECONDS:
            request_times.popleft()


# ===== 1画像処理 =====
def process_image(image_path: Path, max_retries: int = MAX_RETRIES) -> Optional[OrderedDict]:
    """
    - 画像をAPIに投げて緩くJSONを抽出して OrderedDict に整形（先頭キー: 'ファイル名'）
    - JSON抽出に失敗した場合は最大 max_retries 回までリトライする
    - JSONでないorパース失敗なら None を返す（呼び出し側でログ/エントリ追加）
    """
    for attempt in range(1, max_retries + 1):
        try:
            wait_for_rate_slot()

            uploaded = client.files.upload(file=str(image_path))

            resp = client.models.generate_content(
                model=MODEL_NAME,
                contents=[uploaded, PROMPT_TEXT],
                config={"response_mime_type": "application/json"},
            )

            request_times.append(time.time())
            text = extract_text_from_response(resp)

            if not text:
                log("ERROR", f"{image_path.name} - 応答テキストが空です (試行{attempt}/{max_retries})")
                continue  # リトライ

            parsed = extract_json_loose(text)
            if parsed is None:
                log("ERROR", f"{image_path.name} - JSON抽出に失敗しました (試行{attempt}/{max_retries})")
                continue  # リトライ

            # JSON抽出成功
            od = OrderedDict()
            od["ファイル名"] = image_path.name
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    od[k] = v
            else:
                od["data"] = parsed
            return od

        except Exception as e:
            if is_rate_limit_error(e):
                log("ERROR", f"レート上限エラー検出: {e}")
                raise
            log("ERROR", f"{image_path.name} の処理で例外: {e} (試行{attempt}/{max_retries})")
            continue  # リトライ

    # すべて失敗した場合
    log("ERROR", f"{image_path.name} - 最大リトライ回数({max_retries})を超えました")
    return None

# ===== メイン =====
def main():
    ensure_folders()

    image_files = sorted([p for p in INPUT_DIR.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")])
    if not image_files:
        log("INFO", f"処理対象の画像が見つかりません: {INPUT_DIR}")
        return

    results = []
    try:
        for idx, img_path in enumerate(image_files, start=1):
            log("INFO", f"({idx}/{len(image_files)}) 処理中: {img_path.name}")
            try:
                od = process_image(img_path)
            except Exception as e:
                # レート上限等の致命的エラーはここで捕まって中断
                log("ERROR", "致命的エラー（レート上限など）により処理を中断します")
                break

            if od is None:
                # 非JSONや例外によるスキップはログに記録済み。結果にはエラー要素として保存する
                results.append(OrderedDict([("ファイル名", img_path.name), ("error", "Invalid or no JSON")]))
            else:
                results.append(od)

    finally:
        # 途中終了でもこれまでの結果を保存する
        if results:
            ts_str = datetime.now().strftime("%Y%m%d_%H%M")  # YYYYMMDD_hhmm
            out_file = OUTPUT_DIR / f"{ts_str}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            log("INFO", f"結果を保存しました: {out_file}")
        else:
            log("INFO", "保存する結果はありません")

    # 終了
    log("INFO", "処理終了")


if __name__ == "__main__":
    main()
