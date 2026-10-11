import base64, json, sys, urllib.request

img = base64.b64encode(open(sys.argv[1], "rb").read()).decode()
body = json.dumps({
    "model": "gemma4-26b-a4b-mtp-q4_k_m",
    "messages": [{"role": "user", "content": [
        {"type": "text", "text": sys.argv[2] if len(sys.argv) > 2 else "설명해줘."},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
    ]}],
}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:11536/v1/chat/completions",
    data=body, headers={"Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req, timeout=600))
    print(r["choices"][0]["message"]["content"])
except Exception as e:
    print("ERR:", e)
