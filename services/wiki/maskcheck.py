import importlib.util as u, sys
from pathlib import Path

spec = u.from_file_location("wiki_server", "server.py")
m = u.module_from_spec(spec)
spec.loader.exec_module(m)

# Build a corpus from real rendered pages + source docs; count what the
# masker reports as still-leaking. We intentionally do NOT embed secret
# strings here; we detect them by shape (long hex / password-ish).
targets = list(Path("services/documents").glob("*.md"))
corpus = "\n".join(p.read_text(errors="ignore") for p in targets)

# Simulate: strip each known credential line and check patterns catch them.
samples = [
    "BASIC_AUTH_PASSWORD=abcdef123456",
    "BASIC_