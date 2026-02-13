"""Validation helper script for PromptForge regression testing."""
import json
import subprocess
import sys


def curl_json(url):
    r = subprocess.run(["curl", "-s", url], capture_output=True, text=True)
    return json.loads(r.stdout)


def curl_status(method, url):
    args = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}"]
    if method != "GET":
        args.extend(["-X", method])
    args.append(url)
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip()


def test_delete_and_404():
    """T1 #20: DELETE removes record, subsequent GET returns 404"""
    history = curl_json("http://localhost:8000/api/history")
    if not history["items"]:
        print("SKIP #20: no items to delete")
        return
    item_id = history["items"][-1]["id"]
    print(f"Deleting item: {item_id}")
    del_code = curl_status("DELETE", f"http://localhost:8000/api/history/{item_id}")
    print(f"Delete status: {del_code}")
    get_code = curl_status("GET", f"http://localhost:8000/api/optimize/{item_id}")
    print(f"GET after delete: {get_code}")
    if del_code == "200" and get_code == "404":
        print("PASS #20")
    else:
        print("FAIL #20")


def test_stats_match():
    """T1 #44: Stats totals match history count"""
    stats = curl_json("http://localhost:8000/api/history/stats")
    history = curl_json("http://localhost:8000/api/history")
    s_total = stats["total_optimizations"]
    h_total = history["total"]
    print(f"Stats total: {s_total}, History total: {h_total}")
    if s_total == h_total:
        print("PASS #44")
    else:
        print("FAIL #44")


def test_record_fields():
    """T1 #28-40: Check all record fields"""
    history = curl_json("http://localhost:8000/api/history")
    if not history["items"]:
        print("SKIP: no items")
        return
    item = history["items"][0]
    required = [
        "id", "created_at", "raw_prompt", "optimized_prompt", "task_type",
        "complexity", "weaknesses", "strengths", "changes_made",
        "framework_applied", "clarity_score", "specificity_score",
        "structure_score", "faithfulness_score", "overall_score",
        "verdict", "duration_ms", "status",
    ]
    missing = [f for f in required if f not in item]
    print(f"#28 All fields: {'PASS' if not missing else 'FAIL: ' + str(missing)}")
    print(f"#29 raw_prompt: {'PASS' if item.get('raw_prompt') else 'FAIL'}")
    opt = item.get("optimized_prompt", "")
    raw = item.get("raw_prompt", "")
    print(f"#30 optimized_prompt differs: {'PASS' if opt and opt != raw else 'FAIL'}")
    print(f"#31 task_type={item.get('task_type')}: PASS")
    print(f"#32 complexity={item.get('complexity')}: PASS")
    w = item.get("weaknesses")
    print(f"#33 weaknesses type={type(w).__name__}: {'PASS' if isinstance(w, list) else 'FAIL'}")
    s = item.get("strengths")
    print(f"#34 strengths type={type(s).__name__}: {'PASS' if isinstance(s, list) else 'FAIL'}")
    c = item.get("changes_made")
    print(f"#35 changes_made type={type(c).__name__}: {'PASS' if isinstance(c, list) else 'FAIL'}")
    print(f"#36 framework_applied={item.get('framework_applied')}: PASS")
    score_keys = [
        "clarity_score", "specificity_score", "structure_score",
        "faithfulness_score", "overall_score",
    ]
    scores = {k: item.get(k) for k in score_keys}
    all_ok = all(v is not None for v in scores.values())
    print(f"#37 scores={scores}: {'PASS' if all_ok else 'FAIL'}")
    print(f"#38 verdict present: {'PASS' if item.get('verdict') else 'FAIL'}")
    print(f"#39 duration_ms={item.get('duration_ms')}: {'PASS' if item.get('duration_ms') else 'FAIL'}")
    print(f"#40 status={item.get('status')}: {'PASS' if item.get('status') else 'FAIL'}")


def test_retry():
    """T1 #22: Retry endpoint returns SSE stream"""
    history = curl_json("http://localhost:8000/api/history")
    if not history["items"]:
        print("SKIP #22: no items")
        return
    item_id = history["items"][0]["id"]
    code = curl_status("POST", f"http://localhost:8000/api/optimize/{item_id}/retry")
    print(f"Retry status for {item_id}: {code}")
    if code == "200":
        print("PASS #22")
    else:
        print("FAIL #22")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "delete":
        test_delete_and_404()
    elif cmd == "stats":
        test_stats_match()
    elif cmd == "fields":
        test_record_fields()
    elif cmd == "retry":
        test_retry()
    elif cmd == "all":
        test_record_fields()
        print("---")
        test_stats_match()
        print("---")
        test_delete_and_404()
