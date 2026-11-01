import sys, os, csv, json, re
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

def main():
    repo_root = Path(__file__).resolve().parent.parent
    inv_path = repo_root / "EduSim_API" / "curriculum_pipeline" / "output" / "inventory" / "textbooks_inventory.csv"
    if not inv_path.exists():
        inv_path = repo_root / "curriculum_pipeline" / "output" / "inventory" / "textbooks_inventory.csv"

    meta_path = repo_root / "EduSim_API" / "faiss_index_v2" / "metadata.json"
    if not meta_path.exists():
        meta_path = repo_root / "faiss_index_v2" / "metadata.json"

    reports_dir = repo_root / "EduSim_API" / "curriculum_pipeline" / "output" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_csv = reports_dir / "index_coverage_audit.csv"

    books_dir = repo_root / "EduSim_API" / "curriculum_pipeline" / "output" / "curriculum" / "books"
    pages_dir = repo_root / "EduSim_API" / "curriculum_pipeline" / "output" / "pages"

    with open(inv_path, "r", encoding="utf-8-sig") as f:
        inv_rows = list(csv.DictReader(f))

    with open(meta_path, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    # Map source_pdf -> chunk_count
    chunk_counts = Counter(d.get("source_pdf") for d in meta_data if d.get("source_pdf"))

    # Map book_code -> extraction_status
    book_status = {}
    if books_dir.exists():
        for bf in books_dir.glob("*.json"):
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    bdata = json.load(f)
                    book_status[bf.stem] = bdata.get("extraction_status", "unknown")
            except Exception:
                pass

    audit_rows = []
    missing_ncert_reasons = Counter()
    missing_all_reasons = Counter()

    for r in inv_rows:
        fn = r["file"]
        board = (r.get("board") or "").strip().lower()
        lang = (r.get("language") or "").strip().lower()
        scan_note = (r.get("scan_note") or "").strip()
        dup = (r.get("duplicate_of") or "").strip()
        needs_ocr_raw = str(r.get("needs_ocr") or "").strip().lower()
        needs_ocr = needs_ocr_raw in ("true", "1", "yes")
        pages = int(r.get("pages") or 0)
        try:
            chars_pp = float(r.get("chars_per_page") or 0.0)
        except ValueError:
            chars_pp = 0.0

        count = chunk_counts.get(fn, 0)
        in_index = count > 0

        reason_missing = ""
        if not in_index:
            if dup:
                reason_missing = "duplicate_of"
            elif lang and lang != "en":
                reason_missing = "non-English-excluded"
            elif "not en" in scan_note.lower() or "not whitelisted" in scan_note.lower():
                reason_missing = "non-English-excluded"
            elif needs_ocr or (chars_pp < 50.0 and chars_pp > 0):
                reason_missing = "needs_ocr"
            else:
                m = re.match(r"^([a-z])([a-z])([a-z0-9]{2})(\d)", fn.lower())
                bcode = m.group(1) + m.group(2) + m.group(3) + m.group(4) if m else fn
                b_st = book_status.get(bcode)
                if b_st in ("needs_review", "failed", "skipped_legacy_encoding", "skipped_garbled", "ok"):
                    reason_missing = "extractor_failed"
                elif b_st is None:
                    reason_missing = "not_processed"
                else:
                    reason_missing = "extractor_failed"

            missing_all_reasons[reason_missing] += 1
            if board == "ncert":
                missing_ncert_reasons[reason_missing] += 1

        audit_rows.append({
            "file": fn,
            "in_index": in_index,
            "chunk_count": count,
            "pages": pages,
            "chars_per_page": round(chars_pp, 1),
            "needs_ocr": needs_ocr,
            "scan_note": scan_note,
            "reason_missing": reason_missing,
        })

    # Write output CSV
    fieldnames = [
        "file",
        "in_index",
        "chunk_count",
        "pages",
        "chars_per_page",
        "needs_ocr",
        "scan_note",
        "reason_missing",
    ]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    print(f"\nAudit CSV written to: {out_csv}")
    print("=" * 70)
    print("  SUMMARY: INDEX COVERAGE AUDIT")
    print("=" * 70)
    total_inv = len(inv_rows)
    total_in_index = sum(1 for r in audit_rows if r["in_index"])
    total_missing = sum(1 for r in audit_rows if not r["in_index"])
    ncert_total = sum(1 for r in inv_rows if r.get("board") == "ncert")
    ncert_in_index = sum(1 for r in audit_rows if r["in_index"] and r["file"] in {x["file"] for x in inv_rows if x.get("board") == "ncert"})
    ncert_missing_count = sum(missing_ncert_reasons.values())

    print(f"Total inventory PDFs    : {total_inv}")
    print(f"Total in FAISS index    : {total_in_index}")
    print(f"Total missing from index: {total_missing}")
    print(f"\nNCERT corpus total      : {ncert_total}")
    print(f"NCERT in index          : {ncert_in_index}")
    print(f"NCERT missing (71/72)   : {ncert_missing_count}")
    print("\nReason Breakdown for Missing NCERT PDFs:")
    for reason, c in missing_ncert_reasons.most_common():
        print(f"  - {reason:<22}: {c}")

    print("\nReason Breakdown for All Missing PDFs (NCERT + SSC):")
    for reason, c in missing_all_reasons.most_common():
        print(f"  - {reason:<22}: {c}")

    # Section 3: 1-Chunk PDFs Analysis
    print("\n" + "=" * 70)
    print("  1-CHUNK PDFs ANALYSIS (18 files)")
    print("=" * 70)
    one_chunk_pdfs = sorted([pdf for pdf, c in chunk_counts.items() if c == 1])
    inv_map = {r["file"]: r for r in inv_rows}

    for pdf in one_chunk_pdfs:
        chunk = next((d for d in meta_data if d.get("source_pdf") == pdf), {})
        inv_item = inv_map.get(pdf, {})
        p_count = inv_item.get("pages", "?")
        
        # Check extracted text from pages jsonl or chunk
        p_path = pages_dir / f"{pdf}.jsonl"
        extracted_chars = 0
        if p_path.exists():
            with open(p_path, "r", encoding="utf-8") as pf:
                for line in pf:
                    rec = json.loads(line)
                    if rec.get("type") != "metadata":
                        extracted_chars += len(rec.get("text", ""))
        else:
            extracted_chars = len(chunk.get("text", ""))

        text_preview = chunk.get("text", "").replace("\n", " ")[:200]
        tokens = chunk.get("token_count", "?")

        # Assessment: short-by-design vs failed
        nature = "short-by-design (Grade 1/2 poem/story)" if int(p_count) <= 9 and extracted_chars < 3000 else "check"

        print(f"\nPDF: {pdf} | Pages: {p_count} | Extracted Chars: {extracted_chars} | Tokens: {tokens} | Status: {nature}")
        print(f"  First 200 chars: \"{text_preview}\"")

if __name__ == "__main__":
    main()
