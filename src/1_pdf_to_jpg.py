import os
import glob
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image

def pdf_to_jpg_converter():
    """
    PDFをJPGに変換する関数
    - inputPDFフォルダ内の全PDFファイルを処理
    - 複数ページのPDFは各ページを別JPGファイルとして出力
    - 出力ファイル名に連番サフィックス（0埋め）を付与
    - 高画質で変換
    """
    


    # プロジェクトルート配下の data ディレクトリを使用
    repo_root = Path(__file__).resolve().parent.parent
    input_folder = str(repo_root / "data" / "pdf")
    output_folder = str(repo_root / "data" / "jpg")
    
    # 入力フォルダの存在確認
    if not os.path.exists(input_folder):
        print(f"エラー: '{input_folder}' フォルダが存在しません。")
        return
    
    # 出力フォルダの作成
    os.makedirs(output_folder, exist_ok=True)
    print(f"出力フォルダ: {output_folder}")
    
    # PDFファイルのリストを取得
    pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))
    #pdf_files.extend(glob.glob(os.path.join(input_folder, "*.PDF")))  # 大文字拡張子も対応
    
    if not pdf_files:
        print(f"'{input_folder}' フォルダ内にPDFファイルが見つかりません。")
        return
    
    print(f"処理対象のPDFファイル数: {len(pdf_files)}")
    
    # 各PDFファイルを処理
    for pdf_path in pdf_files:
        try:
            # ファイル名（拡張子なし）を取得
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            print(f"\n処理中: {base_name}.pdf")
            
            # PDFをイメージに変換（高画質設定）
            # dpi=300で高解像度、fmt='JPEG'でJPEG形式指定
            images = convert_from_path(
                pdf_path,
                dpi=300,  # 高解像度（300 DPI）
                fmt='JPEG',
                jpegopt={'quality': 95, 'optimize': True}  # 高品質JPEG設定
            )
            
            # ページ数に応じて連番の桁数を決定（0埋め用）
            total_pages = len(images)
            digits = len(str(total_pages))
            
            print(f"  総ページ数: {total_pages}")
            
            # 各ページをJPGとして保存
            for i, image in enumerate(images, 1):
                # 連番サフィックス付きファイル名を生成
                if total_pages == 1:
                    # 単一ページの場合はサフィックスなし
                    output_filename = f"{base_name}.jpg"
                else:
                    # 複数ページの場合は0埋めした連番を付与
                    page_suffix = str(i).zfill(digits)
                    output_filename = f"{base_name}_{page_suffix}.jpg"
                
                output_path = os.path.join(output_folder, output_filename)
                
                # JPGとして保存（高品質設定）
                image.save(
                    output_path,
                    'JPEG',
                    quality=95,  # 高品質
                    optimize=True,  # ファイルサイズ最適化
                    dpi=(300, 300)  # DPI情報を保持
                )
                
                print(f"  保存完了: {output_filename}")
            
        except Exception as e:
            print(f"エラー - {os.path.basename(pdf_path)}: {str(e)}")
            continue
    
    print(f"\n変換処理完了！出力先: {output_folder}")

def main():
    """メイン関数"""
    print("=== PDF to JPG Converter ===")
    print("data/pdf 内のPDFファイルをJPGに変換します。")
    print("出力先: data/jpg/\n")
    
    # 必要なライブラリの確認
    try:
        import pdf2image
        from PIL import Image
    except ImportError as e:
        print("必要なライブラリがインストールされていません:")
        print("pip install pdf2image Pillow")
        print("\nWindowsの場合は Poppler の導入が必要です（poppler パス設定 or conda-forge から導入）")
        return
    
    # PDF変換実行
    pdf_to_jpg_converter()

if __name__ == "__main__":
    main()
