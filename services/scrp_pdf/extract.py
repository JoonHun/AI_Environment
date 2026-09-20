import re, html as h
doc = open('/tmp/page_dom.html', encoding='utf-8', errors='replace').read()

# find the editor block and page-frames
m = re.search(r'<div class="editor".*?(?=sd-next-page|</body>)', doc, re.S)
print("editor block found:", bool(m))

# Look for canvas/img inside pages
print("\ncanvas count:", len(re.findall(r'<canvas', doc)))
print("img count:", len(re.findall(r'<img', doc)))
imgs = re.findall(r'<img[^>]*src="([^"]+)"', doc)
for u in imgs[:20]:
    print("  img:", u[:120])

# Extract visible text from page-frame divs
frames = re.findall(r'class="page-frame[^"]*"', doc)
print("\npage-frame matches:", len(frames))

# grab text of .editor region
em = re.search(r'class="editor"', doc)
seg = doc[em.start():em.start()+40000] if em else ""
text = re.sub(r'<script.*?</script>', ' ', seg, flags=re.S)
text = re.sub(r'<style.*?</style>', ' ', text, flags=re.S)
text = re.sub(r'<[^>]+>', '\n', text)
text = h.unescape(text)
lines = [l.strip() for l in text.split('\n') if l.strip()]
print("\nTEXT LINES:", len(lines))
print("=== first 60 lines ===")
for l in lines[:60]:
    print(" ", l)
