#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tb-chatgpt-export-viewer 1.0.18
# Last updated: 2026-11-16
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 tb-utils
# Convert a ChatGPT export ZIP (or extracted folder) into a searchable offline HTML viewer.
# Python 3.10+. Standard library only. No network requests.
#
# Usage:
#   python tb_chatgpt_export_viewer.py export.zip --out viewer_dir --work export_work_dir
#   python tb_chatgpt_export_viewer.py extracted_export_dir --out viewer_dir
#   python tb_chatgpt_export_viewer.py --show-internal  # uses ./chatgpt_export_work
#   python tb_chatgpt_export_viewer.py extracted_export_dir --out viewer_dir --show-internal
#
# Defaults (relative to current working directory):
#   --out  ./chatgpt_export_viewer
#   input  ./chatgpt_export_work (extracted directory, when omitted)
#   --work ./chatgpt_export_work (used only for ZIP input)
#
# WARNING: The output contains private conversations and attachments. Do not publish it.

from __future__ import annotations

import argparse
import ast
import datetime as dt
import html
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

PROGRAM_NAME = "tb_chatgpt_export_viewer.py"
PROGRAM_VERSION = "1.0.18"

BASE_CSS = """
:root{--bg:#fff;--fg:#111;--muted:#666;--line:#d8d8d8;--user:#f7fbff;--assistant:#f8fff7;--system:#fff8ef;--tool:#f7f7f7;--internal:#f5f2ff;--accent:#0645ad}
*{box-sizing:border-box}
body{margin:0;font-family:"Yu Gothic UI","Meiryo",sans-serif;font-size:18px;line-height:1.75;color:var(--fg);background:var(--bg)}
a{color:var(--accent)}
.wrapper{max-width:1180px;margin:0 auto;padding:22px}
.header{border-bottom:1px solid var(--line);padding:18px 0;margin-bottom:20px}
h1{font-size:30px;line-height:1.35;margin:0 0 8px}
h2{font-size:24px;margin:30px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:22px;margin:26px 0 10px}
h4{font-size:20px;margin:22px 0 8px}
.meta{color:var(--muted);font-size:14px}
.searchbox{width:100%;font-size:18px;padding:10px;border:1px solid var(--line);border-radius:8px;margin:16px 0}
.chat-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.chat-card{border:1px solid var(--line);border-radius:10px;padding:12px;background:#fff}
.chat-card h2{font-size:18px;border:0;margin:0 0 8px;padding:0}
.msg{border:1px solid var(--line);border-radius:10px;margin:18px 0;padding:14px}
.msg.User{background:var(--user)}
.msg.ChatGPT{background:var(--assistant)}
.msg.System{background:var(--system)}
.msg.Tool{background:var(--tool)}
.msg.Internal{background:var(--internal)}
.msg.alternate{border-left:5px solid #9b7acb}
.branch-label{display:inline-block;font-size:12px;font-weight:700;padding:2px 7px;border-radius:5px;background:#e9f3fb;color:#164a72}
.branch-label.alt{background:#f1eafd;color:#653c8d}
.branch-nav{border:1px solid var(--line);padding:10px 12px;border-radius:8px;margin:12px 0;background:#fbfbfb}
.branch-nav a{margin-right:12px}
.branch-note{font-size:12px;color:var(--muted)}
.msg-head{display:flex;gap:12px;align-items:baseline;border-bottom:1px solid var(--line);padding-bottom:6px;margin-bottom:10px}
.role{font-weight:700}.time{color:var(--muted);font-size:13px}
.code{background:#111;color:#eee;padding:10px;border-radius:8px;overflow:auto;line-height:1.45;font-size:14px}
.code-lang{color:#aaa;font-size:12px;margin-bottom:6px}
.md-table-wrap{overflow-x:auto;margin:0 0 1em}.md-table{border-collapse:collapse;width:max-content;min-width:100%;font-size:0.95em}.md-table th,.md-table td{border:1px solid var(--line);padding:5px 10px;vertical-align:top}.md-table th{background:#f1f3f5;text-align:left}
.attachments{border-top:1px dashed var(--line);margin-top:12px;padding-top:8px}
.attachment{margin:8px 0}.attachment img{max-width:520px;max-height:360px;display:block;border:1px solid var(--line);border-radius:6px;margin-top:6px}
.generated-file{display:inline-block;background:#eef7ff;border:1px solid #cfe6ff;border-radius:6px;padding:1px 6px;margin:1px 0}.generated-file .label{font-weight:700;color:#444;margin-right:4px}.missing-file{color:#777}
.toc{border:1px solid var(--line);background:#fafafa;border-radius:10px;padding:12px;margin:16px 0}.toc ul{margin:8px 0 0 20px;padding:0}
.day{font-weight:700;margin:22px 0 6px;color:#333}.toplink{font-size:13px;text-align:right}.small{font-size:13px;color:var(--muted)}
p{margin:0 0 0.9em}ul,ol{margin-top:0.2em}hr{border:none;border-top:1px solid var(--line);margin:1.4em 0}
"""


def safe_filename(name: str, max_len: int = 80) -> str:
    name = (name or "untitled").strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", "_", name).strip("._ ")
    return (name or "untitled")[:max_len]


def fmt_ts(value: Any) -> str:
    if value is None:
        return ""
    try:
        if isinstance(value, (int, float)):
            return dt.datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, str):
            try:
                return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return value
    except Exception:
        pass
    return str(value)


def ts_num(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0
    return 0.0


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=False)


def die(msg: str) -> None:
    raise SystemExit("[ERROR] " + msg)


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def ensure_safe_paths(out_dir: Path, work_dir: Path | None) -> None:
    if work_dir is None:
        return
    out_r = out_dir.resolve()
    work_r = work_dir.resolve()
    if out_r == work_r:
        die("--out and --work must not be the same directory.")
    if is_relative_to(work_r, out_r):
        die("--work must not be inside --out. Choose separate directories.")
    if is_relative_to(out_r, work_r):
        die("--out must not be inside --work. Choose separate directories.")


def remove_dir(path: Path, label: str) -> None:
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except PermissionError as e:
        die(f"{label} could not be removed.\\n{path}\\n\\nA browser, File Explorer, preview window, or antivirus software may be accessing files. Close them and retry.\\nDetails: {e}")
    except Exception as e:
        die(f"{label} could not be removed.\\n{path}\\nDetails: {e}")


def replace_extracted_work(staging: Path, work: Path) -> None:
    """Install a complete extraction without deleting an existing work directory first.

    Any error while moving directories attempts to restore the original work path.
    A unique backup is used so that a backup from a previous interrupted run
    can never be silently discarded.
    """
    backup: Path | None = None
    if work.exists():
        if not work.is_dir():
            die(f"--work exists but is not a directory: {work}")
        # Reserve a unique path without touching any existing backup.
        backup_holder = Path(tempfile.mkdtemp(prefix=work.name + "_backup_", dir=work.parent))
        backup_holder.rmdir()
        backup = backup_holder
        try:
            work.rename(backup)
        except OSError as e:
            die(f"Cannot replace ZIP extraction directory; existing data was not changed.\n"
                f"Directory: {work}\nDetails: {e}\n"
                "Close programs using extracted files and retry, or specify another --work directory.")
    try:
        staging.rename(work)
    except OSError as e:
        restore_error = None
        if backup is not None and backup.exists():
            try:
                backup.rename(work)
            except OSError as restore_exc:
                restore_error = restore_exc
        if restore_error is not None:
            die(f"Cannot install new extraction: {e}\n"
                f"Automatic rollback also failed: {restore_error}\n"
                f"Original extraction is preserved at: {backup}\n"
                "Do not delete this backup; restore it manually after closing files in use.")
        die(f"Cannot install new extraction; previous directory was restored.\n"
            f"Destination: {work}\nDetails: {e}")
    if backup is not None and backup.exists():
        try:
            shutil.rmtree(backup)
        except OSError as e:
            print(f"[WARN] New extraction installed, but old backup could not be removed: "
                  f"{backup} ({e})", flush=True)


def prepare_input(input_path: Path, out_dir: Path, work_arg: str | None) -> Path:
    input_path = input_path.resolve()
    if input_path.is_dir():
        return input_path
    if input_path.suffix.lower() == ".zip":
        work = Path(work_arg).resolve() if work_arg else (out_dir.parent / (out_dir.name + "_work")).resolve()
        ensure_safe_paths(out_dir, work)
        if is_relative_to(input_path, work):
            die("The input ZIP must not be inside --work, because --work is replaced after extraction.")
        if not input_path.is_file():
            die(f"Input ZIP does not exist: {input_path}")
        work.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=work.name + "_extract_", dir=work.parent))
        print(f"[INFO] ZIP extraction started: {input_path} -> {staging} (staging)", flush=True)
        try:
            with zipfile.ZipFile(input_path, "r") as z:
                z.extractall(staging)
            # Reject invalid or incomplete exports before touching the old extraction.
            conv_path = find_conversations_json(staging)
            conversations = json.loads(conv_path.read_text(encoding="utf-8"))
            if not isinstance(conversations, list):
                raise ValueError("conversations.json must contain a JSON array")
            print(f"[INFO] ZIP extraction validated; replacing work directory: {work}", flush=True)
            replace_extracted_work(staging, work)
            print(f"[INFO] ZIP extraction completed: {work}", flush=True)
        except SystemExit:
            raise
        except Exception as e:
            die(f"ZIP extraction failed; existing work directory was preserved if replacement "
                f"had not begun.\nInput: {input_path}\nDestination: {work}\nDetails: {e}")
        finally:
            if staging.exists():
                try:
                    shutil.rmtree(staging)
                except OSError as e:
                    print(f"[WARN] Could not remove incomplete staging directory: {staging} ({e})", flush=True)
        return work
    die("Input must be a ZIP file or extracted export directory.")
    return input_path


