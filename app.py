import os
import re
import json
import logging
import base64
import concurrent.futures
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez")

app = Flask(__name__)

# ── Lazy Gemini ──
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
                logger.info("Monjez V7 ready")
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
#  HARD-CODED LAYOUT RULES (enforced by CODE, not by AI)
# ══════════════════════════════════════════════════════════
# 1pt = 0.3528mm, 1cm = 28.35pt
# A4 = 595 x 842 pt

LETTERHEAD_TOP = 128    # 4.5cm
LETTERHEAD_BOTTOM = 125 # 4.4cm
SIDE_MARGIN = 42        # ~1.5cm


def compute_layout(width, height, has_letterhead):
    """Compute exact foreignObject position - ALWAYS reserve safe margins for letterhead."""
    # التحديث: دائمًا نترك هامش 4.5 سم من الأعلى والأسفل لتفادي الاشتباك إذا أضيفت رأسية لاحقًا
    top = LETTERHEAD_TOP
    bottom = LETTERHEAD_BOTTOM
    side = SIDE_MARGIN
    
    fo_x = side
    fo_y = top
    fo_w = width - (side * 2)
    fo_h = height - top - bottom
    return fo_x, fo_y, fo_w, fo_h


def build_svg_wrapper(width, height, fo_x, fo_y, fo_w, fo_h, inner_html, letterhead_tag=""):
    """Build the final SVG with multi-page support and exact realistic layout."""
    
    # تقسيم المحتوى إلى صفحات واقعية بناءً على وسم <pagebreak/>
    pages = re.split(r'<pagebreak\s*/?>', inner_html, flags=re.IGNORECASE)
    pages = [p for p in pages if p.strip()]
    if not pages: 
        pages = [inner_html]

    num_pages = len(pages)
    total_height = height * num_pages

    # خلفية مساحة العمل رمادية فاتحة لإبراز الأوراق البيضاء
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_height}" width="{width}" height="{total_height}" style="background:#f3f4f6;">\n'

    for i, page_html in enumerate(pages):
        y_offset = i * height
        abs_fo_y = y_offset + fo_y

        # رسم ورقة A4 بيضاء واقعية لكل صفحة
        svg += f'<rect x="0" y="{y_offset}" width="{width}" height="{height}" fill="white" />\n'

        # إضافة الرأسية لكل صفحة بذكاء (مع تعديل مكانها للأسفل حسب الصفحة)
        if letterhead_tag:
            shifted_lh = re.sub(r'y="\d+"', f'y="{y_offset}"', letterhead_tag)
            svg += shifted_lh + '\n'

        # إضافة محتوى الصفحة (مع حماية CSS صارمة لمنع خروج النص من اليسار وتنسيق السطور)
        svg += f'<foreignObject x="{fo_x}" y="{abs_fo_y}" width="{fo_w}" height="{fo_h}">\n'
        svg += f'<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:13px; color:#111; line-height:1.7; direction:rtl; padding:4px; box-sizing:border-box; overflow-wrap:break-word; word-wrap:break-word; word-break:break-word; max-width:100%; height:{fo_h}px; text-align:justify;">\n'
        svg += page_html.strip()
        svg += '\n</div>\n</foreignObject>\n'

        # فاصل بصري بين الصفحات (ظل خفيف) لتظهر كصفحات منفصلة
        if i < num_pages - 1:
            svg += f'<rect x="0" y="{y_offset + height}" width="{width}" height="8" fill="#e5e7eb" />\n'

    svg += '</svg>'
    return svg


def extract_inner_html(svg_text):
    """Extract ONLY the inner HTML content, combining multiple pages back together."""
    # استخراج محتوى جميع الصفحات لدمجها قبل إرسالها للتعديل
    divs = re.findall(r'<div[^>]*xmlns="http://www.w3.org/1999/xhtml"[^>]*>(.*?)</div>\s*</foreignObject>', svg_text, re.DOTALL)
    if divs:
        return "\n<pagebreak/>\n".join([d.strip() for d in divs])

    # Fallback: get everything inside foreignObject
    fos = re.findall(r'<foreignObject[^>]*>(.*?)</foreignObject>', svg_text, re.DOTALL)
    if fos:
        return "\n<pagebreak/>\n".join([f.strip() for f in fos])

    # Last resort: if no SVG structure, return as-is
    if '<svg' not in svg_text:
        return svg_text.strip()

    return ""


