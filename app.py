import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez")

app = Flask(__name__)

# ── Lazy Gemini (Flask starts fast → Render detects port) ──
_client = None
_types = None
_init = False

def get_client():
    global _client, _types, _init
    if not _init:
        _init = True
        try:
            from google import genai as g
            from google.genai import types as t
            _types = t
            k = os.environ.get("GOOGLE_API_KEY")
            if k:
                _client = g.Client(api_key=k, http_options={"api_version": "v1beta"})
                logger.info("Monjez V6 ready")
        except Exception as e:
            logger.error(f"Init: {e}")
    return _client

def get_types():
    get_client()
    return _types

def call_gemini(model, contents, config, timeout):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        f = ex.submit(get_client().models.generate_content, model=model, contents=contents, config=config)
        return f.result(timeout=timeout)

def extract_json(text):
    try:
        m = re.search(r"\{.*\}", text.replace("\n", " "), re.DOTALL)
        if m: return json.loads(m.group(0))
    except: pass
    return {}


# ══════════════════════════════════════════════════════════
#  MAURITANIAN DOCUMENT STANDARDS
# ══════════════════════════════════════════════════════════
# 1 CSS point = 0.0353 cm → 1 cm = 28.35 pt
# 4.5 cm = 127.6 pt ≈ 128 pt (top margin for letterhead)
# 4.4 cm = 124.7 pt ≈ 125 pt (bottom margin for footer)
# These are for documents WITH letterhead/footer only.
# Documents WITHOUT letterhead: full page freedom.
# ══════════════════════════════════════════════════════════

LETTERHEAD_TOP_PT = 128    # 4.5 cm
LETTERHEAD_BOTTOM_PT = 125 # 4.4 cm


def get_style_prompt(style, mode):

    if mode == "resumes":
        return """=== RESUME / CV ===
Creative layout: sidebar, skill bars, icons, color accents.
Colors: navy #1e3a5f, teal #0d9488, charcoal #374151.
Sections: info, experience, education, skills, languages.
Make it visually impressive and professional."""

    if mode == "simulation":
        return """=== DOCUMENT CLONING ===
Reproduce EXACTLY the text, tables, structure from the reference image.
IGNORE: logos, stamps, signatures, watermarks, decorative images.
Focus ONLY on textual content and table structure.
Do NOT invent any data not visible in the image."""

    if style == "modern":
        return """=== MODERN STYLE ===
- Headers: color:#2563eb; font-weight:700;
- Tables: alternating rows (#f9fafb/white), border-bottom:1px solid #e5e7eb.
- Clean contemporary look.
- Accent colors allowed for headers and dividers."""

    # ── FORMAL STYLE (Default for Mauritania) ──
    return """=== FORMAL / OFFICIAL STYLE ===
Design like a skilled HUMAN designer in Mauritania. Professional, clean, elegant.

TYPOGRAPHY:
- Title: 16px bold, centered, margin-bottom:10px.
- Section headers: 13px bold, border-bottom:2px solid #333, padding-bottom:3px, margin:10px 0 6px.
- Body: 12px, line-height:1.5.
- Subtle <hr> (1px solid #ddd) between sections.

COLORS ALLOWED: #333, #555, #f7f7f7, #f0f0f0, #ddd, white ONLY. No bright colors.

GENERAL TABLE DESIGN:
- table: width:100%; border-collapse:collapse; border:1px solid #333;
- th: background:#333; color:white; padding:7px 8px; font-size:11px; font-weight:bold; text-align:right; border:1px solid #333;
- td: padding:6px 8px; font-size:11px; border:1px solid #ddd; text-align:right;
- Even rows: background:#f7f7f7;

=== MAURITANIAN INVOICE TABLE (Facture / فاتورة) ===
When designing invoices (فاتورة, facture, devis, عرض سعر, bon de commande):

COLUMN ORDER (right to left, Arabic direction):
| البيان / الوصف (50% width) | السعر | الكمية | الإجمالي |

TOTAL ROW STRUCTURE (CRITICAL):
The total row ("الإجمالي المستحق") is OUTSIDE the <tbody> in a <tfoot>.
- "الإجمالي المستحق" label spans 3 columns (colspan="3"), right-aligned, bold, border:1px solid #333.
- The total number is in the last column (الإجمالي), bold, border:1px solid #333, background:#f0f0f0.
- Example:
<tfoot>
  <tr>
    <td colspan="3" style="text-align:right; font-weight:bold; padding:8px; border:1px solid #333; font-size:12px;">الإجمالي المستحق</td>
    <td style="text-align:center; font-weight:bold; padding:8px; border:1px solid #333; background:#f0f0f0; font-size:12px;">461</td>
  </tr>
</tfoot>

AFTER THE TABLE:
Add the French closing line:
"Arrête la/le présent(e) facture/devis a la somme de : [AMOUNT IN WORDS] [CURRENCY]"
Style: font-size:11px; margin-top:10px; font-style:italic;

=== SMART CONTENT PLACEMENT ===
- If content is SHORT (small invoice, short letter): do NOT stick it to the top.
  Instead, add padding-top to push content to the upper-third area, leaving balanced whitespace.
  Use: padding-top: 5-15% of available height for short content.
- If content is MEDIUM: normal placement from top.
- If content is LONG: compact everything to fit.

=== FORMS / APPLICATIONS (استمارة) ===
When user provides raw unstructured text for a form:
- Identify field labels and organize them into a clean form layout.
- Use tables or grid with label:value pairs.
- Add input-style boxes: border:1px solid #999; min-height:24px; padding:4px;
- Think like a human designer: what would this form look like printed?

=== LETTERS (خطاب / رسالة) ===
- Date: top-left or top-right, font-size:11px.
- Recipient: right-aligned block.
- Subject line: centered, bold, underlined.
- Body: justified, 12px.
- Signature area: bottom-left, with space for stamp.

REMEMBER: Formal ≠ boring. It means NO colors but WITH good design, spacing, hierarchy, and professional layout."""


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V6"})


