import json
import os
os.environ["STRETCH_PROFILE"] = "demo"
from fastapi.testclient import TestClient
import main as app_module

client = TestClient(app_module.app, raise_server_exceptions=False)

def run():
    print("=== E01 (Extraction) ===")
    text = "I have 500 dollars. I spend 20 a day. Aunt might give me 200 on Oct 15th. I have to pay 150 for electricity on Oct 12th."
    r = client.post("/api/setup/extract", json={"text": text})
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data.get("draft", data), indent=2))
        for t in data.get("trace", []):
            if t["step"].startswith("llm"):
                print("TIMING:", t)
    else:
        print(r.status_code, r.text)
    
    print("\nLoading demo situation...")
    r = client.post("/api/situation/demo")
    
    print("\n=== Q01 (In-scope plan) ===")
    r = client.post("/api/ask/plan", json={"question": "When do I run out of money if I don't get the aunt's money?"})
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data.get("plan", data), indent=2))
        print("Model:", data.get("model"))
    else:
        print(r.status_code, r.text)
    
    print("\n=== Q02 (Clarification) ===")
    r = client.post("/api/ask/plan", json={"question": "What if I buy a car?"})
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data.get("plan", data), indent=2))
        print("Model:", data.get("model"))
    else:
        print(r.status_code, r.text)
    
    print("\n=== X02 (Out of scope) ===")
    r = client.post("/api/ask/plan", json={"question": "Should I invest in crypto?"})
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data.get("plan", data), indent=2))
        print("Model:", data.get("model"))
    else:
        print(r.status_code, r.text)

if __name__ == "__main__":
    run()
