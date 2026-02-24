import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# MONJEZ DOCUMENT ENGINE V2.0
# ──────────────────────────────────────────────────────
# - Style-aware generation (formal / modern / classic)
# - Smart pagination with real page breaks
# - Adaptive margins & letterhead system
# - Mode-separated prompts (documents / simulation / resumes)
# - Fixed: Unicode quotes, proper escaping
# ======================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Monjez_Engine_V2")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get("GOOGLE_API_KEY")
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1beta"})
        logger.info("Document Engine connected (Gemini)")
    else:
        logger.warning("GOOGLE_API_KEY is missing.")
except Exception as e:
    logger.error(f"Gemini init error: {e}")


# ──────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ──────────────────────────────────────────────────────

def extract_safe_json(text):
    """Extract JSON object from mixed text safely."""
    try:
        match = re.search(r"\{.*\}", text.replace("\n", " "), re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass
    return {}


def ensure_svg_namespaces(svg_code):
    """Ensure SVG has proper XML namespaces."""
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_code:
        svg_code = svg_code.replace(
            "<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1
        )
    if "xmlns:xhtml" not in svg_code and "<foreignObject" in svg_code:
        svg_code = svg_code.replace(
            "<foreignObject",
            '<foreignObject xmlns:xhtml="http://www.w3.org/1999/xhtml"',
            1,
        )
    return svg_code


def clean_white_backgrounds(svg_code):
    """Remove white backgrounds that may cover content."""
    svg_code = re.sub(
        r'<rect[^>]*fill=["\'](?:white|#FFF|#ffffff|#fff|#FFFFFF)["\'][^>]*>',
        "",
        svg_code,
    )
    svg_code = svg_code.replace("background-color: white;", "background-color: transparent;")
    svg_code = svg_code.replace("background: white;", "background: transparent;")
    return svg_code


def calculate_adaptive_margins(width, height, letterhead_active, content_type="documents"):
    """Calculate dynamic margins based on content type and letterhead."""
    margin_left = int(width * 0.06)
    margin_right = int(width * 0.06)
    margin_bottom = int(height * 0.08)

    if letterhead_active:
        margin_top = int(height * 0.12)
    else:
        margin_top = int(height * 0.08)

    content_width = width - (margin_left + margin_right)
    content_height = height - (margin_top + margin_bottom)

    return {
        "x": margin_left,
        "y": margin_top,
        "width": content_width,
        "height": content_height,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom,
    }


def inject_letterhead_smart(svg_code, letterhead_b64, width, height):
    """Insert letterhead image on first page only."""
    if not letterhead_b64 or "<svg" not in svg_code:
        return svg_code

    bg_image = (
        f'<image href="data:image/jpeg;base64,{letterhead_b64}" '
        f'x="0" y="0" width="{width}" height="{height}" '
        f'preserveAspectRatio="none" />\n'
    )

    # Insert before first foreignObject
    if "<foreignObject" in svg_code:
        return svg_code.replace("<foreignObject", f"{bg_image}<foreignObject", 1)
    return svg_code


def detect_page_size_from_image(reference_b64):
    """
    Attempt to detect the page orientation/size from a reference image.
    Returns suggested PageSize string.
    """
    # Default to A4 portrait - actual detection happens via aspect ratio
    # in the AI prompt, this gives a hint
    return "a4Portrait"


def call_gemini_with_timeout(model_name, contents, config, timeout_sec):
    """Call Gemini API with a timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.models.generate_content,
            model=model_name,
            contents=contents,
            config=config,
        )
        return future.result(timeout=timeout_sec)


# ──────────────────────────────────────────────────────
# STYLE SYSTEM
# ──────────────────────────────────────────────────────

def get_style_instructions(style, mode):
    """Return AI instructions based on selected design style."""

    if mode == "resumes":
        return """
=== RESUME DESIGN MODE ===
- ROLE: Professional CV Designer with creative vision.
- Create a UNIQUE, modern resume layout.
- Use creative sidebars, color accents, skill bars, icons.
- Professional yet visually distinctive.
- STRICT FIT: width: 100%; box-sizing: border-box;
- Use professional color palette (navy, teal, charcoal, or similar).
- Section headers must be clearly styled and hierarchical.
- Contact info prominently placed.
"""

    if mode == "simulation":
        return """
=== DOCUMENT CLONING MODE ===
- ROLE: Precision Document Typesetter.
- EXACT COPY: Mirror the structure, tables, and text from the image.
- IGNORE all logos, stamps, signatures, and decorative images.
- FOCUS ONLY on: text content, tables, form fields, structure.
- NO INVENTION: Do not add or fabricate any missing data.
- TABLES: width: 100%; table-layout: fixed; border-collapse: collapse;
- Preserve the exact hierarchy and layout of the original.
- If the document has a specific form factor, match it.
"""

    # Documents mode - style-dependent
    if style == "formal":
        return """
=== FORMAL DOCUMENT STYLE ===
- MINIMALIST: Black text on transparent background.
- TABLES: Closed borders, 1px solid #333, clean cells.
- HIERARCHY: Clear size contrast (title 18px, subtitle 14px, body 12px).
- NO decorative elements, NO colored backgrounds, NO fancy fonts.
- Professional administrative look (invoices, official letters, reports).
- Table style: width: 100%; table-layout: fixed; border-collapse: collapse; border: 1px solid #333;
- Cell style: padding: 6px 8px; font-size: 12px; border: 1px solid #333;
- Headers: font-weight: bold; background-color: #f5f5f5;
"""
    elif style == "modern":
        return """
=== MODERN DOCUMENT STYLE ===
- USE professional colors: accent headers, subtle backgrounds.
- TABLES: Rounded feel, alternating row colors, no heavy borders.
- TYPOGRAPHY: Varied weights, clear visual hierarchy.
- Subtle design elements: colored dividers, icon-style bullets.
- Modern and clean but with personality.
- Table style: width: 100%; border-collapse: collapse; border: none;
- Cell style: padding: 10px 12px; font-size: 13px; border-bottom: 1px solid #e0e0e0;
- Headers: color: #2563EB; font-weight: 700;
"""
    elif style == "classic":
        return """
=== CLASSIC DOCUMENT STYLE ===
- ELEGANT: Serif-inspired hierarchy, fine lines, generous spacing.
- TABLES: Thin borders, wide margins, refined look.
- Traditional and dignified aesthetic.
- Subtle use of gray tones for depth.
- Table style: width: 100%; border-collapse: collapse; border: 1px solid #999;
- Cell style: padding: 8px 12px; font-size: 12px; border: 1px solid #ccc;
- Headers: font-variant: small-caps; letter-spacing: 1px;
"""
    else:
        return get_style_instructions("formal", mode)


# ──────────────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez Engine V2.0 Online"})


@app.route("/gemini", methods=["POST"])
def generate():
    """Generate a new document."""
    if not client:
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get("message", "")
        width = int(data.get("width", 595))
        height = int(data.get("height", 842))
        mode = data.get("mode", "documents")
        style = data.get("style", "formal")
        page_size = data.get("pageSize", "a4Portrait")

        reference_b64 = data.get("reference_image")
        letterhead_b64 = data.get("letterhead_image")

        # Calculate adaptive margins
        margins = calculate_adaptive_margins(width, height, bool(letterhead_b64), mode)
        fo_x = margins["x"]
        fo_y = margins["y"]
        fo_w = margins["width"]
        fo_h = margins["height"]

        # Get style-specific instructions
        style_instruction = get_style_instructions(style, mode)

        # Letterhead instructions
        if letterhead_b64:
            letterhead_instruction = f"""
=== LETTERHEAD ACTIVE ===
- Reserved space at top: {margins['margin_top']}px (letterhead image will be placed here).
- Start ALL content below this reserved space.
- NO logos, NO top decorations, NO header designs.
- Transparent background ONLY.
- Content must NOT overlap with letterhead area.
"""
        else:
            letterhead_instruction = """
=== NO LETTERHEAD ===
- Full page available for content.
- Leave 8% whitespace at bottom for signatures/stamps.
"""

        # Reference image handling
        ref_instruction = ""
        if reference_b64:
            if mode == "simulation":
                ref_instruction = """
=== SMART CLONE FROM IMAGE ===
1. Analyze the attached image carefully.
2. Clone ONLY the text content, tables, and structure.
3. IGNORE all logos, stamps, watermarks, and decorative images.
4. Match the document form factor and layout precisely.
5. Do NOT invent or hallucinate any data not visible in the image.
6. After cloning, the user can add letterhead/images separately.
"""
            else:
                ref_instruction = f"""
=== REFERENCE IMAGE ===
- Embed this image in the document:
  <img src="data:image/jpeg;base64,{reference_b64}" style="max-width:100%; height:auto; border-radius:4px; margin: 10px 0;" />
- Center aligned within content area.
"""

        # Anti-hallucination rules
        anti_hallucination = """
=== STRICT ANTI-HALLUCINATION RULES ===
1. Format ONLY the text/data provided by the user.
2. NEVER invent greetings, dates, reference numbers, or signatures.
3. NEVER add "Dear Sir/Madam" or similar unless the user wrote it.
4. NEVER add stamps, seals, or signature lines unless requested.
5. If the user gives minimal input, create a minimal document.
"""

        # Pagination rules
        pagination = f"""
=== SMART PAGINATION ===
- Available content height per page: {fo_h}px.
- If content exceeds one page, extend viewBox height to {height * 2} (or more).
- Each new page = a NEW <foreignObject> starting at y="{height}" (page 2), y="{height * 2}" (page 3), etc.
- Each foreignObject has the SAME width={fo_w} and height={fo_h}.
- NEVER shrink font size to fit content. Create new pages instead.
- Each page is INDEPENDENT (not stretched).
"""

        sys_prompt = f"""ROLE: Master Document Designer & Executive Secretary.

{style_instruction}

{letterhead_instruction}

{ref_instruction}

{anti_hallucination}

{pagination}

RETURN EXACTLY THIS SVG STRUCTURE:
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
    <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
        <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; box-sizing: border-box; padding: 15px; background: transparent; direction: rtl; font-family: -apple-system, BlinkMacSystemFont, sans-serif; color: #111; line-height: 1.6;">
            [CONTENT HERE]
        </div>
    </foreignObject>
</svg>

CRITICAL: Return ONLY the SVG code. No markdown, no explanation, no backticks.
"""

        contents = []
        if user_msg:
            contents.append(user_msg)
        else:
            contents.append("Create a simple formal document with proper tables.")

        if reference_b64:
            contents.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": reference_b64,
                }
            })

        gen_config = types.GenerateContentConfig(
            system_instruction=sys_prompt,
            temperature=0.2 if style == "formal" else 0.35,
            max_output_tokens=8192,
        )

        response = None
        try:
            response = call_gemini_with_timeout(
                "gemini-2.5-flash", contents, gen_config, timeout_sec=45.0
            )
        except Exception as e:
            logger.warning(f"Primary model failed: {e}")
            response = call_gemini_with_timeout(
                "gemini-2.0-flash", contents, gen_config, timeout_sec=40.0
            )

        raw_text = response.text or ""

        # Extract SVG
        svg_match = re.search(r"(?s)<svg[^>]*>.*?</svg>", raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # Clean up
        final_svg = clean_white_backgrounds(final_svg)
        final_svg = ensure_svg_namespaces(final_svg)
        final_svg = inject_letterhead_smart(final_svg, letterhead_b64, width, height)

        logger.info(
            f"Generated document (mode={mode}, style={style}, "
            f"letterhead={bool(letterhead_b64)})"
        )
        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"Generate error: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Document generation failed",
            "details": str(e),
        }), 500


@app.route("/modify", methods=["POST"])
def modify():
    """Modify an existing document."""
    if not client:
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_svg = data.get("current_html", "") or data.get("current_svg", "")
        instruction = data.get("instruction", "")
        reference_b64 = data.get("reference_image")
        letterhead_b64 = data.get("letterhead_image")

        # Extract dimensions from current SVG
        width_match = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        width = int(width_match.group(1)) if width_match else 595
        height = int(width_match.group(2)) if width_match else 842

        # Calculate margins
        margins = calculate_adaptive_margins(
            width, height, bool(letterhead_b64), "documents"
        )
        fo_x = margins["x"]
        fo_y = margins["y"]
        fo_w = margins["width"]
        fo_h = margins["height"]

        # Image insertion instruction
        image_instruction = ""
        if reference_b64:
            image_instruction = (
                "INSERT THIS IMAGE in the document: "
                f'<img src="data:image/jpeg;base64,{reference_b64}" '
                'style="max-width:100%; height:auto; margin:10px 0; '
                'border-radius:4px;" />'
            )

        # Letterhead instruction
        letterhead_mod = ""
        if letterhead_b64:
            letterhead_mod = (
                f"LETTERHEAD ACTIVE: Ensure foreignObject starts at "
                f'x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}". '
                f"Content must not overlap with top {margins['margin_top']}px."
            )

        system_prompt = f"""ROLE: Expert Document Modifier.

MODIFICATION RULES:
1. PRESERVE all existing content and structure.
2. Apply ONLY the requested change.
3. If adding content exceeds {fo_h}px height:
   - Extend viewBox height to {height * 2}
   - Add NEW <foreignObject> at y="{height}" with same dimensions
   - This creates a real new page, NOT stretching
4. NEVER shrink text to fit. Create new pages instead.
5. {image_instruction}
6. {letterhead_mod}

Page dimensions: {width}x{height}px
Content area: {fo_w}x{fo_h}px at ({fo_x}, {fo_y})

RESPONSE FORMAT - STRICT JSON:
{{
    "message": "Brief Arabic summary of changes",
    "response": "<svg>...complete SVG code...</svg>"
}}

CRITICAL: Return valid JSON only. No markdown, no backticks.
"""

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.15,
            max_output_tokens=16384,
        )

        contents = [
            f"CURRENT SVG:\n{current_svg}\n\n"
            f"USER INSTRUCTION:\n{instruction}\n\n"
            f"MODIFY THIS DOCUMENT."
        ]

        if reference_b64:
            contents.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": reference_b64,
                }
            })

        response = None
        try:
            response = call_gemini_with_timeout(
                "gemini-2.5-flash", contents, gen_config, timeout_sec=50.0
            )
        except Exception as e:
            logger.warning(f"Modify primary model failed: {e}")
            response = call_gemini_with_timeout(
                "gemini-2.0-flash", contents, gen_config, timeout_sec=45.0
            )

        result_data = extract_safe_json(response.text if response.text else "")
        raw_svg = result_data.get("response", "")
        message = result_data.get("message", "")

        # If JSON extraction failed, try extracting SVG directly
        if not raw_svg:
            svg_match = re.search(
                r"(?s)<svg[^>]*>.*?</svg>", response.text or ""
            )
            if svg_match:
                raw_svg = svg_match.group(0)
                message = message or "Applied modification"

        # Clean up
        raw_svg = clean_white_backgrounds(raw_svg)
        updated_svg = ensure_svg_namespaces(raw_svg)
        updated_svg = inject_letterhead_smart(
            updated_svg, letterhead_b64, width, height
        )

        logger.info("Modified document successfully")
        return jsonify({
            "response": updated_svg,
            "message": message,
        })

    except Exception as e:
        logger.error(f"Modify error: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Modification failed",
            "details": str(e),
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
