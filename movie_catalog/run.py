"""Entry point for the movie catalog."""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from .main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MovieCatalog")
    app.setOrganizationName("QtStudentProject")
    try:
        window = MainWindow()
    except Exception as error:
        QMessageBox.critical(None, "Ошибка запуска", str(error))
        return 1
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
