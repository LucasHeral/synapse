import os

import requests

api_key = os.getenv("HERMES_CUSTOM_ARTEFACT_GATEWAY_API_KEY")
print("API Key present:", bool(api_key))

url = "https://llmgateway.artechfact.fr/chat/completions"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

for model in ["claude-3-7-sonnet", "gpt-4o-mini", "claude-3-5-sonnet-20241022", "gemini-1.5-flash", "gpt-4o"]:
    payload = {"model": model, "messages": [{"role": "user", "content": "Dis bonjour."}], "max_tokens": 15}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        print(f"Model {model}: status {r.status_code}")
        if r.status_code == 200:
            print("  Output:", r.json()["choices"][0]["message"]["content"])
            break
    except Exception as e:
        print(f"Model {model} failed:", e)
