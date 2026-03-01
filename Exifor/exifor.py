#!/usr/bin/env python3
"""
Exifor — Privacy-first metadata manager for iSH (iOS)
Wraps system ExifTool. No logs. No traces. No command-line args needed.
Just run: python3 exifor.py
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import subprocess
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
except ImportError:
    print("\n  Установи зависимости: pip3 install rich\n")
    sys.exit(1)

# ── Terminal ──────────────────────────────────────────────────────────────────
C = Console(highlight=False)

# ── Palette ───────────────────────────────────────────────────────────────────
A  = "cyan"             # accent
G  = "#00c87a"          # green / success
Y  = "yellow"           # label / warning
R  = "red"              # error / danger
D  = "bright_black"     # muted
W  = "white"            # body

MEDIA = {
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".heif",
    ".gif", ".bmp", ".webp", ".raw", ".cr2", ".cr3", ".nef",
    ".arw", ".dng", ".orf", ".rw2", ".pef",
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv",
    ".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".zip",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def clear():
    os.system("clear")

def rule(label: str = ""):
    if label:
        C.print(Rule(f"[{D}] {label} [/]", style=D))
    else:
        C.print(Rule(style=D))

def ok(msg):
    C.print(f"\n  [{G}]✓[/]  {msg}\n")

def err(msg):
    C.print(f"\n  [{R}]✗[/]  {msg}\n")

def warn(msg):
    C.print(f"\n  [{Y}]![/]  {msg}\n")

def pause():
    C.print(f"  [{D}]Нажми Enter...[/]", end="")
    input()

def ask(prompt: str, default: str = "") -> str:
    hint = f" [{D}][{default}][/]" if default else ""
    C.print(f"  [{A}]{prompt}[/]{hint}  ", end="")
    val = input().strip()
    return val if val else default

def yesno(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    C.print(f"  [{D}]{prompt} [{hint}][/]  ", end="")
    v = input().strip().lower()
    if not v:
        return default
    return v in ("y", "yes", "д", "да")

def spin(label: str) -> Progress:
    return Progress(SpinnerColumn(style=A), TextColumn(f"[{D}]{label}[/]"), transient=True)

def header(title: str = "", sub: str = ""):
    clear()
    t = Text()
    t.append("  Exifor", style=f"bold {A}")
    t.append("  —  ExifTool Manager", style=W)
    if title:
        t.append(f"  ·  {title}", style=f"{Y}")
    if sub:
        t.append(f"  ·  {sub}", style=D)
    C.print(t)
    rule()
    C.print()

def sz(path: str) -> str:
    try:
        b = os.path.getsize(path)
        for u in ("B", "KB", "MB", "GB"):
            if b < 1024:
                return f"{b:.0f} {u}"
            b /= 1024
        return f"{b:.1f} TB"
    except Exception:
        return "?"

# ── ExifTool wrapper ──────────────────────────────────────────────────────────
#
#  АРХИТЕКТУРА БЕЗОПАСНОСТИ:
#  ─────────────────────────
#  Этот класс является тонкой обёрткой над системным бинарником `exiftool`.
#  Python-код в этом файле НИКОГДА не читает и не пишет метаданные самостоятельно.
#
#  Распределение ответственности:
#    ExifTool (системный бинарник) → ВСЕ операции с метаданными:
#      чтение, запись, удаление, копирование тегов
#    Python (этот файл) → ТОЛЬКО:
#      • интерфейс (меню, ввод пользователя, цвета)
#      • передача команд в ExifTool через subprocess
#      • парсинг JSON-ответа от ExifTool (не бинарных файлов!)
#      • ZIP-контейнер: распаковка/упаковка (не метаданные внутри файлов)
#      • запись экспортных файлов (JSON/CSV) из готового ответа ExifTool
#
#  В коде нет:
#    ✗ open(file, "rb")     — прямого чтения бинарных файлов
#    ✗ struct.unpack()      — разбора бинарных форматов
#    ✗ bytearray / bytes()  — работы с байтами медиафайлов
#    ✗ PIL / exif-py / piexif — сторонних парсеров метаданных
#
class ET:
    def __init__(self):
        self.bin = shutil.which("exiftool")
        if not self.bin:
            err("ExifTool не найден.\n\n  В iSH выполни:  [bold]apk add exiftool[/]")
            sys.exit(1)

    def _run(self, args: list) -> str:
        """Единственная точка запуска системного ExifTool. Всё идёт через сюда."""
        try:
            r = subprocess.run(
                [self.bin] + args,       # self.bin = путь к системному exiftool
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if r.returncode not in (0, 1):
                raise RuntimeError(r.stderr.strip() or "Ошибка ExifTool")
            return r.stdout
        except FileNotFoundError:
            raise RuntimeError("ExifTool не найден")

    def version(self) -> str:
        return self._run(["-ver"]).strip()

    def read(self, path: str) -> dict:
        out = self._run(["-json", "-a", "-u", "-g", "--", path])
        d = json.loads(out)
        return d[0] if d else {}

    def read_flat(self, path: str) -> dict:
        out = self._run(["-json", "--", path])
        d = json.loads(out)
        return d[0] if d else {}

    def read_tags(self, path: str, tags: list) -> dict:
        out = self._run(["-json"] + [f"-{t}" for t in tags] + ["--", path])
        d = json.loads(out)
        return d[0] if d else {}

    def write(self, path: str, tags: dict, backup: bool = False) -> str:
        args = [f"-{k}={v}" for k, v in tags.items()]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["--", path])

    def strip_all(self, path: str, backup: bool = False) -> str:
        args = ["-all="]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["--", path])

    def strip_gps(self, path: str, backup: bool = False) -> str:
        args = ["-gps:all="]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["--", path])

    def strip_tag(self, path: str, tag: str, backup: bool = False) -> str:
        args = [f"-{tag}="]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["--", path])

    def read_gps(self, path: str) -> dict:
        return self.read_tags(path, [
            "GPSLatitude", "GPSLongitude", "GPSAltitude",
            "GPSLatitudeRef", "GPSLongitudeRef", "GPSAltitudeRef",
            "GPSSpeed", "GPSDateStamp", "GPSTimeStamp",
        ])

    def write_gps(self, path: str, lat: float, lon: float, alt: Optional[float] = None, backup: bool = False):
        tags = {
            "GPSLatitude": str(abs(lat)),
            "GPSLatitudeRef": "N" if lat >= 0 else "S",
            "GPSLongitude": str(abs(lon)),
            "GPSLongitudeRef": "E" if lon >= 0 else "W",
        }
        if alt is not None:
            tags["GPSAltitude"] = str(abs(alt))
            tags["GPSAltitudeRef"] = "0" if alt >= 0 else "1"
        self.write(path, tags, backup)

    def strip_dir(self, directory: str, exts: Optional[list], backup: bool = False) -> str:
        args = ["-all="]
        if exts:
            for e in exts:
                args += ["-ext", e]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["-r", "--", directory])

    def strip_gps_dir(self, directory: str, exts: Optional[list], backup: bool = False) -> str:
        args = ["-gps:all="]
        if exts:
            for e in exts:
                args += ["-ext", e]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["-r", "--", directory])

    def write_dir(self, directory: str, tags: dict, exts: Optional[list], backup: bool = False) -> str:
        args = [f"-{k}={v}" for k, v in tags.items()]
        if exts:
            for e in exts:
                args += ["-ext", e]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["-r", "--", directory])

    def copy_from(self, src: str, dst: str, backup: bool = False):
        args = ["-TagsFromFile", src]
        if not backup:
            args.append("-overwrite_original")
        self._run(args + ["--", dst])

    def export_json(self, path: str, out: str):
        data = self.read(path)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def export_csv(self, path: str, out: str):
        import csv
        data = self.read(path)
        rows = []
        for grp, vals in data.items():
            if isinstance(vals, dict):
                for k, v in vals.items():
                    rows.append({"Группа": grp, "Тег": k, "Значение": str(v)})
            else:
                rows.append({"Группа": "", "Тег": grp, "Значение": str(vals)})
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Группа", "Тег", "Значение"])
            w.writeheader()
            w.writerows(rows)

    def strip_zip(self, zip_in: str, zip_out: str) -> int:
        """Extract ZIP, strip all metadata from every file, repack as clean ZIP.
        Returns count of processed files."""
        tmpdir = tempfile.mkdtemp(prefix="exifor_")
        try:
            with zipfile.ZipFile(zip_in, "r") as zf:
                zf.extractall(tmpdir)

            self._run(["-all=", "-overwrite_original", "-r", "--", tmpdir])

            count = 0
            with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf_out:
                for root, _, files in os.walk(tmpdir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, tmpdir)
                        zf_out.write(fpath, arcname)
                        count += 1
            return count
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def list_zip_metadata(self, zip_in: str) -> list:
        """Check which files in ZIP have metadata."""
        tmpdir = tempfile.mkdtemp(prefix="exifor_")
        try:
            with zipfile.ZipFile(zip_in, "r") as zf:
                zf.extractall(tmpdir)
            out = self._run(["-json", "-a", "-u", "-r", "--", tmpdir])
            if not out.strip():
                return []
            items = json.loads(out)
            results = []
            for item in items:
                src = item.get("SourceFile", "")
                tag_count = sum(
                    len(v) if isinstance(v, dict) else 1
                    for k, v in item.items()
                    if k not in ("SourceFile", "ExifToolVersion", "File")
                )
                rel = os.path.relpath(src, tmpdir)
                results.append({"file": rel, "tags": tag_count})
            return results
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── File browser ──────────────────────────────────────────────────────────────

def browse(want_dir: bool = False, title: str = "Выбери файл") -> Optional[str]:
    """
    Interactive file/folder browser.
    Returns selected file path (or dir path if want_dir=True), or None if cancelled.
    """
    cwd = os.getcwd()

    while True:
        header(title, cwd)

        try:
            entries_raw = sorted(os.scandir(cwd), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            err("Нет доступа к этой папке")
            cwd = os.path.dirname(cwd)
            continue

        dirs  = [e for e in entries_raw if e.is_dir() and not e.name.startswith(".")]
        files = [e for e in entries_raw if e.is_file()]
        media = [e for e in files if os.path.splitext(e.name)[1].lower() in MEDIA]
        other = [e for e in files if e not in media]

        rows = []  # (display_text, kind, path)

        # Up
        rows.append((f"[{D}]../  вверх[/]", "up", os.path.dirname(cwd)))

        # Dirs
        for d in dirs:
            rows.append((f"[{A}]{d.name}/[/]", "dir", d.path))

        # Media files (highlighted)
        for f in media:
            ext = os.path.splitext(f.name)[1].lower()
            color = Y if ext == ".zip" else G
            rows.append((f"[{color}]{f.name}[/]  [{D}]{sz(f.path)}[/]", "file", f.path))

        # Other files
        for f in other:
            rows.append((f"[{D}]{f.name}  {sz(f.path)}[/]", "file", f.path))

        # Print numbered list
        for i, (label, kind, path) in enumerate(rows):
            prefix = f"[{D}]{i:2}[/]"
            C.print(f"  {prefix}  {label}")

        C.print()
        if want_dir:
            C.print(f"  [{G}]S[/]   Выбрать текущую папку")
        C.print(f"  [{D}]p[/]   Ввести путь вручную")
        C.print(f"  [{D}]q[/]   Отмена")
        rule()

        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip().lower()

        if raw == "q":
            return None

        if raw == "s" and want_dir:
            return cwd

        if raw == "p":
            C.print(f"  [{A}]Путь[/]  ", end="")
            path = os.path.expanduser(input().strip())
            if want_dir and os.path.isdir(path):
                return path
            if not want_dir and os.path.isfile(path):
                return path
            err("Путь не найден")
            pause()
            continue

        try:
            idx = int(raw)
            if idx < 0 or idx >= len(rows):
                raise ValueError
            label, kind, path = rows[idx]
            if kind == "up":
                cwd = path
            elif kind == "dir":
                cwd = path
            elif kind == "file":
                if want_dir:
                    err("Это файл, а не папка")
                    pause()
                else:
                    return path
        except (ValueError, IndexError):
            err("Введи номер из списка")
            pause()


# ── Action: View metadata ─────────────────────────────────────────────────────

def act_view(et: ET):
    path = browse(title="Просмотр метаданных  —  выбери файл")
    if not path:
        return

    header("Метаданные", os.path.basename(path))
    with spin("Читаю теги...") as p:
        p.add_task("", total=None)
        try:
            data = et.read(path)
        except Exception as e:
            err(str(e)); pause(); return

    if not data:
        warn("Метаданные не найдены"); pause(); return

    found = False
    for group, vals in data.items():
        if group in ("SourceFile", "ExifToolVersion"):
            continue
        if isinstance(vals, dict) and vals:
            found = True
            t = Table(show_header=False, box=box.SIMPLE, padding=(0, 1), expand=True)
            t.add_column("Тег",      style=f"bold {W}", min_width=26)
            t.add_column("Значение", style=W, overflow="fold")
            for k, v in vals.items():
                s = str(v)
                t.add_row(k, s[:160] + "…" if len(s) > 160 else s)
            C.print(Panel(t, title=f"[bold {Y}]{group}[/]", border_style=D, padding=(0, 1)))

    if not found:
        warn("Теги не найдены")
    pause()


# ── Action: Strip metadata (privacy) ─────────────────────────────────────────

STRIP_PRESETS = [
    ("Удалить ВСЕ метаданные",       "all"),
    ("Удалить только GPS",           "gps"),
    ("Удалить один тег",             "one"),
]

def act_strip(et: ET):
    path = browse(title="Очистка метаданных  —  выбери файл")
    if not path:
        return

    header("Очистка метаданных", os.path.basename(path))
    C.print(f"  [{D}]1[/]  [{R}]Удалить ВСЕ метаданные[/]  [{D}](максимальная приватность)[/]")
    C.print(f"  [{D}]2[/]  Удалить только GPS данные")
    C.print(f"  [{D}]3[/]  Удалить один конкретный тег")
    C.print(f"  [{D}]0[/]  Отмена")
    rule()
    C.print(f"  [{A}]→[/]  ", end="")
    raw = input().strip()

    if raw == "0":
        return

    backup = yesno("Оставить резервную копию оригинала?", default=False)

    try:
        if raw == "1":
            if not yesno(f"[{R}]Точно удалить ВСЕ теги? Это необратимо.[/]", default=False):
                warn("Отменено"); return
            with spin("Удаляю все метаданные...") as p:
                p.add_task("", total=None)
                et.strip_all(path, backup)
            ok("Все метаданные удалены")

        elif raw == "2":
            with spin("Удаляю GPS...") as p:
                p.add_task("", total=None)
                et.strip_gps(path, backup)
            ok("GPS данные удалены")

        elif raw == "3":
            tag = ask("Имя тега для удаления  (например: Comment, Artist)")
            if not tag:
                warn("Тег не указан"); return
            with spin(f"Удаляю {tag}...") as p:
                p.add_task("", total=None)
                et.strip_tag(path, tag, backup)
            ok(f"Тег [{tag}] удалён")
        else:
            err("Неверный выбор")
            return
    except Exception as e:
        err(str(e))
    pause()


# ── Action: GPS ───────────────────────────────────────────────────────────────

def act_gps(et: ET):
    path = browse(title="GPS  —  выбери файл")
    if not path:
        return

    while True:
        header("GPS", os.path.basename(path))
        C.print(f"  [{D}]1[/]  Посмотреть координаты")
        C.print(f"  [{D}]2[/]  Задать координаты вручную")
        C.print(f"  [{D}]3[/]  Удалить GPS данные")
        C.print(f"  [{D}]0[/]  Назад")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip()

        if raw == "0":
            return

        if raw == "1":
            with spin("Читаю GPS...") as p:
                p.add_task("", total=None)
                try:
                    gps = et.read_gps(path)
                except Exception as e:
                    err(str(e)); pause(); continue

            header("GPS данные", os.path.basename(path))
            lat     = gps.get("GPSLatitude",    "—")
            lon     = gps.get("GPSLongitude",   "—")
            lat_ref = gps.get("GPSLatitudeRef", "")
            lon_ref = gps.get("GPSLongitudeRef","")
            alt     = gps.get("GPSAltitude",    "—")
            speed   = gps.get("GPSSpeed",       "—")
            gdate   = gps.get("GPSDateStamp",   "—")
            gtime   = gps.get("GPSTimeStamp",   "—")

            if lat == "—" and lon == "—":
                warn("GPS данных нет в этом файле")
            else:
                t = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
                t.add_column("", style=D, min_width=16)
                t.add_column("", style=W)
                t.add_row("Широта",    f"{lat} {lat_ref}")
                t.add_row("Долгота",   f"{lon} {lon_ref}")
                t.add_row("Высота",    str(alt))
                t.add_row("Скорость",  str(speed))
                t.add_row("Дата GPS",  str(gdate))
                t.add_row("Время GPS", str(gtime))
                C.print(Panel(t, border_style=D, padding=(1, 2)))
                try:
                    lat_f = float(str(lat).split()[0]) * (-1 if lat_ref == "S" else 1)
                    lon_f = float(str(lon).split()[0]) * (-1 if lon_ref == "W" else 1)
                    C.print(f"\n  [{D}]Google Maps[/]  [{A}]https://maps.google.com/?q={lat_f},{lon_f}[/]")
                except Exception:
                    pass
            pause()

        elif raw == "2":
            C.print(f"\n  [{D}]Десятичные градусы. + Север/Восток, − Юг/Запад[/]")
            C.print(f"  [{D}]Пример: Москва = 55.7558, 37.6173[/]\n")
            try:
                lat_f = float(ask("Широта   (−90 до 90)"))
                lon_f = float(ask("Долгота  (−180 до 180)"))
                if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
                    err("Координаты вне диапазона"); pause(); continue
                alt_s = ask("Высота в метрах  (Enter — пропустить)", "")
                alt_f = float(alt_s) if alt_s else None
                backup = yesno("Оставить резервную копию?", default=False)
                with spin("Записываю...") as p:
                    p.add_task("", total=None)
                    et.write_gps(path, lat_f, lon_f, alt_f, backup)
                ok(f"GPS записан: {lat_f}, {lon_f}" + (f"  высота {alt_f} м" if alt_f is not None else ""))
            except ValueError:
                err("Неверный формат числа")
            pause()

        elif raw == "3":
            backup = yesno("Оставить резервную копию?", default=False)
            try:
                with spin("Удаляю GPS...") as p:
                    p.add_task("", total=None)
                    et.strip_gps(path, backup)
                ok("GPS данные удалены")
            except Exception as e:
                err(str(e))
            pause()


# ── Action: Edit tags ─────────────────────────────────────────────────────────

POPULAR_TAGS = [
    ("Artist",           "Автор / Художник"),
    ("Copyright",        "Авторские права"),
    ("Description",      "Описание"),
    ("Comment",          "Комментарий"),
    ("Title",            "Заголовок"),
    ("Subject",          "Тема"),
    ("Keywords",         "Ключевые слова"),
    ("Make",             "Производитель камеры"),
    ("Model",            "Модель камеры"),
    ("Software",         "ПО / Приложение"),
    ("Creator",          "Создатель"),
    ("DateTimeOriginal", "Дата оригинала"),
    ("CreateDate",       "Дата создания"),
    ("Rating",           "Рейтинг  (0–5)"),
]

def act_edit(et: ET):
    path = browse(title="Редактирование  —  выбери файл")
    if not path:
        return

    while True:
        header("Редактировать теги", os.path.basename(path))
        try:
            cur = et.read_flat(path)
        except Exception:
            cur = {}

        t = Table(
            show_header=True,
            header_style=f"bold {A}",
            box=box.SIMPLE_HEAD,
            padding=(0, 2),
            expand=True,
        )
        t.add_column("#",       style=f"bold {D}", width=4)
        t.add_column("Тег",    style=f"bold {W}", min_width=20)
        t.add_column("Описание", style=D, min_width=20)
        t.add_column("Сейчас", style=Y, overflow="fold")

        for i, (tag, desc) in enumerate(POPULAR_TAGS, 1):
            v = str(cur.get(tag, ""))
            v_show = v[:55] + "…" if len(v) > 55 else v
            t.add_row(str(i), tag, desc, v_show or f"[{D}]—[/]")

        C.print(Panel(t, border_style=D, padding=(0, 1)))
        C.print(f"  [{D}]c[/]  Ввести произвольный тег")
        C.print(f"  [{D}]m[/]  Изменить несколько тегов за раз")
        C.print(f"  [{D}]0[/]  Назад")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip().lower()

        if raw == "0":
            return

        if raw == "c":
            tag = ask("Тег (например: XMP:Description, IPTC:Keywords)").strip()
            if not tag:
                continue
        elif raw == "m":
            _edit_multi(et, path)
            continue
        else:
            try:
                idx = int(raw) - 1
                if not (0 <= idx < len(POPULAR_TAGS)):
                    raise ValueError
                tag = POPULAR_TAGS[idx][0]
            except ValueError:
                err("Неверный выбор"); pause(); continue

        old = str(cur.get(tag, ""))
        if old:
            C.print(f"\n  [{D}]Текущее значение:[/] [{Y}]{old}[/]")
        val = ask(f"Новое значение для  [{tag}]")
        if not val:
            warn("Пустое значение — пропущено"); continue
        backup = yesno("Оставить резервную копию?", default=False)
        try:
            with spin("Записываю...") as p:
                p.add_task("", total=None)
                et.write(path, {tag: val}, backup)
            ok(f"{tag} = {val}")
        except Exception as e:
            err(str(e))
        pause()


def _edit_multi(et: ET, path: str):
    tags = {}
    header("Несколько тегов", os.path.basename(path))
    C.print(f"  [{D}]Вводи теги. Оставь тег пустым, чтобы завершить.[/]\n")
    while True:
        tag = ask("Тег  (Enter — завершить)").strip()
        if not tag:
            break
        val = ask(f"Значение для [{tag}]")
        tags[tag] = val
        C.print(f"  [{G}]+[/]  {tag} = [{Y}]{val}[/]")
    if not tags:
        warn("Нет тегов — отменено")
        pause()
        return
    backup = yesno("Оставить резервную копию?", default=False)
    try:
        with spin("Записываю...") as p:
            p.add_task("", total=None)
            et.write(path, tags, backup)
        ok(f"Записано тегов: {len(tags)}")
    except Exception as e:
        err(str(e))
    pause()


# ── Action: ZIP cleaner ───────────────────────────────────────────────────────

def act_zip(et: ET):
    header("ZIP Cleaner", "Очистка метаданных внутри ZIP архива")
    C.print(f"  [{Y}]Как это работает:[/]")
    C.print(f"  [{D}]  1. Ты выбираешь ZIP файл[/]")
    C.print(f"  [{D}]  2. Инструмент извлекает все файлы во временную папку[/]")
    C.print(f"  [{D}]  3. ExifTool удаляет метаданные у каждого файла[/]")
    C.print(f"  [{D}]  4. Все файлы упаковываются обратно в новый чистый ZIP[/]")
    C.print(f"  [{D}]  5. Временная папка удаляется без следа[/]")
    C.print()
    C.print(f"  [{D}]1[/]  Очистить ZIP  (удалить ВСЕ метаданные)")
    C.print(f"  [{D}]2[/]  Проверить ZIP  (посмотреть что внутри)")
    C.print(f"  [{D}]0[/]  Назад")
    rule()
    C.print(f"  [{A}]→[/]  ", end="")
    raw = input().strip()

    if raw == "0":
        return

    path = browse(title="ZIP Cleaner  —  выбери ZIP файл")
    if not path:
        return

    if not path.lower().endswith(".zip"):
        err("Выбранный файл не является ZIP архивом")
        pause()
        return

    if raw == "2":
        header("ZIP: проверка метаданных", os.path.basename(path))
        with spin("Анализирую содержимое ZIP...") as p:
            p.add_task("", total=None)
            try:
                results = et.list_zip_metadata(path)
            except Exception as e:
                err(str(e)); pause(); return

        if not results:
            ok("Метаданных не найдено — архив чистый")
        else:
            t = Table(show_header=True, header_style=f"bold {A}", box=box.SIMPLE_HEAD, padding=(0, 2))
            t.add_column("Файл",          style=W, overflow="fold")
            t.add_column("Тегов найдено", style=Y, justify="right")
            total_tags = 0
            dirty = 0
            for item in results:
                count = item["tags"]
                total_tags += count
                if count > 0:
                    dirty += 1
                color = R if count > 0 else G
                t.add_row(item["file"], f"[{color}]{count}[/]")
            C.print(Panel(t, border_style=D, padding=(0, 1)))
            if dirty:
                C.print(f"\n  [{R}]{dirty} файлов содержат метаданные[/]  [{D}](всего {total_tags} тегов)[/]")
            else:
                ok("Все файлы чистые")
        pause()
        return

    if raw == "1":
        header("ZIP Cleaner", os.path.basename(path))

        # Count files in ZIP
        try:
            with zipfile.ZipFile(path, "r") as zf:
                file_list = [n for n in zf.namelist() if not n.endswith("/")]
                file_count = len(file_list)
        except Exception as e:
            err(f"Не удалось открыть ZIP: {e}"); pause(); return

        C.print(f"  [{D}]Архив:[/]   {os.path.basename(path)}")
        C.print(f"  [{D}]Файлов:[/]  {file_count}")
        C.print(f"  [{D}]Размер:[/]  {sz(path)}")

        base = os.path.splitext(path)[0]
        out_default = base + "_clean.zip"
        C.print()
        out_path = ask("Куда сохранить чистый ZIP", out_default)
        out_path = os.path.expanduser(out_path)

        if os.path.exists(out_path):
            if not yesno(f"[{Y}]Файл {os.path.basename(out_path)} уже есть. Перезаписать?[/]", default=False):
                warn("Отменено"); return

        C.print()
        with spin("Очищаю метаданные и пакую...") as p:
            p.add_task("", total=None)
            try:
                processed = et.strip_zip(path, out_path)
            except Exception as e:
                err(str(e)); pause(); return

        clean_sz = sz(out_path)
        ok(f"Готово!  {processed} файлов обработано  →  [{A}]{out_path}[/]  [{D}]{clean_sz}[/]")
        C.print(f"  [{D}]Оригинальный ZIP не изменён.[/]")
        pause()


# ── Action: Folder batch ──────────────────────────────────────────────────────

def act_folder(et: ET):
    header("Папка целиком", "Пакетная обработка всех файлов")
    C.print(f"  [{D}]1[/]  [{R}]Удалить ВСЕ метаданные[/] в папке")
    C.print(f"  [{D}]2[/]  Удалить GPS у всех файлов")
    C.print(f"  [{D}]3[/]  Записать одинаковые теги всем файлам")
    C.print(f"  [{D}]0[/]  Назад")
    rule()
    C.print(f"  [{A}]→[/]  ", end="")
    raw = input().strip()

    if raw == "0":
        return

    folder = browse(want_dir=True, title="Выбери папку")
    if not folder:
        return

    ext_s = ask("Расширения через запятую  (например: jpg,png  или Enter — все файлы)", "")
    exts  = [e.strip().lower() for e in ext_s.split(",")] if ext_s.strip() else None
    backup = yesno("Оставить резервные копии?", default=False)

    try:
        if raw == "1":
            if not yesno(f"[{R}]Удалить ВСЕ метаданные у ВСЕХ файлов в папке?[/]", default=False):
                warn("Отменено"); return
            with spin("Обрабатываю...") as p:
                p.add_task("", total=None)
                out = et.strip_dir(folder, exts, backup)
            ok(out.strip() or "Метаданные удалены")

        elif raw == "2":
            with spin("Удаляю GPS...") as p:
                p.add_task("", total=None)
                out = et.strip_gps_dir(folder, exts, backup)
            ok(out.strip() or "GPS удалён у всех файлов")

        elif raw == "3":
            tags = {}
            C.print(f"\n  [{D}]Вводи теги. Пустой тег — завершить.[/]\n")
            while True:
                tag = ask("Тег  (Enter — готово)").strip()
                if not tag:
                    break
                val = ask(f"Значение для [{tag}]")
                tags[tag] = val
                C.print(f"  [{G}]+[/]  {tag} = [{Y}]{val}[/]")
            if not tags:
                warn("Нет тегов — отменено"); return
            if not yesno(f"Записать {len(tags)} тегов всем файлам?", default=False):
                warn("Отменено"); return
            with spin("Записываю...") as p:
                p.add_task("", total=None)
                out = et.write_dir(folder, tags, exts, backup)
            ok(out.strip() or f"Записано {len(tags)} тегов")

        else:
            err("Неверный выбор")
            return

    except Exception as e:
        err(str(e))
    pause()


# ── Action: Export ────────────────────────────────────────────────────────────

def act_export(et: ET):
    path = browse(title="Экспорт метаданных  —  выбери файл")
    if not path:
        return

    header("Экспорт метаданных", os.path.basename(path))
    C.print(f"  [{D}]1[/]  Сохранить в JSON")
    C.print(f"  [{D}]2[/]  Сохранить в CSV")
    C.print(f"  [{D}]0[/]  Отмена")
    rule()
    C.print(f"  [{A}]→[/]  ", end="")
    raw = input().strip()

    if raw == "0":
        return

    base = os.path.splitext(os.path.abspath(path))[0]

    if raw == "1":
        out = ask("Сохранить как", base + "_metadata.json")
    elif raw == "2":
        out = ask("Сохранить как", base + "_metadata.csv")
    else:
        err("Неверный выбор"); return

    out = os.path.expanduser(out)
    with spin("Экспортирую...") as p:
        p.add_task("", total=None)
        try:
            if raw == "1":
                et.export_json(path, out)
            else:
                et.export_csv(path, out)
            ok(f"Сохранено: {out}")
        except Exception as e:
            err(str(e))
    pause()


# ── Action: Copy tags ─────────────────────────────────────────────────────────

def act_copy(et: ET):
    header("Копировать теги", "Перенос метаданных между файлами")
    C.print(f"  [{D}]Шаг 1/2  —  Выбери источник (откуда брать теги):[/]\n")
    src = browse(title="Источник тегов")
    if not src:
        return

    C.print(f"  [{D}]Шаг 2/2  —  Выбери цель (куда скопировать теги):[/]\n")
    dst = browse(title="Куда скопировать теги")
    if not dst:
        return

    header("Копировать теги")
    C.print(f"  [{D}]Откуда:[/]  [{Y}]{os.path.basename(src)}[/]")
    C.print(f"  [{D}]Куда:  [/]  [{Y}]{os.path.basename(dst)}[/]\n")

    if not yesno("Скопировать метаданные?"):
        warn("Отменено"); return

    backup = yesno("Оставить резервную копию целевого файла?", default=False)
    with spin("Копирую...") as p:
        p.add_task("", total=None)
        try:
            et.copy_from(src, dst, backup)
            ok("Метаданные скопированы")
        except Exception as e:
            err(str(e))
    pause()


# ── Main menu ─────────────────────────────────────────────────────────────────

MENU = [
    ("1", "Просмотр метаданных",              act_view,   W),
    ("2", "Очистить метаданные  (приватность)", act_strip,  R),
    ("3", "ZIP Cleaner  —  очистить архив",    act_zip,    Y),
    ("4", "GPS  —  посмотреть / изменить",     act_gps,    A),
    ("5", "Редактировать теги",                act_edit,   W),
    ("6", "Папка целиком  (пакетно)",          act_folder, W),
    ("7", "Экспорт в JSON / CSV",              act_export, W),
    ("8", "Копировать теги между файлами",     act_copy,   W),
]

def main():
    et = ET()

    while True:
        header()
        try:
            ver = et.version()
        except Exception:
            ver = "?"
        C.print(f"  [{G}]●[/] ExifTool {ver}  [{D}]|[/]  [{D}]Без логов. Без следов.[/]\n")

        for key, label, _, color in MENU:
            C.print(f"  [{D}]{key}[/]  [{color}]{label}[/]")

        C.print()
        C.print(f"  [{D}]q[/]  [{D}]Выход[/]")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip().lower()

        if raw in ("q", "quit", "exit", "0"):
            clear()
            C.print(f"\n  [{D}]Пока![/]\n")
            sys.exit(0)

        matched = False
        for key, label, fn, _ in MENU:
            if raw == key:
                try:
                    fn(et)
                except KeyboardInterrupt:
                    C.print()
                    warn("Прервано")
                    pause()
                matched = True
                break

        if not matched and raw:
            err("Неверный выбор — введи номер из меню")
            pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        C.print(f"\n  [{D}]Пока![/]\n")
        sys.exit(0)
