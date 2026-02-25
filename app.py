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
                logger.info("Monjez V7 (Smart Pagination & Vision) ready")
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

LETTERHEAD_TOP = 128    # 4.5cm EXACTLY
LETTERHEAD_BOTTOM = 128 # 4.5cm EXACTLY
SIDE_MARGIN = 42        # ~1.5cm


def compute_layout(width, height, has_letterhead):
    """
    Compute exact foreignObject position.
    التحديث: دائمًا نترك هامش 4.5 سم من الأعلى والأسفل (سواء برأسية أو بدون)
    لتفادي الاشتباك إذا أضاف المستخدم رأسية لاحقًا.
    """
    top = LETTERHEAD_TOP
    bottom = LETTERHEAD_BOTTOM
    side = SIDE_MARGIN
    
    fo_x = side
    fo_y = top
    fo_w = width - (side * 2)
    fo_h = height - top - bottom
    return fo_x, fo_y, fo_w, fo_h


def build_svg_wrapper(width, height, fo_x, fo_y, fo_w, fo_h, inner_html, letterhead_tag=""):
    """Build the final SVG with multi-page support and CSS protections."""
    
    # تقسيم المحتوى إلى صفحات واقعية
    pages = re.split(r'<pagebreak\s*/?>', inner_html, flags=re.IGNORECASE)
    pages = [p for p in pages if p.strip()]
    if not pages: 
        pages = [inner_html]

    num_pages = len(pages)
    total_height = height * num_pages

    # خلفية مساحة العمل رمادية فاتحة لإبراز الأوراق
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {total_height}" width="{width}" height="{total_height}" style="background:#f3f4f6;">\n'

    # 🛡️ حقن CSS إجباري لحماية المستند من التشوه والخطوط العشوائية
    css_protections = """
    <style>
        table { width: 100% !important; table-layout: fixed !important; word-wrap: break-word !important; overflow-wrap: break-word !important; border-collapse: collapse; margin-bottom: 15px; }
        td, th { word-wrap: break-word !important; overflow-wrap: break-word !important; white-space: normal !important; }
        hr { display: none !important; } /* يمنع رسم خطوط طويلة تفصل بين النصوص */
        p { margin-bottom: 12px; text-align: justify; line-height: 1.7; }
    </style>
    """

    for i, page_html in enumerate(pages):
        y_offset = i * height
        abs_fo_y = y_offset + fo_y

        # رسم ورقة A4 بيضاء واقعية
        svg += f'<rect x="0" y="{y_offset}" width="{width}" height="{height}" fill="white" />\n'

        if letterhead_tag:
            shifted_lh = re.sub(r'y="\d+"', f'y="{y_offset}"', letterhead_tag)
            svg += shifted_lh + '\n'

        svg += f'<foreignObject x="{fo_x}" y="{abs_fo_y}" width="{fo_w}" height="{fo_h}">\n'
        svg += f'<div xmlns="http://www.w3.org/1999/xhtml" style="font-family:Arial,Helvetica,sans-serif; font-size:13px; color:#111; line-height:1.7; direction:rtl; padding:4px; box-sizing:border-box; max-width:100%; height:{fo_h}px;">\n'
        svg += css_protections
        svg += page_html.strip()
        svg += '\n</div>\n</foreignObject>\n'

        # فاصل بصري بين الصفحات
        if i < num_pages - 1:
            svg += f'<rect x="0" y="{y_offset + height}" width="{width}" height="8" fill="#e5e7eb" />\n'

    svg += '</svg>'
    return svg


def extract_inner_html(svg_text):
    divs = re.findall(r'<div[^>]*xmlns="http://www.w3.org/1999/xhtml"[^>]*>(.*?)</div>\s*</foreignObject>', svg_text, re.DOTALL)
    if divs:
        # مسح كود الستايل المحقون حتى لا يتكرر
        cleaned = ["\n<pagebreak/>\n".join([re.sub(r'<style>.*?</style>', '', d, flags=re.DOTALL).strip() for d in divs])]
        return cleaned[0]

    fos = re.findall(r'<foreignObject[^>]*>(.*?)</foreignObject>', svg_text, re.DOTALL)
    if fos:
        return "\n<pagebreak/>\n".join([re.sub(r'<style>.*?</style>', '', f, flags=re.DOTALL).strip() for f in fos])

    if '<svg' not in svg_text:
        return svg_text.strip()

    return ""