def find_conversations_json(root: Path) -> Path:
    found = list(root.rglob("conversations.json"))
    if found:
        return found[0]
    for p in root.rglob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list) and data and isinstance(data[0], dict) and ("mapping" in data[0] or "title" in data[0]):
                return p
        except Exception:
            pass
    raise SystemExit("conversations.json was not found.")


def build_file_index(root: Path) -> dict[str, Path]:
    idx = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        keys = {p.name, p.stem, rel}
        for m in re.findall(r"(file_[0-9a-fA-F]+|file-[0-9a-zA-Z_-]+)", rel):
            keys.add(m)
        for k in keys:
            idx.setdefault(k, p)
    return idx


def load_conversation_asset_file_names(root: Path) -> dict[str, str]:
    """conversation_asset_file_names.json から file_id -> 元ファイル名 を作る。

    ChatGPTエクスポートには、添付実体が file_xxx.dat として保存され、
    conversation_asset_file_names.json に
        "file_xxx.dat": "元ファイル名.png"
    の対応が入ることがある。

    この対応表がある場合は、会話本文側の曖昧な添付情報より優先する。
    """
    result: dict[str, str] = {}

    candidates = list(root.rglob("conversation_asset_file_names.json"))
    if not candidates:
        return result

    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue

        for k, v in data.items():
            if not isinstance(k, str) or not isinstance(v, str) or not v.strip():
                continue

            # key は file_...dat / file-...dat のことが多い
            m = re.search(r"(file_[0-9a-fA-F]+|file-[0-9A-Za-z_-]+)(?:\.dat)?$", Path(k).name)
            if m:
                fid = m.group(1)
            else:
                fid = Path(k).stem

            if fid and fid != "file_unknown":
                result[fid] = v.strip()

    return result



def load_library_files(root: Path) -> dict[str, str]:
    """library_files.json から file_id -> file_name を作る。"""
    result: dict[str, str] = {}
    for p in root.rglob("library_files.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            fid = item.get("file_id")
            name = item.get("file_name")
            if isinstance(fid, str) and isinstance(name, str) and fid.strip() and name.strip():
                result[fid.strip()] = name.strip()
    return result


def unique_asset_name(desired: str, used: set[str]) -> str:
    base = make_safe_asset_name(desired)
    if base not in used:
        used.add(base)
        return base
    p = Path(base)
    stem, suffix = p.stem, p.suffix
    n = 2
    while True:
        candidate = make_safe_asset_name(f"{stem} ({n}){suffix}")
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def pre_copy_all_dat_assets(
    root: Path,
    assets_dir: Path,
    library_names: dict[str, str],
    original_names: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """ZIP/展開フォルダ内の *.dat を assets に事前コピーする。

    優先順位:
      1. library_files.json: assets/元ファイル名.ext
      2. conversation_asset_file_names.json 等: assets/file_id.元ファイル名.ext
      3. 不明: assets/file_id.dat
    """
    assets_dir.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, Any]] = {}
    used: set[str] = set()

    dat_files: list[Path] = []
    for p in root.rglob("*.dat"):
        if not p.is_file():
            continue
        m = re.search(r"(file_[0-9a-fA-F]+|file-[0-9A-Za-z_-]+)", p.name)
        if m:
            dat_files.append(p)

    dat_files.sort(key=lambda p: p.name)

    library_count = 0
    fallback_count = 0
    raw_count = 0

    total_dat = len(dat_files)
    print(f"[INFO] Copying export assets: 0/{total_dat}", flush=True)
    for copy_index, src in enumerate(dat_files, start=1):
        m = re.search(r"(file_[0-9a-fA-F]+|file-[0-9A-Za-z_-]+)", src.name)
        if not m:
            continue
        fid = m.group(1)

        if fid in library_names and _is_original_attachment_name(library_names[fid]):
            desired = library_names[fid]
            kind = "library"
            library_count += 1
        elif fid in original_names and _is_original_attachment_name(original_names[fid]):
            desired = f"{fid}.{original_names[fid]}"
            kind = "fallback"
            fallback_count += 1
        else:
            desired = src.name
            kind = "raw"
            raw_count += 1

        asset_name = unique_asset_name(desired, used)
        dst = assets_dir / asset_name
        if not dst.exists():
            shutil.copy2(src, dst)

        records[fid] = {
            "asset_name": asset_name,
            "href": "../assets/" + quote(asset_name),
            "is_image": is_image(Path(asset_name)),
            "source_kind": kind,
            "source_path": src,
        }
        if copy_index % 25 == 0 or copy_index == total_dat:
            print(f"[INFO] Copying export assets: {copy_index}/{total_dat}", flush=True)

    print(f"[INFO] Export .dat files: {len(dat_files)}; copied: {len(records)} "
          f"(library: {library_count}, fallback: {fallback_count}, raw: {raw_count})")
    return records



def make_safe_asset_name(name: str, max_len: int = 180) -> str:
    name = (name or "attachment").strip()
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._")
    return (name or "attachment")[:max_len]


def copy_asset(src: Path, root: Path, assets_dir: Path, dest_name: str | None = None) -> str:
    if dest_name:
        safe = make_safe_asset_name(dest_name)
        dst = assets_dir / safe
        rel_for_url = safe
    else:
        rel = src.relative_to(root)
        dst = assets_dir / rel
        rel_for_url = str(rel).replace("\\", "/")

    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
    return "../assets/" + quote(rel_for_url.replace("\\", "/"))

def is_image(path: Path) -> bool:
    return path.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"]


def attachment_candidates(ref: Any) -> list[str]:
    vals = []
    if isinstance(ref, str):
        vals.append(ref)
    elif isinstance(ref, dict):
        for k in ["file_name", "filename", "name", "id", "file_id", "path", "asset_pointer"]:
            v = ref.get(k)
            if isinstance(v, str):
                vals.append(v)
    return vals


def guess_attachment_path(ref: Any, file_index: dict[str, Path]) -> Path | None:
    for v in attachment_candidates(ref):
        tail = v.split("/")[-1].split("\\")[-1]
        for key in [v, tail, Path(tail).stem]:
            if key in file_index:
                return file_index[key]
    return None


def display_attachment_name(ref: Any, path: Path | None) -> str:
    if isinstance(ref, dict):
        for k in ["file_name", "filename", "name"]:
            if ref.get(k):
                return str(ref[k])
        for k in ["id", "file_id"]:
            if ref.get(k):
                return f"{ref[k]} ({path.name})" if path else str(ref[k])
    if isinstance(ref, str):
        return path.name if path else ref
    return path.name if path else "Attachment"


def extract_text_from_content(content: Any, show_internal: bool = False) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(extract_text_from_content(x, show_internal) for x in content)
    if isinstance(content, dict):
        ctype = content.get("content_type")
        # 内部思考系は通常本文ではない。表示する場合は walk_messages 側で扱う。
        if ctype == "thoughts":
            return json.dumps(content, ensure_ascii=False, indent=2) if show_internal else ""
        if ctype == "reasoning_recap":
            if show_internal:
                return json.dumps(content, ensure_ascii=False, indent=2)
            return str(content.get("content") or "")

        parts = content.get("parts")
        if isinstance(parts, list):
            out = []
            for part in parts:
                if isinstance(part, str):
                    out.append(part)
                elif isinstance(part, dict):
                    ptype = part.get("content_type")
                    if ptype in ["thoughts", "reasoning_recap"]:
                        # 本文に辞書そのものを出さない
                        val = part.get("content") or part.get("text") or ""
                        if ptype == "reasoning_recap" and val:
                            out.append(str(val))
                        continue
                    if "text" in part:
                        out.append(str(part.get("text") or ""))
                    elif "content" in part and not isinstance(part.get("content"), dict):
                        out.append(str(part.get("content") or ""))
                    elif "content" in part:
                        out.append(extract_text_from_content(part.get("content"), show_internal))
                    else:
                        # asset_pointer/file_id だけの part は、下の「添付ファイル」欄で表示する。
                        # 本文にも [添付/参照: sediment://file_...] を出すと二重表示になるため抑制する。
                        label = part.get("name") or part.get("file_name")
                        if label:
                            out.append(f"[Attachment reference: {label}]")
            return "\n".join(x for x in out if x)
        for k in ["text", "result", "content"]:
            if k in content and not isinstance(content.get(k), (dict, list)):
                return str(content.get(k) or "")
    return str(content)


def _decode_entity_array_text(arr_text: str) -> str:
    """ChatGPT export内の entity 表記を、画面に見えていた表示名へ戻す。"""
    try:
        arr = json.loads(arr_text)
    except Exception:
        try:
            arr = ast.literal_eval(arr_text)
        except Exception:
            return arr_text
    if isinstance(arr, list):
        # 例: ["point_of_interest", "早島IC", "Okayama, Japan"] -> 早島IC
        if len(arr) >= 2 and isinstance(arr[1], str):
            return arr[1]
        if arr and isinstance(arr[0], str):
            return arr[0]
    return arr_text


