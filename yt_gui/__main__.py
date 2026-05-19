import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .app import App


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("yt-gui")
    try:
        window = App()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(
            None, "Fatal Error", f"An error occurred during startup:\n{e}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
