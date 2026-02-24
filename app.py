import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# MONJEZ DOCUMENT ENGINE V4.0
# ──────────────────────────────────────────────────────
# KEY CHANGE: Returns HTML with <div class="page"> wrappers
# Client renders with CSS page-break for real separate pages
# - No more SVG stretching
# - No more content cut off at bottom
# - Invoice totals attached to tables (tfoot)
# - Font: Arial
# - AI notes for user feedback
# ======================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez_V4")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1beta"})
        logger.info("Monjez Engine V4 connected")
    else:
        logger.warning("GOOGLE_API_KEY missing")
except Exception as e:
    logger.error(f"Gemini init error: {e}")


def call_gemini(model_name, contents, config, timeout_sec):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.models.generate_content,
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


def get_style_prompt(style, mode):
    if mode == "resumes":
        return """
=== RESUME DESIGN ===
- Create a creative, modern CV layout.
- Use sidebars, color accents, skill bars, section icons.
- Professional colors (navy #1e3a5f, teal #0d9488, charcoal #374151).
- Font: Arial, sans-serif.
"""

    if mode == "simulation":
        return """
=== DOCUMENT CLONING ===
- Clone EXACTLY the text, tables, and structure from the image.
- IGNORE logos, stamps, signatures, decorative images completely.
- Focus ONLY on textual content, tables, form fields.
- Do NOT invent any data not visible in the image.
- Font: Arial, sans-serif.
"""

    if style == "modern":
        return """
=== MODERN STYLE ===
- Professional accent colors on headers and dividers.
- Tables: alternating row colors (#f9fafb / white), no heavy borders.
- Clean, contemporary look with visual hierarchy.
- Font: Arial, sans-serif.
- Table borders: border-bottom: 1px solid #e5e7eb;
- Headers: color: #2563eb; font-weight: 700;
"""

    # formal (default)
    return """
=== FORMAL STYLE (Official Documents) ===
- BLACK text on WHITE background. NO colors except #f5f5f5 for header cells.
- Tables: CLOSED borders on ALL sides. 1px solid #333.
- Clean, professional, administrative look.
- Perfect for: invoices, contracts, official letters, purchase orders.
- Font: Arial, sans-serif.
- INVOICE TABLES: Total/subtotal rows MUST be inside <tfoot> (attached to table).
  Do NOT put totals in a separate div or table. Use <tfoot> inside the same <table>.
- Table: width:100%; table-layout:fixed; border-collapse:collapse;
- th,td: padding:6px 8px; font-size:12px; border:1px solid #333; text-align:right;
- th: background:#f5f5f5; font-weight:bold;
- tfoot td: font-weight:bold; background:#f0f0f0; border-top:2px solid #333;
"""


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez Engine V4.0 Online"})


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

        # Calculate margins
        top_margin = int(height * 0.14) if has_letterhead else int(height * 0.06)
        bottom_margin = int(height * 0.08)
        side_margin = int(width * 0.06)
        content_height = height - top_margin - bottom_margin

        style_prompt = get_style_prompt(style, mode)

        letterhead_note = ""
        if has_letterhead:
            letterhead_note = f"""
=== LETTERHEAD (Client-side) ===
- The client will overlay a letterhead image on the first page.
- Top {top_margin}px is RESERVED. Start content below this area.
- Do NOT create any header design or logo area.
- Keep background transparent/white.
"""

        ref_instruction = ""
        if reference_b64 and mode != "simulation":
            ref_instruction = f"""
=== IMAGE TO INSERT ===
<img src="data:image/jpeg;base64,{reference_b64}" style="max-width:100%; height:auto; border-radius:4px; margin:10px 0;" />
"""

        sys_prompt = f"""ROLE: Professional Document Designer.

{style_prompt}
{letterhead_note}

=== CRITICAL RULES ===
1. ANTI-HALLUCINATION: Only format text the user provided. NEVER invent data.
2. NEVER add greetings, dates, signatures, stamps unless the user wrote them.
3. Font: Arial, sans-serif throughout.
4. For invoices/tables: totals MUST be in <tfoot> inside the SAME table, NOT separate.

=== OUTPUT FORMAT ===
Return HTML content wrapped in <div class="page">...</div> tags.
Each page is a separate div.page element.

PAGINATION RULES:
- Each page can hold approximately {content_height}px of content.
- If content fits in ONE page, return ONE <div class="page">content</div>.
- If content is too long, split it across MULTIPLE <div class="page"> elements.
- Each page is independent. Tables can span pages but prefer keeping them together.
- NEVER cut off content. ALL user content MUST appear.
- When splitting, end a page at a natural break (after a paragraph, after a table row).

EXAMPLE for single page:
<div class="page">
  <h2>Title</h2>
  <p>Content here...</p>
  <table>...</table>
</div>

EXAMPLE for multi-page:
<div class="page">
  <h2>Title</h2>
  <p>First part of content...</p>
</div>
<div class="page">
  <p>Continuation of content...</p>
  <table>...</table>
</div>

{ref_instruction}

Return ONLY the HTML div.page content. No markdown, no backticks, no explanation, no <html> or <body> tags.
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

        raw = response.text or ""

        # Clean markdown artifacts
        raw = raw.replace("```html", "").replace("```", "").strip()

        # Ensure content is wrapped in page divs
        if '<div class="page">' not in raw:
            raw = f'<div class="page">\n{raw}\n</div>'

        # Count pages for note
        page_count = raw.count('<div class="page">')
        note = ""
        if page_count > 1:
            note = f"المحتوى طويل، تم توزيعه على {page_count} صفحات. يمكنك طلب ضغطه في صفحة واحدة."

        logger.info(f"Generated (mode={mode}, style={style}, pages={page_count})")

        result = {"response": raw}
        if note:
            result["note"] = note
        return jsonify(result)

    except Exception as e:
        logger.error(f"Generate error: {str(e)}", exc_info=True)
        return jsonify({"error": "Generation failed", "details": str(e)}), 500


@app.route("/modify", methods=["POST"])
def modify():
    if not client:
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_content = data.get("current_content", "") or data.get("current_svg", "") or data.get("current_html", "")
        instruction = data.get("instruction", "")
        reference_b64 = data.get("reference_image")

        image_instruction = ""
        if reference_b64:
            image_instruction = (
                "INSERT THIS IMAGE in the document: "
                f'<img src="data:image/jpeg;base64,{reference_b64}" '
                'style="max-width:100%; height:auto; margin:10px 0; border-radius:4px;" />'
            )

        system_prompt = f"""ROLE: Expert Document Modifier.