def restore_visible_entities(text: str) -> str:
    # entity は画面上に表示される文字を含むので、削除せず表示名へ戻す。
    # 代表例:
    #   entity["point_of_interest","早島IC","Okayama, Japan"] -> 早島IC
    #   entitypoint_of_interest早島ICOkayama, Japan -> 早島IC
    #   �entity�["point_of_interest","早島IC","Okayama, Japan"]� -> 早島IC
    #   entity["point_of_interest","早島IC","Okayama, Japan"] -> 早島IC

    def decode_array_or_text(s: str) -> str:
        s = s.strip()
        if s.startswith('['):
            return _decode_entity_array_text(s)
        # JSON配列ではない場合はそのまま表示名候補として返す
        return s

    def cite_entity_repl(mm: re.Match) -> str:
        body = mm.group(1)
        # entityJSON配列 形式
        if body.startswith('entity'):
            rest = body[len('entity'):]
            # 1) entity["point_of_interest","早島IC",...]
            if rest.lstrip().startswith('['):
                return _decode_entity_array_text(rest)
            # 2) entitypoint_of_interest早島IC...
            parts = rest.split('')
            if len(parts) >= 2:
                return decode_array_or_text(parts[1])
            if parts:
                return decode_array_or_text(parts[0])
        return ''

    # ChatGPT独自cite風entity。後段の「...汎用削除」の前に必ず処理する。
    text = re.sub(r"(entity[^]+)", cite_entity_repl, text, flags=re.DOTALL)

    # 配列JSON/疑似JSON型 entity
    markers = ["�", "\ufffd", "□", "\u25a1"]
    for m in markers:
        pat = re.escape(m + "entity" + m) + r"(\[.*?\])" + re.escape(m)
        text = re.sub(pat, lambda mm: _decode_entity_array_text(mm.group(1)), text, flags=re.DOTALL)

    text = re.sub(r"entity(\[.*?\])", lambda mm: _decode_entity_array_text(mm.group(1)), text, flags=re.DOTALL)
    return text

def clean_export_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")

    # 重要: entity / url は cite/image_group 等の削除より先に復元する。
    # 後段の汎用内部表記削除で可視テキストごと消えるのを防ぐ。
    text = restore_visible_entities(text)

    # ChatGPT独自URL表記。例:
    # urlVisual Studio Build Toolshttps://visualstudio.microsoft.com/visual-cpp-build-tools/
    # いったんMarkdownリンクにして、後段の inline_markdown() でHTMLリンク化する。
    text = re.sub(
        r"url([^]+)([^]+)",
        lambda m: (f"[{m.group(1)}]({m.group(2)})" if re.match(r"^https?://", m.group(2).strip(), re.I)
                   else m.group(1)),
        text,
        flags=re.DOTALL,
    )

    text = re.sub(r"cite[^]+", "", text)
    text = re.sub(r"filecite[^]+", "", text)
    text = re.sub(r"navlist[^]+", "", text)
    text = re.sub(r"image_group.*?", "[Image group]", text, flags=re.DOTALL)
    text = re.sub(r"i[^]+", "[Image]", text)
    text = re.sub(r"[^]{0,500}", "", text, flags=re.DOTALL)
    text = re.sub(r":contentReference\[[^\]]*\]\{[^}]*\}", "", text)
    text = re.sub(r"【?oaicite:[^】\s]+】?", "", text)

    text = re.sub(r'\{"aspect_ratio"\s*:\s*"[^"]+"\s*,\s*"query"\s*:\s*\[.*?\]\s*,\s*"num_per_query"\s*:\s*\d+\}', "[Image group]", text, flags=re.DOTALL)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def extract_attachments(message: dict[str, Any]) -> list[Any]:
    found = []
    meta = message.get("metadata") or {}
    for key in ["attachments", "files", "uploaded_files"]:
        v = meta.get(key)
        if isinstance(v, list):
            found.extend(v)
    content = message.get("content") or {}
    parts = content.get("parts") if isinstance(content, dict) else None
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict) and any(k in part for k in ["asset_pointer", "file_id", "file_name", "filename", "name"]):
                found.append(part)
    for key in ["attachments", "files"]:
        v = message.get(key)
        if isinstance(v, list):
            found.extend(v)
    seen = set()
    out = []
    for x in found:
        s = json.dumps(x, ensure_ascii=False, sort_keys=True) if isinstance(x, dict) else str(x)
        if s not in seen:
            seen.add(s)
            out.append(x)
    return out


def role_of_message(message: dict[str, Any]) -> str:
    if message.get("_internal_type"):
        return "Internal"
    role = ((message.get("author") or {}).get("role") or message.get("role") or "unknown")
    return {"assistant": "ChatGPT", "user": "User", "system": "System", "tool": "Tool"}.get(role, str(role))


def _mapping_display_order(mapping: dict[str, Any]) -> dict[str, int]:
    """mapping の parent/children を使い、ChatGPT画面に近い順序を作る。
    create_time 順だけだと thoughts/reasoning_recap が最終メッセージ後に見えることがあるため、
    エクスポートツリー上の順序を優先する。
    """
    roots = []
    for node_id, node in mapping.items():
        if not isinstance(node, dict):
            continue
        parent = node.get("parent")
        if parent is None or parent not in mapping:
            roots.append(node_id)

    order: dict[str, int] = {}
    seen: set[str] = set()

    def sort_key(nid: str):
        node = mapping.get(nid) or {}
        msg = node.get("message") or {}
        return (ts_num(msg.get("create_time")), str(nid))

    def dfs(nid: str) -> None:
        if nid in seen:
            return
        seen.add(nid)
        order[nid] = len(order)
        node = mapping.get(nid) or {}
        children = node.get("children") or []
        if isinstance(children, list):
            for cid in sorted(children, key=sort_key):
                if cid in mapping:
                    dfs(cid)

    for rid in sorted(roots, key=sort_key):
        dfs(rid)
    for nid in mapping.keys():
        if nid not in seen:
            dfs(nid)
    return order


def classify_branches(conv: dict[str, Any]) -> tuple[set[str], dict[str, int], dict[int, str | None]]:
    """Classify exported nodes using the chain ending at current_node.

    All nodes on the current_node -> parent chain belong to the main branch.
    For an off-main node, the first off-main ancestor is the branch root.
    Siblings that diverge from the main chain get different branch numbers.
    The traversal has cycle protection; detached subtrees are also classified.
    """
    mapping = conv.get("mapping")
    if not isinstance(mapping, dict):
        return set(), {}, {}
    current = conv.get("current_node")
    if current not in mapping:
        return set(), {}, {}
    main_ids: set[str] = set()
    nid = current
    while nid in mapping and nid not in main_ids:
        main_ids.add(nid)
        node = mapping[nid]
        nid = node.get("parent") if isinstance(node, dict) else None

    roots: dict[str, str | None] = {}
    def off_main_root(node_id: str) -> str | None:
        if node_id in main_ids:
            return None
        trail: list[str] = []
        seen: set[str] = set()
        nid = node_id
        while nid in mapping and nid not in main_ids and nid not in seen:
            if nid in roots:
                root = roots[nid]
                for x in trail:
                    roots[x] = root
                return root
            seen.add(nid)
            trail.append(nid)
            node = mapping[nid]
            parent = node.get("parent") if isinstance(node, dict) else None
            if parent in main_ids or parent not in mapping:
                root = nid
                for x in trail:
                    roots[x] = root
                return root
            nid = parent
        # Cycle: do not recurse indefinitely; use stable representative.
        root = min(trail) if trail else node_id
        for x in trail:
            roots[x] = root
        return root

    all_roots = {off_main_root(n) for n in mapping if n not in main_ids}
    all_roots.discard(None)
    def sort_key(root: str) -> tuple[float, str]:
        node = mapping.get(root) or {}
        msg = node.get("message") or {}
        return ts_num(msg.get("create_time")), root
    numbered = {root: i for i, root in enumerate(sorted(all_roots, key=sort_key), start=1)}
    branch_ids = {n: numbered[r] for n, r in roots.items() if r in numbered}
    origins = {}
    for root, number in numbered.items():
        node = mapping[root]
        origins[number] = node.get("parent") if isinstance(node, dict) else None
    return main_ids, branch_ids, origins


def walk_messages(conv: dict[str, Any], show_internal: bool = False) -> list[dict[str, Any]]:
    """メッセージを表示用に抽出する。

    v5では parent/children ツリー順を優先したが、エクスポートによっては枝の順序が
    ChatGPT画面の直列表示と大きくズレることがあったため、v6では create_time の
    単純時系列順へ戻す。通常閲覧で一番破綻しにくい。
    """
    mapping = conv.get("mapping")
    if isinstance(mapping, dict):
        main_ids, branch_ids, origins = classify_branches(conv)
        msgs = []
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            msg = node.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content") or {}
            ctype = content.get("content_type") if isinstance(content, dict) else None
            if ctype in ["thoughts", "reasoning_recap"] and not show_internal:
                continue

            text = clean_export_text(extract_text_from_content(content, show_internal))
            atts = extract_attachments(msg)
            if not text.strip() and not atts:
                continue

            msg = dict(msg)
            msg["_node_id"] = node_id
            msg["_branch"] = ("main" if node_id in main_ids else branch_ids.get(node_id)) if main_ids else None
            msg["_branch_parent"] = origins.get(branch_ids.get(node_id)) if node_id in branch_ids else None
            msg["_clean_text"] = text
            if ctype in ["thoughts", "reasoning_recap"]:
                msg["_internal_type"] = ctype
            msgs.append(msg)

        msgs.sort(key=lambda m: (ts_num(m.get("create_time")), m.get("_node_id", "")))
        if show_internal:
            msgs = reorder_internal_blocks_before_assistant(msgs, mapping=mapping)
        return msgs

    msgs = conv.get("messages")
    if isinstance(msgs, list):
        out = []
        for i, m in enumerate(msgs):
            if isinstance(m, dict):
                m = dict(m)
                m.setdefault("_node_id", str(i))
                out.append(m)
        out.sort(key=lambda m: (ts_num(m.get("create_time")), m.get("_node_id", "")))
        return out
    return []


