import json, time, urllib.request, websocket

# List open targets on the running headless Chrome
targets = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
print("targets:")
for t in targets:
    print(" ", t.get('type'), "|", t.get('title'), "|", t.get('url')[:90])

# Use the about:blank tab (or first page tab)
page = next((t for t in targets if t.get('type') == 'page'), None)
if not page:
    # create new tab
    t = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/new?about:blank", data=b'', method='PUT'))
    page = t
    print("created:", t['id'])

ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=120)
mid = [0]
def cmd(method, **params):
    mid[0] += 1
    ws.send(json.dumps({'id': mid[0], 'method': method, 'params': params}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == mid[0]:
            return m

URL = "https://view.chunjae.co.kr/streamdocs/view/sd;streamdocsId=Bg15FHYoXyKEheqrLbIL5FtYY7OomHoAYFmtAJP7vAk;isExternal=eQ;printUse=;enableDapSide=;pageView="

cmd('Network.enable')
cmd('Network.setExtraHTTPHeaders', headers=[{'name':'Accept','value':'*/*'}])
print("navigating...")
nav = cmd('Page.navigate', url=URL)
print("nav result:", nav)

# Collect responses for ~25s
import time
reqs = []
start = time.time()
end = start + 25
while time.time() < end:
    try:
        ws.settimeout(0.5)
        m = json.loads(ws.recv())
    except Exception:
        m = None
    if m and m.get('method') == 'Network.responseReceived':
        r = m['params']['response']
        u = r.get('url','')
        ct = r.get('mimeType','')
        reqs.append((r.get('status'), m['params']['requestId'], u, ct))

print("\n=== responses ===")
for st, rid, u, ct in reqs:
    interesting = any(k in u.lower() for k in ['pdf','doc','page','content','stream','blob','image','api','streamdocsId','image'])
    print(f"{st} {ct:20s} {u[:130]}")

# Save full list
import json as J
open('/tmp/reqs.json','w').write(J.dumps(reqs, ensure_ascii=False))
ws.close()
