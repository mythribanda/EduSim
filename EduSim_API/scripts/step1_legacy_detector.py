import os
import sys
import json
import fitz
import re
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

def analyze_legacy():
    manifest_path = "EduSim_API/data/manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    results = []
    flagged_files = []

    print(f"Scanning all {len(manifest)} manifest files for legacy encoding...")

    for entry in manifest:
        fpath = os.path.join("EduSim_API", entry["file_path"])
        if not os.path.exists(fpath):
            continue

        fn = os.path.basename(entry["file_path"])
        board = entry.get("board", "")
        subj = entry.get("subject", "")
        lang = entry.get("language", "en")
        
        try:
            doc = fitz.open(fpath)
        except Exception as e:
            continue

        total_chars = 0
        devanagari_chars = 0
        pua_chars = 0
        fffd_control_chars = 0
        extended_chars = 0 # Latin-1 supplement 0x80 to 0xFF excluding ASCII
        total_letters = 0

        # Scan up to first 10 pages for comprehensive signature
        for pno in range(min(10, len(doc))):
            t = doc[pno].get_text()
            for c in t:
                cp = ord(c)
                total_chars += 1
                if c.isalpha():
                    total_letters += 1
                if 0x0900 <= cp <= 0x097F:
                    devanagari_chars += 1
                elif 0xE000 <= cp <= 0xF8FF:
                    pua_chars += 1
                elif cp == 0xFFFD or (cp < 32 and c not in '\n\r\t'):
                    fffd_control_chars += 1
                elif 0x80 <= cp <= 0x024F:
                    extended_chars += 1

        doc.close()

        pct_dev = (devanagari_chars / total_letters * 100) if total_letters else 0
        pct_pua = (pua_chars / total_chars * 100) if total_chars else 0
        pct_fffd = (fffd_control_chars / total_chars * 100) if total_chars else 0
        pct_ext = (extended_chars / total_chars * 100) if total_chars else 0

        # Krutidev / ISM signature:
        # 1. Subject is Hindi/Sanskrit, but Devanagari share is < 30%
        # 2. Or high share of extended characters / legacy quotes / specific Krutidev danda patterns
        is_hindi_sanskrit = any(s in subj.lower() for s in ["hindi", "sanskrit"]) or lang in ["hi", "sa"]
        is_krutidev_signature = (
            (is_hindi_sanskrit and pct_dev < 30.0 and total_chars > 200) or
            (board == "SSC" and ("hindi" in fn.lower() or "tel" in fn.lower())) or
            (pct_ext > 15.0 and pct_dev < 10.0 and total_chars > 500)
        )

        reason = None
        if is_hindi_sanskrit and pct_dev < 30.0:
            reason = f"Hindi/Sanskrit subject but Devanagari letter share is {pct_dev:.1f}% (< 30%) - Legacy Krutidev/DV-TT font"
        elif board == "SSC" and "tel" in fn.lower():
            reason = f"Telugu-medium SSC book with legacy PUA/custom font ({pct_pua:.1f}% PUA)"
        elif board == "SSC" and "hindi" in fn.lower():
            reason = f"Hindi-medium SSC book with legacy Krutidev font ({pct_ext:.1f}% extended symbols)"

        item = {
            "file_name": fn,
            "board": board,
            "subject": subj,
            "language": lang,
            "total_chars": total_chars,
            "pct_devanagari": pct_dev,
            "pct_pua": pct_pua,
            "pct_fffd_control": pct_fffd,
            "pct_extended": pct_ext,
            "needs_ocr": is_krutidev_signature or entry.get("needs_ocr") is True,
            "reason": reason
        }
        results.append(item)

        if item["needs_ocr"]:
            flagged_files.append(item)

    # Save to data/evidence/legacy_encoding_report.json
    with open("EduSim_API/data/evidence/legacy_encoding_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Generate markdown table for flagged files
    md_lines = [
        "# Legacy-Encoding Detection & Flagged Files Audit\n",
        f"Total Files Scanned: {len(results)}\n",
        f"Total Flagged (`needs_ocr=True`): {len(flagged_files)}\n\n",
        "| File Name | Board | Subject | Dev % | PUA % | Ext % | Lang Corrected | Reason |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |"
    ]
    for ff in flagged_files:
        correct_lang = "hi" if "hindi" in ff["subject"].lower() or "hindi" in ff["file_name"].lower() else ("te" if "tel" in ff["file_name"].lower() else "sa")
        md_lines.append(
            f"| `{ff['file_name']}` | {ff['board']} | {ff['subject']} | {ff['pct_devanagari']:.1f}% | {ff['pct_pua']:.1f}% | {ff['pct_extended']:.1f}% | `{correct_lang}` | {ff['reason']} |"
        )

    with open("EduSim_API/data/evidence/legacy_flagged_audit.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"DONE: Flagged {len(flagged_files)} files.")
    print("Files flagged:")
    for ff in flagged_files:
        print(f"  {ff['file_name']:20} : {ff['reason']}")

if __name__ == "__main__":
    analyze_legacy()
