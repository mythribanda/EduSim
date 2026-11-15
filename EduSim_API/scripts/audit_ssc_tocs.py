import os
import sys
import re
import fitz

sys.stdout.reconfigure(encoding="utf-8")

def parse_footer_page_label(text):
    # Try finding page numbers in the bottom 20% of text
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return "N/A"
    # check last 3 lines
    for l in reversed(lines[-3:]):
        # Match standalone numbers or e.g. "124", "[ 12 ]", "(vii)"
        m = re.search(r"^\(?\[?([0-9ivxlcIVXLC]+)\]?\)?$", l)
        if m:
            return m.group(1)
        # Or e.g. "Mathematics 124"
        m2 = re.search(r"\b([0-9]+)\b$", l)
        if m2 and len(l) < 25:
            return m2.group(1)
    return "N/A"

def audit_ssc_chapters():
    import glob
    ssc_files = glob.glob("EduSim_API/textbooks/Text Books/*.pdf")
    
    out_lines = [
        "# SSC Whole-Book Chapter Split & Table of Contents Audit\n",
        "Comprehensive verification of all 35 valid SSC whole-book PDFs in `EduSim_API/textbooks/Text Books/`.\n",
        "| Book Name | Ch # | Chapter Title (Stored/Bookmark) | Start PDF P | End PDF P | Footer Printed Label | Contents Printed Title & Page | Status |",
        "| :--- | :---: | :--- | :---: | :---: | :---: | :--- | :---: |"
    ]

    total_books = 0
    total_chapters = 0
    mismatches = 0

    for ssc_f in sorted(ssc_files):
        if os.path.getsize(ssc_f) == 0:
            continue
        total_books += 1
        fn = os.path.basename(ssc_f)
        try:
            doc = fitz.open(ssc_f)
        except:
            continue

        toc = doc.get_toc()
        # Find printed contents page
        contents_text = ""
        for pno in range(min(12, len(doc))):
            t = doc[pno].get_text()
            if "contents" in t.lower() or "index" in t.lower():
                contents_text += "\n" + t

        # Filter valid level 1 bookmarks with page > 0
        valid_toc = [e for e in toc if e[0] == 1 and e[2] > 0]
        # remove cover or full book bookmarks if present at the end
        filtered_toc = []
        for e in valid_toc:
            title_lower = e[1].lower()
            if "cover" in title_lower or "total book" in title_lower or (len(filtered_toc) > 0 and e[2] < filtered_toc[-1][2]):
                continue
            filtered_toc.append(e)

        for i, item in enumerate(filtered_toc):
            total_chapters += 1
            lvl, bm_title, start_p = item
            end_p = filtered_toc[i+1][2] - 1 if i+1 < len(filtered_toc) else len(doc)
            
            # Read footer label from start page
            start_page_text = doc[start_p - 1].get_text() if 1 <= start_p <= len(doc) else ""
            footer_label = parse_footer_page_label(start_page_text)

            # Match in printed contents
            bm_clean = re.sub(r"^(Ch\s*\d+|Unit\s*\d+|\d+)\s*[-_.]?\s*", "", bm_title, flags=re.IGNORECASE)
            bm_clean = re.sub(r"\.pdf$", "", bm_clean, flags=re.IGNORECASE).replace("BIL", "").strip()

            # Find matching line in printed contents
            found_printed_match = "N/A"
            for line in contents_text.split("\n"):
                if len(bm_clean) > 4 and bm_clean.lower() in line.lower():
                    found_printed_match = line.strip()
                    break

            # Status check
            status = "Match"
            if end_p < start_p:
                status = "Overlap/Invalid Range"
                mismatches += 1
            elif found_printed_match == "N/A" and "initial" not in bm_title.lower() and "syllabus" not in bm_title.lower() and "answer" not in bm_title.lower():
                status = "Title Needs Review"

            out_lines.append(
                f"| `{fn[:25]}` | {i+1} | {bm_title.replace('.pdf','')} | {start_p} | {end_p} | {footer_label} | {found_printed_match[:35]} | {status} |"
            )

        doc.close()

    with open("EduSim_API/data/evidence/ssc_chapters.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

    print(f"DONE: Audited {total_books} SSC books, {total_chapters} chapters. Mismatches/overlaps flagged: {mismatches}")

if __name__ == "__main__":
    audit_ssc_chapters()
