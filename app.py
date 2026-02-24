import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# MONJEZ DOCUMENT ENGINE V3.0
# - Real multi-page pagination (separate foreignObjects)
# - Font: Arial for formal documents
# - Style: formal (classic) + modern only
# - hasLetterhead flag (no base64 sent from client)
# - AI notes system for user feedback
# - Content visibility fixes (footer text not cut off)
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Monjez_V3")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1beta"})
        logger.info("Monjez Engine V3 connected")
    else:
        logger.warning("GOOGLE_API_KEY is missing.")
except Exception as e:
    logger.error(f"Gemini init error: {e}")


def extract_safe_json(text):
    try:
        match = re.search(r"\{.*\}", text.replace("\n", " "), re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    return {}


def ensure_svg_namespaces(svg_code):
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_code:
        svg_code = svg_code.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if "xmlns:xhtml" not in svg_code and "<foreignObject" in svg_code:
        svg_code = svg_code.replace(
            "<foreignObject",
            '<foreignObject xmlns:xhtml="http://www.w3.org/1999/xhtml"',
            1,
        )
    return svg_code


def clean_white_backgrounds(svg_code):
    svg_code = re.sub(
        r'<rect[^>]*fill=["\'](?:white|#FFF|#ffffff|#fff|#FFFFFF)["\'][^>]*>',
        "",
        svg_code,
    )
    svg_code = svg_code.replace("background-color: white;", "background-color: transparent;")
    svg_code = svg_code.replace("background: white;", "background: transparent;")
    return svg_code


def calculate_margins(width, height, has_letterhead):
    margin_left = int(width * 0.06)
    margin_right = int(width * 0.06)
    margin_bottom = int(height * 0.08)
    margin_top = int(height * 0.14) if has_letterhead else int(height * 0.06)

    return {
        "x": margin_left,
        "y": margin_top,
        "width": width - margin_left - margin_right,
        "height": height - margin_top - margin_bottom,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom,
    }


def call_gemini(model_name, contents, config, timeout_sec):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.models.generate_content,
            model=model_name,
            contents=contents,
            config=config,
        )
        return future.result(timeout=timeout_sec)


def get_style_prompt(style, mode):
    if mode == "resumes":
        return """
=== RESUME DESIGN ===
- Creative, modern CV layout with sidebars and color accents.
- Use professional colors (navy, teal, charcoal).
- Skill bars, icons, clear section headers.
- Font: Arial, Helvetica, sans-serif.
- STRICT: width: 100%; box-sizing: border-box;
"""

    if mode == "simulation":
        return """
=== DOCUMENT CLONING ===
- Mirror the EXACT text, tables, and structure from the image.
- IGNORE logos, stamps, signatures, decorative images.
- Focus ONLY on textual content and table structure.
- Do NOT invent or add any data not visible in the image.
- Font: Arial, Helvetica, sans-serif.
- Tables: width: 100%; table-layout: fixed; border-collapse: collapse;
"""

    if style == "modern":
        return """
=== MODERN STYLE ===
- Professional colors: accent headers, subtle colored backgrounds.
- Tables: alternating row colors, no heavy borders, clean look.
- Dividers, colored section headers, visual hierarchy.
- Font: Arial, Helvetica, sans-serif.
- Table: width:100%; border-collapse:collapse; border:none;
- Cell: padding:10px 12px; font-size:13px; border-bottom:1px solid #e0e0e0;
- Headers: color:#2563EB; font-weight:700;
"""

    # Default: formal (classic official documents)
    return """
=== FORMAL STYLE (Official Documents) ===
- STRICT FORMAL: Black text, transparent background, no colors.
- Tables: CLOSED borders, 1px solid #333, clean professional cells.
- Mix of rounded and sharp corners allowed for variety.
- Clear size hierarchy: title 18px bold, subtitle 14px, body 12px.
- NO decorative elements, NO colored backgrounds.
- Perfect for: invoices, official letters, contracts, purchase orders.
- Font: Arial, Helvetica, sans-serif.
- Table: width:100%; table-layout:fixed; border-collapse:collapse; border:1px solid #333;
- Cell: padding:6px 8px; font-size:12px; border:1px solid #333;
- Header cells: font-weight:bold; background-color:#f5f5f5;
"""


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez Engine V3.0 Online"})


