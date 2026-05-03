from tkinter import messagebox
from .app import App


def main():
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        messagebox.showerror("致命的なエラー", f"アプリケーションの起動中にエラーが発生しました:\n{e}")


if __name__ == "__main__":
    main()
