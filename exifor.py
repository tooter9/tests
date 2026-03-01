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
    from rich.markup import escape
    from rich import box
except ImportError:
    print("\n  Missing dependency — install with:  pip3 install rich\n")
    sys.exit(1)

C = Console(highlight=False)

EXIFOR_VERSION = "1.3.0"

A = "cyan"
G = "#00c87a"
Y = "yellow"
R = "red"
D = "bright_black"
W = "white"

MEDIA = {
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".heif",
    ".gif", ".bmp", ".webp", ".raw", ".cr2", ".cr3", ".nef",
    ".arw", ".dng", ".orf", ".rw2", ".pef",
    ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv",
    ".mp3", ".flac", ".m4a", ".wav", ".aac", ".ogg",
    ".pdf", ".docx", ".xlsx", ".pptx",
    ".zip",
}


def clear():
    os.system("clear")


def rule(label: str = ""):
    if label:
        C.print(Rule(f"[{D}] {label} [/]", style=D))
    else:
        C.print(Rule(style=D))


def ok(msg):
    C.print(f"\n  [{G}]✓[/]  {escape(msg)}\n")


def err(msg):
    C.print(f"\n  [{R}]✗[/]  {escape(msg)}\n")


def warn(msg):
    C.print(f"\n  [{Y}]![/]  {escape(msg)}\n")


def pause():
    C.print(f"  [{D}]Press Enter to continue...[/]", end="")
    input()


def ask(prompt: str, default: str = "") -> str:
    hint = f" [{D}]{escape(default)}[/]" if default else ""
    C.print(f"  [{A}]{escape(prompt)}[/]{hint}  ", end="")
    val = input().strip()
    return val if val else default


def yesno(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    text = Text()
    text.append("  ")
    text.append(f"{prompt}  [{hint}]  ", style=D)
    C.print(text, end="")
    v = input().strip().lower()
    if not v:
        return default
    return v in ("y", "yes")


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


def show_result(
    success: bool,
    action: str,
    input_path: str,
    output_path: Optional[str] = None,
    backup_path: Optional[str] = None,
    extra_msg: str = "",
):
    color = G if success else R
    status_icon = "✓" if success else "✗"
    status_text = "Success" if success else "Failed"

    t = Table(show_header=False, box=box.SIMPLE, padding=(0, 2), expand=True)
    t.add_column("", style=f"bold {D}", min_width=12)
    t.add_column("", style=W, overflow="fold")

    t.add_row("Action", escape(action))
    t.add_row("Status", f"[bold {color}]{status_icon}  {status_text}[/]")
    t.add_row("Input", escape(input_path))

    if output_path:
        if output_path == input_path:
            t.add_row("Output", f"[{G}]{escape(output_path)}[/]  [{D}](modified in-place)[/]")
        else:
            t.add_row("Output", f"[{G}]{escape(output_path)}[/]")

    if backup_path:
        if os.path.exists(backup_path):
            t.add_row("Backup", f"[{Y}]{escape(backup_path)}[/]")
        else:
            t.add_row("Backup", f"[{R}]backup not found[/]")

    if extra_msg:
        t.add_row("Details", escape(extra_msg))

    title_style = f"bold {G}" if success else f"bold {R}"
    C.print(Panel(t, title=f"[{title_style}]Result[/]", border_style=color, padding=(0, 1)))


class ET:
    def __init__(self):
        self.bin = shutil.which("exiftool")
        if not self.bin:
            err(
                "ExifTool not found.\n\n"
                "  Install it first:\n"
                "    iSH / Alpine:  apk add exiftool\n"
                "    macOS:         brew install exiftool\n"
                "    Debian/Ubuntu: apt install libimage-exiftool-perl"
            )
            sys.exit(1)

    def _run(self, args: list) -> str:
        try:
            r = subprocess.run(
                [self.bin] + args,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if r.returncode not in (0, 1):
                raise RuntimeError(r.stderr.strip() or "ExifTool error")
            return r.stdout
        except FileNotFoundError:
            raise RuntimeError("ExifTool not found")

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

    def strip_all_to(self, src: str, dst: str) -> str:
        shutil.copy2(src, dst)
        return self._run(["-all=", "-overwrite_original", "--", dst])

    def strip_gps(self, path: str, backup: bool = False) -> str:
        args = ["-gps:all="]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["--", path])

    def strip_gps_to(self, src: str, dst: str) -> str:
        shutil.copy2(src, dst)
        return self._run(["-gps:all=", "-overwrite_original", "--", dst])

    def strip_tag(self, path: str, tag: str, backup: bool = False) -> str:
        args = [f"-{tag}="]
        if not backup:
            args.append("-overwrite_original")
        return self._run(args + ["--", path])

    def strip_tag_to(self, src: str, dst: str, tag: str) -> str:
        shutil.copy2(src, dst)
        return self._run([f"-{tag}=", "-overwrite_original", "--", dst])

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
                    rows.append({"Group": grp, "Tag": k, "Value": str(v)})
            else:
                rows.append({"Group": "", "Tag": grp, "Value": str(vals)})
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["Group", "Tag", "Value"])
            w.writeheader()
            w.writerows(rows)

    def strip_zip(self, zip_in: str, zip_out: str) -> int:
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


