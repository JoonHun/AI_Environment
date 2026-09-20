# Ollama model-name convention (GB10)

## User's naming scheme
`{name}_{paramsB}_{ctxK}_{quant}[_suffix]`, e.g.:
- `qwen3.8_27B_128K_Q4`
- `qwen3.8_27B_128K_Q4_MTP`
- `qwen3.6_35B_128K_Q4`

Ollama **auto-aliases** (`{name}:{paramsB}`) coexist as **separate entries** in `/api/tags`
but share the same binary. So the dashboard sees BOTH:
```
qwen3.6:35b
qwen3.6_35B_128K_Q4:latest
qwen3.8:27b
qwen3.8:27b-mtp-q4_K_M
qwen3.8:27b-mtp-q8_0
qwen3.8_27B_128K_Q4:latest
qwen3.8_27B_128K_Q4_MTP:latest
qwen3.8_27B_128K_Q8_MTP:latest
```

## Grouping rule (for the "Installed models" box)
**Family = the full token before the first `_` or `:`** (case-insensitive). This keeps
`qwen3.6` and `qwen3.8` as **separate families** while still grouping each with its aliases.

### Correct JS (`indexOf("_")` / first `_`)
```js
const groupKey = (name) => {
    const base = name.replace(/:.*$/, '');   // strip :tag
    const idx  = base.indexOf('_');
    return (idx > 0 ? base.slice(0, idx) : base).toLowerCase();
};
```

### WRONG (the bug we hit — do NOT use)
```js
// Stops at the non-word `.`, so qwen3.6 + qwen3.8 collapse into ONE wrong `qwen3` group
name.match(/^[a-zA-Z][a-zA-Z0-9]*/)[0]
```

### Render (per row)
Strip the family prefix from the displayed name so each row shows only the variant part:
```js
const displayName = m.name.startsWith(family)
    ? m.name.slice(family.length).replace(/^[_:]/, '')
    : m.name;
// "qwen3.8_27B_128K_Q4:latest" → "27B_128K_Q4:latest"
// "qwen3.8:27b"               → "27b"
```

## Verify your grouping (quick one-liner before touching the UI)
```bash
curl -s http://<ollama>/api/tags | python3 -c "
import sys,json
d=json.load(sys.stdin)
groups={}
for m in d.get('models',[]):
    base=m['name'].split(':')[0]
    i=base.find('_')
    k=base[:i] if i>0 else base
    groups.setdefault(k.lower(),[]).append(m['name'])
for k in sorted(groups):
    print(f'[{k}] {len(groups[k])}개')
"
```
Expected on GB10 (2026-08): `gemma4`=2, `llama3.3`=3, `muse-glimmer`=3, `qwen3.6`=2, `qwen3.8`=6.

## Suffix convention (2026-08, user-corrected)
Model suffixes after `{name}_{paramsB}_{ctxK}_{quant}` (e.g. `MTP`, and now `dflash`) **must
be preserved verbatim and always placed at the END of the custom name** — including when a
custom model is created from a base that already carries that suffix.

- Example (this is what bit us): base `muse-glimmer:30b-q8_0-dflash` — a custom 128K variant
  must be named `muse-glimmer_30B_128K_Q8_dflash`, **NOT** `muse-glimmer_30B_128K_Q8`.
  The Modelfile must match: `Modelfile.muse-glimmer_30B_128K_Q8_dflash`. The `_dflash` tag is
  a distinguishing feature of the base binary, not decoration — dropping it makes the model
  name ambiguous (indistinguishable from a non-dflash build) and is an explicit user correction,
  not a style preference.

So the rule generalizes to: `{name}_{paramsB}_{ctxK}_{quant}[_MTP][_dflash]` — both suffixes
allowed together, order preserved as in the base, and neither dropped.
