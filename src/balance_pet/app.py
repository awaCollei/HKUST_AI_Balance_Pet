"""应用入口。"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from .pet import PetWindow


def project_root() -> Path:
    """返回源码项目或打包后可执行文件所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def main() -> int:
    root = project_root()
    load_dotenv(root / ".env")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("余额桌面宠物")
    app.setOrganizationName("BalancePet")
    app.setQuitOnLastWindowClosed(False)

    try:
        pet = PetWindow(root / "pet.png")
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "启动失败", str(exc))
        return 1

    app.aboutToQuit.connect(pet.close)
    pet.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
