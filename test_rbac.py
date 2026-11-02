from app.engine import query_agent

def run_rbac_tests():
    print("========================================")
    print("TEST 1: Finance Lead queries Q4 Financials")
    print("========================================")
    res1 = query_agent(
        user_id="usr_finance_01",
        user_role="finance",
        question="What were the operating margins and enterprise revenue?"
    )
    print(f"Answer: {res1['answer']}")
    print(f"Accessed Chunks: {[c['id'] for c in res1['citations']]}")
    print(f"Grounded: {res1.get('is_grounded')}\n")

    print("========================================")
    print("TEST 2: Engineering Lead queries Q4 Financials (UNAUTHORIZED)")
    print("========================================")
    res2 = query_agent(
        user_id="usr_eng_02",
        user_role="engineering",
        question="What were the operating margins and enterprise revenue?"
    )
    print(f"Answer: {res2['answer']}")
    print(f"Accessed Chunks: {[c['id'] for c in res2['citations']]}\n")

    print("========================================")
    print("TEST 3: Engineering Lead queries Cloud Infrastructure")
    print("========================================")
    res3 = query_agent(
        user_id="usr_eng_02",
        user_role="engineering",
        question="What is the event throughput of the streaming pipeline?"
    )
    print(f"Answer: {res3['answer']}")
    print(f"Accessed Chunks: {[c['id'] for c in res3['citations']]}")
    print(f"Grounded: {res3.get('is_grounded')}\n")

if __name__ == "__main__":
    run_rbac_tests()