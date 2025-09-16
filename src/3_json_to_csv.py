#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON to CSV Converter
JSONファイルを読み込み、CSV形式に変換するプログラム

このプログラムは以下の機能を提供します：
1. JSONファイルを読み込んでCSVに変換する関数
2. 指定フォルダ内のすべてのJSONファイルを一括処理
3. 詳細な実行ログをターミナルに出力
"""

import json
import csv
import os
import glob
from pathlib import Path
from typing import List, Dict, Any, Union
from datetime import datetime

# マジックワード（設定定数）
# リポジトリルートをベースにパスを解決（実行ディレクトリに依存しない）
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
INPUT_FOLDER = str(DATA_DIR / "json")      # 処理対象のJSONファイルがあるフォルダ
OUTPUT_FOLDER = str(DATA_DIR / "csv")      # 出力先のCSVファイルを保存するフォルダ
LOG_PREFIX = "[JSON2CSV]"          # ログ出力時のプレフィックス
CSV_DELIMITER = ","                # CSV区切り文字（","、";"、"\t"など）
CSV_ENCODING = "utf-8-sig"         # CSV出力エンコーディング（utf-8-sig=Excel対応、utf-8=一般的）

def log_message(message: str, level: str = "INFO") -> None:
    """
    ターミナルにログメッセージを出力する関数
    
    Args:
        message (str): 出力するメッセージ
        level (str): ログレベル（INFO, WARNING, ERROR）
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{LOG_PREFIX} [{level}] {timestamp} - {message}")

def normalize_value(value: Any) -> str:
    """
    JSONの値を正規化してCSVに適した文字列に変換する関数
    
    Args:
        value: JSON内の任意の値（文字列、数値、リストなど）
    
    Returns:
        str: 正規化された文字列
    """
    # None（null）の場合は空文字列を返す
    if value is None:
        return ""
    
    # リストや辞書の場合はJSON文字列として保存
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    
    # 文字列の場合、制御文字を削除（改行は保持）
    if isinstance(value, str):
        # 制御文字のうち、タブと改行以外を削除
        cleaned = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n')
        return cleaned
    
    # その他の場合は文字列に変換
    return str(value)

def extract_all_keys(json_data: List[Dict[str, Any]]) -> List[str]:
    """
    JSON配列内のすべてのオブジェクトからキーを抽出し、重複を除いた一覧を作成する関数
    
    Args:
        json_data: JSONデータ（辞書のリスト）
    
    Returns:
        List[str]: すべてのキーの一覧（重複なし、出現順）
    """
    all_keys = []
    
    # 各オブジェクトのキーを順次チェック
    for item in json_data:
        if isinstance(item, dict):  # 辞書型かどうか確認
            for key in item.keys():
                # まだリストに含まれていないキーのみ追加（順序を保持）
                if key not in all_keys:
                    all_keys.append(key)
    
    log_message(f"抽出されたキー: {all_keys}")
    return all_keys

