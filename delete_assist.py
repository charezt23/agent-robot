# delete_assist.py
import requests
import json
import os

BASE_URL = os.getenv("LANGGRAPH_URL", "http://localhost:8123")
THREADS_FILE = "threads.json"
ASSISTANTS_FILE = "assistants.json"

# Baca threads JSON
with open(THREADS_FILE, "r", encoding="utf-8") as f:
    threads = json.load(f)

# Baca assistants JSON
with open(ASSISTANTS_FILE, "r", encoding="utf-8") as f:
    assistants = json.load(f)

# Loop dan hapus threads
for thread in threads:
    thread_id = thread.get("thread_id")
    if thread_id:
        try:
            response = requests.delete(f"{BASE_URL}/threads/{thread_id}")
            if response.status_code in [200, 204]:
                print(f"✓ Deleted thread: {thread_id}")
            else:
                print(f"✗ Failed thread {thread_id}: {response.status_code}")
        except Exception as e:
            print(f"✗ Error thread {thread_id}: {e}")

# Loop dan hapus assistants
for assistant in assistants:
    assistant_id = assistant.get("assistant_id")
    if assistant_id:
        try:
            response = requests.delete(f"{BASE_URL}/assistants/{assistant_id}")
            if response.status_code in [200, 204]:
                print(f"✓ Deleted assistant: {assistant_id}")
            else:
                print(f"✗ Failed assistant {assistant_id}: {response.status_code}")
        except Exception as e:
            print(f"✗ Error assistant {assistant_id}: {e}")

print("Done!")
