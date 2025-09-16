import sys
import subprocess
from pathlib import Path


def run_step(script_path: Path, name: str, cwd: Path | None = None) -> None:
    print(f"=== {name} ===\n-> {script_path}")
    subprocess.run([sys.executable, str(script_path)], check=True, cwd=str(cwd) if cwd else None)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"
    steps = [
        ("PDF -> JPG", src_dir / "1_pdf_to_jpg.py"),
        ("JPG -> JSON (OCR)", src_dir / "2_jpg_to_json_byGeminiOCR.py"),
        ("JSON -> CSV", src_dir / "3_json_to_csv.py"),
    ]

    for name, script in steps:
        if not script.exists():
            print(f"ERROR: スクリプトが見つかりません: {script}")
            sys.exit(1)
        run_step(script, name, cwd=repo_root)

    print("\n=== すべての処理が完了しました ===")


if __name__ == "__main__":
    main()