def browse(want_dir: bool = False, title: str = "Select a file") -> Optional[str]:
    cwd = os.getcwd()

    while True:
        header(title, cwd)

        try:
            entries_raw = sorted(os.scandir(cwd), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            err("Permission denied for this folder")
            cwd = os.path.dirname(cwd)
            continue

        dirs  = [e for e in entries_raw if e.is_dir() and not e.name.startswith(".")]
        files = [e for e in entries_raw if e.is_file()]
        media = [e for e in files if os.path.splitext(e.name)[1].lower() in MEDIA]
        other = [e for e in files if e not in media]

        rows = []
        rows.append((f"[{D}]../  go up[/]", "up", os.path.dirname(cwd)))

        for d in dirs:
            rows.append((f"[{A}]{escape(d.name)}/[/]", "dir", d.path))

        for f in media:
            ext = os.path.splitext(f.name)[1].lower()
            color = Y if ext == ".zip" else G
            rows.append((f"[{color}]{escape(f.name)}[/]  [{D}]{sz(f.path)}[/]", "file", f.path))

        for f in other:
            rows.append((f"[{D}]{escape(f.name)}  {sz(f.path)}[/]", "file", f.path))

        for i, (label, kind, path) in enumerate(rows, 1):
            prefix = f"[{D}]{i:2}[/]"
            C.print(f"  {prefix}  {label}")

        C.print()
        if want_dir:
            C.print(f"  [{G}]S[/]   Select current folder")
        C.print(f"  [{D}]p[/]   Enter path manually")
        C.print(f"  [{D}]0[/]   Cancel / Back")
        rule()

        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip().lower()

        if raw == "0":
            return None

        if raw == "s" and want_dir:
            return cwd

        if raw == "p":
            C.print(f"  [{A}]Path[/]  ", end="")
            path = os.path.expanduser(input().strip())
            if want_dir and os.path.isdir(path):
                return path
            if not want_dir and os.path.isfile(path):
                return path
            err("Path not found or wrong type")
            pause()
            continue

        try:
            idx = int(raw)
            if idx < 1 or idx > len(rows):
                raise ValueError
            label, kind, path = rows[idx - 1]
            if kind == "up":
                parent = os.path.dirname(cwd)
                if parent == cwd:
                    warn("Already at root")
                    pause()
                else:
                    cwd = parent
            elif kind == "dir":
                cwd = path
            elif kind == "file":
                if want_dir:
                    err("That is a file, not a folder — use S to select the current folder")
                    pause()
                else:
                    return path
        except (ValueError, IndexError):
            err("Enter a number from the list, or 0 to cancel")
            pause()


def choose_output_path(src: str, suffix: str = "_clean") -> Optional[str]:
    base, ext = os.path.splitext(os.path.abspath(src))
    default_copy = base + suffix + ext

    C.print(f"\n  [{Y}]Where should the output go?[/]")
    C.print(f"  [{D}]1[/]  Overwrite original  [{D}](modify file in-place)[/]")
    C.print(f"  [{D}]2[/]  Save as a new copy  [{D}](original stays untouched)[/]")
    C.print(f"  [{D}]0[/]  Cancel")
    rule()
    C.print(f"  [{A}]→[/]  ", end="")
    raw = input().strip()

    if raw == "0":
        return None

    if raw == "1":
        return src

    if raw == "2":
        out = ask("Save copy as", default_copy)
        out = os.path.expanduser(out)
        if os.path.exists(out):
            if not yesno(f"{os.path.basename(out)} already exists. Overwrite?", default=False):
                warn("Cancelled")
                return None
        return out

    err("Invalid choice — enter 1, 2, or 0")
    return None


def act_view(et: ET):
    path = browse(title="View Metadata  —  select a file")
    if not path:
        return

    header("Metadata", os.path.basename(path))
    with spin("Reading tags...") as p:
        p.add_task("", total=None)
        try:
            data = et.read(path)
        except Exception as e:
            err(str(e)); pause(); return

    if not data:
        warn("No metadata found in this file"); pause(); return

    found = False
    for group, vals in data.items():
        if group in ("SourceFile", "ExifToolVersion"):
            continue
        if isinstance(vals, dict) and vals:
            found = True
            t = Table(show_header=False, box=box.SIMPLE, padding=(0, 1), expand=True)
            t.add_column("Tag",   style=f"bold {W}", min_width=26)
            t.add_column("Value", style=W, overflow="fold")
            for k, v in vals.items():
                s = str(v)
                display = s[:160] + "…" if len(s) > 160 else s
                t.add_row(escape(k), escape(display))
            C.print(Panel(t, title=f"[bold {Y}]{escape(group)}[/]", border_style=D, padding=(0, 1)))

    if not found:
        warn("No tags found")
    pause()


def act_strip(et: ET):
    path = browse(title="Strip Metadata  —  select a file")
    if not path:
        return

    while True:
        header("Strip Metadata", os.path.basename(path))
        C.print(f"  [{D}]1[/]  [{R}]Remove ALL metadata[/]  [{D}](maximum privacy)[/]")
        C.print(f"  [{D}]2[/]  Remove GPS data only")
        C.print(f"  [{D}]3[/]  Remove one specific tag")
        C.print(f"  [{D}]0[/]  Back to main menu")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip()

        if raw == "0":
            return

        if raw not in ("1", "2", "3"):
            err("Invalid choice — enter 1, 2, 3, or 0"); pause(); continue

        out_path = choose_output_path(path)
        if out_path is None:
            continue

        save_as_copy = (out_path != path)
        backup_path = None

        if not save_as_copy:
            keep_backup = yesno("Keep a backup of the original?", default=False)
            backup_path = path + "_original" if keep_backup else None
        else:
            keep_backup = False

        try:
            if raw == "1":
                if not yesno("Remove ALL tags from this file? This cannot be undone.", default=False):
                    warn("Cancelled"); pause(); continue
                with spin("Removing all metadata...") as p:
                    p.add_task("", total=None)
                    if save_as_copy:
                        et.strip_all_to(path, out_path)
                    else:
                        et.strip_all(path, keep_backup)
                show_result(True, "Remove all metadata", path, out_path, backup_path)

            elif raw == "2":
                with spin("Removing GPS...") as p:
                    p.add_task("", total=None)
                    if save_as_copy:
                        et.strip_gps_to(path, out_path)
                    else:
                        et.strip_gps(path, keep_backup)
                show_result(True, "Remove GPS data", path, out_path, backup_path)

            elif raw == "3":
                tag = ask("Tag name to remove  (e.g. Comment, Artist, Software)")
                if not tag:
                    warn("No tag specified — cancelled"); pause(); continue
                with spin(f"Removing {tag}...") as p:
                    p.add_task("", total=None)
                    if save_as_copy:
                        et.strip_tag_to(path, out_path, tag)
                    else:
                        et.strip_tag(path, tag, keep_backup)
                show_result(True, f"Remove tag: {tag}", path, out_path, backup_path)

        except Exception as e:
            show_result(False, "Strip metadata", path, out_path, None, str(e))

        pause()
        return


def act_gps(et: ET):
    path = browse(title="GPS  —  select a file")
    if not path:
        return

    while True:
        header("GPS", os.path.basename(path))
        C.print(f"  [{D}]1[/]  View GPS coordinates")
        C.print(f"  [{D}]2[/]  Set GPS coordinates manually")
        C.print(f"  [{D}]3[/]  Remove GPS data")
        C.print(f"  [{D}]0[/]  Back to main menu")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip()

        if raw == "0":
            return

        if raw == "1":
            with spin("Reading GPS...") as p:
                p.add_task("", total=None)
                try:
                    gps = et.read_gps(path)
                except Exception as e:
                    err(str(e)); pause(); continue

            header("GPS Data", os.path.basename(path))
            lat     = gps.get("GPSLatitude",    "—")
            lon     = gps.get("GPSLongitude",   "—")
            lat_ref = gps.get("GPSLatitudeRef", "")
            lon_ref = gps.get("GPSLongitudeRef","")
            alt     = gps.get("GPSAltitude",    "—")
            speed   = gps.get("GPSSpeed",       "—")
            gdate   = gps.get("GPSDateStamp",   "—")
            gtime   = gps.get("GPSTimeStamp",   "—")

            if lat == "—" and lon == "—":
                warn("No GPS data found in this file")
            else:
                t = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
                t.add_column("", style=D, min_width=16)
                t.add_column("", style=W)
                t.add_row("Latitude",   escape(f"{lat} {lat_ref}"))
                t.add_row("Longitude",  escape(f"{lon} {lon_ref}"))
                t.add_row("Altitude",   escape(str(alt)))
                t.add_row("Speed",      escape(str(speed)))
                t.add_row("GPS Date",   escape(str(gdate)))
                t.add_row("GPS Time",   escape(str(gtime)))
                C.print(Panel(t, border_style=D, padding=(1, 2)))
                try:
                    lat_f = float(str(lat).split()[0]) * (-1 if lat_ref == "S" else 1)
                    lon_f = float(str(lon).split()[0]) * (-1 if lon_ref == "W" else 1)
                    C.print(f"\n  [{D}]Google Maps[/]  [{A}]https://maps.google.com/?q={lat_f},{lon_f}[/]")
                except Exception:
                    pass
            pause()

        elif raw == "2":
            C.print(f"\n  [{D}]Decimal degrees. + = North/East, − = South/West[/]")
            C.print(f"  [{D}]Example: New York = 40.7128, -74.0060[/]\n")
            try:
                lat_s = ask("Latitude   (−90 to 90)")
                if not lat_s:
                    warn("Cancelled"); pause(); continue
                lon_s = ask("Longitude  (−180 to 180)")
                if not lon_s:
                    warn("Cancelled"); pause(); continue
                lat_f = float(lat_s)
                lon_f = float(lon_s)
                if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
                    err("Coordinates out of valid range"); pause(); continue
                alt_s = ask("Altitude in meters  (Enter to skip)", "")
                alt_f = float(alt_s) if alt_s else None
                keep_backup = yesno("Keep a backup of the original?", default=False)
                backup_path = path + "_original" if keep_backup else None
                with spin("Writing GPS...") as p:
                    p.add_task("", total=None)
                    et.write_gps(path, lat_f, lon_f, alt_f, keep_backup)
                extra = f"{lat_f}, {lon_f}" + (f"  alt {alt_f} m" if alt_f is not None else "")
                show_result(True, "Write GPS coordinates", path, path, backup_path, extra)
            except ValueError:
                err("Invalid number format")
            pause()

        elif raw == "3":
            keep_backup = yesno("Keep a backup of the original?", default=False)
            backup_path = path + "_original" if keep_backup else None
            try:
                with spin("Removing GPS...") as p:
                    p.add_task("", total=None)
                    et.strip_gps(path, keep_backup)
                show_result(True, "Remove GPS data", path, path, backup_path)
            except Exception as e:
                show_result(False, "Remove GPS data", path, path, None, str(e))
            pause()

        else:
            err("Invalid choice — enter 1, 2, 3, or 0"); pause()


POPULAR_TAGS = [
    ("Artist",           "Author / Artist"),
    ("Copyright",        "Copyright notice"),
    ("Description",      "Description"),
    ("Comment",          "Comment"),
    ("Title",            "Title"),
    ("Subject",          "Subject"),
    ("Keywords",         "Keywords"),
    ("Make",             "Camera manufacturer"),
    ("Model",            "Camera model"),
    ("Software",         "Software / App"),
    ("Creator",          "Creator"),
    ("DateTimeOriginal", "Original date/time"),
    ("CreateDate",       "Creation date/time"),
    ("Rating",           "Rating  (0–5)"),
]


def act_edit(et: ET):
    path = browse(title="Edit Tags  —  select a file")
    if not path:
        return

    while True:
        header("Edit Tags", os.path.basename(path))
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
        t.add_column("#",           style=f"bold {D}", width=4)
        t.add_column("Tag",         style=f"bold {W}", min_width=20)
        t.add_column("Description", style=D, min_width=20)
        t.add_column("Current",     style=Y, overflow="fold")

        for i, (tag, desc) in enumerate(POPULAR_TAGS, 1):
            v = str(cur.get(tag, ""))
            v_show = v[:55] + "…" if len(v) > 55 else v
            t.add_row(str(i), tag, desc, escape(v_show) if v_show else f"[{D}]—[/]")

        C.print(Panel(t, border_style=D, padding=(0, 1)))
        C.print(f"  [{D}]c[/]  Enter a custom tag name")
        C.print(f"  [{D}]m[/]  Edit multiple tags at once")
        C.print(f"  [{D}]0[/]  Back to main menu")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip().lower()

        if raw == "0":
            return

        if raw == "c":
            tag = ask("Tag name  (e.g. XMP:Description, IPTC:Keywords)").strip()
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
                err("Invalid choice — enter a number, c, m, or 0"); pause(); continue

        old = str(cur.get(tag, ""))
        if old:
            C.print(f"\n  [{D}]Current value:[/] [{Y}]{escape(old)}[/]")
        val = ask(f"New value for {tag}")
        if not val:
            warn("Empty value — skipped"); continue
        keep_backup = yesno("Keep a backup of the original?", default=False)
        backup_path = path + "_original" if keep_backup else None
        try:
            with spin("Writing...") as p:
                p.add_task("", total=None)
                et.write(path, {tag: val}, keep_backup)
            show_result(True, f"Write tag: {tag} = {val}", path, path, backup_path)
        except Exception as e:
            show_result(False, f"Write tag: {tag}", path, path, None, str(e))
        pause()


def _edit_multi(et: ET, path: str):
    tags = {}
    header("Edit Multiple Tags", os.path.basename(path))
    C.print(f"  [{D}]Enter tags one by one. Leave tag name blank to finish.[/]\n")
    while True:
        tag = ask("Tag  (Enter to finish)").strip()
        if not tag:
            break
        val = ask(f"Value for {tag}")
        tags[tag] = val
        C.print(f"  [{G}]+[/]  {escape(tag)} = [{Y}]{escape(val)}[/]")
    if not tags:
        warn("No tags entered — cancelled")
        pause()
        return
    keep_backup = yesno("Keep a backup of the original?", default=False)
    backup_path = path + "_original" if keep_backup else None
    try:
        with spin("Writing...") as p:
            p.add_task("", total=None)
            et.write(path, tags, keep_backup)
        show_result(True, f"Write {len(tags)} tag(s)", path, path, backup_path)
    except Exception as e:
        show_result(False, "Write tags", path, path, None, str(e))
    pause()


def act_zip(et: ET):
    while True:
        header("ZIP Cleaner", "Strip metadata from every file inside a ZIP archive")
        C.print(f"  [{Y}]How it works:[/]")
        C.print(f"  [{D}]  1. Select a ZIP file[/]")
        C.print(f"  [{D}]  2. Files are extracted to a temporary folder[/]")
        C.print(f"  [{D}]  3. ExifTool strips all metadata from each file[/]")
        C.print(f"  [{D}]  4. Files are repacked into a clean new ZIP[/]")
        C.print(f"  [{D}]  5. Temporary folder is removed[/]")
        C.print()
        C.print(f"  [{D}]1[/]  Clean ZIP  (remove ALL metadata from every file)")
        C.print(f"  [{D}]2[/]  Inspect ZIP  (check which files have metadata)")
        C.print(f"  [{D}]0[/]  Back to main menu")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip()

        if raw == "0":
            return

        if raw not in ("1", "2"):
            err("Invalid choice — enter 1, 2, or 0"); pause(); continue

        path = browse(title="ZIP Cleaner  —  select a ZIP file")
        if not path:
            continue

        if not path.lower().endswith(".zip"):
            err("Selected file is not a ZIP archive")
            pause()
            continue

        if raw == "2":
            header("ZIP: Inspect Metadata", os.path.basename(path))
            with spin("Analysing ZIP contents...") as p:
                p.add_task("", total=None)
                try:
                    results = et.list_zip_metadata(path)
                except Exception as e:
                    err(str(e)); pause(); continue

            if not results:
                ok("No metadata found — archive is clean")
            else:
                t = Table(show_header=True, header_style=f"bold {A}", box=box.SIMPLE_HEAD, padding=(0, 2))
                t.add_column("File",       style=W, overflow="fold")
                t.add_column("Tags found", style=Y, justify="right")
                total_tags = 0
                dirty = 0
                for item in results:
                    count = item["tags"]
                    total_tags += count
                    if count > 0:
                        dirty += 1
                    color = R if count > 0 else G
                    t.add_row(escape(item["file"]), f"[{color}]{count}[/]")
                C.print(Panel(t, border_style=D, padding=(0, 1)))
                if dirty:
                    C.print(f"\n  [{R}]{dirty} file(s) contain metadata[/]  [{D}](total {total_tags} tags)[/]")
                else:
                    ok("All files are clean")
            pause()
            continue

        if raw == "1":
            header("ZIP Cleaner", os.path.basename(path))

            try:
                with zipfile.ZipFile(path, "r") as zf:
                    file_list = [n for n in zf.namelist() if not n.endswith("/")]
                    file_count = len(file_list)
            except Exception as e:
                err(f"Could not open ZIP: {e}"); pause(); continue

            C.print(f"  [{D}]Archive:[/]   {escape(os.path.basename(path))}")
            C.print(f"  [{D}]Files:  [/]   {file_count}")
            C.print(f"  [{D}]Size:   [/]   {sz(path)}")

            base = os.path.splitext(path)[0]
            out_default = base + "_clean.zip"
            C.print()
            C.print(f"  [{Y}]Where to save the cleaned ZIP?[/]")
            out_path = ask("Output path", out_default)
            out_path = os.path.expanduser(out_path)

            if os.path.abspath(out_path) == os.path.abspath(path):
                err("Output path cannot be the same as the input ZIP — choose a different filename")
                pause()
                continue

            if os.path.exists(out_path):
                if not yesno(f"{os.path.basename(out_path)} already exists. Overwrite?", default=False):
                    warn("Cancelled"); continue

            C.print()
            with spin("Stripping metadata and repacking...") as p:
                p.add_task("", total=None)
                try:
                    processed = et.strip_zip(path, out_path)
                except Exception as e:
                    show_result(False, "ZIP clean", path, out_path, None, str(e))
                    pause(); continue

            show_result(
                True,
                "ZIP Cleaner",
                path,
                out_path,
                None,
                f"{processed} file(s) processed  |  Output size: {sz(out_path)}  |  Original ZIP untouched",
            )
            pause()
            continue


def act_folder(et: ET):
    while True:
        header("Folder Batch", "Process all files in a directory")
        C.print(f"  [{D}]1[/]  [{R}]Remove ALL metadata[/] from every file")
        C.print(f"  [{D}]2[/]  Remove GPS from every file")
        C.print(f"  [{D}]3[/]  Write the same tags to every file")
        C.print(f"  [{D}]0[/]  Back to main menu")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip()

        if raw == "0":
            return

        if raw not in ("1", "2", "3"):
            err("Invalid choice — enter 1, 2, 3, or 0"); pause(); continue

        folder = browse(want_dir=True, title="Select folder to process")
        if not folder:
            continue

        ext_s = ask("File extensions to include  (e.g. jpg,png — or Enter for all files)", "")
        exts  = [e for e in (e.strip().lower() for e in ext_s.split(",")) if e] if ext_s.strip() else None
        keep_backup = yesno("Keep backup copies of originals?", default=False)

        try:
            if raw == "1":
                if not yesno("Remove ALL metadata from ALL files in this folder?", default=False):
                    warn("Cancelled"); continue
                with spin("Processing folder...") as p:
                    p.add_task("", total=None)
                    out = et.strip_dir(folder, exts, keep_backup)
                show_result(True, "Remove all metadata (folder)", folder, folder, None, out.strip() or "Done")

            elif raw == "2":
                with spin("Removing GPS...") as p:
                    p.add_task("", total=None)
                    out = et.strip_gps_dir(folder, exts, keep_backup)
                show_result(True, "Remove GPS (folder)", folder, folder, None, out.strip() or "Done")

            elif raw == "3":
                tags = {}
                C.print(f"\n  [{D}]Enter tags. Leave tag name blank to finish.[/]\n")
                while True:
                    tag = ask("Tag  (Enter to finish)").strip()
                    if not tag:
                        break
                    val = ask(f"Value for {tag}")
                    tags[tag] = val
                    C.print(f"  [{G}]+[/]  {escape(tag)} = [{Y}]{escape(val)}[/]")
                if not tags:
                    warn("No tags entered — cancelled"); continue
                if not yesno(f"Write {len(tags)} tag(s) to all files in folder?", default=False):
                    warn("Cancelled"); continue
                with spin("Writing...") as p:
                    p.add_task("", total=None)
                    out = et.write_dir(folder, tags, exts, keep_backup)
                show_result(True, f"Write {len(tags)} tag(s) (folder)", folder, folder, None, out.strip() or "Done")

        except Exception as e:
            show_result(False, "Folder batch operation", folder, folder, None, str(e))

        pause()


def act_export(et: ET):
    path = browse(title="Export Metadata  —  select a file")
    if not path:
        return

    while True:
        header("Export Metadata", os.path.basename(path))
        C.print(f"  [{D}]1[/]  Save as JSON")
        C.print(f"  [{D}]2[/]  Save as CSV")
        C.print(f"  [{D}]0[/]  Back to main menu")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip()

        if raw == "0":
            return

        if raw not in ("1", "2"):
            err("Invalid choice — enter 1, 2, or 0"); pause(); continue

        base = os.path.splitext(os.path.abspath(path))[0]

        if raw == "1":
            out = ask("Save as", base + "_metadata.json")
        else:
            out = ask("Save as", base + "_metadata.csv")

        out = os.path.expanduser(out)

        with spin("Exporting...") as p:
            p.add_task("", total=None)
            try:
                if raw == "1":
                    et.export_json(path, out)
                else:
                    et.export_csv(path, out)
                show_result(True, "Export metadata", path, out, None, f"Size: {sz(out)}")
            except Exception as e:
                show_result(False, "Export metadata", path, out, None, str(e))
        pause()
        return


def act_copy(et: ET):
    header("Copy Tags", "Transfer metadata from one file to another")
    C.print(f"  [{D}]Step 1/2  —  Select the source file (copy tags FROM):[/]\n")
    C.print(f"  [{D}]Enter 0 at any time to cancel.[/]\n")
    src = browse(title="Source file (copy tags from)")
    if not src:
        return

    C.print(f"  [{D}]Step 2/2  —  Select the destination file (copy tags TO):[/]\n")
    dst = browse(title="Destination file (copy tags to)")
    if not dst:
        return

    header("Copy Tags")
    C.print(f"  [{D}]From:[/]  [{Y}]{escape(src)}[/]")
    C.print(f"  [{D}]To:  [/]  [{Y}]{escape(dst)}[/]\n")

    if not yesno("Copy metadata from source to destination?"):
        warn("Cancelled"); return

    keep_backup = yesno("Keep a backup of the destination file?", default=False)
    backup_path = dst + "_original" if keep_backup else None

    with spin("Copying tags...") as p:
        p.add_task("", total=None)
        try:
            et.copy_from(src, dst, keep_backup)
            show_result(True, "Copy tags", src, dst, backup_path)
        except Exception as e:
            show_result(False, "Copy tags", src, dst, None, str(e))
    pause()


MENU = [
    ("1", "View metadata",                    act_view,   W),
    ("2", "Strip metadata  (privacy)",        act_strip,  R),
    ("3", "ZIP Cleaner  —  clean archive",    act_zip,    Y),
    ("4", "GPS  —  view / edit / remove",     act_gps,    A),
    ("5", "Edit tags",                        act_edit,   W),
    ("6", "Folder batch  (all files)",        act_folder, W),
    ("7", "Export metadata  (JSON / CSV)",    act_export, W),
    ("8", "Copy tags between files",          act_copy,   W),
]


def main():
    et = ET()

    while True:
        header()
        try:
            ver = et.version()
        except Exception:
            ver = "?"

        C.print(f"  [{D}]Exifor {EXIFOR_VERSION}[/]  [{D}]·[/]  [{G}]ExifTool {ver}[/]\n")

        for key, label, _, color in MENU:
            C.print(f"  [{D}]{key}[/]  [{color}]{label}[/]")

        C.print()
        C.print(f"  [{D}]q[/]  [{D}]Quit[/]")
        rule()
        C.print(f"  [{A}]→[/]  ", end="")
        raw = input().strip().lower()

        if raw in ("q", "quit", "exit"):
            clear()
            C.print(f"\n  [{D}]Goodbye![/]\n")
            sys.exit(0)

        matched = False
        for key, label, fn, _ in MENU:
            if raw == key:
                try:
                    fn(et)
                except KeyboardInterrupt:
                    C.print()
                    warn("Interrupted")
                    pause()
                matched = True
                break

        if not matched and raw:
            err("Invalid choice — enter a number from the menu")
            pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        C.print(f"\n  [{D}]Goodbye![/]\n")
        sys.exit(0)
