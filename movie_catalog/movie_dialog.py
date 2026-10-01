"""Editor form for one movie."""

from datetime import date

from PyQt6 import uic
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QDialog, QDialogButtonBox, QFileDialog,
    QListWidgetItem, QMessageBox,
)

from .paths import resource_path


class MovieDialog(QDialog):
    def __init__(self, genres, movie=None, selected_genre_ids=None, parent=None):
        super().__init__(parent)
        uic.loadUi(str(resource_path("movie_dialog.ui")), self)
        self.movie = movie
        self.poster_path = movie["poster_path"] if movie else ""
        self.setWindowTitle("Изменить фильм" if movie else "Добавить фильм")
        self.dialogHeading.setText(self.windowTitle())
        self.yearSpin.setValue(date.today().year)
        self.ratingSpin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.buttonBox.button(
            QDialogButtonBox.StandardButton.Save
        ).setText("Сохранить")
        self.buttonBox.button(
            QDialogButtonBox.StandardButton.Cancel
        ).setText("Отмена")
        if selected_genre_ids is None and movie:
            selected_genre_ids = [movie["genre_id"]]
        selected_genre_ids = set(selected_genre_ids or [])
        for genre in genres:
            item = QListWidgetItem(genre["name"], self.genreList)
            item.setData(Qt.ItemDataRole.UserRole, genre["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = (Qt.CheckState.Checked if genre["id"] in selected_genre_ids
                     else Qt.CheckState.Unchecked)
            item.setCheckState(state)
        self.genreList.itemChanged.connect(self._update_genre_summary)
        self._update_genre_summary()
        if movie:
            self._fill_movie(movie)
        self.statusCombo.currentTextChanged.connect(self._update_rating)
        self.ratingUpButton.clicked.connect(self.ratingSpin.stepUp)
        self.ratingDownButton.clicked.connect(self.ratingSpin.stepDown)
        self.choosePosterButton.clicked.connect(self._choose_poster)
        self.clearPosterButton.clicked.connect(self._clear_poster)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self._update_rating()
        self._update_poster()
        self.titleEdit.setFocus()

    def _fill_movie(self, movie):
        self.titleEdit.setText(movie["title"])
        self.yearSpin.setValue(movie["year"])
        self.statusCombo.setCurrentText(movie["status"])
        self.ratingSpin.setValue(movie["rating"] or 1)
        self.notesEdit.setPlainText(movie["notes"])

    def _update_rating(self):
        watched = self.statusCombo.currentText() == "Просмотрено"
        for widget in (self.ratingSpin, self.ratingLabel,
                       self.ratingUpButton, self.ratingDownButton):
            widget.setEnabled(watched)
        self.ratingSpin.setToolTip(
            "Оценку можно поставить просмотренному фильму" if not watched else ""
        )

    def _choose_poster(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "Выберите постер", "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*)",
        )
        if not selected:
            return
        if QPixmap(selected).isNull():
            QMessageBox.warning(self, "Ошибка", "Не удалось открыть изображение.")
            return
        self.poster_path = selected
        self._update_poster()

    def _clear_poster(self):
        self.poster_path = ""
        self._update_poster()

    def _update_poster(self):
        pixmap = QPixmap(self.poster_path) if self.poster_path else QPixmap()
        if pixmap.isNull():
            self.posterPreview.setPixmap(QPixmap())
            self.posterPreview.setText("Нет постера")
        else:
            self.posterPreview.setText("")
            self.posterPreview.setPixmap(pixmap.scaled(
                80, 100, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        self.clearPosterButton.setEnabled(bool(self.poster_path))

    def selected_genre_ids(self):
        return [
            self.genreList.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.genreList.count())
            if self.genreList.item(index).checkState() == Qt.CheckState.Checked
        ]

    def _update_genre_summary(self, _item=None):
        names = [
            self.genreList.item(index).text()
            for index in range(self.genreList.count())
            if self.genreList.item(index).checkState() == Qt.CheckState.Checked
        ]
        if names:
            self.selectedGenresLabel.setText(
                f"Выбрано: {len(names)} — {', '.join(names)}"
            )
        else:
            self.selectedGenresLabel.setText("Отметьте один или несколько жанров")

    def values(self):
        return {
            "title": self.titleEdit.text().strip(),
            "year": self.yearSpin.value(),
            "genre_ids": self.selected_genre_ids(),
            "status": self.statusCombo.currentText(),
            "rating": self.ratingSpin.value()
            if self.statusCombo.currentText() == "Просмотрено" else None,
            "notes": self.notesEdit.toPlainText(),
            "poster_path": self.poster_path,
        }

    def accept(self):
        if not self.titleEdit.text().strip():
            QMessageBox.warning(self, "Нужно название", "Укажите название фильма.")
            self.titleEdit.setFocus()
            return
        if not self.selected_genre_ids():
            QMessageBox.warning(self, "Нужен жанр", "Выберите хотя бы один жанр.")
            self.genreList.setFocus()
            return
        super().accept()