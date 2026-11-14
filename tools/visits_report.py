#!/usr/bin/env python3
"""Отчёт «когда заходят на сайт»: дни недели и часы.

Зачем: выбрать время отправки писем не по чужим исследованиям, а по своим данным.
Считаем первое событие каждой сессии (name='view') — это и есть факт захода.

Время в базе пишется локальным временем сервера (alwaysdata живёт в Europe/Paris).
Киев = Париж + 1 час круглый год (CET→EET зимой, CEST→EEST летом), поэтому
пересчёт делается постоянным сдвигом.

Запуск:
    python3 tools/visits_report.py [--db data/sto.db] [--src email] [--days 90]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import os
import sqlite3
import sys

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def load_visits(db_path: str, days: int, src: str | None, shift_hours: int = 0) -> list[tuple[dt.datetime, str]]:
    """Первое событие каждой сессии.

    Время в базе уже киевское (server.py выставляет TZ=Europe/Kyiv при старте).
    Параметр shift_hours нужен только для старых записей, сделанных до этой правки:
    сервер писал их в CET, то есть на час раньше — для них shift_hours=1.
    """
    if not os.path.exists(db_path):
        raise SystemExit(f"нет файла базы: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    has_src = "src" in cols

    since = (dt.datetime.now() - dt.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    # Источник берём не только у первого события сессии: человек мог сначала зайти
    # на сайт напрямую, а потом открыть ссылку из письма — такая сессия должна
    # считаться пришедшей из письма.
    if has_src:
        src_pick = ("(SELECT e2.src FROM events e2 WHERE e2.session=e.session "
                    "AND COALESCE(e2.src,'')<>'' ORDER BY e2.created_at LIMIT 1)")
    else:
        src_pick = "''"
    rows = conn.execute(
        f"SELECT session, MIN(created_at) AS first_at, {src_pick} AS src "
        "FROM events e WHERE name='view' AND created_at >= ? "
        "GROUP BY session ORDER BY first_at",
        (since,),
    ).fetchall()
    conn.close()

    out: list[tuple[dt.datetime, str]] = []
    for r in rows:
        raw = r["first_at"]
        if not raw:
            continue
        try:
            stamp = dt.datetime.strptime(raw, "%Y-%m-%d %H:%M:%S") + dt.timedelta(hours=shift_hours)
        except ValueError:
            continue
        source = (r["src"] or "").strip()
        if src and source != src:
            continue
        out.append((stamp, source))
    return out


def render(visits: list[tuple[dt.datetime, str]], src_filter: str | None) -> str:
    if not visits:
        return ("Данных пока нет: ни одного захода за выбранный период.\n"
                "Счётчик пишет события с момента установки, статистика накопится по мере заходов.")

    by_day: collections.Counter[int] = collections.Counter()
    by_hour: collections.Counter[int] = collections.Counter()
    by_slot: collections.Counter[tuple[int, int]] = collections.Counter()
    by_src: collections.Counter[str] = collections.Counter()

    for stamp, source in visits:
        wd, hour = stamp.weekday(), stamp.hour
        by_day[wd] += 1
        by_hour[hour] += 1
        by_slot[(wd, hour)] += 1
        by_src[source or "(прямой заход)"] += 1

    total = len(visits)
    lines: list[str] = []
    title = "Заходы на сайт по дням и часам (киевское время)"
    if src_filter:
        title += f", источник: {src_filter}"
    lines.append(title)
    lines.append(f"Всего заходов (уникальных сессий): {total}")
    span_from = min(v[0] for v in visits).strftime("%d.%m.%Y %H:%M")
    span_to = max(v[0] for v in visits).strftime("%d.%m.%Y %H:%M")
    lines.append(f"Период: {span_from} — {span_to}\n")

    lines.append("По дням недели:")
    lines.append("  день   заходов   доля")
    for wd in sorted(by_day, key=lambda d: -by_day[d]):
        share = by_day[wd] / total * 100
        bar = "█" * max(1, round(share / 3))
        lines.append(f"  {WEEKDAYS[wd]:<5} {by_day[wd]:>6}   {share:5.1f}%  {bar}")

    lines.append("\nПо часам:")
    hours = sorted(by_hour)
    for h in range(min(hours), max(hours) + 1):
        cnt = by_hour.get(h, 0)
        bar = "█" * round(cnt / max(1, max(by_hour.values())) * 24)
        lines.append(f"  {h:02d}:00  {cnt:>4}  {bar}")

    lines.append("\nТоп-7 окон (день + час):")
    for (wd, h), cnt in by_slot.most_common(7):
        share = cnt / total * 100
        lines.append(f"  {WEEKDAYS[wd]} {h:02d}:00–{h:02d}:59 — {cnt} ({share:.0f}%)")

    if len(by_src) > 1 or src_filter is None:
        lines.append("\nИсточники заходов:")
        for name, cnt in by_src.most_common(8):
            lines.append(f"  {name:<24} {cnt}")

    lines.append("\nКак читать: если заходов меньше 50, порядок дней и часов случайный —")
    lines.append("делать выводы рано, нужно накопить хотя бы 2–3 недели рассылки.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Когда заходят на сайт: дни и часы")
    ap.add_argument("--db", default="data/sto.db", help="путь к базе (по умолчанию data/sto.db)")
    ap.add_argument("--src", default=None, help="только заходы с этим utm_source (например, email)")
    ap.add_argument("--days", type=int, default=90, help="за сколько последних дней считать")
    ap.add_argument("--shift-hours", type=int, default=0,
                    help="сдвиг для старых записей (1 — данные, сделанные до перехода на киевский пояс)")
    args = ap.parse_args()

    visits = load_visits(args.db, args.days, args.src, args.shift_hours)
    print(render(visits, args.src))
    return 0


if __name__ == "__main__":
    sys.exit(main())