def strip_white_rects(svg):
    """Remove all white/opaque rects that could cover letterhead, EXCEPT our page backgrounds."""
    # لن نقوم بمسح الخلفية البيضاء الأساسية للصفحات التي رسمناها للتو.
    # سنمسح فقط المستطيلات المضافة عشوائياً بدون تحديد العرض والطول الكامل.
    return re.sub(
        r'<rect(?! x="0" y="\d+" width="\d+" height="\d+" fill="white")[^>]*(?:fill=["\'](?:white|#fff(?:fff)?|rgba?\(255[^)]*\))["\'])[^>]*/?>',
        '', svg, flags=re.IGNORECASE
    )


# ══════════════════════════════════════════════════════════
#  STYLE PROMPTS (for AI creativity, not for layout rules)
# ══════════════════════════════════════════════════════════

def get_style_prompt(style, mode):
    if mode == "resumes":
        return """RESUME/CV: Creative layout with sidebar, skill bars, icons, color accents.
Colors: navy #1e3a5f, teal #0d9488, charcoal #374151."""

    if mode == "simulation":
        return """CLONING: Reproduce EXACTLY text/tables from the reference image.
IGNORE logos, stamps, signatures. Do NOT invent data."""

    if style == "modern":
        return """MODERN: Headers color:#2563eb, alternating table rows (#f9fafb/white),
border-bottom:1px solid #e5e7eb. Clean contemporary look."""

    return """FORMAL/OFFICIAL - Professional Mauritanian document design.

TYPOGRAPHY: Title 16px bold centered. Sections 13px bold with border-bottom:2px solid #333.
Body 13px. Subtle <hr> between sections. NO bright colors.
Colors: #333, #555, #f7f7f7, #f0f0f0, #ddd, white only.

TABLE DESIGN:
- th: background:#333; color:white; padding:7px; font-size:12px; border:1px solid #333;
- td: padding:6px 8px; font-size:12px; border:1px solid #ddd; text-align:right;
- Even rows: background:#f7f7f7;

INVOICE TABLE (فاتورة/facture/devis):
Columns right-to-left: البيان/الوصف(50%) | السعر | الكمية | الإجمالي
Total row in <tfoot>: "الإجمالي المستحق" colspan=3, amount in last column only.
After table: "Arrête la présente facture a la somme de : [WORDS] [CURRENCY]"

FORMS (استمارة): Organize raw text into clean form with label:value pairs and input boxes.
LETTERS (خطاب): Date, recipient, subject (centered bold), body, signature area.

Formal ≠ boring. Good design, spacing, hierarchy - just no colors."""


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V7 (Real Pagination & Safe Margins)"})


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

        needs_lh = has_letterhead or (letterhead_b64 is not None)

        # ── LAYOUT: computed by CODE, not by AI ──
        fo_x, fo_y, fo_w, fo_h = compute_layout(width, height, needs_lh)

        style_prompt = get_style_prompt(style, mode)

        # Letterhead tag
        lh_tag = ""
        if letterhead_b64:
            lh_tag = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMin slice"/>'

        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = "\nATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        lh_note = f"\nLETTERHEAD AND MARGINS: Top {fo_y}px and bottom {LETTERHEAD_BOTTOM}px are PERMANENTLY reserved. Content area is strictly {fo_h}px height."

        # ── AI PROMPT: ask for HTML content only, NOT full SVG ──
        prompt = f"""You are a professional document designer in Mauritania.

{style_prompt}
{lh_note}
{ref_note}

CRITICAL RULES:
1. Return ONLY the HTML content (no <svg>, no <foreignObject>, no wrapper).
2. Content area per page is strictly {fo_h}px height.
3. REAL PAGINATION: If the report or text is long (e.g. over 500 words or long tables), you MUST split it into multiple realistic pages by inserting exactly `<pagebreak/>` where the split should happen. Do NOT shrink text to fit an impossibly small area.
4. TEXT FORMATTING: Do NOT write long unbroken lines of text. Use `<p style="text-align: justify; margin-bottom: 15px; line-height: 1.7;">` to structure paragraphs beautifully.
5. Format ONLY user's text. NEVER invent content, dates, greetings, signatures.
6. Make tables look compact: strictly use `width: 100%; table-layout: fixed; word-wrap: break-word;` to prevent overflowing.

OUTPUT: Return ONLY the inner HTML content. Use `<pagebreak/>` between pages if content is long."""

        contents = [user_msg] if user_msg else ["Create a formal document."]
        if reference_b64:
            contents.append(get_types().Part.from_bytes(
                data=base64.b64decode(reference_b64), mime_type="image/jpeg"
            ))

        gen_config = get_types().GenerateContentConfig(
            system_instruction=prompt,
            temperature=0.2 if style == "formal" else 0.3,
            max_output_tokens=16000, # زيادة لدعم تقارير متعددة الصفحات
        )

        resp = None
        try:
            resp = call_gemini("gemini-3-flash-preview", contents, gen_config, 55)
        except Exception as e:
            logger.warning(f"Primary fail: {e}")
            try:
                resp = call_gemini("gemini-2.5-flash", contents, gen_config, 50)
            except Exception as e2:
                return jsonify({"error": "AI failed", "details": str(e2)}), 500

        raw = (resp.text or "").strip()

        # Clean markdown wrapping
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            raw = raw.strip()

        # ── EXTRACT INNER HTML ──
        if '<svg' in raw:
            inner = extract_inner_html(raw)
        elif '<foreignObject' in raw:
            inner = extract_inner_html(raw)
        else:
            inner = raw

        if not inner:
            inner = raw  # fallback

        # ── BUILD FINAL SVG (CODE controls layout) ──
        final_svg = build_svg_wrapper(width, height, fo_x, fo_y, fo_w, fo_h, inner, lh_tag)

        # ── POST-PROCESSING (hard rules) ──
        final_svg = strip_white_rects(final_svg)

        logger.info(f"OK: mode={mode}, style={style}, lh={needs_lh}, inner={len(inner)}, total={len(final_svg)}")
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
        ref_b64 = data.get("reference_image")
        lh_b64 = data.get("letterhead_image")

        # Parse dimensions
        vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        w = int(vb.group(1)) if vb else 595
        # The height in viewBox might be total_height (multiple pages). We need the single page height.
        h = 842 # نثبت الارتفاع ليكون A4 قياسي بدلاً من أخذ الارتفاع الكلي المتمدد

        # Detect if letterhead exists
        has_lh = '<image' in current_svg
        fo_x, fo_y, fo_w, fo_h = compute_layout(w, h, has_lh)

        # Extract current inner HTML (This will now gracefully extract all pages separated by <pagebreak/>)
        current_inner = extract_inner_html(current_svg)

        img_note = ""
        if ref_b64:
            img_note = f"\nINSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        sys = f"""Expert document modifier for Mauritanian documents.

