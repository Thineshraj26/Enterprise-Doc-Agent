import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
custom_timeout = httpx.Timeout(120.0, connect=10.0)

def safe_print_response(res):
    print("Status:", res.status_code)
    try:
        print("Payload:", res.json())
    except Exception:
        print("Raw Content:", res.text)
    print()

def run_api_suite():
    with httpx.Client(base_url=BASE_URL, timeout=custom_timeout) as client:
        print("--- 1. Testing Authorized Finance Query ---")
        res1 = client.post(
            "/analyze",
            headers={"X-User-ID": "usr_finance_42", "X-User-Role": "finance"},
            json={"question": "What is the targeted EBITDA guidance?"}
        )
        safe_print_response(res1)

        print("--- 2. Testing Cross-Department Unauthorized Query (Engineering asking Finance) ---")
        res2 = client.post(
            "/analyze",
            headers={"X-User-ID": "usr_eng_88", "X-User-Role": "engineering"},
            json={"question": "What is the targeted EBITDA guidance?"}
        )
        safe_print_response(res2)

        print("--- 3. Testing Audit Log Access Control (Unauthorized User) ---")
        res3 = client.get(
            "/audit/logs",
            headers={"X-User-Role": "engineering"}
        )
        safe_print_response(res3)

        print("--- 4. Testing Audit Log Access Control (Compliance Officer) ---")
        res4 = client.get(
            "/audit/logs?limit=3",
            headers={"X-User-Role": "auditor"}
        )
        safe_print_response(res4)
        if res4.status_code == 200:
            for entry in res4.json():
                print(f"[{entry['timestamp']}] User: {entry['user_id']} ({entry['user_role']}) | Chunks: {entry['accessed_chunk_ids']}")

if __name__ == "__main__":
    run_api_suite()