import os
import json
import glob
import fitz
from collections import defaultdict

def run_checks():
    manifest_path = "EduSim_API/data/manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. PUA SCAN (fast font check on NCERT files)
    ncert_entries = [e for e in manifest if e["board"] == "NCERT"]
    pua_files = []
    font_pua_counts = defaultdict(int)

    for entry in ncert_entries:
        fpath = os.path.join("EduSim_API", entry["file_path"])
        if not os.path.exists(fpath):
            continue
        doc = fitz.open(fpath)
        file_pua = 0
        file_fonts = set()
        for page in doc:
            # fast span iteration
            d = page.get_text("dict")
            for b in d.get("blocks", []):
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        text = s["text"]
                        font = s["font"]
                        p = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
                        if p > 0:
                            file_pua += p
                            file_fonts.add(font)
                            font_pua_counts[font] += p
        doc.close()
        if file_pua > 0:
            pua_files.append({
                "file": os.path.basename(entry["file_path"]),
                "count": file_pua,
                "fonts": list(file_fonts)
            })

    pua_files.sort(key=lambda x: x["count"], reverse=True)
    with open("EduSim_API/data/pua_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "total_ncert": len(ncert_entries),
            "total_pua_files": len(pua_files),
            "files": pua_files,
            "fonts": dict(font_pua_counts)
        }, f, indent=2)

    print("PUA SCAN COMPLETE:")
    print(f"Total NCERT files with PUA: {len(pua_files)} / {len(ncert_entries)}")

if __name__ == "__main__":
    run_checks()
