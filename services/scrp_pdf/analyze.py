import re, collections
html = open('/tmp/page_dom.html', encoding='utf-8', errors='replace').read()
print("TOTAL BYTES:", len(html))

# Korean chars present?
korean = re.findall(r'[\uac00-\ud7a3]{2,}', html)
print("KOR runs:", len(korean))
print("KOR sample:", korean[:20])

# visible body-ish containers
for kw in ['content','editor','doc-text','page','viewer','canvas','print-view','sd-print']:
    hits = re.findall(r'class="[^"]*' + kw + r'[^"]*"', html)
    if hits:
        c = collections.Counter(hits)
        print(f"\n[{kw}]", c.most_common(5))

# api / pdf hints
print("\n=== pdf/print/api hints ===")
for m in sorted(set(re.findall(r'(?:pdf|print|/api/|export|download)[^"\'<>]{0,50}', html, re.I))):
    print(" ", m[:80])

# any visible text in <td>/<p>/<div> with words
print("\n=== <title>", re.findall(r'<title>(.*?)</title>', html))
