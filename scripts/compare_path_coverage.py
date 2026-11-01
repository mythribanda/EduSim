import json
from pathlib import Path
from collections import defaultdict

repo_root = Path(__file__).resolve().parent.parent
api_root = repo_root / "EduSim_API"
before_report_path = api_root / "curriculum_pipeline" / "output" / "reports" / "path_coverage_report.json"
chunks_dir = api_root / "curriculum_pipeline" / "output" / "chunks"

with open(before_report_path, "r", encoding="utf-8") as f:
    before_data = json.load(f)

before_subjects = before_data.get("subject_summaries", {})

# Scan current chunks
after_stats = defaultdict(lambda: {"total": 0, "with_path": 0, "missing": 0})
total_after = 0
with_path_after = 0

for cfile in chunks_dir.glob("*.jsonl"):
    with open(cfile, "r", encoding="utf-8") as cf:
        for line in cf:
            if not line.strip():
                continue
            c = json.loads(line)
            subj = str(c.get("subject") or "unknown").strip().lower()
            p = c.get("topic_subtopic_path")
            total_after += 1
            after_stats[subj]["total"] += 1
            if p:
                with_path_after += 1
                after_stats[subj]["with_path"] += 1
            else:
                after_stats[subj]["missing"] += 1

print("\n" + "=" * 92)
print(f"{'SUBJECT':<20} | {'BEFORE (Path / Total)':<23} | {'AFTER (Path / Total)':<23} | {'COVERAGE GAIN':<15}")
print("=" * 92)

all_subjs = sorted(set(list(before_subjects.keys()) + list(after_stats.keys())))

total_before_tot = before_data.get("total_chunks", 0)
total_before_with = before_data.get("with_path", 0)

for s in all_subjs:
    b_info = before_subjects.get(s, {"total_chunks": 0, "with_path": 0, "coverage_pct": 0.0})
    b_tot = b_info.get("total_chunks", 0)
    b_with = b_info.get("with_path", 0)
    b_pct = b_info.get("coverage_pct", (b_with / b_tot * 100) if b_tot else 0.0)

    a_info = after_stats.get(s, {"total": 0, "with_path": 0, "missing": 0})
    a_tot = a_info["total"]
    a_with = a_info["with_path"]
    a_pct = (a_with / a_tot * 100) if a_tot else 0.0

    diff_pct = a_pct - b_pct
    gain_str = f"+{diff_pct:+.1f}%"
    if b_pct == 0 and a_pct == 0:
        gain_str = "0.0%"

    b_str = f"{b_with:>5} / {b_tot:<5} ({b_pct:>5.1f}%)"
    a_str = f"{a_with:>5} / {a_tot:<5} ({a_pct:>5.1f}%)"

    print(f"{s:<20} | {b_str:<23} | {a_str:<23} | {gain_str:<15}")

print("-" * 92)
b_tot_pct = (total_before_with / total_before_tot * 100) if total_before_tot else 0.0
a_tot_pct = (with_path_after / total_after * 100) if total_after else 0.0
tot_diff = a_tot_pct - b_tot_pct
tot_b_str = f"{total_before_with:>5} / {total_before_tot:<5} ({b_tot_pct:>5.1f}%)"
tot_a_str = f"{with_path_after:>5} / {total_after:<5} ({a_tot_pct:>5.1f}%)"
tot_gain_str = f"{tot_diff:+.1f}% (+{with_path_after - total_before_with} chunks)"
print(f"{'OVERALL TOTAL':<20} | {tot_b_str:<23} | {tot_a_str:<23} | {tot_gain_str:<15}")
print("=" * 92)