@app.route("/gemini", methods=["POST"])
def generate():
    if not client:
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

        margins = calculate_margins(width, height, has_letterhead)
        fo_x, fo_y = margins["x"], margins["y"]
        fo_w, fo_h = margins["width"], margins["height"]

        style_prompt = get_style_prompt(style, mode)

        letterhead_note = ""
        if has_letterhead:
            letterhead_note = f"""
=== LETTERHEAD ACTIVE ===
- Top {margins['margin_top']}px is RESERVED for letterhead (added by client).
- Start ALL content below y={margins['margin_top']}px.
- NO logos, NO header decorations. Content only.
- Background MUST be transparent.
"""
        else:
            letterhead_note = """
=== NO LETTERHEAD ===
- Full page available. Leave 8% bottom for signatures/stamps.
- Always leave top 6% margin for clean spacing.
"""

        ref_instruction = ""
        if reference_b64 and mode != "simulation":
            ref_instruction = f"""
=== EMBEDDED IMAGE ===
- Insert: <img src="data:image/jpeg;base64,{reference_b64}" style="max-width:100%; height:auto; border-radius:4px; margin:10px 0;" />
"""

        pagination_rules = f"""
=== CRITICAL: CONTENT VISIBILITY & PAGINATION ===
1. ALL content MUST be visible. Nothing should be cut off or hidden.
2. Available height per page: {fo_h}px.
3. If content fits in one page but text near bottom might be cut:
   - Slightly reduce font size (minimum 10px, never smaller).
   - Reduce padding/margins slightly.
4. If content STILL does not fit after adjustments:
   - Extend viewBox height to {height * 2} (for 2 pages) or {height * 3} (for 3).
   - Create a NEW <foreignObject> for page 2 at y="{height}" with width="{fo_w}" height="{fo_h}".
   - Each page is INDEPENDENT with its own foreignObject.
   - NEVER stretch a single page. Create real separate pages.
5. NEVER hide or truncate any content the user provided.
6. If you create multiple pages, include this in your note.

=== RESPONSE FORMAT ===
Return ONLY valid SVG code. No markdown, no backticks, no explanation.
"""

        anti_hallucination = """
=== ANTI-HALLUCINATION ===
1. Format ONLY the text/data provided by the user.
2. NEVER invent greetings, dates, reference numbers, signatures, stamps.
3. NEVER add "Dear Sir" or salutations unless the user wrote them.
4. If user gives minimal input, create a minimal document.
5. Do NOT add any decorative text or placeholder content.
"""

        sys_prompt = f"""ROLE: Master Document Designer.

{style_prompt}
{letterhead_note}
{ref_instruction}
{anti_hallucination}
{pagination_rules}

SVG STRUCTURE:
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
    <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
        <div xmlns="http://www.w3.org/1999/xhtml" style="width:100%; box-sizing:border-box; padding:15px; background:transparent; direction:rtl; font-family:Arial, Helvetica, sans-serif; color:#111; line-height:1.6; font-size:13px;">
            [CONTENT]
        </div>
    </foreignObject>
</svg>
"""

        contents = [user_msg] if user_msg else ["Create a simple formal document."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        gen_config = types.GenerateContentConfig(
            system_instruction=sys_prompt,
            temperature=0.2 if style == "formal" else 0.35,
            max_output_tokens=12000,
        )

        response = None
        try:
            response = call_gemini("gemini-2.5-flash", contents, gen_config, 50.0)
        except Exception as e:
            logger.warning(f"Primary model failed: {e}")
            response = call_gemini("gemini-2.0-flash", contents, gen_config, 45.0)

        raw_text = response.text or ""

        svg_match = re.search(r"(?s)<svg[^>]*>.*?</svg>", raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        final_svg = clean_white_backgrounds(final_svg)
        final_svg = ensure_svg_namespaces(final_svg)

        # Detect if multi-page was created
        note = ""
        fo_count = final_svg.count("<foreignObject")
        if fo_count > 1:
            note = f"النص طويل، تم توزيعه على {fo_count} صفحات. يمكنك طلب حشر المحتوى في صفحة واحدة إن أردت."

        # Check if viewBox was extended
        vb_match = re.search(r'viewBox="0 0 (\d+) (\d+)"', final_svg)
        if vb_match:
            vb_height = int(vb_match.group(2))
            if vb_height > height:
                pages = (vb_height + height - 1) // height
                if not note:
                    note = f"تم إنشاء {pages} صفحات لاستيعاب كامل المحتوى."

        logger.info(f"Generated (mode={mode}, style={style}, pages={fo_count})")

        result = {"response": final_svg}
        if note:
            result["note"] = note

        return jsonify(result)

    except Exception as e:
        logger.error(f"Generate error: {str(e)}", exc_info=True)
        return jsonify({"error": "Document generation failed", "details": str(e)}), 500


@app.route("/modify", methods=["POST"])
def modify():
    if not client:
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_svg = data.get("current_html", "") or data.get("current_svg", "")
        instruction = data.get("instruction", "")
        reference_b64 = data.get("reference_image")

        width_match = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        width = int(width_match.group(1)) if width_match else 595
        base_height = int(width_match.group(2)) if width_match else 842

        # Use single page height for margin calculation
        page_height = min(base_height, 842)
        margins = calculate_margins(width, page_height, False)
        fo_x, fo_y = margins["x"], margins["y"]
        fo_w, fo_h = margins["width"], margins["height"]

        image_instruction = ""
        if reference_b64:
            image_instruction = (
                "INSERT THIS IMAGE: "
                f'<img src="data:image/jpeg;base64,{reference_b64}" '
                'style="max-width:100%; height:auto; margin:10px 0; border-radius:4px;" />'
            )

        system_prompt = f"""ROLE: Expert Document Modifier.

RULES:
1. PRESERVE all existing content and structure.
2. Apply ONLY the requested change.
3. Font: Arial, Helvetica, sans-serif.
4. ALL content must remain visible after modification.
5. If content exceeds page height ({fo_h}px):
   - Create new page: extend viewBox, add new foreignObject at y={page_height}.
   - NEVER shrink text below 10px. Create pages instead.
6. {image_instruction}

RESPONSE FORMAT - JSON:
{{
    "message": "Brief Arabic summary of changes",
    "response": "<svg>...complete SVG...</svg>"
}}

Return valid JSON only. No markdown.
"""

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.15,
            max_output_tokens=16384,
        )

        contents = [
            f"CURRENT SVG:\n{current_svg}\n\nUSER REQUEST:\n{instruction}\n\nMODIFY NOW."
        ]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = None
        try:
            response = call_gemini("gemini-2.5-flash", contents, gen_config, 50.0)
        except Exception as e:
            logger.warning(f"Modify primary failed: {e}")
            response = call_gemini("gemini-2.0-flash", contents, gen_config, 45.0)

        result_data = extract_safe_json(response.text if response.text else "")
        raw_svg = result_data.get("response", "")
        message = result_data.get("message", "")

        if not raw_svg:
            svg_match = re.search(r"(?s)<svg[^>]*>.*?</svg>", response.text or "")
            if svg_match:
                raw_svg = svg_match.group(0)
                message = message or "تم التعديل"

        raw_svg = clean_white_backgrounds(raw_svg)
        updated_svg = ensure_svg_namespaces(raw_svg)

        logger.info("Modified document successfully")
        return jsonify({"response": updated_svg, "message": message})

    except Exception as e:
        logger.error(f"Modify error: {str(e)}", exc_info=True)
        return jsonify({"error": "Modification failed", "details": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
