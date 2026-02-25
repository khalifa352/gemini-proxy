import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# MONJEZ DOCUMENT ENGINE V5.0
# ──────────────────────────────────────────────────────
# FIXES:
# 1. Font too big → enforced 13px body, proper size hierarchy
# 2. A4 not actual size → strict viewBox 595x842
# 3. Content overflows page → strict content area with overflow hidden
# 4. Letterhead not showing → reserved top space when hasLetterhead=true
# 5. Multi-page → real second SVG page (new foreignObject)
# ======================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez_V5")

app = Flask(__name__)

# Lazy-load Gemini client (so Flask starts FAST and Render detects the port)
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
                logger.info("Monjez Engine V5 ready (lazy init)")
            else:
                logger.warning("GOOGLE_API_KEY missing")
        except Exception as e:
            logger.error(f"Gemini init error: {e}")
    return _client

def get_types():
    get_client()  # ensure initialized
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
        return """RESUME: Creative CV with sidebar, skill bars, color accents.
Colors: navy #1e3a5f, teal #0d9488, charcoal #374151.
Use sections: personal info, experience, education, skills."""

    if mode == "simulation":
        return """CLONING: Copy EXACTLY the text/tables from the reference image.
IGNORE logos, stamps, signatures, decorative images.
Focus ONLY on text content and table structure. Do NOT invent data."""

    if style == "modern":
        return """MODERN: Accent colors on headers (#2563eb), subtle backgrounds.
Tables: alternating rows (#f9fafb/white), border-bottom: 1px solid #e5e7eb.
Clean contemporary look."""

    return """FORMAL: Black text, white background, NO colors except #f5f5f5 headers.
Tables: CLOSED borders ALL sides, 1px solid #333.
Invoice totals: put in <tfoot> inside SAME table (not separate).
Perfect for: invoices, contracts, official letters, purchase orders."""


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez Engine V5.0"})


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

        # Fixed margins
        margin_side = int(width * 0.07)
        margin_bottom = int(height * 0.06)

        if has_letterhead or letterhead_b64:
            margin_top = int(height * 0.15)
        else:
            margin_top = int(height * 0.06)

        fo_x = margin_side
        fo_y = margin_top
        fo_w = width - (margin_side * 2)
        fo_h = height - margin_top - margin_bottom

        style_instructions = get_style_instructions(style, mode)

        # Build letterhead injection
        letterhead_svg = ""
        if letterhead_b64:
            letterhead_svg = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMin slice" opacity="1"/>'

        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = """You have a reference image attached. Insert it using:
<img src="data:image/jpeg;base64,..." style="max-width:80%; height:auto; margin:8px auto; display:block; border-radius:4px;" />"""

        sys_prompt = f"""You are a PRECISE document designer. Output ONLY valid SVG code.

=== STYLE ===
{style_instructions}

=== CRITICAL SIZE RULES ===
The page is {width}x{height} points (A4).
Content area: x={fo_x}, y={fo_y}, width={fo_w}, height={fo_h}.

FONT SIZES (STRICT - never exceed these):
- Title/Main header: 18px maximum, font-weight: bold
- Section headers: 14px, font-weight: bold
- Body text: 12-13px, font-weight: normal
- Table cells: 11-12px
- Small notes/footer: 10px
- NEVER use font-size above 20px for anything

LINE HEIGHT: 1.5 for body, 1.3 for tables.

=== LETTERHEAD ===
{"Top " + str(margin_top) + "px is RESERVED for letterhead. Do NOT put any content there." if (has_letterhead or letterhead_b64) else "Leave top 6% as clean margin."}

=== ANTI-HALLUCINATION ===
1. Format ONLY what the user wrote. NEVER invent greetings, dates, signatures, reference numbers.
2. If user gives minimal text, create a minimal document. Do NOT pad with fake content.
3. For simulation mode: clone ONLY visible text from the image.

=== TABLES ===
- width:100%; table-layout:fixed; border-collapse:collapse;
- th,td: padding:5px 7px; font-size:11px; border:1px solid #333;
- th: background:#f5f5f5; font-weight:bold;
- Totals: use <tfoot> inside the SAME <table>, not a separate element.

{ref_note}

=== PAGINATION ===
If ALL content fits in {fo_h}px, use ONE foreignObject.
If content is too long:
- First try reducing font slightly (min 10px body).
- If still too long: extend viewBox to "0 0 {width} {height * 2}" and add a SECOND foreignObject at y="{height}" with same width/margins.
- NEVER hide or cut content.

=== OUTPUT FORMAT ===
Return ONLY this SVG structure. No markdown, no backticks, no explanation:

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:white">
{letterhead_svg}
<foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:13px; color:#111; line-height:1.5; direction:rtl; padding:10px; box-sizing:border-box; overflow:hidden;">
YOUR_CONTENT_HERE
</div>
</foreignObject>
</svg>
"""

        contents = []
        if user_msg:
            contents.append(user_msg)
        else:
            contents.append("Create a simple formal document.")

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
            logger.warning(f"Primary failed: {e}, trying fallback...")
            try:
                response = call_gemini("gemini-2.0-flash", contents, gen_config, 50.0)
            except Exception as e2:
                logger.error(f"Both models failed: {e2}")
                return jsonify({"error": "AI generation failed", "details": str(e2)}), 500

        raw = response.text or ""

        # Clean markdown wrapping
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            raw = raw.strip()

        # Extract SVG
        svg_match = re.search(r"(?s)(<svg[^>]*>.*?</svg>)", raw)
        if svg_match:
            final_svg = svg_match.group(1)
        else:
            # Wrap raw content in SVG if AI didn't
            final_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:white">
{letterhead_svg}
<foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:13px; color:#111; line-height:1.5; direction:rtl; padding:10px; box-sizing:border-box;">
{raw}
</div>
</foreignObject>
</svg>'''

        # Ensure xmlns
        if 'xmlns="http://www.w3.org/2000/svg"' not in final_svg:
            final_svg = final_svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        # Inject letterhead if provided but not already in SVG
        if letterhead_b64 and 'letterhead' not in final_svg.lower() and letterhead_svg:
            if '<foreignObject' in final_svg:
                final_svg = final_svg.replace(
                    '<foreignObject',
                    f'{letterhead_svg}\n<foreignObject',
                    1
                )

        # Remove any white background rects that cover content
        final_svg = re.sub(
            r'<rect[^>]*fill=["\'](?:white|#fff(?:fff)?)["\'][^>]*/?>',
            '',
            final_svg,
            flags=re.IGNORECASE
        )

        logger.info(f"Generated OK: mode={mode}, style={style}, len={len(final_svg)}")

        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"Generate error: {str(e)}", exc_info=True)
        return jsonify({"error": "Generation failed", "details": str(e)}), 500


@app.route("/modify", methods=["POST"])
def modify():
    if not get_client():
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_svg = data.get("current_svg", "") or data.get("current_content", "") or data.get("current_html", "")
        instruction = data.get("instruction", "")
        reference_b64 = data.get("reference_image")
        letterhead_b64 = data.get("letterhead_image")

        # Parse dimensions from existing SVG
        vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        width = int(vb.group(1)) if vb else 595
        height = int(vb.group(2)) if vb else 842

        image_note = ""
        if reference_b64:
            image_note = f'INSERT this image: <img src="data:image/jpeg;base64,{reference_b64}" style="max-width:80%; height:auto; margin:8px auto; display:block; border-radius:4px;" />'

        letterhead_note = ""
        if letterhead_b64:
            lh_tag = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMin slice"/>'
            letterhead_note = f"Add this letterhead as first element inside <svg>: {lh_tag}"

        system_prompt = f"""You are an expert SVG document modifier.

RULES:
1. PRESERVE all existing content and structure.
2. Apply ONLY the user's requested change.
3. Font: Arial, Helvetica, sans-serif. Body: 12-13px max. Title: 18px max.
4. ALL content must remain visible. NEVER cut off text.
5. Tables: totals in <tfoot> inside same table.
6. {image_note}
7. {letterhead_note}

RESPONSE: Return valid JSON:
{{"message": "وصف التعديل", "response": "<svg>...SVG...</svg>"}}

No markdown. Just JSON."""

        gen_config = get_types().GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.15,
            max_output_tokens=16384,
        )

        contents = [f"CURRENT SVG:\n{current_svg}\n\nREQUEST:\n{instruction}\n\nMODIFY:"]
        if reference_b64:
            contents.append(get_types().Part.from_bytes(
                data=__import__('base64').b64decode(reference_b64),
                mime_type="image/jpeg"
            ))

        response = None
        try:
            response = call_gemini("gemini-2.5-flash", contents, gen_config, 55.0)
        except Exception as e:
            logger.warning(f"Modify primary failed: {e}")
            response = call_gemini("gemini-2.0-flash", contents, gen_config, 50.0)

        raw_text = response.text or ""

        # Try JSON parse first
        result_data = extract_safe_json(raw_text)
        svg_out = result_data.get("response", "")
        message = result_data.get("message", "")

        # Fallback: extract SVG directly
        if not svg_out:
            cleaned = raw_text.replace("```svg", "").replace("```json", "").replace("```", "").strip()
            svg_match = re.search(r"(?s)(<svg[^>]*>.*?</svg>)", cleaned)
            if svg_match:
                svg_out = svg_match.group(1)
            else:
                svg_out = current_svg  # Return original if all fails
            message = message or "تم التعديل"

        # Ensure xmlns
        if svg_out and 'xmlns="http://www.w3.org/2000/svg"' not in svg_out:
            svg_out = svg_out.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

        logger.info("Modify OK")
        return jsonify({"response": svg_out, "message": message})

    except Exception as e:
        logger.error(f"Modify error: {str(e)}", exc_info=True)
        return jsonify({"error": "Modification failed", "details": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
