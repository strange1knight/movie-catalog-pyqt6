"""SQLite storage for movies and their genres."""

from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_GENRES = (
    "Без жанра", "Боевик", "Детектив", "Драма", "Комедия", "Мультфильм",
    "Приключения", "Триллер", "Ужасы", "Фантастика", "Фэнтези",
)
STATUSES = ("В планах", "Просмотрено")

MOVIE_SELECT = """
    SELECT m.*,
           COALESCE((
               SELECT GROUP_CONCAT(name, ', ')
               FROM (
                   SELECT g2.name AS name
                   FROM movie_genres AS mg
                   JOIN genres AS g2 ON g2.id = mg.genre_id
                   WHERE mg.movie_id = m.id
                   ORDER BY g2.name COLLATE NOCASE
               )
           ), g.name) AS genre_name
    FROM movies AS m
    JOIN genres AS g ON g.id = m.genre_id
"""


class CatalogDatabase:
    """Owns the database connection and all SQL operations."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self):
        with self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS genres (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE
                );
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    year INTEGER NOT NULL CHECK(year BETWEEN 1888 AND 2100),
                    genre_id INTEGER NOT NULL REFERENCES genres(id),
                    status TEXT NOT NULL CHECK(status IN ('В планах', 'Просмотрено')),
                    rating INTEGER CHECK(rating BETWEEN 1 AND 10),
                    notes TEXT NOT NULL DEFAULT '',
                    poster_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK(status = 'Просмотрено' OR rating IS NULL)
                );
                CREATE TABLE IF NOT EXISTS movie_genres (
                    movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
                    genre_id INTEGER NOT NULL REFERENCES genres(id),
                    PRIMARY KEY (movie_id, genre_id)
                );
                CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title);
                CREATE INDEX IF NOT EXISTS idx_movies_status ON movies(status);
                CREATE INDEX IF NOT EXISTS idx_movie_genres_genre
                    ON movie_genres(genre_id);
                """
            )
            self.connection.executemany(
                "INSERT OR IGNORE INTO genres(name) VALUES (?)",
                ((name,) for name in DEFAULT_GENRES),
            )
            # Older releases stored one genre directly on movies. Keep that
            # column for compatibility and copy existing selections once.
            self.connection.execute(
                """INSERT OR IGNORE INTO movie_genres(movie_id, genre_id)
                   SELECT id, genre_id FROM movies"""
            )

    def genres(self):
        return self.connection.execute(
            "SELECT id, name FROM genres ORDER BY name COLLATE NOCASE"
        ).fetchall()

    def movie_genre_ids(self, movie_id):
        rows = self.connection.execute(
            """SELECT genre_id FROM movie_genres
               WHERE movie_id = ? ORDER BY genre_id""",
            (movie_id,),
        ).fetchall()
        return [row["genre_id"] for row in rows]

    def add_genre(self, name: str):
        name = name.strip()
        if not name:
            raise ValueError("Название жанра не может быть пустым")
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO genres(name) VALUES (?)", (name,)
            )
        return cursor.lastrowid

    def list_movies(self, search="", status="Все", genre_id=None):
        """Return movies with optional filters; never interpolate user input."""
        sql = MOVIE_SELECT + " WHERE 1 = 1"
        params = []
        if search.strip():
            sql += " AND (m.title LIKE ? OR m.notes LIKE ?)"
            pattern = "%" + search.strip() + "%"
            params.extend((pattern, pattern))
        if status in STATUSES:
            sql += " AND m.status = ?"
            params.append(status)
        if genre_id is not None:
            sql += """ AND EXISTS (
                SELECT 1 FROM movie_genres AS mg
                WHERE mg.movie_id = m.id AND mg.genre_id = ?
            )"""
            params.append(genre_id)
        sql += " ORDER BY m.title COLLATE NOCASE, m.year DESC, m.id"
        return self.connection.execute(sql, params).fetchall()

    def get_movie(self, movie_id):
        return self.connection.execute(
            MOVIE_SELECT + " WHERE m.id = ?", (movie_id,)
        ).fetchone()

    def save_movie(self, movie, movie_id=None):
        """Insert or update one movie and all its genres atomically."""
        genre_ids = movie.get("genre_ids")
        if genre_ids is None and "genre_id" in movie:
            genre_ids = [movie["genre_id"]]
        genre_ids = list(dict.fromkeys(genre_ids or []))
        if not genre_ids:
            raise ValueError("Выберите хотя бы один жанр")
        title = movie["title"].strip()
        if not title:
            raise ValueError("Укажите название фильма")
        values = (
            title, movie["year"], genre_ids[0], movie["status"],
            movie["rating"], movie["notes"].strip(), movie["poster_path"],
        )
        with self.connection:
            if movie_id is None:
                cursor = self.connection.execute(
                    """INSERT INTO movies
                       (title, year, genre_id, status, rating, notes, poster_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    values,
                )
                movie_id = cursor.lastrowid
            else:
                cursor = self.connection.execute(
                    """UPDATE movies SET title = ?, year = ?, genre_id = ?,
                       status = ?, rating = ?, notes = ?, poster_path = ?
                       WHERE id = ?""",
                    (*values, movie_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("Фильм не найден")
                self.connection.execute(
                    "DELETE FROM movie_genres WHERE movie_id = ?", (movie_id,)
                )
            self.connection.executemany(
                """INSERT INTO movie_genres(movie_id, genre_id)
                   VALUES (?, ?)""",
                ((movie_id, genre_id) for genre_id in genre_ids),
            )
        return movie_id

    def delete_movie(self, movie_id):
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM movies WHERE id = ?", (movie_id,)
            )
        return cursor.rowcount > 0

    def counts(self):
        rows = self.connection.execute(
            "SELECT status, COUNT(*) AS total FROM movies GROUP BY status"
        ).fetchall()
        values = {row["status"]: row["total"] for row in rows}
        planned = values.get("В планах", 0)
        watched = values.get("Просмотрено", 0)
        return planned + watched, planned, watched

    def close(self):
        self.connection.close()