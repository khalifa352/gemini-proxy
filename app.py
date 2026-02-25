import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez")

app = Flask(__name__)

_client = None
_genai = None
_types = None
_initialized = False

def get_client():
    global _client, _genai, _types, _initialized
    if not _initialized:
        _initialized = True
        try:
            from google import genai as _g
            from google.genai import types as _t
            _genai = _g
            _types = _t
            API_KEY = os.environ.get("GOOGLE_API_KEY")
            if API_KEY:
                _client = _g.Client(api_key=API_KEY, http_options={"api_version": "v1beta"})
                logger.info("Monjez V5.1 ready")
            else:
                logger.warning("GOOGLE_API_KEY missing")
        except Exception as e:
            logger.error(f"Gemini init error: {e}")
    return _client

def get_types():
    get_client()
    return _types

def call_gemini(model_name, contents, config, timeout_sec):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            get_client().models.generate_content,
            model=model_name, contents=contents, config=config,
        )
        return future.result(timeout=timeout_sec)

def extract_safe_json(text):
    try:
        match = re.search(r"\{.*\}", text.replace("\n", " "), re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    return {}

def get_style_instructions(style, mode):
    if mode == "resumes":
        return """RESUME / CV:
- Creative layout: sidebar, skill bars, icons, color accents.
- Colors: navy #1e3a5f, teal #0d9488, charcoal #374151.
- Sections: personal info, experience, education, skills."""

    if mode == "simulation":
        return """CLONING MODE:
- Reproduce EXACTLY the text/tables from the reference image.
- IGNORE logos, stamps, signatures, decorative images.
- Do NOT invent any data."""

    if style == "modern":
        return """MODERN:
- Headers: color:#2563eb; font-weight:700;
- Tables: alternating rows (#f9fafb/white), border-bottom:1px solid #e5e7eb.
- Clean contemporary look with visual hierarchy."""

    return """FORMAL / OFFICIAL - PROFESSIONAL DOCUMENT DESIGN:

DESIGN PHILOSOPHY: Like a skilled human designer. Clean, elegant, well-spaced.

TYPOGRAPHY & SPACING:
- Title: font-size:16px; font-weight:bold; text-align:center; margin-bottom:12px;
- Section headers: font-size:13px; font-weight:bold; border-bottom:2px solid #333; padding-bottom:3px; margin:10px 0 6px 0;
- Body: font-size:12px; line-height:1.5;
- Use horizontal rules (<hr style="border:none; border-top:1px solid #ddd; margin:8px 0;">) between major sections.
- Good spacing between elements (margin: 6-10px).

TABLE DESIGN (elegant professional tables):
- table: width:100%; border-collapse:collapse; margin:8px 0;
- th: background:#333; color:white; padding:7px 8px; font-size:11px; font-weight:bold; text-align:right; border:1px solid #333;
- td: padding:6px 8px; font-size:11px; border:1px solid #ddd; text-align:right;
- Alternating rows: even rows background:#f7f7f7;
- Clean look with dark header and light body.

INVOICE TOTAL ROW (CRITICAL):
- Use <tfoot> INSIDE the same <table>.
- Total cells should ONLY appear under the numeric columns.
- Description/item columns in tfoot: <td style="border:none; background:none;"></td>
- Total label + amount cells: <td style="font-weight:bold; background:#f0f0f0; border:1px solid #333; padding:7px 8px;">
- Example for 4-column table [بيان, وصف, كمية, سعر]:
  <tfoot><tr>
    <td style="border:none;"></td>
    <td style="border:none;"></td>
    <td style="font-weight:bold; background:#f0f0f0; border:1px solid #333; text-align:right; padding:7px;">المجموع</td>
    <td style="font-weight:bold; background:#f0f0f0; border:1px solid #333; text-align:right; padding:7px;">1500 ر.س</td>
  </tr></tfoot>
- NEVER span the total across the full table width.

COLORS ALLOWED: #333, #f7f7f7, #f0f0f0, #ddd, white only. NO bright colors."""


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V5.1"})


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

        margin_side = int(width * 0.07)
        margin_bottom = int(height * 0.15)

        if has_letterhead or letterhead_b64:
            margin_top = int(height * 0.15)
        else:
            margin_top = int(height * 0.06)

        fo_x = margin_side
        fo_y = margin_top
        fo_w = width - (margin_side * 2)
        fo_h = height - margin_top - margin_bottom

        style_instructions = get_style_instructions(style, mode)

        letterhead_svg = ""
        if letterhead_b64:
            letterhead_svg = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMin slice" opacity="1"/>'

        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = "ATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        sys_prompt = f"""You are a PROFESSIONAL document designer creating production-ready documents.

=== STYLE ===
{style_instructions}

=== PAGE LAYOUT (ABSOLUTE RULES) ===
Page: {width} x {height} points.
Content zone: x={fo_x} y={fo_y} w={fo_w} h={fo_h}.
Bottom {margin_bottom}px ({int(margin_bottom/height*100)}%) is RESERVED for stamps/signatures/footer. NEVER put content there.
{"Top " + str(margin_top) + "px RESERVED for letterhead. Start content below." if (has_letterhead or letterhead_b64) else ""}

=== FONT SIZES ===
- Title: 16-18px bold (max)
- Sections: 13px bold
- Body: 12px normal
- Tables: 11px
- Notes: 10px
- NEVER exceed 18px anywhere.
- Font: Arial, Helvetica, sans-serif.

=== CONTENT FITTING (MOST IMPORTANT RULE) ===
Content MUST fit in {fo_h}px height. Strategies:
1. Short content → normal sizes, generous spacing.
2. Medium content → normal sizes, tighter spacing.
3. Long content → reduce to 11px body, 10px tables, minimal margins.
4. Very long → 10px everything, 1px padding, compress.
ABSOLUTE: NEVER overflow. NEVER extend viewBox beyond {width}x{height}.
Better to have slightly smaller text than to LOSE any user content.

=== ANTI-HALLUCINATION ===
Format ONLY user's text. NEVER invent greetings, dates, signatures, stamps, reference numbers.
Minimal input = minimal document.

{ref_note}

=== OUTPUT (SVG only, no markdown) ===
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:white">
{letterhead_svg}
<foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:12px; color:#111; line-height:1.5; direction:rtl; padding:6px; box-sizing:border-box; overflow:hidden; height:{fo_h}px;">
CONTENT
</div>
</foreignObject>
</svg>"""

        contents = [user_msg] if user_msg else ["Create a simple formal document."]
        if reference_b64:
            contents.append(get_types().Part.from_bytes(
                data=__import__('base64').b64decode(reference_b64),
                mime_type="image/jpeg"
            ))

        gen_config = get_types().GenerateContentConfig(
            system_instruction=sys_prompt,
            temperature=0.2 if style == "formal" else 0.3,
            max_output_tokens=12000,
        )

        response = None
        try:
            response = call_gemini("gemini-2.5-flash", contents, gen_config, 55.0)
        except Exception as e:
            logger.warning(f"Primary failed: {e}")
            try:
                response = call_gemini("gemini-2.0-flash", contents, gen_config, 50.0)
            except Exception as e2:
                return jsonify({"error": "AI failed", "details": str(e2)}), 500

        raw = response.text or ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            raw = raw.strip()

        svg_match = re.search(r"(?s)(<svg[^>]*>.*?</svg>)", raw)
        if svg_match:
            final_svg = svg_match.group(1)
        else:
            final_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:white">
{letterhead_svg}
<foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:12px; color:#111; line-height:1.5; direction:rtl; padding:6px; box-sizing:border-box; overflow:hidden;">
{raw}
</div>
</foreignObject>
</svg>'''

        # Post-processing
        if 'xmlns="http://www.w3.org/2000/svg"' not in final_svg:
            final_svg = final_svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        # FORCE single page dimensions
        final_svg = re.sub(r'viewBox="0 0 \d+ \d+"', f'viewBox="0 0 {width} {height}"', final_svg)
        # Fix width/height on <svg> tag only (first occurrence)
        final_svg = re.sub(r'(<svg[^>]*?)width="\d+"', f'\\1width="{width}"', final_svg, count=1)
        final_svg = re.sub(r'(<svg[^>]*?)height="\d+"', f'\\1height="{height}"', final_svg, count=1)

        # Inject letterhead if missing
        if letterhead_b64 and letterhead_svg and '<image' not in final_svg:
            if '<foreignObject' in final_svg:
                final_svg = final_svg.replace('<foreignObject', f'{letterhead_svg}\n<foreignObject', 1)

        # Cap foreignObject height
        def cap_fo_height(m):
            h_val = int(m.group(1))
            return f'height="{min(h_val, fo_h)}"'
        final_svg = re.sub(r'(<foreignObject[^>]*?)height="(\d+)"',
                           lambda m: m.group(0).replace(f'height="{m.group(2)}"', f'height="{min(int(m.group(2)), fo_h)}"'),
                           final_svg, count=1)

        # Remove covering white rects
        final_svg = re.sub(r'<rect[^>]*fill=["\'](?:white|#fff(?:fff)?)["\'][^>]*/?>',
                           '', final_svg, flags=re.IGNORECASE)

        logger.info(f"OK: mode={mode}, style={style}, len={len(final_svg)}")
        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


@app.route("/modify", methods=["POST"])
def modify():
    if not get_client():
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_svg = data.get("current_svg", "") or data.get("current_content", "")
        instruction = data.get("instruction", "")
        reference_b64 = data.get("reference_image")
        letterhead_b64 = data.get("letterhead_image")

        vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        width = int(vb.group(1)) if vb else 595
        height = int(vb.group(2)) if vb else 842

        image_note = ""
        if reference_b64:
            image_note = f"INSERT image: <img src='data:image/jpeg;base64,{reference_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        lh_note = ""
        if letterhead_b64:
            lh_note = f'Add letterhead: <image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMin slice"/>'

        system_prompt = f"""Expert SVG modifier.
RULES:
1. Preserve all content. Apply ONLY requested change.
2. Font: Arial. Body 12px, Title 16-18px max.
3. ALL content visible. NEVER cut off.
4. viewBox stays "0 0 {width} {height}". NEVER extend.
5. Bottom 15% reserved for stamps/footer.
6. Invoice totals: <tfoot>, only under number columns.
7. {image_note}
8. {lh_note}
Return JSON: {{"message": "وصف", "response": "<svg>...</svg>"}}"""

        gen_config = get_types().GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.15,
            max_output_tokens=16384,
        )

        contents = [f"SVG:\n{current_svg}\n\nREQUEST:\n{instruction}\n\nMODIFY:"]
        if reference_b64:
            contents.append(get_types().Part.from_bytes(
                data=__import__('base64').b64decode(reference_b64), mime_type="image/jpeg"
            ))

        response = None
        try:
            response = call_gemini("gemini-2.5-flash", contents, gen_config, 55.0)
        except Exception as e:
            logger.warning(f"Modify fail: {e}")
            response = call_gemini("gemini-2.0-flash", contents, gen_config, 50.0)

        raw_text = response.text or ""
        result_data = extract_safe_json(raw_text)
        svg_out = result_data.get("response", "")
        message = result_data.get("message", "")

        if not svg_out:
            cleaned = raw_text.replace("```svg", "").replace("```json", "").replace("```", "").strip()
            svg_match = re.search(r"(?s)(<svg[^>]*>.*?</svg>)", cleaned)
            svg_out = svg_match.group(1) if svg_match else current_svg
            message = message or "تم التعديل"

        svg_out = re.sub(r'viewBox="0 0 \d+ \d+"', f'viewBox="0 0 {width} {height}"', svg_out)
        if svg_out and 'xmlns="http://www.w3.org/2000/svg"' not in svg_out:
            svg_out = svg_out.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        return jsonify({"response": svg_out, "message": message})

    except Exception as e:
        logger.error(f"Modify error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
