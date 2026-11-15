import json

with open("retrieval_metrics_report.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("Failed / Missed P@1 Cases in retrieval_metrics_report.json:\n")
for lang, stats in data.get("languages", {}).items():
    print(f"=== {lang.upper()} (Total: {stats.get('total_queries')}, P@1: {stats.get('precision@1')}) ===")
    for q in stats.get("per_query_details", []):
        if not q.get("p@1_hit"):
            print(f"Query: {q.get('query')}")
            print(f"  Expected Subject: {q.get('expected_subject')}, Detected Subject: {q.get('detected_subject')}")
            print(f"  Expected Chapter: {q.get('expected_chapter')}")
            print(f"  Top Score: {q.get('top_score')}")
            print(f"  Top Result: Book: {q.get('top_book')}, Ch: {q.get('top_chapter')}")
            print(f"  P@5 Hit: {q.get('p@5_hit')}, Reciprocal Rank: {q.get('reciprocal_rank')}")
            print("-" * 50)
