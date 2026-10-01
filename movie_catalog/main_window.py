"""Catalog window, user interactions, and poster file management."""

import shutil
import sqlite3
import uuid
from pathlib import Path

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QHeaderView, QInputDialog, QMainWindow, QMenu,
    QMessageBox, QTableWidgetItem,
)

from .database import CatalogDatabase, STATUSES
from .movie_dialog import MovieDialog
from .paths import data_dir, resource_path


class MainWindow(QMainWindow):
    def __init__(self, db=None):
        super().__init__()
        uic.loadUi(str(resource_path("main_window.ui")), self)
        self.db = db or CatalogDatabase(data_dir() / "catalog.sqlite3")
        self.poster_dir = data_dir() / "posters"
        self.poster_dir.mkdir(parents=True, exist_ok=True)
        self._selected_id = None
        self._configure_table()
        self._configure_filters()
        self._connect_actions()
        self._apply_style()
        self.refresh()

    def _configure_table(self):
        self.movieTable.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.movieTable.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.movieTable.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.movieTable.setAlternatingRowColors(True)
        self.movieTable.verticalHeader().setVisible(False)
        header = self.movieTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.movieTable.setColumnWidth(2, 175)
        self.movieTable.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.contentSplitter.setSizes([720, 320])

    def _configure_filters(self):
        self.statusFilter.addItems(("Все", *STATUSES))
        self._reload_genres()

    def _reload_genres(self, selected=None):
        self.genreFilter.blockSignals(True)
        self.genreFilter.clear()
        self.genreFilter.addItem("Все жанры", None)
        for genre in self.db.genres():
            self.genreFilter.addItem(genre["name"], genre["id"])
        index = self.genreFilter.findData(selected)
        self.genreFilter.setCurrentIndex(max(index, 0))
        self.genreFilter.blockSignals(False)

    def _connect_actions(self):
        self.searchEdit.textChanged.connect(self.refresh)
        self.statusFilter.currentIndexChanged.connect(self.refresh)
        self.genreFilter.currentIndexChanged.connect(self.refresh)
        self.addButton.clicked.connect(self.add_movie)
        self.editButton.clicked.connect(self.edit_movie)
        self.deleteButton.clicked.connect(self.delete_movie)
        self.genreButton.clicked.connect(self.add_genre)
        self.movieTable.itemSelectionChanged.connect(self._selection_changed)
        self.movieTable.itemDoubleClicked.connect(lambda _: self.edit_movie())
        self.movieTable.customContextMenuRequested.connect(self._show_context_menu)
        self._shortcuts = []
        for sequence, callback in (
            ("Return", self.edit_movie),
            ("Delete", self.delete_movie),
            ("F5", self.refresh),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self.movieTable)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)
        global_add = QShortcut(QKeySequence("Ctrl+N"), self)
        global_add.activated.connect(self.add_movie)
        self._shortcuts.append(global_add)
        global_search = QShortcut(QKeySequence("Ctrl+F"), self)
        global_search.activated.connect(self.searchEdit.setFocus)
        self._shortcuts.append(global_search)

    def _apply_style(self):
        self.setStyleSheet("""
            QWidget { color: #1f2937; }
            QMainWindow, QDialog { background: #f7f8fa; color: #1f2937; }
            QLabel#headingLabel { color: #172033; font-size: 27px; font-weight: 700; }
            QLabel#subtitleLabel { color: #6b7280; font-size: 13px; }
            QLabel#detailTitle { color: #172033; font-size: 19px; font-weight: 700; }
            QLabel#detailMeta { color: #526172; }
            QLabel#posterLabel { background: #e7ebf0; border: 1px solid #d4dce5;
                                 border-radius: 8px; color: #748293; }
            QLineEdit, QComboBox, QListWidget, QPlainTextEdit, QTextBrowser {
                color: #1f2937; background: white; border: 1px solid #cbd5e1; border-radius: 5px;
                padding: 6px; selection-background-color: #2563eb;
            }
            QListWidget::indicator { width: 16px; height: 16px; border: 1px solid #64748b;
                                      border-radius: 3px; background: white; }
            QListWidget::indicator:checked { background: #2563eb; border-color: #2563eb; }
            QTableWidget { color: #1f2937; background: white; border: 1px solid #dbe2e9;
                           gridline-color: #edf1f5; }
            QHeaderView::section { color: #344054; background: #eef2f7; padding: 8px;
                                   border: none; font-weight: 600; }
            QPushButton { color: #1f2937; background: white; border: 1px solid #cbd5e1;
                          border-radius: 5px; padding: 8px 12px; }
            QPushButton:hover { background: #e9f0ff; }
            QPushButton#addButton { background: #2563eb; color: white;
                                    border: 1px solid #2563eb; font-weight: 600; }
            QPushButton#addButton:hover { background: #1d4ed8; }
            QPushButton#deleteButton:hover { background: #fee2e2; }
        """)

    def refresh(self):
        selected_id = self._selected_id
        movies = self.db.list_movies(
            self.searchEdit.text(), self.statusFilter.currentText(),
            self.genreFilter.currentData(),
        )
        self.movieTable.blockSignals(True)
        self.movieTable.setRowCount(len(movies))
        selected_row = -1
        for row_index, movie in enumerate(movies):
            columns = (
                movie["title"], str(movie["year"]), movie["genre_name"],
                movie["status"], str(movie["rating"] or "—"),
            )
            for column, value in enumerate(columns):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, movie["id"])
                if column in (1, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2:
                    item.setToolTip(movie["genre_name"])
                if column == 3:
                    color = "#166534" if movie["status"] == "Просмотрено" else "#92400e"
                    item.setForeground(QColor(color))
                self.movieTable.setItem(row_index, column, item)
            if movie["id"] == selected_id:
                selected_row = row_index
        self.movieTable.clearSelection()
        if selected_row >= 0:
            self.movieTable.selectRow(selected_row)
        self.movieTable.blockSignals(False)
        self._selection_changed()
        total, planned, watched = self.db.counts()
        self.countLabel.setText(
            f"Всего: {total}  •  В планах: {planned}  •  Просмотрено: {watched}"
        )
        self.statusbar.showMessage(f"Показано фильмов: {len(movies)}")

    def _selection_changed(self):
        row = self.movieTable.currentRow()
        item = self.movieTable.item(row, 0) if row >= 0 else None
        if not item or not item.isSelected():
            self._selected_id = None
            self._show_details(None)
            return
        self._selected_id = item.data(Qt.ItemDataRole.UserRole)
        self._show_details(self.db.get_movie(self._selected_id))

    def _show_details(self, movie):
        enabled = movie is not None
        self.editButton.setEnabled(enabled)
        self.deleteButton.setEnabled(enabled)
        if not movie:
            self.detailTitle.setText("Выберите фильм")
            self.detailMeta.setText("Информация появится здесь")
            self.notesView.clear()
            self.posterLabel.setPixmap(QPixmap())
            self.posterLabel.setText("Постер фильма")
            return
        self.detailTitle.setText(movie["title"])
        rating = f"  •  {movie['rating']}/10" if movie["rating"] else ""
        self.detailMeta.setText(
            f"{movie['year']}  •  {movie['genre_name']}\n"
            f"{movie['status']}{rating}"
        )
        self.notesView.setPlainText(movie["notes"] or "Заметок пока нет.")
        pixmap = QPixmap(movie["poster_path"]) if movie["poster_path"] else QPixmap()
        if pixmap.isNull():
            self.posterLabel.setPixmap(QPixmap())
            self.posterLabel.setText("Постер не выбран")
        else:
            self.posterLabel.setText("")
            self.posterLabel.setPixmap(pixmap.scaled(
                260, 310, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def add_movie(self):
        self._edit_movie(None)

    def edit_movie(self):
        if self._selected_id is not None:
            self._edit_movie(self._selected_id)

    def _edit_movie(self, movie_id):
        movie = self.db.get_movie(movie_id) if movie_id is not None else None
        genre_ids = self.db.movie_genre_ids(movie_id) if movie else None
        dialog = MovieDialog(self.db.genres(), movie, genre_ids, self)
        if not dialog.exec():
            return
        values = dialog.values()
        new_poster = None
        try:
            source = Path(values["poster_path"]) if values["poster_path"] else None
            if source and source.is_file() and source.parent != self.poster_dir:
                new_poster = self.poster_dir / f"{uuid.uuid4().hex}{source.suffix.lower()}"
                shutil.copy2(source, new_poster)
                values["poster_path"] = str(new_poster)
            saved_id = self.db.save_movie(values, movie_id)
        except (OSError, sqlite3.Error, ValueError) as error:
            if new_poster and new_poster.exists():
                new_poster.unlink()
            QMessageBox.critical(self, "Не удалось сохранить", str(error))
            return
        if movie and movie["poster_path"] != values["poster_path"]:
            self._remove_managed_poster(movie["poster_path"])
        self._selected_id = saved_id
        self.refresh()
        self.statusbar.showMessage("Фильм сохранён", 4000)

    def _remove_managed_poster(self, path):
        if not path:
            return
        poster = Path(path)
        if poster.parent == self.poster_dir:
            try:
                poster.unlink(missing_ok=True)
            except OSError:
                pass

    def delete_movie(self):
        if self._selected_id is None:
            return
        movie = self.db.get_movie(self._selected_id)
        if not movie:
            self.refresh()
            return
        answer = QMessageBox.question(
            self, "Удалить фильм?", f"Удалить «{movie['title']}» из каталога?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_movie(self._selected_id)
        except sqlite3.Error as error:
            QMessageBox.critical(self, "Не удалось удалить", str(error))
            return
        self._remove_managed_poster(movie["poster_path"])
        self._selected_id = None
        self.refresh()
        self.statusbar.showMessage("Фильм удалён", 4000)

    def add_genre(self):
        name, accepted = QInputDialog.getText(self, "Новый жанр", "Название жанра:")
        if not accepted or not name.strip():
            return
        try:
            genre_id = self.db.add_genre(name)
        except sqlite3.IntegrityError:
            QMessageBox.information(self, "Жанр уже есть", "Такой жанр уже существует.")
            return
        except (sqlite3.Error, ValueError) as error:
            QMessageBox.critical(self, "Не удалось добавить жанр", str(error))
            return
        self._reload_genres(genre_id)
        self.refresh()
        self.statusbar.showMessage("Жанр добавлен", 4000)

    def _show_context_menu(self, position):
        item = self.movieTable.itemAt(position)
        if item is None:
            return
        self.movieTable.selectRow(item.row())
        menu = QMenu(self)
        edit_action = QAction("Изменить", self)
        delete_action = QAction("Удалить", self)
        edit_action.triggered.connect(self.edit_movie)
        delete_action.triggered.connect(self.delete_movie)
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(self.movieTable.viewport().mapToGlobal(position))

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)