RULES:
1. PRESERVE all existing content and structure.
2. Apply ONLY the user's requested change.
3. Font: Arial, sans-serif.
4. ALL content must remain visible.
5. Keep the <div class="page">...</div> structure.
6. If content overflows, create additional page divs.
7. For invoices: totals stay in <tfoot> inside the same table.
8. {image_instruction}

RESPONSE FORMAT - JSON:
{{
    "message": "Brief Arabic summary of changes",
    "response": "<div class=\\"page\\">...modified content...</div>"
}}

Return valid JSON only. No markdown backticks.
"""

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.15,
            max_output_tokens=16384,
        )

        contents = [
            f"CURRENT CONTENT:\n{current_content}\n\nUSER REQUEST:\n{instruction}\n\nMODIFY NOW."
        ]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = None
        try:
            response = call_gemini("gemini-2.5-flash", contents, gen_config, 50.0)
        except Exception as e:
            logger.warning(f"Modify primary failed: {e}")
            response = call_gemini("gemini-2.0-flash", contents, gen_config, 45.0)

        raw_text = response.text or ""
        result_data = extract_safe_json(raw_text)
        content = result_data.get("response", "")
        message = result_data.get("message", "")

        # Fallback: extract HTML directly if JSON parsing failed
        if not content:
            # Try to find page divs
            cleaned = raw_text.replace("```html", "").replace("```json", "").replace("```", "").strip()
            if '<div class="page">' in cleaned:
                start = cleaned.find('<div class="page">')
                last = cleaned.rfind("</div>")
                if start >= 0 and last >= 0:
                    content = cleaned[start:last + 6]
            elif cleaned:
                content = f'<div class="page">\n{cleaned}\n</div>'
            message = message or "تم التعديل"

        # Ensure page wrapper
        if content and '<div class="page">' not in content:
            content = f'<div class="page">\n{content}\n</div>'

        logger.info("Modified document successfully")
        return jsonify({"response": content, "message": message})

    except Exception as e:
        logger.error(f"Modify error: {str(e)}", exc_info=True)
        return jsonify({"error": "Modification failed", "details": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
