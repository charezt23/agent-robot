# fetch_search.py
import requests
import json
import os

BASE_URL = "http://localhost:8123"
THREADS_FILE = "threads.json"
ASSISTANTS_FILE = "assistants.json"

# Fetch threads dari /search (POST)
threads_payload = {
    "metadata": {},
    "graph_id": "app",
    "name": "",
    "limit": 100,
    "offset": 0,
    "sort_by": "thread_id",
    "sort_order": "asc",
    "select": ["thread_id"]
}
try:
    threads_response = requests.post(
        f"{BASE_URL}/threads/search",
        json=threads_payload,
        headers={"Content-Type": "application/json"}
    )
    threads_response.raise_for_status()
    threads_data = threads_response.json() if threads_response.text else []
except Exception as e:
    print(f"Error fetching threads: {e}")
    threads_data = []

# Fetch assistants dari /search (POST)
assistants_payload = {
    "metadata": {},
    "graph_id": "app",
    "name": "",
    "limit": 100,
    "offset": 0,
    "sort_by": "assistant_id",
    "sort_order": "asc",
    "select": ["assistant_id"]
}
try:
    assistants_response = requests.post(
        f"{BASE_URL}/assistants/search",
        json=assistants_payload,
        headers={"Content-Type": "application/json"}
    )
    assistants_response.raise_for_status()
    assistants_data = assistants_response.json() if assistants_response.text else []
except Exception as e:
    print(f"Error fetching assistants: {e}")
    assistants_data = []

# Parse threads - response langsung array
threads_list = []
if isinstance(threads_data, list):
    for thread in threads_data:
        if thread and "thread_id" in thread:
            threads_list.append({
                "thread_id": thread["thread_id"]
            })

# Parse assistants - response langsung array
assistants_list = []
if isinstance(assistants_data, list):
    for assistant in assistants_data:
        if assistant and "assistant_id" in assistant:
            assistants_list.append({
                "assistant_id": assistant["assistant_id"]
            })

# Simpan ke file terpisah
with open(THREADS_FILE, "w", encoding="utf-8") as f:
    json.dump(threads_list, f, indent=2, ensure_ascii=False)

with open(ASSISTANTS_FILE, "w", encoding="utf-8") as f:
    json.dump(assistants_list, f, indent=2, ensure_ascii=False)

print(f"✓ Data tersimpan:")
print(f"  - {len(threads_list)} threads → {THREADS_FILE}")
print(f"  - {len(assistants_list)} assistants → {ASSISTANTS_FILE}")

