"""小说原文导入脚本：解析章节，生成 chapters.jsonl 和 ingest_report.json。"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "projects.json"

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
             "百": 100, "千": 1000, "万": 10000}

# 站点广告 / 推广行特征，导入时过滤；同时剔除章末标记
AD_LINE_MARKERS = ("更多精彩小说", "请访问", "sudugu", "记住我们网",
                   "推荐一本书", "推书", "求推荐", "求收藏")


def clean_text(line: str) -> str:
    return (line.replace("(本章完)", "").replace("（本章完）", "")
            .replace("本章完", "").replace("(全本完)", "").replace("（全本完）", ""))


def is_ad_line(line: str) -> bool:
    s = line.strip()
    return any(m in s for m in AD_LINE_MARKERS)


def cn_to_int(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    result, temp = 0, 0
    for ch in s:
        if ch not in CN_DIGITS:
            return None
        val = CN_DIGITS[ch]
        if val >= 10:
            if temp == 0:
                temp = 1
            result += temp * val
            temp = 0
        else:
            temp = val
    result += temp
    return result if result > 0 else None


def load_project(project_id: str) -> dict:
    projects = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    for p in projects:
        if p["project_id"] == project_id:
            return p
    raise ValueError(f"Project '{project_id}' not found in config/projects.json")


def build_chapter_pattern(patterns: list[str]) -> re.Pattern:
    combined = "|".join(f"(?:{p})" for p in patterns)
    return re.compile(combined)


def parse_chapters(text: str, pattern: re.Pattern, source_file: str,
                   project_id: str, remove_dup: bool) -> tuple[list[dict], list[str]]:
    lines = text.split("\n")
    warnings: list[str] = []
    raw_chapters: list[tuple[int, str, int]] = []  # (chapter_no, title, line_idx)

    for i, line in enumerate(lines):
        stripped = line.strip()
        m = pattern.match(stripped)
        if m:
            groups = [g for g in m.groups() if g is not None]
            num_str = groups[0] if groups else None
            title = groups[1].strip() if len(groups) > 1 else ""
            if num_str is None:
                warnings.append(f"Line {i}: matched but no chapter number: {stripped[:60]}")
                continue
            ch_no = cn_to_int(num_str)
            if ch_no is None:
                warnings.append(f"Line {i}: cannot parse chapter number '{num_str}'")
                continue
            raw_chapters.append((ch_no, title, i))

    # Deduplicate: keep first occurrence of each chapter_no
    seen: set[int] = set()
    chapter_starts: list[tuple[int, str, int]] = []
    for ch_no, title, line_idx in raw_chapters:
        if ch_no not in seen:
            seen.add(ch_no)
            chapter_starts.append((ch_no, title, line_idx))
        elif remove_dup:
            pass  # skip duplicate
        else:
            warnings.append(f"Duplicate chapter {ch_no} at line {line_idx}, kept first occurrence")

    # Extract text between chapter boundaries
    chapters: list[dict] = []
    for idx, (ch_no, title, start_line) in enumerate(chapter_starts):
        # End line is start of next chapter (skip its duplicate title lines)
        if idx + 1 < len(chapter_starts):
            end_line = chapter_starts[idx + 1][2]
        else:
            end_line = len(lines)

        # Skip the chapter title line(s) from body
        body_start = start_line + 1
        # Skip duplicate title line if present
        if (remove_dup and start_line + 1 < len(lines)
                and pattern.match(lines[start_line + 1].strip())):
            body_start = start_line + 2

        body_lines = [clean_text(l) for l in lines[body_start:end_line] if not is_ad_line(l)]
        # Strip leading/trailing empty lines
        while body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]
        while body_lines and not body_lines[-1].strip():
            body_lines = body_lines[:-1]

        body = "\n".join(body_lines).strip()
        if not body:
            warnings.append(f"Chapter {ch_no} '{title}' has empty body")
            continue

        chapters.append({
            "project_id": project_id,
            "chapter_no": ch_no,
            "chapter_title": title,
            "source_file": source_file,
            "text": body,
        })

    return chapters, warnings


def build_chunks(chapters: list[dict], chunk_size: int, chunk_overlap: int,
                 project_id: str) -> list[dict]:
    # Deduplicate chapters: keep the one with longest text for each chapter_no
    best: dict[int, dict] = {}
    for ch in chapters:
        cn = ch["chapter_no"]
        if cn not in best or len(ch["text"]) > len(best[cn]["text"]):
            best[cn] = ch
    chapters = sorted(best.values(), key=lambda c: c["chapter_no"])

    chunks: list[dict] = []
    for ch in chapters:
        text = ch["text"]
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        # Aggregate paragraphs into chunks
        current_parts: list[str] = []
        current_len = 0
        chunk_idx = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > chunk_size and current_parts:
                # Emit current chunk
                chunk_idx += 1
                chunk_text = "\n".join(current_parts)
                chunks.append({
                    "chunk_id": f"{project_id}_ch{ch['chapter_no']:04d}_{chunk_idx:04d}",
                    "project_id": project_id,
                    "chapter_no": ch["chapter_no"],
                    "chapter_title": ch["chapter_title"],
                    "source_file": ch["source_file"],
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                })
                # Overlap: keep tail of current chunk
                overlap_text = chunk_text[-chunk_overlap:] if chunk_overlap > 0 else ""
                current_parts = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)

            current_parts.append(para)
            current_len += para_len

        # Emit remaining
        if current_parts:
            chunk_idx += 1
            chunk_text = "\n".join(current_parts)
            # Avoid emitting if overlap already covers it
            if not chunks or chunks[-1]["text"] != chunk_text:
                chunks.append({
                    "chunk_id": f"{project_id}_ch{ch['chapter_no']:04d}_{chunk_idx:04d}",
                    "project_id": project_id,
                    "chapter_no": ch["chapter_no"],
                    "chapter_title": ch["chapter_title"],
                    "source_file": ch["source_file"],
                    "chunk_index": chunk_idx,
                    "text": chunk_text,
                })

    return chunks


def check_continuity(chapters: list[dict]) -> dict:
    if not chapters:
        return {"first": None, "last": None, "missing": [], "duplicates": []}

    nums = [c["chapter_no"] for c in chapters]
    first, last = min(nums), max(nums)
    expected = set(range(first, last + 1))
    actual = set(nums)

    missing = sorted(expected - actual)
    from collections import Counter
    counts = Counter(nums)
    duplicates = sorted(n for n, c in counts.items() if c > 1)

    return {"first": first, "last": last, "missing": missing, "duplicates": duplicates}


def ingest(project_id: str) -> None:
    cfg = load_project(project_id)
    source_dir = ROOT / cfg["source_dir"]
    if not source_dir.exists():
        print(f"ERROR: Source directory not found: {source_dir}")
        sys.exit(1)

    pattern = build_chapter_pattern(cfg["chapter_patterns"])
    remove_dup = cfg.get("remove_duplicate_chapter_title", True)

    txt_files = sorted(source_dir.glob("*.txt"))
    if not txt_files:
        print(f"ERROR: No .txt files found in {source_dir}")
        sys.exit(1)

    all_chapters: list[dict] = []
    all_warnings: list[str] = []
    source_files: list[str] = []

    for txt_file in txt_files:
        print(f"Parsing: {txt_file.name}")
        text = txt_file.read_text(encoding=cfg["encoding"])
        chapters, warnings = parse_chapters(text, pattern, txt_file.name,
                                            project_id, remove_dup)
        all_chapters.extend(chapters)
        all_warnings.extend(warnings)
        source_files.append(txt_file.name)
        print(f"  -> {len(chapters)} chapters, {len(warnings)} warnings")

    # 跨文件章节重叠（如 501-1000 文件实际从 497 章开始）：先报告重复，再合并保留最长正文
    from collections import Counter
    num_counts = Counter(c["chapter_no"] for c in all_chapters)
    merged_duplicates = sorted(n for n, c in num_counts.items() if c > 1)

    best: dict[int, dict] = {}
    for ch in all_chapters:
        cn = ch["chapter_no"]
        if cn not in best or len(ch["text"]) > len(best[cn]["text"]):
            best[cn] = ch
    all_chapters = sorted(best.values(), key=lambda c: c["chapter_no"])

    # Check continuity
    cont = check_continuity(all_chapters)

    # Write output
    out_dir = ROOT / "data" / project_id
    out_dir.mkdir(parents=True, exist_ok=True)

    chapters_path = out_dir / "chapters.jsonl"
    with open(chapters_path, "w", encoding="utf-8") as f:
        for ch in all_chapters:
            f.write(json.dumps(ch, ensure_ascii=False) + "\n")

    # Build and write chunks
    chunk_size = cfg.get("chunk_size", 1000)
    chunk_overlap = cfg.get("chunk_overlap", 200)
    all_chunks = build_chunks(all_chapters, chunk_size, chunk_overlap, project_id)

    chunks_path = out_dir / "chunks.jsonl"
    with open(chunks_path, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    # Validate chunks
    empty_chunks = [c for c in all_chunks if not c["text"].strip()]
    if empty_chunks:
        all_warnings.append(f"{len(empty_chunks)} chunks have empty text")

    report = {
        "project_id": project_id,
        "source_files": source_files,
        "chapter_count": len(all_chapters),
        "chunk_count": len(all_chunks),
        "first_chapter_no": cont["first"],
        "last_chapter_no": cont["last"],
        "duplicate_chapter_numbers": merged_duplicates,
        "missing_chapter_numbers": cont["missing"],
        "warnings": all_warnings,
    }
    report_path = out_dir / "ingest_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDone: {len(all_chapters)} chapters -> {chapters_path}")
    print(f"Chunks: {len(all_chunks)} -> {chunks_path}")
    print(f"Report -> {report_path}")
    if cont["missing"]:
        print(f"Missing chapters: {len(cont['missing'])} ({cont['missing'][:10]}...)")
    if merged_duplicates:
        print(f"Merged duplicate chapters (cross-file): {merged_duplicates}")
    if all_warnings:
        print(f"Total warnings: {len(all_warnings)}")


def main():
    parser = argparse.ArgumentParser(description="Ingest novel text files")
    parser.add_argument("--project", required=True, help="Project ID from config/projects.json")
    args = parser.parse_args()
    ingest(args.project)


if __name__ == "__main__":
    main()
