import httpx

base = "http://localhost:8001"

def test():
    # 1. Classes
    r = httpx.get(f"{base}/api/curriculum/classes")
    print("Classes status:", r.status_code)
    classes = r.json()
    print("Classes count:", len(classes))
    for c in classes[:3]:
        print("  Class:", c.get("id"), c.get("name"))

    if not classes:
        print("No classes found!")
        return

    first_cls = classes[0]["id"]

    # 2. Subjects
    r = httpx.get(f"{base}/api/curriculum/classes/{first_cls}/subjects")
    print(f"Subjects for class {first_cls} status:", r.status_code)
    subjects = r.json()
    print("Subjects count:", len(subjects))
    for s in subjects[:3]:
        print("  Subject:", s.get("id"), s.get("name"))

    if not subjects:
        print("No subjects found!")
        return

    first_subj = subjects[0]["id"]

    # 3. Chapters
    r = httpx.get(f"{base}/api/curriculum/classes/{first_cls}/subjects/{first_subj}/chapters")
    print(f"Chapters for class {first_cls}, subj {first_subj} status:", r.status_code)
    chapters = r.json()
    print("Chapters count:", len(chapters))
    for ch in chapters[:3]:
        print("  Chapter:", ch.get("name") if isinstance(ch, dict) else ch)

    if not chapters:
        print("No chapters found!")
        return

    first_ch = chapters[0]["name"] if isinstance(chapters[0], dict) else chapters[0]

    # 4. Topics
    r = httpx.get(f"{base}/api/curriculum/classes/{first_cls}/subjects/{first_subj}/chapters/{first_ch}/topics")
    print(f"Topics status:", r.status_code)
    topics = r.json()
    print("Topics count:", len(topics))
    for t in topics[:3]:
        print("  Topic:", t.get("name") if isinstance(t, dict) else t)

test()