@app.route("/gemini", methods=["POST"])
def generate():
    if not get_client():
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get("message", "")
        width = int(data.get("width", 595))
        height = int(data.get("height", 842))
        mode = data.get("mode", "documents")
        style = data.get("style", "formal")
        has_letterhead = data.get("hasLetterhead", False)
        reference_b64 = data.get("reference_image")
        letterhead_b64 = data.get("letterhead_image")

        # ── MARGINS ──
        margin_side = int(width * 0.07)

        needs_letterhead_margins = has_letterhead or (letterhead_b64 is not None)

        if needs_letterhead_margins:
            # 4.5cm top, 4.4cm bottom for letterhead documents
            margin_top = LETTERHEAD_TOP_PT
            margin_bottom = LETTERHEAD_BOTTOM_PT
        else:
            # Free layout - minimal margins
            margin_top = int(height * 0.04)
            margin_bottom = int(height * 0.04)

        fo_x = margin_side
        fo_y = margin_top
        fo_w = width - (margin_side * 2)
        fo_h = height - margin_top - margin_bottom

        style_prompt = get_style_prompt(style, mode)

        # Letterhead SVG image tag
        letterhead_tag = ""
        if letterhead_b64:
            letterhead_tag = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMin slice"/>'

        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = "ATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        letterhead_note = ""
        if needs_letterhead_margins:
            letterhead_note = f"""
=== LETTERHEAD DOCUMENT ===
Top {margin_top}px (4.5cm) is RESERVED for the letterhead header. Do NOT place content there.
Bottom {margin_bottom}px (4.4cm) is RESERVED for footer/stamps. Do NOT place content there.
Your content area is ONLY {fo_h}px tall. Stay within it."""
        else:
            letterhead_note = f"""
=== NO LETTERHEAD ===
This document has NO letterhead. You have the FULL page to work with.
Content area: {fo_h}px tall. Use it freely with appropriate margins."""

        prompt = f"""You are a PROFESSIONAL document designer working in Mauritania.
You create production-ready documents that look like they were designed by an expert human.

{style_prompt}

{letterhead_note}

=== PAGE DIMENSIONS ===
Page: {width} x {height} pt.
Content foreignObject: x={fo_x} y={fo_y} w={fo_w} h={fo_h}.

=== FONT RULES ===
- Title: 16-18px bold max.
- Sections: 13px bold.
- Body: 12px.
- Tables: 11px.
- Notes: 10px.
- Font: Arial, Helvetica, sans-serif.
- NEVER exceed 18px.

=== CONTENT FITTING ===
ALL content MUST fit in {fo_h}px.
If long: reduce font (min 10px), reduce spacing. NEVER overflow.
viewBox MUST be "0 0 {width} {height}". NEVER extend or change it.

=== ANTI-HALLUCINATION (ABSOLUTE) ===
1. Format ONLY what the user wrote. NEVER invent content.
2. NEVER add greetings, dates, signatures, stamps, reference numbers unless user wrote them.
3. Minimal input = minimal document. Do NOT pad with fake content.
4. Be intelligent: detect document type from context (invoice, letter, form, etc.) and apply appropriate layout.

=== NO BACKGROUND RECTANGLES ===
NEVER add <rect> elements with white/opaque fill that could cover letterhead, stamps, or footer.
The SVG background is already white via style="background:white".
Do NOT add any covering elements. The foreignObject handles content containment.

{ref_note}

=== SVG OUTPUT ===
Return ONLY this SVG. No markdown, no backticks, no text before or after:

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:white">
{letterhead_tag}
<foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:12px; color:#111; line-height:1.5; direction:rtl; padding:6px; box-sizing:border-box; overflow:hidden;">
CONTENT_HERE
</div>
</foreignObject>
</svg>"""

        contents = [user_msg] if user_msg else ["Create a formal document."]
        if reference_b64:
            contents.append(get_types().Part.from_bytes(
                data=__import__('base64').b64decode(reference_b64),
                mime_type="image/jpeg"
            ))

        gen_config = get_types().GenerateContentConfig(
            system_instruction=prompt,
            temperature=0.2 if style == "formal" else 0.3,
            max_output_tokens=12000,
        )

        resp = None
        try:
            resp = call_gemini("gemini-2.5-flash", contents, gen_config, 55)
        except Exception as e:
            logger.warning(f"Primary fail: {e}")
            try:
                resp = call_gemini("gemini-2.0-flash", contents, gen_config, 50)
            except Exception as e2:
                return jsonify({"error": "AI failed", "details": str(e2)}), 500

        raw = (resp.text or "").strip()

        # Clean markdown
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            raw = raw.strip()

        # Extract SVG
        svg_m = re.search(r"(?s)(<svg[^>]*>.*?</svg>)", raw)
        if svg_m:
            svg = svg_m.group(1)
        else:
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:white">
{letterhead_tag}
<foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:12px; color:#111; line-height:1.5; direction:rtl; padding:6px; box-sizing:border-box; overflow:hidden;">
{raw}
</div>
</foreignObject>
</svg>'''

        # ── POST-PROCESSING ──

        # 1. Ensure xmlns
        if 'xmlns="http://www.w3.org/2000/svg"' not in svg:
            svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        # 2. FORCE single-page viewBox (NEVER let AI extend it)
        svg = re.sub(r'viewBox="[^"]*"', f'viewBox="0 0 {width} {height}"', svg)

        # 3. Force correct width/height on svg tag
        svg = re.sub(r'(<svg[^>]*?)width="[^"]*"', f'\\1width="{width}"', svg, count=1)
        svg = re.sub(r'(<svg[^>]*?)height="[^"]*"', f'\\1height="{height}"', svg, count=1)

        # 4. REMOVE all white/opaque rects that cover content
        svg = re.sub(
            r'<rect[^>]*(?:fill=["\'](?:white|#fff(?:fff)?|rgba?\(255[^)]*\))["\'])[^>]*/?>',
            '', svg, flags=re.IGNORECASE
        )

        # 5. Inject letterhead if provided but missing from SVG
        if letterhead_b64 and letterhead_tag and '<image' not in svg:
            svg = svg.replace('<foreignObject', f'{letterhead_tag}\n<foreignObject', 1)

        # 6. Cap foreignObject height to safe area
        def fix_fo(match):
            full = match.group(0)
            h_m = re.search(r'height="(\d+)"', full)
            if h_m:
                old_h = int(h_m.group(1))
                if old_h > fo_h:
                    full = full.replace(f'height="{old_h}"', f'height="{fo_h}"')
            return full
        svg = re.sub(r'<foreignObject[^>]*>', fix_fo, svg, count=1)

        logger.info(f"OK: mode={mode}, style={style}, lh={needs_letterhead_margins}, len={len(svg)}")
        return jsonify({"response": svg})

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


@app.route("/modify", methods=["POST"])
def modify():
    if not get_client():
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current = data.get("current_svg", "") or data.get("current_content", "")
        instruction = data.get("instruction", "")
        ref_b64 = data.get("reference_image")
        lh_b64 = data.get("letterhead_image")

        vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', current)
        w = int(vb.group(1)) if vb else 595
        h = int(vb.group(2)) if vb else 842

        img_note = ""
        if ref_b64:
            img_note = f"INSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        lh_note = ""
        if lh_b64:
            lh_note = f'Add letterhead: <image href="data:image/jpeg;base64,{lh_b64}" x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="xMidYMin slice"/>'

        sys = f"""Expert SVG document modifier for Mauritanian documents.

RULES:
1. Preserve ALL existing content. Apply ONLY the requested change.
2. Font: Arial. Body 12px, Title 16-18px max.
3. ALL content MUST remain visible. NEVER cut off or hide text.
4. viewBox MUST stay "0 0 {w} {h}". NEVER extend.
5. NEVER add white <rect> elements that cover letterhead or stamps.
6. Invoice totals: Mauritanian format - "الإجمالي المستحق" colspan 3, amount in last column only.
7. {img_note}
8. {lh_note}

Return JSON: {{"message": "وصف بالعربي", "response": "<svg>...</svg>"}}
No markdown."""

        cfg = get_types().GenerateContentConfig(
            system_instruction=sys, temperature=0.15, max_output_tokens=16384,
        )

        cts = [f"SVG:\n{current}\n\nREQUEST:\n{instruction}\n\nMODIFY:"]
        if ref_b64:
            cts.append(get_types().Part.from_bytes(
                data=__import__('base64').b64decode(ref_b64), mime_type="image/jpeg"
            ))

        resp = None
        try:
            resp = call_gemini("gemini-2.5-flash", cts, cfg, 55)
        except:
            resp = call_gemini("gemini-2.0-flash", cts, cfg, 50)

        raw = (resp.text or "").strip()
        rd = extract_json(raw)
        out = rd.get("response", "")
        msg = rd.get("message", "")

        if not out:
            cleaned = raw.replace("```svg", "").replace("```json", "").replace("```", "").strip()
            sm = re.search(r"(?s)(<svg[^>]*>.*?</svg>)", cleaned)
            out = sm.group(1) if sm else current
            msg = msg or "تم التعديل"

        # Force single page
        out = re.sub(r'viewBox="[^"]*"', f'viewBox="0 0 {w} {h}"', out)

        # Remove white rects
        out = re.sub(r'<rect[^>]*(?:fill=["\'](?:white|#fff(?:fff)?)["\'])[^>]*/?>',
                      '', out, flags=re.IGNORECASE)

        if out and 'xmlns="http://www.w3.org/2000/svg"' not in out:
            out = out.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        return jsonify({"response": out, "message": msg})

    except Exception as e:
        logger.error(f"Modify: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
