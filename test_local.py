import subprocess
import time
import sys
import os

project_dir = r"C:\Users\Hoan\Desktop\lark-coze-middleware"
python_exe = os.path.join(project_dir, "venv", "Scripts", "python.exe")

# Start uvicorn
proc = subprocess.Popen(
    [python_exe, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=project_dir,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

time.sleep(3)

try:
    import requests

    # Test root
    r0 = requests.get("http://127.0.0.1:8000/", timeout=5)
    print("Root:", r0.status_code, r0.json())

    # Test health
    r1 = requests.get("http://127.0.0.1:8000/health", timeout=5)
    print("Health check:", r1.status_code, r1.json())

    # Test Lark URL verification challenge
    r2 = requests.post(
        "http://127.0.0.1:8000/webhook",
        json={"type": "url_verification", "challenge": "12345"},
        timeout=5
    )
    print("Challenge response:", r2.status_code, r2.json())

    if r0.status_code == 200 and r1.status_code == 200 and r2.status_code == 200 and r2.json().get("challenge") == "12345":
        print("\n[OK] Local test passed!")
    else:
        print("\n[ERROR] Test failed")
        sys.exit(1)

except Exception as e:
    print(f"\n[ERROR] Error during test: {e}")
    sys.exit(1)

finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Server stopped")
