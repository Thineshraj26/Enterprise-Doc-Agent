import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
custom_timeout = httpx.Timeout(120.0, connect=10.0)

def safe_print_response(title, res):
    print(f"=== {title} ===")
    print("Status:", res.status_code)
    try:
        data = res.json()
        print("Answer:", data.get("answer"))
        print("Grounded:", data.get("is_grounded"))
        print("Chunks:", [c["id"] for c in data.get("citations", [])])
    except Exception:
        print("Raw Content:", res.text)
    print()

def run_matrix():
    with httpx.Client(base_url=BASE_URL, timeout=custom_timeout) as client:
        # 1. Engineering asks Engineering (Authorized)
        res1 = client.post(
            "/analyze",
            headers={"X-User-ID": "usr_eng_01", "X-User-Role": "engineering"},
            json={"question": "What is the throughput of the Kafka streaming pipeline?"}
        )
        safe_print_response("1. Engineering querying Cloud Specs (Authorized)", res1)

        # 2. Finance asks Engineering (Unauthorized)
        res2 = client.post(
            "/analyze",
            headers={"X-User-ID": "usr_fin_02", "X-User-Role": "finance"},
            json={"question": "What is the throughput of the Kafka streaming pipeline?"}
        )
        safe_print_response("2. Finance querying Cloud Specs (Unauthorized)", res2)

if __name__ == "__main__":
    run_matrix()