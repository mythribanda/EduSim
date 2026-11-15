import fitz
import sys

sys.stdout.reconfigure(encoding="utf-8")

def compare_toc():
    # 1. 8 English F
    f1 = "EduSim_API/textbooks/Text Books/8 English F 08.11.24.pdf"
    doc1 = fitz.open(f1)
    toc1 = doc1.get_toc()
    print("=== 8 English F 08.11.24.pdf ===")
    print(f"Total Pages: {len(doc1)}, ToC entries: {len(toc1)}")
    for item in toc1:
        lvl, title, page = item
        if lvl <= 2:
            print(f"  Level {lvl} | Page {page:3d} | {title}")

    # 2. 8 Maths EM
    f2 = "EduSim_API/textbooks/Text Books/8 Maths EM 2025-26 Final 08.11.24.pdf"
    doc2 = fitz.open(f2)
    toc2 = doc2.get_toc()
    print("\n=== 8 Maths EM 2025-26 Final 08.11.24.pdf ===")
    print(f"Total Pages: {len(doc2)}, ToC entries: {len(toc2)}")
    for item in toc2:
        lvl, title, page = item
        if lvl <= 2:
            print(f"  Level {lvl} | Page {page:3d} | {title}")

    # 3. Check all other SSC books for ToC presence
    import glob
    ssc_files = glob.glob("EduSim_API/textbooks/Text Books/*.pdf")
    print("\n=== ALL SSC WHOLE BOOKS TOC STATUS ===")
    for ssc_f in sorted(ssc_files):
        d = fitz.open(ssc_f)
        t = d.get_toc()
        fn = os.path.basename(ssc_f)
        print(f"  {fn[:40]:40} | ToC entries: {len(t):3d} | Pages: {len(d):3d}")
        d.close()

if __name__ == "__main__":
    import os
    compare_toc()
