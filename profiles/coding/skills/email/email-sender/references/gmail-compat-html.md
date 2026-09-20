# Gmail-Compat HTML Email Bodies

Gmail strips most modern CSS/JS from user-composed HTML emails. If your HTML body renders as a
single-column page in a browser but shows up as a **jumbled multi-column mess** in Gmail, or if
**tab/accordion UIs don't react to clicks**, you hit this. Root causes + the table-based fix.

## Root causes (verified against a real research-brief page in 2026-08)

| Symptom in Gmail | Cause | Fix |
|---|---|---|
| Cards/items that are `display: flex; flex-direction: column` in a browser render **side-by-side** in Gmail | Gmail **ignores `display:flex` / `display:grid`** entirely. Flex siblings collapse to inline-flow, so multiple card divs line up horizontally. | Wrap each card in its own `<table role="presentation"><tr><td>…</td></tr></table>` and stack tables vertically. |
| Tabs/toggles that use `<script>addEventListener('click',…)` **do nothing** when clicked | Gmail **strips `<script>` blocks and all `on*=` inline handlers** from user-composed HTML bodies. The "hidden" section (`display:none` until a tab adds `active`) never reappears. | Drop tabs/toggles. Show **all sections consecutively** with a heading per section. |
| Layout looks fine in browser (or a preview pane) but breaks after paste | External `<style>` blocks are stripped; only **inline `style=""`** survives reliably. | Put every visual property on the element itself. |
| `class`-based styling disappears | No `<style>` block ⇒ class names are inert. | Same: inline everything. |
| Nested `display:none + .active{display:block}` pattern | Depends on the JS that Gmail deletes. | Replace with always-visible sections. |

## Golden rules for Gmail HTML bodies

1. **Layout = tables only.** Nested `<table role="presentation" cellpadding="0" cellspacing="0">`. One table per card, stacked in a column. No `display: flex/grid/inline-block` for layout.
2. **All styling inline** — no `<style>` block, no `class` (or at most as a fallback that is fully redundant).
3. **No JavaScript** — no `<script>`, no `onclick`, no `onload`.
4. **No interactive state** — tabs, accordions, dropdowns, `:hover`-only reveals, CSS `position: sticky`. Make content linear.
5. **`max-width` on the outer table** (e.g. `720px`) + `width:100%` wrapper table for responsive behavior. `width` attribute on the table as a pre-CSS fallback.
6. **`border-radius`** works in Gmail but is ignored in Outlook — keep it, don't depend on it.
7. **Jinja2 note:** if you build from a template, use `autoescape=True` and pass plain data; do not rely on `env.filters` for layout control.
8. **Footer auto-append:** many pipelines auto-append a bilingual AI disclaimer. Keep your own footer consistent with it (see `references/ai-email-disclaimer.md` if available in this profile).

## Known-good skeleton

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
       style="background:#f4f4f7; font-family:-apple-system, 'Segoe UI', Roboto, Arial, sans-serif;">
  <tr><td align="center" style="padding:24px 12px;">
    <table role="presentation" width="720" cellpadding="0" cellspacing="0"
           style="width:720px; max-width:100%; background:#fff; border-radius:10px; overflow:hidden;
                  border:1px solid #e3e6ec;">
      <!-- header row -->
      <tr><td style="padding:20px 28px; border-bottom:1px solid #e9ecef;">
        <h1 style="margin:0; font-size:20px;">{{ date }}</h1>
      </td></tr>
      <!-- one row per section; stack all sections vertically (no tabs) -->
      <tr><td style="padding:24px 28px;">
        <h2 style="margin:0 0 16px 0; font-size:16px; border-left:3px solid #2563eb;">Section A</h2>
        <!-- one card = one table -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="width:100%; border:1px solid #e2e5ea; border-radius:8px; margin-bottom:14px;">
          <tr><td style="padding:16px 18px;">
            <h3 style="margin:0 0 8px 0; font-size:15px;">Title</h3>
            <p style="margin:0 0 12px 0; font-size:14px; line-height:1.7;">Summary …</p>
            <a href="{{ url }}" style="color:#2563eb; text-decoration:none; font-size:12px;">Source</a>
          </td></tr>
        </table>
        <!-- more cards … -->
        <h2 style="margin:24px 0 16px 0; font-size:16px; border-left:3px solid #2563eb;">Section B</h2>
        <!-- … -->
      </td></tr>
      <tr><td style="padding:14px 28px 18px; border-top:1px solid #e9ecef; font-size:11px;
                     color:#a2a7b3; text-align:center;">*AI-generated.*</td></tr>
    </table>
  </td></tr>
</table>
```

## Quick diagnostic checklist (run after first email renders wrong in Gmail)

1. Grep the generated HTML for `display:flex`, `display:grid`, `<script`, `onclick=`,
   `position:sticky`, `<style>` — all must be **0**.
2. Verify every card is inside its own `<table>`.
3. Verify all sections are rendered (no `display:none` gating a section).
4. If a tabbed browser page was the source: **re-render with a separate email-friendly template**
   (see `~/.hermes/services/research/html_render.py` for a working Jinja2 + table-based example),
   don't try to "fix" the browser template to also work in email.
