from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiosqlite

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
    full_name TEXT NOT NULL,
    username TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invites (
    token TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    used_by INTEGER,
    used_at TEXT
);

CREATE TABLE IF NOT EXISTS homework (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT,
    file_id TEXT,
    file_kind TEXT,
    student_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT,
    file_id TEXT,
    file_kind TEXT,
    student_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(telegram_id)
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    starts_at TEXT NOT NULL,
    topic TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    notified_day INTEGER NOT NULL DEFAULT 0,
    notified_hour INTEGER NOT NULL DEFAULT 0,
    notified_start INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES users(telegram_id)
);
"""


def _now(tz: ZoneInfo) -> str:
    return datetime.now(tz).isoformat()


class Database:
    def __init__(self, path: str, tz: ZoneInfo) -> None:
        self.path = path
        self.tz = tz
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._migrate()
        await self._conn.commit()

    async def _migrate(self) -> None:
        cur = await self.conn.execute("PRAGMA table_info(materials)")
        cols = {row[1] for row in await cur.fetchall()}
        if "student_id" not in cols:
            await self.conn.execute("ALTER TABLE materials ADD COLUMN student_id INTEGER")

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None
        return self._conn

    async def upsert_user(
        self,
        telegram_id: int,
        role: str,
        full_name: str,
        username: str | None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO users (telegram_id, role, full_name, username, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username
            """,
            (telegram_id, role, full_name, username, _now(self.tz)),
        )
        await self.conn.commit()

    async def get_user(self, telegram_id: int) -> dict[str, Any] | None:
        cur = await self.conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def list_students(self) -> list[dict[str, Any]]:
        cur = await self.conn.execute(
            "SELECT * FROM users WHERE role = 'student' ORDER BY full_name"
        )
        return [dict(r) for r in await cur.fetchall()]

    async def remove_student(self, telegram_id: int) -> bool:
        await self.conn.execute("DELETE FROM homework WHERE student_id = ?", (telegram_id,))
        await self.conn.execute("DELETE FROM materials WHERE student_id = ?", (telegram_id,))
        await self.conn.execute("DELETE FROM lessons WHERE student_id = ?", (telegram_id,))
        cur = await self.conn.execute(
            "DELETE FROM users WHERE telegram_id = ? AND role = 'student'",
            (telegram_id,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def create_invite(self) -> str:
        token = secrets.token_urlsafe(8)
        await self.conn.execute(
            "INSERT INTO invites (token, created_at) VALUES (?, ?)",
            (token, _now(self.tz)),
        )
        await self.conn.commit()
        return token

    async def consume_invite(self, token: str, telegram_id: int) -> bool:
        cur = await self.conn.execute(
            "SELECT * FROM invites WHERE token = ? AND used_by IS NULL",
            (token,),
        )
        row = await cur.fetchone()
        if not row:
            return False
        await self.conn.execute(
            "UPDATE invites SET used_by = ?, used_at = ? WHERE token = ?",
            (telegram_id, _now(self.tz), token),
        )
        await self.conn.commit()
        return True

    async def add_homework(
        self,
        title: str,
        body: str | None,
        file_id: str | None,
        file_kind: str | None,
        student_id: int | None,
    ) -> int:
        cur = await self.conn.execute(
            """
            INSERT INTO homework (title, body, file_id, file_kind, student_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, body, file_id, file_kind, student_id, _now(self.tz)),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def list_homework(
        self,
        student_id: int | None = None,
        *,
        shared_only: bool = False,
    ) -> list[dict[str, Any]]:
        if shared_only:
            cur = await self.conn.execute(
                "SELECT * FROM homework WHERE student_id IS NULL ORDER BY id DESC LIMIT 30"
            )
        elif student_id is None:
            cur = await self.conn.execute(
                "SELECT * FROM homework ORDER BY id DESC LIMIT 30"
            )
        else:
            cur = await self.conn.execute(
                """
                SELECT * FROM homework
                WHERE student_id IS NULL OR student_id = ?
                ORDER BY id DESC LIMIT 30
                """,
                (student_id,),
            )
        return [dict(r) for r in await cur.fetchall()]

    async def get_homework(self, hid: int) -> dict[str, Any] | None:
        cur = await self.conn.execute("SELECT * FROM homework WHERE id = ?", (hid,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def delete_homework(self, hid: int) -> bool:
        cur = await self.conn.execute("DELETE FROM homework WHERE id = ?", (hid,))
        await self.conn.commit()
        return cur.rowcount > 0

    async def add_material(
        self,
        title: str,
        body: str | None,
        file_id: str | None,
        file_kind: str | None,
        student_id: int | None,
    ) -> int:
        cur = await self.conn.execute(
            """
            INSERT INTO materials (title, body, file_id, file_kind, student_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, body, file_id, file_kind, student_id, _now(self.tz)),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def list_materials(
        self,
        student_id: int | None = None,
        *,
        shared_only: bool = False,
    ) -> list[dict[str, Any]]:
        if shared_only:
            cur = await self.conn.execute(
                "SELECT * FROM materials WHERE student_id IS NULL ORDER BY id DESC LIMIT 30"
            )
        elif student_id is None:
            cur = await self.conn.execute(
                "SELECT * FROM materials ORDER BY id DESC LIMIT 30"
            )
        else:
            cur = await self.conn.execute(
                """
                SELECT * FROM materials
                WHERE student_id IS NULL OR student_id = ?
                ORDER BY id DESC LIMIT 30
                """,
                (student_id,),
            )
        return [dict(r) for r in await cur.fetchall()]

    async def get_material(self, mid: int) -> dict[str, Any] | None:
        cur = await self.conn.execute("SELECT * FROM materials WHERE id = ?", (mid,))
        row = await cur.fetchone()
        return dict(row) if row else None

    async def delete_material(self, mid: int) -> bool:
        cur = await self.conn.execute("DELETE FROM materials WHERE id = ?", (mid,))
        await self.conn.commit()
        return cur.rowcount > 0

    async def add_lesson(self, student_id: int, starts_at: datetime, topic: str | None) -> int:
        cur = await self.conn.execute(
            """
            INSERT INTO lessons (student_id, starts_at, topic, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, starts_at.isoformat(), topic, _now(self.tz)),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def list_lessons(
        self,
        student_id: int | None = None,
        upcoming_only: bool = True,
    ) -> list[dict[str, Any]]:
        now = datetime.now(self.tz).isoformat()
        if student_id is None:
            if upcoming_only:
                cur = await self.conn.execute(
                    """
                    SELECT lessons.*, users.full_name AS student_name
                    FROM lessons JOIN users ON users.telegram_id = lessons.student_id
                    WHERE status = 'scheduled' AND starts_at >= ?
                    ORDER BY starts_at LIMIT 20
                    """,
                    (now,),
                )
            else:
                cur = await self.conn.execute(
                    """
                    SELECT lessons.*, users.full_name AS student_name
                    FROM lessons JOIN users ON users.telegram_id = lessons.student_id
                    ORDER BY starts_at DESC LIMIT 20
                    """
                )
        else:
            cur = await self.conn.execute(
                """
                SELECT lessons.*, users.full_name AS student_name
                FROM lessons JOIN users ON users.telegram_id = lessons.student_id
                WHERE lessons.student_id = ? AND status = 'scheduled' AND starts_at >= ?
                ORDER BY starts_at LIMIT 20
                """,
                (student_id, now),
            )
        return [dict(r) for r in await cur.fetchall()]

    async def get_lesson(self, lid: int) -> dict[str, Any] | None:
        cur = await self.conn.execute(
            """
            SELECT lessons.*, users.full_name AS student_name
            FROM lessons JOIN users ON users.telegram_id = lessons.student_id
            WHERE lessons.id = ?
            """,
            (lid,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None

    async def update_lesson_starts(self, lid: int, starts_at: datetime) -> bool:
        cur = await self.conn.execute(
            """
            UPDATE lessons
            SET starts_at = ?,
                notified_day = 0,
                notified_hour = 0,
                notified_start = 0
            WHERE id = ? AND status = 'scheduled'
            """,
            (starts_at.isoformat(), lid),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def cancel_lesson(self, lid: int) -> bool:
        cur = await self.conn.execute(
            "UPDATE lessons SET status = 'cancelled' WHERE id = ? AND status = 'scheduled'",
            (lid,),
        )
        await self.conn.commit()
        return cur.rowcount > 0

    async def due_reminders(self) -> list[dict[str, Any]]:
        cur = await self.conn.execute(
            """
            SELECT lessons.*, users.full_name AS student_name
            FROM lessons JOIN users ON users.telegram_id = lessons.student_id
            WHERE status = 'scheduled'
              AND (notified_day = 0 OR notified_hour = 0 OR notified_start = 0)
            """
        )
        return [dict(r) for r in await cur.fetchall()]

    async def mark_notified(self, lid: int, field: str) -> None:
        if field not in {"notified_day", "notified_hour", "notified_start"}:
            raise ValueError(field)
        await self.conn.execute(f"UPDATE lessons SET {field} = 1 WHERE id = ?", (lid,))
        await self.conn.commit()