def strip_white_rects(svg):
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

    return """FORMAL/OFFICIAL - Professional Mauritanian document design.

TYPOGRAPHY: Title 16px bold centered. Sections 13px bold.
Body 13px. NO bright colors. Colors: #333, #555, #f7f7f7, #f0f0f0, #ddd, white only.

TABLE DESIGN:
- th: background:#333; color:white; padding:7px; font-size:12px; border:1px solid #333;
- td: padding:6px 8px; font-size:12px; border:1px solid #ddd; text-align:right;
- Even rows: background:#f7f7f7;

INVOICE TABLE (فاتورة/facture/devis):
Columns right-to-left: البيان/الوصف(50%) | السعر | الكمية | الإجمالي
Total row in <tfoot>: "الإجمالي المستحق" colspan=3, amount in last column only."""


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V7 (Swift-like Real Pagination & Vision)"})


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

        needs_lh = True # تم التثبيت دائماً لحماية التصميم

        fo_x, fo_y, fo_w, fo_h = compute_layout(width, height, needs_lh)
        style_prompt = get_style_prompt(style, mode)

        lh_tag = ""
        if letterhead_b64:
            lh_tag = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="xMidYMin slice"/>'

        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = "\nATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        # ── AI PROMPT: Strict rules simulating Swift's context.beginPage() ──
        prompt = f"""You are an Expert Document Typesetter in Mauritania.

{style_prompt}
{ref_note}

CRITICAL PAGINATION & LAYOUT RULES (MANDATORY):
1. NO SHORTENING: NEVER summarize or omit the user's data. Write everything.
2. NO LONG SEPARATOR LINES: Do NOT use `<hr>` tags or long bottom borders to separate paragraphs.
3. PAGE CAPACITY: The physical space allowed per page is exactly {fo_h}px height. This fits A MAXIMUM of 15 table rows OR 250 words of text.
4. REAL MULTI-PAGE SPLITTING: If the user provides a lot of data, YOU MUST manually split the document into pages using exactly the `<pagebreak/>` tag.
   - Example for long tables:
     <table>
       <tr><th>Headers</th></tr>
       </table>
     <pagebreak/>
     <table>
       <tr><th>Headers (Repeated)</th></tr>
       </table>
5. LETTERHEAD VISION AWARENESS: The top 4.5cm and bottom 4.5cm are PERMANENTLY reserved. Do NOT design headers/footers in the text.

OUTPUT: Return ONLY the raw HTML content. Use `<pagebreak/>` correctly."""

        contents = [user_msg] if user_msg else ["Create a formal document."]
        
        # إرسال الصور للذكاء الاصطناعي ليراها ويستوعب المساحات والمحتوى
        if reference_b64:
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(reference_b64), mime_type="image/jpeg"))
        
        # التحديث الجوهري: إرسال الرأسية لجيميني ليلقي نظرة عليها!
        if letterhead_b64:
            contents.append("I have attached the Letterhead design image as well. Observe the empty space and ensure your layout perfectly matches its aesthetic without overlapping its borders.")
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(letterhead_b64), mime_type="image/jpeg"))

        gen_config = get_types().GenerateContentConfig(
            system_instruction=prompt,
            temperature=0.15, # تقليل الحرارة لضمان اتباع القواعد بصرامة
            max_output_tokens=16000, 
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
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            raw = raw.strip()

        if '<svg' in raw or '<foreignObject' in raw:
            inner = extract_inner_html(raw)
        else:
            inner = raw

        if not inner: inner = raw

        final_svg = build_svg_wrapper(width, height, fo_x, fo_y, fo_w, fo_h, inner, lh_tag)
        final_svg = strip_white_rects(final_svg)

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

        vb = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        w = int(vb.group(1)) if vb else 595
        h = 842 # الارتفاع القياسي للصفحة الواحدة

        has_lh = True # تثبيت الهوامش الآمنة
        fo_x, fo_y, fo_w, fo_h = compute_layout(w, h, has_lh)
        current_inner = extract_inner_html(current_svg)

        img_note = ""
        if ref_b64:
            img_note = f"\nINSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        sys = f"""Expert document modifier for Mauritanian documents.

CRITICAL RULES:
1. Preserve everything. Apply ONLY requested changes.
2. Return ONLY the modified HTML content (No SVG wrappers).
3. PAGE SPLITTING: You MUST use `<pagebreak/>` if tables or text get longer than {fo_h}px (approx 15 table rows). DO NOT shorten content.
4. TABLES: `width:100%; table-layout:fixed; word-wrap:break-word;`
5. NO LONG LINES: Do not use `<hr>` tags.
{img_note}

OUTPUT FORMAT - JSON:
{{"message": "وصف التعديل", "content": "<modified HTML here>"}}"""

        cfg = get_types().GenerateContentConfig(
            system_instruction=sys, temperature=0.15, max_output_tokens=16384,
        )

        cts = [f"CURRENT HTML:\n{current_inner}\n\nREQUEST:\n{instruction}\n\nMODIFY:"]
        if ref_b64:
            cts.append(get_types().Part.from_bytes(data=base64.b64decode(ref_b64), mime_type="image/jpeg"))

        # السماح لجيميني برؤية الرأسية حتى أثناء التعديل
        if lh_b64:
            cts.append("I have attached the NEW Letterhead design image. Ensure your layout fits its empty space.")
            cts.append(get_types().Part.from_bytes(data=base64.b64decode(lh_b64), mime_type="image/jpeg"))

        resp = None
        try:
            resp = call_gemini("gemini-3-flash-preview", cts, cfg, 55)
        except:
            resp = call_gemini("gemini-2.5-flash", cts, cfg, 50)

        raw = (resp.text or "").strip()

        rd = extract_json(raw)
        new_inner = rd.get("content", "") or rd.get("response", "")
        msg = rd.get("message", "تم التعديل")

        if not new_inner:
            cleaned = raw.replace("```html", "").replace("```json", "").replace("```", "").strip()
            if '<svg' in cleaned: new_inner = extract_inner_html(cleaned)
            else: new_inner = cleaned
            if not new_inner: new_inner = current_inner

        lh_tag_match = re.search(r'(<image[^>]*href="data:image[^>]*>)', current_svg)
        lh_tag = ""
        if lh_tag_match:
            lh_tag = re.sub(r'y="\d+"', 'y="0"', lh_tag_match.group(1))

        if lh_b64:
            lh_tag = f'<image href="data:image/jpeg;base64,{lh_b64}" x="0" y="0" width="{w}" height="{h}" preserveAspectRatio="xMidYMin slice"/>'

        final_svg = build_svg_wrapper(w, h, fo_x, fo_y, fo_w, fo_h, new_inner, lh_tag)
        final_svg = strip_white_rects(final_svg)

        return jsonify({"response": final_svg, "message": msg})

    except Exception as e:
        logger.error(f"Modify: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