def reorder_internal_blocks_before_assistant(
    msgs: list[dict[str, Any]], mapping: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Move exported Internal records immediately before their own assistant reply.

    With a mapping, follow the assistant's parent chain instead of relying on
    timestamp adjacency. An assistant can have its own preceding thoughts and
    reasoning_recap nodes whose export timestamps are *later* than the answer.
    An alternate answer can have a different internal parent chain, even when
    its timestamp is virtually identical to the Main answer.

    Without a mapping, retain the older adjacent-block heuristic, but only
    attach records that have the same branch label as the assistant.
    """
    if not mapping:
        out: list[dict[str, Any]] = []
        i = 0
        while i < len(msgs):
            m = msgs[i]
            if role_of_message(m) == "ChatGPT":
                j = i + 1
                block: list[dict[str, Any]] = []
                while (j < len(msgs) and role_of_message(msgs[j]) == "Internal"
                       and msgs[j].get("_branch") == m.get("_branch")):
                    block.append(msgs[j])
                    j += 1
                if block:
                    out.extend(block)
                    out.append(m)
                    i = j
                    continue
            out.append(m)
            i += 1
        return out

    by_node = {m.get("_node_id"): m for m in msgs if m.get("_node_id")}
    claimed: set[str] = set()
    groups: list[tuple[tuple[float, str], list[dict[str, Any]]]] = []

    # Build reverse edges from parent pointers. Exported reasoning_recap can
    # be a *child* of the assistant's response, while thoughts is an ancestor.
    # The mapping's optional children arrays cannot be relied upon.
    children_by_parent: dict[str, list[str]] = {}
    for child_id, node in mapping.items():
        parent_id = (node or {}).get("parent") if isinstance(node, dict) else None
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(child_id)

    def internal_type(node_id: str) -> str | None:
        raw = (mapping.get(node_id) or {}).get("message") or {}
        content = raw.get("content") or {}
        return content.get("content_type")

    for m in msgs:
        if role_of_message(m) != "ChatGPT":
            continue
        nid = m.get("_node_id")
        chain: list[dict[str, Any]] = []
        visited: set[str] = set()
        parent = (mapping.get(nid) or {}).get("parent")
        while parent in mapping and parent not in visited:
            visited.add(parent)
            node = mapping.get(parent) or {}
            ancestor = by_node.get(parent)
            if internal_type(parent) not in ("thoughts", "reasoning_recap"):
                break
            if ancestor is not None and ancestor.get("_branch") == m.get("_branch"):
                chain.append(ancestor)
            parent = node.get("parent")

        # Collect only immediately following internal descendants of THIS
        # assistant reply. They are logically part of the same response even
        # when timestamps place them after the rendered answer.
        descendants: list[dict[str, Any]] = []
        to_visit = list(children_by_parent.get(nid, []))
        seen_desc: set[str] = set()
        while to_visit:
            child = to_visit.pop()
            if child in seen_desc:
                continue
            seen_desc.add(child)
            if internal_type(child) not in ("thoughts", "reasoning_recap"):
                continue
            candidate = by_node.get(child)
            if candidate is not None and candidate.get("_branch") == m.get("_branch"):
                descendants.append(candidate)
            to_visit.extend(children_by_parent.get(child, []))

        # Sort original internal records by their own timestamps. All of them
        # precede the assistant's displayed answer, independent of timestamps.
        internals = list(reversed(chain)) + descendants
        internals.sort(key=lambda x: (ts_num(x.get("create_time")), str(x.get("_node_id"))))
        block = [x for x in internals if x.get("_node_id") not in claimed]
        if block:
            for x in block:
                claimed.add(x["_node_id"])
            groups.append(((ts_num(m.get("create_time")), str(nid)), block + [m]))
            claimed.add(nid)

    for m in msgs:
        nid = m.get("_node_id")
        if nid not in claimed:
            groups.append(((ts_num(m.get("create_time")), str(nid)), [m]))
    groups.sort(key=lambda group: group[0])
    return [m for _, group in groups for m in group]


# sandbox:/mnt/data/... 形式のリンクを、生成済み assets への相対リンクに置換するための対応表。
# main() の pre-copy 後に埋める。
ASSET_NAME_TO_HREF: dict[str, str] = {}


def inline_markdown(s: str) -> str:
    """本文1行の簡易MarkdownをHTML化する。

    - url... から変換した [表示文字](https://...) は通常リンク化
    - ChatGPT生成ファイルに多い [file.py](sandbox:/mnt/data/file.py) は、
      assets に同名ファイルがあれば assets へのリンクに置換
    - assets に無い sandbox リンクは、ローカルで開けないので表示名だけ残す
    """
    placeholders: list[str] = []

    def put_placeholder(html_value: str) -> str:
        placeholders.append(html_value)
        return f"\uE000LINK{len(placeholders)-1}\uE001"

    def resolve_asset_href(label: str, url: str) -> str | None:
        # label自体、または URL末尾のファイル名が assets にあればそれを使う。
        candidates = []
        if label:
            candidates.append(label)
        tail = url.split("/")[-1].split("\\")[-1]
        if tail:
            candidates.append(tail)
        for c in candidates:
            c = c.strip()
            if c in ASSET_NAME_TO_HREF:
                return ASSET_NAME_TO_HREF[c]
        return None

    # Markdownリンクを先に保護してから全体escapeする。
    # URLは https だけでなく sandbox:/mnt/data/... なども拾う。
    def md_link_repl(m: re.Match) -> str:
        raw_label = m.group(1)
        raw_url = m.group(2).strip()
        label = html.escape(raw_label, quote=False)

        if raw_url.startswith("sandbox:/mnt/data/"):
            # The URL basename is the original generated filename. The Markdown
            # label can instead be a descriptive phrase (e.g. "Ver.13").
            # Keep the file name as the primary clickable text, and retain
            # the original label as a separate description in its original spot.
            from urllib.parse import unquote
            filename = unquote(raw_url.rsplit("/", 1)[-1])
            filename_html = html.escape(filename, quote=False)
            description = f' <span class="small">({label})</span>' if raw_label != filename else ''
            href = resolve_asset_href(raw_label, raw_url)
            if href:
                return put_placeholder(
                    f'<span class="generated-file"><span class="label">Generated file:</span> '
                    f'<a href="{html.escape(href, quote=True)}">{filename_html}</a>{description}</span>'
                )
            # Preserve reference details even when the exported target is absent.
            return put_placeholder(
                f'<span class="generated-file missing-file"><span class="label">Generated file:</span> '
                f'{filename_html}{description} <span class="small">(not found in assets)</span></span>'
            )

        # Only convert verifiable external links into live anchors. Other
        # Markdown-looking text may be a regex (e.g. [年/](\d{1,2})), an
        # effect name ([...](Distortion+)), or an export reference
        # ([...](turn0search11)). These are *not* local files. Preserve the
        # original literal text instead of generating a broken local link.
        if re.match(r"^https?://", raw_url, re.IGNORECASE):
            url = html.escape(raw_url, quote=True)
            return put_placeholder(f'<a href="{url}">{label}</a>')
        if raw_url.startswith("#"):
            return put_placeholder(f'<a href="{html.escape(raw_url, quote=True)}">{label}</a>')
        return m.group(0)

    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", md_link_repl, s)

    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)

    # 生URLもリンク化。ただしプレースホルダ内部は既に保護済み。
    s = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', s)

    for i, h in enumerate(placeholders):
        s = s.replace(f"\uE000LINK{i}\uE001", h)
    return s

def split_markdown_table_row(line: str) -> list[str]:
    """Split a simple GFM table row; respect escaped pipes and code spans."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]
    cells: list[str] = []
    buf: list[str] = []
    code_delim = 0
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "`":
            run = len(line[i:]) - len(line[i:].lstrip("`"))
            if not code_delim:
                code_delim = run
            elif code_delim == run:
                code_delim = 0
            buf.append("`" * run)
            i += run
            continue
        if ch == "|" and not code_delim:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def markdown_table_alignments(line: str, columns: int) -> list[str] | None:
    cells = split_markdown_table_row(line)
    if len(cells) != columns:
        return None
    result: list[str] = []
    for cell in cells:
        if not re.fullmatch(r":?-{3,}:?", cell):
            return None
        result.append("center" if cell.startswith(":") and cell.endswith(":")
                      else "right" if cell.endswith(":") else "left")
    return result


def render_markdownish_block(block: str) -> str:
    lines = block.split("\n")
    out: list[str] = []
    in_ul = False
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            i += 1
            continue

        # A table must have a header and a GFM separator, not merely pipes.
        # This prevents ordinary code, regexes and prose from being treated
        # as a table. Fenced code is handled by render_text() separately.
        if i + 1 < len(lines) and "|" in stripped:
            headers = split_markdown_table_row(stripped)
            aligns = markdown_table_alignments(lines[i + 1].strip(), len(headers)) if len(headers) >= 2 else None
            if aligns is not None:
                if in_ul:
                    out.append("</ul>")
                    in_ul = False
                table = ['<div class="md-table-wrap"><table class="md-table"><thead><tr>']
                for h, align in zip(headers, aligns):
                    table.append(f'<th style="text-align:{align}">{inline_markdown(h)}</th>')
                table.append('</tr></thead><tbody>')
                i += 2
                while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                    vals = split_markdown_table_row(lines[i])
                    if len(vals) > len(headers):
                        break
                    vals.extend([""] * (len(headers) - len(vals)))
                    table.append('<tr>')
                    for val, align in zip(vals, aligns):
                        table.append(f'<td style="text-align:{align}">{inline_markdown(val)}</td>')
                    table.append('</tr>')
                    i += 1
                table.append('</tbody></table></div>')
                out.append("".join(table))
                continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            level = min(len(m.group(1)) + 1, 4)
            out.append(f"<h{level}>{inline_markdown(m.group(2))}</h{level}>")
            i += 1
            continue
        if stripped == "---":
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append("<hr>")
            i += 1
            continue
        lm = re.match(r"^[-*]\s+(.*)$", stripped)
        if lm:
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline_markdown(lm.group(1))}</li>")
            i += 1
            continue
        if in_ul:
            out.append("</ul>")
            in_ul = False
        out.append(f"<p>{inline_markdown(stripped)}</p>")
        i += 1
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


def render_text(text: str) -> str:
    text = clean_export_text(text)
    chunks = re.split(r"(```.*?```)", text or "", flags=re.DOTALL)
    out = []
    for ch in chunks:
        if ch.startswith("```") and ch.endswith("```"):
            body = ch[3:-3]
            first, sep, rest = body.partition("\n")
            lang = first.strip()
            code = rest if sep else body
            out.append(f'<pre class="code"><div class="code-lang">{esc(lang)}</div><code>{html.escape(code)}</code></pre>')
        else:
            out.append(render_markdownish_block(ch))
    return "\n".join(out)


def attachment_file_id(ref: Any, path: Path | None) -> str:
    """Get a real file ID, not the 'file-service' URL scheme name.

    For example, file-service://file-ABC must yield file-ABC, so the
    attachment reuses the asset already copied during pre-copy.
    """
    pattern = r"(file_[0-9a-fA-F]+|file-[0-9a-zA-Z_-]+)"
    for value in attachment_candidates(ref):
        # The prefix 'file-service' itself matches the generic file- pattern.
        # Strip the scheme before searching for an actual attachment ID.
        v = re.sub(r"^file-service://", "", value, flags=re.IGNORECASE)
        m = re.search(pattern, v)
        if m and m.group(1).lower() != "file-service":
            return m.group(1)
    if path:
        m = re.search(pattern, path.name)
        if m and m.group(1).lower() != "file-service":
            return m.group(1)
        return path.stem
    return "file_unknown"


def _is_original_attachment_name(name: str | None) -> bool:
    if not name:
        return False
    base = Path(str(name)).name
    if base.startswith("file_") or re.match(r"file-[0-9A-Za-z_-]+", base):
        return False
    if base.lower().endswith(".dat") and re.match(r"file_[0-9a-fA-F]+\.dat$", base):
        return False
    return True



def collect_global_attachment_original_names(conversations: list[dict[str, Any]], file_index: dict[str, Path]) -> dict[str, str]:
    """全会話を先に走査し、file_id -> 元ファイル名 を集める。

    同じ添付が、ある箇所では元ファイル名付き、別の箇所では file_xxx.dat として
    参照されることがある。assets に raw *.dat と元ファイル名版が二重作成されるのを
    避けるため、出力前に全体の対応表を作る。
    """
    result: dict[str, str] = {}

    def iter_messages(conv: dict[str, Any]):
        mapping = conv.get("mapping")
        if isinstance(mapping, dict):
            for node in mapping.values():
                if isinstance(node, dict) and isinstance(node.get("message"), dict):
                    yield node["message"]
        msgs = conv.get("messages")
        if isinstance(msgs, list):
            for m in msgs:
                if isinstance(m, dict):
                    yield m

    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        for msg in iter_messages(conv):
            for ref in extract_attachments(msg):
                path = guess_attachment_path(ref, file_index)
                fid = attachment_file_id(ref, path)
                name = display_attachment_name(ref, path)
                if fid and fid != "file_unknown" and _is_original_attachment_name(name):
                    result.setdefault(fid, name)
    return result

def render_attachment_record(
    record: dict[str, Any],
    root: Path,
    assets_dir: Path,
    global_original_names: dict[str, str] | None = None,
    pre_copied_assets: dict[str, dict[str, Any]] | None = None,
) -> str:
    path = record.get("path")
    fid = record.get("fid") or "file_unknown"
    original_name = record.get("original_name")
    if (not _is_original_attachment_name(original_name)) and global_original_names and fid in global_original_names:
        original_name = global_original_names[fid]
    fallback_name = record.get("name") or (path.name if path else "Attachment")

    if pre_copied_assets and fid in pre_copied_assets:
        rec = pre_copied_assets[fid]
        display_name = rec["asset_name"]
        href = rec["href"]
        if rec.get("is_image"):
            return f'<div class="attachment">Attached image: <a href="{href}">{esc(display_name)}</a><img src="{href}" alt="{esc(display_name)}"></div>'
        return f'<div class="attachment">Attachment: <a href="{href}">{esc(display_name)}</a></div>'

    if path and path.exists():
        if _is_original_attachment_name(original_name):
            dest_name = f"{fid}.{original_name}"
            display_name = dest_name
        else:
            dest_name = path.name
            display_name = path.name
        href = copy_asset(path, root, assets_dir, dest_name=dest_name)
        if is_image(Path(display_name)):
            return f'<div class="attachment">Attached image: <a href="{href}">{esc(display_name)}</a><img src="{href}" alt="{esc(display_name)}"></div>'
        return f'<div class="attachment">Attachment: <a href="{href}">{esc(display_name)}</a></div>'

    name = original_name or fallback_name
    ref = record.get("ref")
    if not isinstance(ref, dict):
        return f'<div class="attachment missing">Attachment: {esc(name)} <span class="small">(source file not found)</span></div>'

    # Keep the original reference for unavailable files, especially voice clips.
    # The export may include audio_asset_pointer metadata without audio bytes.
    content_type = ref.get("content_type")
    mime_type = ref.get("mime_type")
    audio_format = ref.get("format")
    pointer = ref.get("asset_pointer")
    if content_type == "audio_asset_pointer":
        display = f"Audio ({str(audio_format).upper()})" if audio_format else "Audio"
    elif name == "Attachment" and mime_type:
        display = str(mime_type)
    elif name == "Attachment" and content_type:
        display = str(content_type)
    else:
        display = name
    details = []
    if content_type:
        details.append(f"Content type: {esc(content_type)}")
    if mime_type:
        details.append(f"MIME type: {esc(mime_type)}")
    if audio_format:
        details.append(f"Format: {esc(audio_format)}")
    if pointer:
        details.append(f"Asset pointer: {esc(pointer)}")
    elif ref.get("id") or ref.get("file_id"):
        details.append(f"File ID: {esc(ref.get('file_id') or ref.get('id'))}")
    detail_html = (f'<div class="small">{" | ".join(details)}</div>' if details else "")
    return (f'<div class="attachment missing">Attachment: {esc(display)} '
            f'<span class="small">(source file not found)</span>{detail_html}</div>')

def render_attachment(ref: Any, root: Path, assets_dir: Path, file_index: dict[str, Path], global_original_names: dict[str, str] | None = None, pre_copied_assets: dict[str, dict[str, Any]] | None = None) -> str:
    path = guess_attachment_path(ref, file_index)
    name = display_attachment_name(ref, path)
    fid = attachment_file_id(ref, path)
    original_name = name if _is_original_attachment_name(name) else None
    return render_attachment_record({"ref": ref, "path": path, "name": name, "fid": fid, "original_name": original_name}, root, assets_dir, global_original_names, pre_copied_assets)


def remove_redundant_raw_dat_attachment_html(block_html: str) -> str:
    """同じ添付ブロック内に file_id.元名 版がある場合、raw file_id.dat 表示を消す。

    v21では assets の最終クリーンアップで raw file-*.dat を削除できても、
    チャットHTML側には
        添付画像: file-xxx.タイトルなし.png
        添付: file-xxx.dat
    のような raw .dat へのリンクが残るケースがあった。
    これは同一添付の二重参照なので、HTML生成時点で raw .dat 側を非表示にする。
    """
    if not block_html:
        return block_html

    def repl(m: re.Match) -> str:
        fid = m.group("fid")

        # 同じHTMLブロック内に file_id.何か があり、それが .dat でなければ raw .dat は冗長。
        # 例:
        #   ../assets/file-xxx.%E3%82%BF...png
        #   ../assets/file_0000.route.json
        has_renamed = re.search(
            r'../assets/' + re.escape(fid) + r'\.(?!dat(?:["?#]|%22))',
            block_html,
            flags=re.IGNORECASE,
        )
        if has_renamed:
            return ""
        return m.group(0)

    return re.sub(
        r'\n?<div class="attachment">Attachment: <a href="../assets/(?P<fid>file_[0-9a-fA-F]+|file-[0-9A-Za-z_-]+)\.dat">(?P=fid)\.dat</a></div>',
        repl,
        block_html,
    )


def render_attachments_grouped(refs: list[Any], root: Path, assets_dir: Path, file_index: dict[str, Path], global_original_names: dict[str, str] | None = None, pre_copied_assets: dict[str, dict[str, Any]] | None = None) -> str:
    """同一 file_id の添付表示を1つにまとめる。

    exportには「元ファイル名を持つ参照」と「file_xxx.dat参照」が二重に入ることがある。
    v9では file_id を優先キーにして統合し、元ファイル名が分かる場合は
    assets側にも file_id.元ファイル名 だけを作る。raw *.dat は作らない。
    """
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for ref in refs:
        path = guess_attachment_path(ref, file_index)
        fid = attachment_file_id(ref, path)
        name = display_attachment_name(ref, path)
        original_name = name if _is_original_attachment_name(name) else None
        if (not original_name) and global_original_names and fid in global_original_names:
            original_name = global_original_names[fid]

        # file_id が取れるなら必ず file_id でまとめる。取れない場合だけ path/json をキーにする。
        if fid and fid != "file_unknown":
            key = fid
        elif path:
            key = str(path.resolve())
        else:
            key = json.dumps(ref, ensure_ascii=False, sort_keys=True) if isinstance(ref, dict) else str(ref)

        if key not in grouped:
            grouped[key] = {"ref": ref, "path": path, "name": name, "fid": fid, "original_name": original_name}
            order.append(key)
        else:
            g = grouped[key]
            # 実体pathが未確定なら補う
            if not g.get("path") and path:
                g["path"] = path
            # file_idが弱い場合は補う
            if (not g.get("fid") or g.get("fid") == "file_unknown") and fid:
                g["fid"] = fid
            # 元ファイル名がある方を優先
            if original_name and not g.get("original_name"):
                g["original_name"] = original_name
                g["name"] = name
                g["ref"] = ref

    html_block = "\n".join(render_attachment_record(grouped[k], root, assets_dir, global_original_names, pre_copied_assets) for k in order)
    return remove_redundant_raw_dat_attachment_html(html_block)

def conv_filename(i: int, title: str) -> str:
    return f"{i:04d}_{safe_filename(title)}.html"


def build_chat_page(conv: dict[str, Any], msgs: list[dict[str, Any]], out_file: Path, root: Path, assets_dir: Path, file_index: dict[str, Path], global_original_names: dict[str, str] | None = None, pre_copied_assets: dict[str, dict[str, Any]] | None = None) -> str:
    title = conv.get("title") or "Untitled"
    create = fmt_ts(conv.get("create_time"))
    update = fmt_ts(conv.get("update_time"))
    all_text = []
    days = []
    seen = set()
    for m in msgs:
        d = fmt_ts(m.get("create_time"))[:10]
        if d and d not in seen:
            seen.add(d); days.append(d)
    parts = [f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{esc(title)}</title><style>{BASE_CSS}</style></head><body id="top"><div class="wrapper">
<div class="header"><div><a href="../index.html">← Index</a></div>
<h1>{esc(title)}</h1>
<div class="meta">Created: {esc(create)} / Updated: {esc(update)} / Messages: {len(msgs)}</div></div>''']
    if days:
        parts.append('<div class="toc"><b>Dates</b><ul>')
        for d in days:
            parts.append(f'<li><a href="#day-{esc(d)}">{esc(d)}</a></li>')
        parts.append('</ul></div>')
    # Stable message anchors for links pointing to the branch divergence.
    displayed_ids = {m.get("_node_id"): i for i, m in enumerate(msgs)}
    branches = sorted({m.get("_branch") for m in msgs if isinstance(m.get("_branch"), int)})
    main_count = sum(1 for m in msgs if m.get("_branch") == "main")
    if main_count:
        first_main = next(i for i, m in enumerate(msgs) if m.get("_branch") == "main")
        nav = [f'<a href="#m{first_main}">Main ({main_count})</a>']
        for branch in branches:
            first_alt = next(i for i, m in enumerate(msgs) if m.get("_branch") == branch)
            count = sum(1 for m in msgs if m.get("_branch") == branch)
            nav.append(f'<a href="#m{first_alt}">Branch {branch} ({count})</a>')
        parts.append('<div class="branch-nav"><b>Conversation paths</b><div class="small">Main follows the exported current_node; alternate paths are retained.</div>' + ' '.join(nav) + '</div>')
    cur_day = None
    for i, m in enumerate(msgs):
        role = role_of_message(m)
        t = fmt_ts(m.get("create_time"))
        day = t[:10] if t else ""
        if day and day != cur_day:
            cur_day = day
            parts.append(f'<div class="day" id="day-{esc(day)}">{esc(day)}</div>')
        text = m.get("_clean_text")
        if text is None:
            text = clean_export_text(extract_text_from_content(m.get("content")))
        all_text.append(text)
        atts = extract_attachments(m)
        branch = m.get("_branch")
        extra_class = ' alternate' if isinstance(branch, int) else ''
        if branch == "main":
            branch_html = '<span class="branch-label">Main</span>'
        elif isinstance(branch, int):
            branch_html = f'<span class="branch-label alt">Branch {branch}</span>'
            parent_idx = displayed_ids.get(m.get("_branch_parent"))
            if parent_idx is not None:
                branch_html += f' <a class="branch-note" href="#m{parent_idx}">Diverged from #m{parent_idx}</a>'
        else:
            branch_html = ''
        parts.append(f'<article class="msg {esc(role)}{extra_class}" id="m{i}">')
        parts.append(f'<div class="msg-head"><span class="role">{esc(role)}</span>{branch_html}<span class="time">{esc(t)}</span><a class="small" href="#m{i}">#</a></div>')
        if text.strip(): parts.append(render_text(text))
        if atts:
            grouped_html = render_attachments_grouped(atts, root, assets_dir, file_index, global_original_names, pre_copied_assets)
            if grouped_html.strip():
                parts.append('<div class="attachments"><b>Attachments</b>')
                parts.append(grouped_html)
                parts.append('</div>')
        parts.append('<div class="toplink"><a href="#top">▲ TOP</a></div></article>')
    parts.append('</div></body></html>')
    page_html = "\n".join(parts)
    page_html = remove_redundant_raw_dat_attachment_html(page_html)
    out_file.write_text(page_html, encoding="utf-8")
    return "\n".join(all_text)


def fmt_file_mtime(path: Path) -> str:
    """Local file modification time; matches the viewer's local-time timestamps."""
    return dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def build_export_manifest_html(
    export_root: Path,
    input_path: Path,
    pre_copied_assets: dict[str, dict[str, Any]],
    output_assets_dir: Path,
    generated_at: str,
) -> str:
    """Build an embedded, offline inventory of the *source* export files.

    The listing shows original source paths and their original mtime/size;
    renamed copies of .dat files are linked only when present in assets/.
    """
    archive_html = ''
    if input_path.is_file() and input_path.suffix.lower() == '.zip':
        archive_html = (f'<p><b>Source ZIP:</b> {esc(input_path.name)}'
                        f' | Modified: {esc(fmt_file_mtime(input_path))}'
                        f' | Size: {input_path.stat().st_size:,} bytes</p>')
    rows = []
    files = sorted((p for p in export_root.rglob('*') if p.is_file()),
                   key=lambda p: p.relative_to(export_root).as_posix().casefold())
    for src in files:
        relative = src.relative_to(export_root).as_posix()
        link_html = ''
        if src.suffix.lower() == '.dat':
            match = re.search(r'(file_[0-9a-fA-F]+|file-[0-9A-Za-z_-]+)', src.name)
            rec = pre_copied_assets.get(match.group(1)) if match else None
            if rec is not None:
                asset_name = rec['asset_name']
                if (output_assets_dir / asset_name).is_file():
                    link_html = f'<a href="assets/{quote(asset_name)}">{esc(asset_name)}</a>'
                else:
                    link_html = f'{esc(asset_name)} <span class="missing-file">(not found)</span>'
            else:
                link_html = '<span class="missing-file">Not restored</span>'
        rows.append(f'<tr><td>{esc(relative)}</td><td>{esc(fmt_file_mtime(src))}</td>'
                    f'<td class="numeric">{src.stat().st_size:,}</td><td>{link_html}</td></tr>')
    table = (f'<details class="export-inventory" data-restore-key="export-files"><summary>Extracted export files ({len(files)})</summary>'
             f'<p class="small">File names and timestamps are from the extracted export directory. '
             f'For .dat files, the last column links to the restored file in assets/.</p>'
             '<div class="inventory-scroll"><table class="inventory-table">'
             '<thead><tr><th>Export-relative file name</th><th>Modified (local)</th>'
             '<th>Size (bytes)</th><th>Restored asset (.dat)</th></tr></thead><tbody>'
             + ''.join(rows) + '</tbody></table></div></details>')
    return (f'<section class="export-info"><details data-restore-key="export-info"><summary>Export and generation information</summary>'
            f'<p><b>Generated:</b> {esc(generated_at)} (local time)<br>'
            f'<b>Program:</b> {esc(PROGRAM_NAME)} | <b>Version:</b> {esc(PROGRAM_VERSION)}</p>'
            f'{archive_html}<p><b>Extracted export directory:</b> {esc(str(export_root))}</p>'
            f'{table}</details></section>')


def build_index(info: list[dict[str, Any]], out_dir: Path, search_messages: list[dict[str, Any]], export_manifest_html: str = "") -> None:
    # Create offline full-text search UI.
    cards = []
    for i, c in enumerate(info):
        cards.append(f"""<div class="chat-card" id="chat-{i}">
<h2><a href="chats/{quote(c["file"])}">{esc(c["title"])}</a></h2>
<div class="meta">Created: {esc(c["create"])}<br>Updated: {esc(c["update"])}<br>Messages: {c["message_count"]}</div>
<div class="matches"></div></div>""")
    # External JS is loaded via a normal script tag, not fetch(). Works for local file:// pages.
    index_data = [{"title": c["title"], "file": c["file"]} for c in info]
    payload = {"conversations": index_data, "messages": search_messages}
    js_data = 'window.CHAT_SEARCH_DATA = ' + json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + ';\n'
    (out_dir / 'search_data.js').write_text(js_data, encoding='utf-8')
    mb = (out_dir / 'search_data.js').stat().st_size / (1024 * 1024)
    print(f"[INFO] Search index: {len(search_messages)} messages, {mb:.2f} MiB")
    script = r"""<script src="search_data.js"></script>
<script>
(function () {
  'use strict';
  const data = window.CHAT_SEARCH_DATA || {conversations: [], messages: []};
  const input = document.getElementById('q');
  const status = document.getElementById('status');
  const cards = Array.from(document.querySelectorAll('.chat-card'));
  // Avoid re-scanning a long chat history on every individual keystroke.
  let debounce;
  const normalized = data.messages.map(m => ({
    conv: m.conv, id: m.id, text: m.text.toLocaleLowerCase(), original: m.text
  }));
  const titleTexts = data.conversations.map(c => c.title.toLocaleLowerCase());
  function search() {
    const query = input.value.trim().toLocaleLowerCase();
    const terms = query.split(/\s+/).filter(Boolean);
    const hits = Array.from({length: cards.length}, () => []);
    const counts = new Uint32Array(cards.length);
    const titleHit = titleTexts.map(t => terms.every(term => t.includes(term)));
    if (terms.length) {
      for (const m of normalized) {
        // Multiple words must all occur within one message, or in the title.
        if (terms.every(term => m.text.includes(term))) {
          counts[m.conv]++;
          const at = m.text.indexOf(terms[0]);
            const from = Math.max(0, at - 55);
            const snippet = m.original.slice(from, from + 160).replace(/\s+/g, ' ');
          hits[m.conv].push({id:m.id, snippet:(from ? '…' : '') + snippet + '…'});
        }
      }
    }
    let shown = 0;
    cards.forEach((card, i) => {
      const match = !terms.length || titleHit[i] || counts[i] > 0;
      card.hidden = !match;
      if (match) shown++;
      const box = card.querySelector('.matches');
      box.replaceChildren();
      if (!terms.length) return;
      if (counts[i]) {
        const count = document.createElement('div');
        count.className = 'small';
        count.textContent = counts[i] + ' matching message(s)';
        box.append(count);
      }
      const snippets = document.createElement('div');
      snippets.className = 'snippets';
      for (const hit of hits[i]) {
        const p = document.createElement('div'); p.className = 'snippet';
        const a = document.createElement('a');
        a.href = 'chats/' + encodeURIComponent(data.conversations[i].file) + '#m' + hit.id;
        a.textContent = hit.snippet;
        p.append(a); snippets.append(p);
      }
      box.append(snippets);
    });
    status.textContent = shown + ' of ' + cards.length + ' conversations';
  }
  input.addEventListener('input', () => {
    saveQueryState();
    clearTimeout(debounce);
    debounce = setTimeout(search, 250);
  });
  // Remember expanded export panels when navigating to an asset and back.
  // sessionStorage is normally available for file:// pages; history.state is
  // a per-entry fallback for browsers that restrict storage on local files.
  const panels = Array.from(document.querySelectorAll('details[data-restore-key]'));
  const inventoryScroll = document.querySelector('.inventory-scroll');
  const panelStateKey = 'tb-chatgpt-export-viewer:panels:' + location.pathname;
  // Store the query separately from panel state so both Reload and Back/Forward
  // restore the same search. The pathname keeps different viewer files distinct.
  const queryStateKey = 'tb-chatgpt-export-viewer:query:' + location.pathname;
  const queryHistoryKey = '__tbViewerQuery';
  function getQueryState() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(queryStateKey) || 'null');
      if (saved && typeof saved.value === 'string') return saved.value;
    } catch (_) { /* Storage can be restricted on file:// pages. */ }
    try {
      const state = history.state;
      if (state && typeof state[queryHistoryKey] === 'string') return state[queryHistoryKey];
    } catch (_) { /* History API can be restricted on file:// pages. */ }
    return null;
  }
  function saveQueryState() {
    const value = input.value;
    try { sessionStorage.setItem(queryStateKey, JSON.stringify({value})); } catch (_) {}
    try {
      const oldState = history.state;
      const combined = oldState && typeof oldState === 'object' && !Array.isArray(oldState)
        ? {...oldState} : {};
      combined[queryHistoryKey] = value;
      history.replaceState(combined, '');
    } catch (_) {}
  }
  function restoreQueryState() {
    const value = getQueryState();
    if (value !== null) input.value = value;
  }

  const historyStateKey = '__tbViewerPanels';
  let restoringPanels = false;
  let pendingScrollSave = null;
  function getPanelState() {
    // Prefer the most recent tab-local state, which is updated on scrolling.
    // history.state can be stale after a browser Reload.
    try {
      const saved = JSON.parse(sessionStorage.getItem(panelStateKey) || 'null');
      if (saved && saved.open) return saved;
    } catch (_) { /* Storage may be unavailable for a file:// page. */ }
    try {
      const state = history.state;
      if (state && state[historyStateKey]) return state[historyStateKey];
    } catch (_) { /* History API may be unavailable on some file:// origins. */ }
    return null;
  }
  function savePanelState() {
    if (pendingScrollSave !== null) {
      clearTimeout(pendingScrollSave);
      pendingScrollSave = null;
    }
    if (restoringPanels || !panels.length) return;
    const state = {
      open: Object.fromEntries(panels.map(p => [p.dataset.restoreKey, p.open])),
      inventoryScrollTop: inventoryScroll ? inventoryScroll.scrollTop : 0
    };
    try { sessionStorage.setItem(panelStateKey, JSON.stringify(state)); } catch (_) {}
    try {
      const oldState = history.state;
      const combined = oldState && typeof oldState === 'object' && !Array.isArray(oldState)
        ? {...oldState} : {};
      combined[historyStateKey] = state;
      history.replaceState(combined, '');
    } catch (_) {}
  }
  function scheduleScrollSave() {
    if (restoringPanels) return;
    if (pendingScrollSave !== null) clearTimeout(pendingScrollSave);
    // Do not write session/history state on every scroll event.
    pendingScrollSave = setTimeout(savePanelState, 120);
  }
  function restorePanelState() {
    const state = getPanelState();
    if (!state || !state.open) return;
    restoringPanels = true;
    for (const panel of panels) {
      if (Object.prototype.hasOwnProperty.call(state.open, panel.dataset.restoreKey)) {
        panel.open = Boolean(state.open[panel.dataset.restoreKey]);
      }
    }
    if (inventoryScroll && Number.isFinite(state.inventoryScrollTop)) {
      inventoryScroll.scrollTop = state.inventoryScrollTop;
    }
    restoringPanels = false;
  }
  for (const panel of panels) panel.addEventListener('toggle', savePanelState);
  if (inventoryScroll) inventoryScroll.addEventListener('scroll', scheduleScrollSave, {passive: true});
  // Flush the latest scroll position before both navigation and Reload.
  window.addEventListener('pagehide', () => { saveQueryState(); savePanelState(); });
  window.addEventListener('beforeunload', () => { saveQueryState(); savePanelState(); });
  restorePanelState();
  restoreQueryState();

  // On Back/Forward, browsers can restore form values without firing 'input'.
  window.addEventListener('pageshow', () => {
    restorePanelState();
    restoreQueryState();
    clearTimeout(debounce);
    search();
  });
  search();
})();
</script>"""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ChatGPT Export Viewer</title><style>{BASE_CSS}
.export-info{{font-size:14px;margin:16px 0}}.export-info details{{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-top:8px;background:#fafafa}}.export-info summary{{cursor:pointer;font-weight:600}}.export-info p{{margin:8px 0}}.inventory-scroll{{overflow:auto;max-height:420px}}.inventory-table{{width:100%;border-collapse:collapse;font-size:12px}}.inventory-table th,.inventory-table td{{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}.inventory-table th{{position:sticky;top:0;background:#f1f3f5}}.inventory-table td.numeric{{text-align:right;white-space:nowrap}}.chat-card[hidden]{{display:none}}.snippet{{font-size:14px;margin:5px 0;overflow-wrap:anywhere}}.snippets{{max-height:220px;overflow-y:auto;overscroll-behavior:contain;border-top:1px solid var(--line);margin-top:5px}}
</style></head><body><div class="wrapper"><div class="header">
<h1>ChatGPT Export Viewer</h1>
<div class="meta">Conversations: {len(info)} | Offline full-text search</div>
<input id="q" class="searchbox" placeholder="Search all conversation messages..." aria-label="Search conversations">
<div id="status" class="small"></div>
{export_manifest_html}
</div><div class="chat-list">{''.join(cards)}</div></div>{script}</body></html>"""
    (out_dir / 'index.html').write_text(doc, encoding='utf-8')


def repair_removed_dat_links(out_dir: Path, assets_dir: Path, pre_copied_assets: dict[str, dict[str, Any]]) -> int:
    """Fix orphaned raw .dat references after cleanup, using known file-id mappings.

    If the renamed asset exists, direct the link there; otherwise leave the
    reference untouched for the broken-link validator to report.
    """
    from urllib.parse import unquote
    fixed = 0
    mapping = {}
    for fid, rec in pre_copied_assets.items():
        target = assets_dir / rec["asset_name"]
        if target.is_file() and rec["asset_name"] != fid + ".dat":
            mapping[fid] = rec["href"]
    pat = re.compile(r'(?P<prefix>\.\./assets/)(?P<fid>file_[0-9a-fA-F]+|file-[0-9A-Za-z_-]+)\.dat(?=["?#])')
    for page in (out_dir / "chats").glob("*.html"):
        content = page.read_text(encoding="utf-8")
        def replace(match):
            nonlocal fixed
            fid = match.group("fid")
            if fid in mapping:
                fixed += 1
                return mapping[fid]
            return match.group(0)
        changed = pat.sub(replace, content)
        if changed != content:
            page.write_text(changed, encoding="utf-8")
    return fixed


def validate_local_links(out_dir: Path) -> tuple[int, list[str]]:
    """Validate real HTML link attributes in pages generated by this run.

    HTMLParser avoids treating literal `href="..."` text inside conversation
    code samples as actual hyperlinks. HTML files copied into assets/ are
    attachments and intentionally are not inspected.
    """
    from html.parser import HTMLParser
    from urllib.parse import unquote, urlsplit

    class LinkCollector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.urls: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr = dict(attrs)
            url = None
            if tag in ("a", "link"):
                url = attr.get("href")
            elif tag in ("img", "script", "iframe", "audio", "video", "source"):
                url = attr.get("src")
            if url:
                self.urls.append(url)

        handle_startendtag = handle_starttag

    missing: set[str] = set()
    checked = 0
    pages = [out_dir / "index.html"]
    chats_dir = out_dir / "chats"
    if chats_dir.is_dir():
        pages.extend(sorted(chats_dir.glob("*.html")))
    output_root = out_dir.resolve()

    for page in pages:
        if not page.is_file():
            continue
        parser = LinkCollector()
        parser.feed(page.read_text(encoding="utf-8"))
        parser.close()
        for url in parser.urls:
            if url.startswith(("#", "//")) or re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
                continue
            try:
                rel = urlsplit(url).path
            except ValueError:
                missing.add(f"{page.relative_to(out_dir)} -> {url}")
                continue
            if not rel:
                continue
            checked += 1
            target = (page.parent / unquote(rel)).resolve()
            if not target.is_relative_to(output_root) or not target.is_file():
                missing.add(f"{page.relative_to(out_dir)} -> {url}")
    return checked, sorted(missing)


def cleanup_redundant_raw_dat_assets(assets_dir: Path, global_original_names: dict[str, str]) -> None:
    """assets内に残った raw file_id.dat を削除する。

    assetsには原則として
        file_id.元ファイル名
    だけを置き、raw の
        file_id.dat
    は不要。

    安全のため、同じディレクトリに
        file_id.何か
    というリネーム済みファイルが存在する場合だけ raw .dat を削除する。
    conversation_asset_file_names.json にあるかどうかだけには依存しない。
    """
    if not assets_dir.exists():
        return

    removed = 0
    for p in list(assets_dir.rglob("*.dat")):
        name = p.name
        m = re.fullmatch(r"(file_[0-9a-fA-F]+|file-[0-9A-Za-z_-]+)\.dat", name)
        if not m:
            continue

        fid = m.group(1)

        # 対応するリネーム済みファイルがある場合だけ削除する。
        # 例: file-xxx.dat と file-xxx.タイトルなし.png
        renamed_exists = any(
            q.is_file() and q.name.startswith(fid + ".") and q.name != name
            for q in p.parent.iterdir()
        )
        if not renamed_exists:
            continue

        try:
            p.unlink()
            removed += 1
        except PermissionError:
            print(f"[WARN] Could not remove redundant raw .dat (possibly in use): {p}")
        except Exception as e:
            print(f"[WARN] Could not remove redundant raw .dat: {p} ({e})")

    if removed:
        print(f"[INFO] Removed {removed} redundant raw .dat file(s) from assets")



def atomic_replace_dir(tmp_dir: Path, out_dir: Path) -> None:
    backup = out_dir.parent / (out_dir.name + "_old")
    if backup.exists():
        remove_dir(backup, "old backup directory")
    if out_dir.exists():
        try:
            out_dir.rename(backup)
        except PermissionError as e:
            die(f"Could not move the existing output directory to a backup.\\n{out_dir}\\n\\nA browser, File Explorer, preview window, or antivirus software may be using the output directory. Close them and retry.\\nDetails: {e}")
        except Exception as e:
            die(f"Could not move the existing output directory to a backup.\\n{out_dir}\\nDetails: {e}")
    try:
        tmp_dir.rename(out_dir)
    except Exception as e:
        if backup.exists() and not out_dir.exists():
            try:
                backup.rename(out_dir)
            except Exception:
                pass
        die(f"Could not replace the output directory with the temporary output.\\nDetails: {e}")
    if backup.exists():
        remove_dir(backup, "old output directory")


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert ChatGPT data exports to an offline searchable HTML viewer.")
    ap.add_argument("--version", action="version", version="tb-chatgpt-export-viewer 1.0.18")
    ap.add_argument("input", nargs="?", default="./chatgpt_export_work",
                    help="Export ZIP or extracted directory (default if omitted: ./chatgpt_export_work)")
    ap.add_argument("--out", default="./chatgpt_export_viewer", metavar="VIEWER_DIR", help="Output directory (default: ./chatgpt_export_viewer)")
    ap.add_argument("--work", default="./chatgpt_export_work", metavar="EXPORT_WORK_DIR", help="ZIP extraction directory (default: ./chatgpt_export_work; not used for extracted directory input)")
    ap.add_argument("--show-internal", action="store_true", help="Include internal messages where available")
    args = ap.parse_args()

    if not Path(args.input).exists():
        ap.error(f"Input path does not exist: {Path(args.input).resolve()}. "
                 "Specify an export ZIP or an extracted export directory as input.")

    out_dir = Path(args.out).resolve()
    work_dir = Path(args.work).resolve() if Path(args.input).is_file() else None
    ensure_safe_paths(out_dir, work_dir)

    root = prepare_input(Path(args.input), out_dir, args.work)

    tmp_out = out_dir.parent / (out_dir.name + "_tmp")
    remove_dir(tmp_out, "temporary output directory")
    tmp_out.mkdir(parents=True, exist_ok=True)
    conv_path = find_conversations_json(root)
    conversations = json.loads(conv_path.read_text(encoding="utf-8"))
    if not isinstance(conversations, list):
        raise SystemExit("Unexpected conversations.json structure.")

    chats_dir = tmp_out / "chats"
    assets_dir = tmp_out / "assets"
    chats_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    file_index = build_file_index(root)

    library_name_map = load_library_files(root)
    asset_name_map = load_conversation_asset_file_names(root)
    global_original_names = collect_global_attachment_original_names(conversations, file_index)

    # 優先順位は library_files.json > conversation_asset_file_names.json > 会話メタデータ。
    # pre-copyでは library_name_map を別扱いし、library一致分は file_id を付けない元名で保存する。
    global_original_names.update(asset_name_map)
    global_original_names.update(library_name_map)

    if library_name_map:
        print(f"[INFO] library_files.json: {len(library_name_map)} filename mappings loaded")
    if asset_name_map:
        print(f"[INFO] conversation_asset_file_names.json: {len(asset_name_map)} attachment filename mappings loaded")

    pre_copied_assets = pre_copy_all_dat_assets(root, assets_dir, library_name_map, global_original_names)

    # ChatGPT側が本文中に出す [file](sandbox:/mnt/data/file) を assets へ張り替えるため、
    # assets内の全ファイル名をリンク表にする。
    ASSET_NAME_TO_HREF.clear()
    for p in assets_dir.iterdir():
        if p.is_file():
            ASSET_NAME_TO_HREF[p.name] = "../assets/" + quote(p.name)

    conversations = sorted(conversations, key=lambda c: (ts_num(c.get("create_time")), c.get("title") or ""))
    info = []
    search_by_file = {}
    for i, conv in enumerate(conversations, start=1):
        title = conv.get("title") or f"Untitled {i}"
        msgs = walk_messages(conv, show_internal=args.show_internal)
        filename = conv_filename(i, title)
        print(f"[INFO] {i}/{len(conversations)} {title} ({len(msgs)} messages)")
        all_text = build_chat_page(
            conv,
            msgs,
            chats_dir / filename,
            root,
            assets_dir,
            file_index,
            global_original_names,
            pre_copied_assets,
        )
        search_by_file[filename] = [
            {"id": j, "text": m.get("_clean_text") or clean_export_text(extract_text_from_content(m.get("content")))}
            for j, m in enumerate(msgs) if role_of_message(m) in (("User", "ChatGPT", "Internal") if args.show_internal else ("User", "ChatGPT"))
        ]
        info.append({"title": title, "file": filename, "create": fmt_ts(conv.get("create_time")), "update": fmt_ts(conv.get("update_time")), "message_count": len(msgs)})
    info.sort(key=lambda x: x["update"], reverse=True)
    searchable = []
    for ci, c in enumerate(info):
        for m in search_by_file[c["file"]]:
            if m["text"].strip():
                searchable.append({"conv": ci, **m})
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    export_manifest_html = build_export_manifest_html(
        root, Path(args.input).resolve(), pre_copied_assets, assets_dir, generated_at)
    build_index(info, tmp_out, searchable, export_manifest_html)

    cleanup_redundant_raw_dat_assets(assets_dir, global_original_names)
    repaired = repair_removed_dat_links(tmp_out, assets_dir, pre_copied_assets)
    if repaired:
        print(f"[INFO] Repaired {repaired} raw .dat reference(s) in generated HTML")
    checked, missing = validate_local_links(tmp_out)
    print(f"[INFO] Local links checked: {checked}; broken: {len(missing)}")
    for link in missing[:30]:
        print(f"[WARN] Missing local target: {link}")
    if len(missing) > 30:
        print(f"[WARN] ...and {len(missing)-30} more broken links")

    atomic_replace_dir(tmp_out, out_dir)
    print(f"[DONE] Open {out_dir / 'index.html'}")

if __name__ == "__main__": main()
