"""
Build Standalone Exe: Đóng gói bộ ghi nhận thao tác Universal Recorder
thành 1 file thực thi .EXE duy nhất bằng PyInstaller.
File xuất ra: dist/BAT_DAU_GHI_NHAN.exe
Có thể copy sang bất kỳ máy học viên nào để chạy mà KHÔNG cần cài Python.
"""

import os
import sys
import subprocess

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def build():
    print("=" * 75)
    print("📦 BẮT ĐẦU ĐÓNG GÓI BỘ GHI NHẬN EXCEL THÀNH 1 FILE .EXE DUY NHẤT")
    print("=" * 75)

    entry_script = os.path.join(ROOT_DIR, "bat_dau_ghi_nhan.py")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir", # Hoặc --onefile
        "--clean",
        "--name", "BAT_DAU_GHI_NHAN",
        f"--paths={ROOT_DIR}",
        "--hidden-import=win32timezone",
        "--hidden-import=win32com",
        "--hidden-import=win32com.client",
        "--hidden-import=pymysql",
        entry_script,
    ]

    print(f"Lệnh thực thi: {' '.join(cmd)}\n")
    ret = subprocess.run(cmd, cwd=ROOT_DIR)

    if ret.returncode == 0:
        print("\n" + "=" * 75)
        print("🎉 ĐÓNG GÓI HOÀN TẤT THÀNH CÔNG!")
        print("📁 File chạy được lưu tại thư mục: dist/BAT_DAU_GHI_NHAN/")
        print("👉 Bạn chỉ cần copy thư mục/file này sang máy học viên để dùng ngay!")
        print("=" * 75)
    else:
        print(f"\n❌ Đóng gói thất bại với mã lỗi: {ret.returncode}")

if __name__ == "__main__":
    build()
