# -*- coding: utf-8 -*-
"""
Эксплуатация: резервные копии базы и журнал действий администратора.
Зависимостей нет — только stdlib, чтобы работало на любом хостинге.
"""

import os
import glob
import sqlite3
import datetime

BACKUP_KEEP = 7          # сколько копий держим
BACKUP_PREFIX = "sto-"


def backup_db(db_path, backups_dir, keep=BACKUP_KEEP):
    """Копия базы через штатный механизм SQLite (безопасно при работающем сервере)."""
    os.makedirs(backups_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(backups_dir, f"{BACKUP_PREFIX}{stamp}.db")
    src = sqlite3.connect(db_path, timeout=10)
    dst = sqlite3.connect(dest)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    prune(backups_dir, keep)
    return dest


def prune(backups_dir, keep=BACKUP_KEEP):
    """Оставляем последние keep копий, остальные удаляем."""
    files = sorted(glob.glob(os.path.join(backups_dir, BACKUP_PREFIX + "*.db")))
    removed = []
    for old in files[:-keep] if len(files) > keep else []:
        try:
            os.remove(old)
            removed.append(old)
        except OSError:
            pass
    return removed


def last_backup(backups_dir):
    files = sorted(glob.glob(os.path.join(backups_dir, BACKUP_PREFIX + "*.db")))
    if not files:
        return None
    newest = files[-1]
    st = os.stat(newest)
    return {"path": newest, "name": os.path.basename(newest),
            "size": st.st_size, "age_hours": round((datetime.datetime.now().timestamp() - st.st_mtime) / 3600, 1)}


def backup_is_stale(backups_dir, hours=20):
    info = last_backup(backups_dir)
    return info is None or info["age_hours"] > hours


# ------------------------------------------------------------------ журнал

AUDIT_DDL = """CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT DEFAULT (datetime('now','localtime')),
    actor TEXT DEFAULT '',
    action TEXT NOT NULL,
    target TEXT DEFAULT '',
    detail TEXT DEFAULT '')"""


def ensure_audit(conn):
    conn.execute(AUDIT_DDL)
    conn.commit()


def audit(conn, action, target="", detail="", actor="admin"):
    """Пишем действие в журнал. Ошибка записи не должна ломать само действие."""
    try:
        ensure_audit(conn)
        conn.execute("INSERT INTO audit (actor, action, target, detail) VALUES (?,?,?,?)",
                     (actor[:40], action[:60], str(target)[:60], str(detail)[:300]))
        conn.commit()
    except Exception:
        pass


def audit_tail(conn, limit=40):
    try:
        ensure_audit(conn)
        rows = conn.execute(
            "SELECT id, at, actor, action, target, detail FROM audit ORDER BY id DESC LIMIT ?",
            (max(1, min(200, limit)),)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