def json_to_csv(json_file_path: str, csv_file_path: str = None) -> bool:
    """
    JSONファイルを読み込んでCSVファイルに変換するメイン関数
    
    Args:
        json_file_path (str): 入力JSONファイルのパス
        csv_file_path (str, optional): 出力CSVファイルのパス。
                                     Noneの場合、JSONファイル名をベースに自動生成
    
    Returns:
        bool: 変換が成功した場合True、失敗した場合False
    """
    try:
        log_message(f"JSONファイルの読み込み開始: {json_file_path}")
        
        # JSONファイルを読み込む
        with open(json_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
        
        # データが空の場合の処理
        if not data:
            log_message("JSONファイルが空です", "WARNING")
            return False
        
        # データがリストでない場合はリストに変換
        if not isinstance(data, list):
            log_message("JSONデータが配列ではないため、単一要素の配列として処理します", "INFO")
            data = [data]
        
        log_message(f"読み込み完了: {len(data)}件のレコード")
        
        # すべてのキーを抽出（動的にヘッダーを決定）
        headers = extract_all_keys(data)
        
        # 出力ファイルパスが指定されていない場合は自動生成
        if csv_file_path is None:
            # JSONファイルの拡張子を.csvに変更
            base_name = os.path.splitext(os.path.basename(json_file_path))[0]
            csv_file_path = os.path.join(OUTPUT_FOLDER, f"{base_name}.csv")
        
        # 出力ディレクトリが存在しない場合は作成
        output_dir = os.path.dirname(csv_file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            log_message(f"出力ディレクトリを作成しました: {output_dir}")
        
        log_message(f"CSV出力開始: {csv_file_path}")
        
        # CSVファイルに書き込み
        # Excelでの日本語文字化けを防ぐため、BOMを付与したUTF-8を使用
        with open(csv_file_path, 'w', newline='', encoding=CSV_ENCODING) as csv_file:
            writer = csv.writer(csv_file, delimiter=CSV_DELIMITER)
            
            # ヘッダー行を書き込み
            writer.writerow(headers)
            log_message(f"ヘッダー書き込み完了: {headers}")
            
            # データ行を書き込み
            for i, item in enumerate(data):
                row = []
                # 各ヘッダーに対応する値を取得（存在しない場合は空文字）
                for header in headers:
                    value = item.get(header) if isinstance(item, dict) else ""
                    normalized_value = normalize_value(value)
                    row.append(normalized_value)
                
                writer.writerow(row)
                
                # 進捗ログ（100件ごと、または最後の件）
                if (i + 1) % 100 == 0 or (i + 1) == len(data):
                    log_message(f"データ書き込み進捗: {i + 1}/{len(data)}件")
        
        log_message(f"CSV変換完了: {csv_file_path}")
        return True
        
    except FileNotFoundError:
        log_message(f"ファイルが見つかりません: {json_file_path}", "ERROR")
        return False
    except json.JSONDecodeError as e:
        log_message(f"JSONの解析に失敗しました: {e}", "ERROR")
        return False
    except Exception as e:
        log_message(f"予期しないエラーが発生しました: {e}", "ERROR")
        return False

def process_folder(input_folder: str = INPUT_FOLDER, output_folder: str = OUTPUT_FOLDER) -> None:
    """
    指定フォルダ内のすべてのJSONファイルを処理する関数
    
    Args:
        input_folder (str): 入力フォルダのパス
        output_folder (str): 出力フォルダのパス
    """
    log_message("=" * 50)
    log_message("JSON to CSV 一括変換処理を開始します")
    log_message("=" * 50)
    
    # 入力フォルダが存在するかチェック
    if not os.path.exists(input_folder):
        log_message(f"入力フォルダが存在しません: {input_folder}", "ERROR")
        log_message(f"フォルダを作成してJSONファイルを配置してください", "INFO")
        return
    
    # JSONファイルを検索
    json_pattern = os.path.join(input_folder, "*.json")
    json_files = glob.glob(json_pattern)
    
    if not json_files:
        log_message(f"JSONファイルが見つかりませんでした: {input_folder}", "WARNING")
        log_message("*.json形式のファイルを確認してください", "INFO")
        return
    
    log_message(f"処理対象ファイル数: {len(json_files)}件")
    
    # 成功・失敗カウンタ
    success_count = 0
    error_count = 0
    
    # 各JSONファイルを処理
    for json_file in json_files:
        log_message("-" * 30)
        
        # 出力ファイル名を生成
        base_name = os.path.splitext(os.path.basename(json_file))[0]
        csv_file = os.path.join(output_folder, f"{base_name}.csv")
        
        # 変換実行
        if json_to_csv(json_file, csv_file):
            success_count += 1
        else:
            error_count += 1
    
    # 処理結果サマリー
    log_message("=" * 50)
    log_message("処理完了サマリー")
    log_message(f"成功: {success_count}件")
    log_message(f"失敗: {error_count}件")
    log_message(f"合計: {len(json_files)}件")
    log_message("=" * 50)

def main():
    """
    メイン関数：直接実行された場合の処理
    """
    log_message("JSON to CSV Converter を起動します")
    
    # 使用方法の説明
    log_message("使用方法:")
    log_message(f"1. '{INPUT_FOLDER}'フォルダにJSONファイルを配置")
    log_message(f"2. このプログラムを実行")
    log_message(f"3. '{OUTPUT_FOLDER}'フォルダにCSVファイルが出力されます")
    log_message("")
    
    # フォルダ処理を実行
    process_folder()

# スクリプトが直接実行された場合の処理
if __name__ == "__main__":
    main()

# 使用例（関数として使用する場合）:
# 
# # 単一ファイルの変換
# success = json_to_csv("input.json", "output.csv")
# 
# # フォルダ内の一括変換
# process_folder("./my_json_folder", "./my_csv_folder")