RULES:
1. You receive the CURRENT HTML content of the document.
2. Apply ONLY the requested change. Preserve everything else.
3. Return ONLY the modified HTML content (no SVG wrapper, no foreignObject).
4. REAL PAGINATION: If content becomes too long, insert `<pagebreak/>` to create realistic new pages! Do NOT shrink text.
5. TEXT FORMATTING: Do NOT output long unbroken lines. Use `<p style="margin-bottom: 15px;">` for proper paragraphs.
6. TABLES: MUST be `width:100%; table-layout:fixed; word-wrap:break-word;` so they don't overflow the page.
7. NEVER add white rectangles or background elements.
{img_note}

OUTPUT FORMAT - JSON:
{{"message": "وصف التعديل", "content": "<modified HTML here>"}}
No markdown, just JSON."""

        cfg = get_types().GenerateContentConfig(
            system_instruction=sys, temperature=0.15, max_output_tokens=16384,
        )

        cts = [f"CURRENT HTML:\n{current_inner}\n\nREQUEST:\n{instruction}\n\nMODIFY:"]
        if ref_b64:
            cts.append(get_types().Part.from_bytes(
                data=base64.b64decode(ref_b64), mime_type="image/jpeg"
            ))

        resp = None
        try:
            resp = call_gemini("gemini-3-flash-preview", cts, cfg, 55)
        except:
            resp = call_gemini("gemini-2.5-flash", cts, cfg, 50)

        raw = (resp.text or "").strip()

        # Try JSON parse
        rd = extract_json(raw)
        new_inner = rd.get("content", "") or rd.get("response", "")
        msg = rd.get("message", "تم التعديل")

        if not new_inner:
            # Clean and use directly
            cleaned = raw.replace("```html", "").replace("```json", "").replace("```", "").strip()
            if '<svg' in cleaned:
                new_inner = extract_inner_html(cleaned)
            else:
                new_inner = cleaned
            if not new_inner:
                new_inner = current_inner  # fallback to original

        # Preserve letterhead tag from original SVG (ensure y="0" for the multiplier logic)
        lh_tag_match = re.search(r'(<image[^>]*href="data:image[^>]*>)', current_svg)
        lh_tag = ""
        if lh_tag_match:
            lh_tag = re.sub(r'y="\d+"', 'y="0"', lh_tag_match.group(1))

        # Also handle new letterhead if user uploads one during modify
        if lh_b64:
            lh_tag = f'<image href="data:image/jpeg;base64,{lh_b64}" x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="xMidYMin slice"/>'

        # ── REBUILD SVG (CODE controls layout) ──
        final_svg = build_svg_wrapper(w, h, fo_x, fo_y, fo_w, fo_h, new_inner, lh_tag)
        final_svg = strip_white_rects(final_svg)

        return jsonify({"response": final_svg, "message": msg})

    except Exception as e:
        logger.error(f"Modify: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
