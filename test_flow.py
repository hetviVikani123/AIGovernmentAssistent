"""Full diagnostic test of the Government Schemes Bot."""
import requests
import json
import sys

BASE = "http://localhost:8000"

def send(phone, message):
    r = requests.post(f"{BASE}/test", json={"phone": phone, "message": message}, timeout=15)
    data = r.json()
    resp = data.get("bot_response", data.get("error", "NO RESPONSE"))
    print(f"\n{'='*60}")
    print(f"USER ({phone}): {message}")
    print(f"BOT : {resp[:300]}")
    print(f"{'='*60}")
    return resp

def test_chat():
    """Test the /api/chat endpoint."""
    print("\n\n>>> TESTING /api/chat ENDPOINT <<<")
    try:
        r = requests.post(f"{BASE}/api/chat", json={
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello in one sentence."}
            ]
        }, timeout=30, stream=True)
        print(f"Status: {r.status_code}")
        full = ""
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    parsed = json.loads(data)
                    full += parsed.get("content", "")
                except:
                    full += data
        print(f"Chat response: {full[:200]}")
    except Exception as e:
        print(f"Chat ERROR: {e}")

def test_health():
    print("\n>>> TESTING /health <<<")
    r = requests.get(f"{BASE}/health")
    print(f"Status: {r.status_code}, Body: {r.json()}")

def test_root():
    print("\n>>> TESTING / (root) <<<")
    r = requests.get(BASE)
    print(f"Status: {r.status_code}, Content-Type: {r.headers.get('content-type')}")
    print(f"Starts with: {r.text[:100]}")

# Full conversation flow test
print("="*60)
print("GOVERNMENT SCHEMES BOT - FULL DIAGNOSTIC")
print("="*60)

test_health()
test_root()

phone = "test_diag_001"

# Step 0: Reset
print("\n\n>>> STEP 0: RESET <<<")
send(phone, "restart")

# Step 1: Say hi (should trigger welcome)
print("\n>>> STEP 1: GREETING <<<")
resp = send(phone, "hi")
if "Student" not in resp:
    print("!!! BUG: 'hi' should show welcome + category selection")

# Step 2: Pick category 
print("\n>>> STEP 2: CATEGORY <<<")
resp = send(phone, "1")
if "income" not in resp.lower():
    print("!!! BUG: Picking category '1' should ask about income")

# Step 3: Pick income
print("\n>>> STEP 3: INCOME <<<")
resp = send(phone, "1")
if "state" not in resp.lower():
    print("!!! BUG: Picking income '1' should ask about state")

# Step 4: Enter state
print("\n>>> STEP 4: STATE <<<")
resp = send(phone, "maharashtra")
if "special" not in resp.lower() and "category" not in resp.lower():
    print("!!! BUG: Entering state should ask about special category")

# Step 5: Pick special category (None)
print("\n>>> STEP 5: SPECIAL CATEGORY <<<")
resp = send(phone, "1")
if "scheme" not in resp.lower() and "found" not in resp.lower():
    print("!!! BUG: Should show matched schemes")

# Step 6: Pick first scheme for details
print("\n>>> STEP 6: SCHEME DETAIL <<<")
resp = send(phone, "1")
if "apply" not in resp.lower() and "benefit" not in resp.lower():
    print("!!! BUG: Should show scheme details")

# Test the Chat endpoint
test_chat()

print("\n\n>>> ALL TESTS COMPLETE <<<")
