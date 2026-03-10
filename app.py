import os
import re
import json
import logging
import base64
import concurrent.futures
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez_V9.6_Server")

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
                logger.info("✅ Monjez V9.6 Server (Canvas Adaptation Rule Active)")
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

def clean_html_output(raw_text):
    raw = raw_text.strip()
    if raw.startswith("`" * 3):
        raw = re.sub(r"^`{3}(?:html|xml)?\n?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\n?`{3}$", "", raw)

    div_match = re.search(r'<div[^>]*xmlns="http://www.w3.org/1999/xhtml"[^>]*>(.*?)</div>\s*</foreignObject>', raw, re.DOTALL)
    if div_match:
        raw = div_match.group(1)

    raw = re.sub(r'\s?contenteditable="[^"]*"', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s?contenteditable=\'[^\']*\'', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s?contenteditable', '', raw, flags=re.IGNORECASE)

    return raw.strip()


# ══════════════════════════════════════════════════════════
# STYLE PROMPTS & THE 21x29.7 CANVAS RULE
# ══════════════════════════════════════════════════════════

def get_style_prompt(style, mode):
    # 🚀 فكرتك تم تطبيقها هنا بالحرف!
    global_rules = """
⚠️ THE CANVAS ADAPTATION RULE (CRITICAL - DO NOT FAIL THIS):
You have a strictly limited physical canvas space (e.g., 21cm x 29.7cm for A4). 
Regardless of how huge or wide the document looks in the original image, you MUST ADAPT, COMPRESS, and SHRINK the layout to fit perfectly INSIDE this canvas.
- If a table has many columns (like 5, 6, or 7), you MUST aggressively shrink the font size (to 9px, 10px, or 11px) and reduce cell padding to a minimum (e.g., 2px 3px).
- DO NOT copy the original size; copy the original DATA but ADAPT its presentation to fit the paper exactly.
- NO OVERFLOW: Nothing is allowed to spill out of the 100% width boundary.

BUG 1: TABLE COLUMNS & ALIGNMENT REVERSING
FIX: Completely disable the browser's automatic RTL flipping.
- The outermost wrapper MUST use `dir="ltr"`.
- EVERY `<table>` MUST explicitly have `dir="ltr"`.
- For Arabic text, apply `dir="rtl" style="text-align: right;"` ON THAT SPECIFIC CELL ONLY.
- French/English text MUST explicitly use `dir="ltr" style="text-align: left;"`.

BUG 2: PUNCTUATION & LABEL REFLECTION
FIX: Structurally separate labels from colons/dots using Flexbox locked in LTR.

BUG 3: PHONE NUMBERS & SPACES REVERSING
FIX: Phone numbers or ANY numbers containing spaces MUST NOT flip. Wrap them in:
`<span dir="ltr" style="display:inline-block; unicode-bidi:bidi-override; white-space:nowrap;">44 55 66 77</span>`

RULE D – EXACT PAGE FIT (CRITICAL):
1. STRICTLY FORBIDDEN: `width: [X]px`, `min-width`, `white-space: nowrap` (except for phone numbers).
2. TABLES MUST COMPLY: Every `<table>` MUST have `width: 100%; max-width: 100%; table-layout: fixed; word-wrap: break-word; overflow-wrap: anywhere; word-break: break-word;`.
3. The outermost wrapper MUST be exactly: `<div style="width:100%; max-width:100%; margin:0 auto; padding:10px; box-sizing:border-box; direction:ltr; overflow-wrap:anywhere; word-break:break-word; overflow:hidden;">`.
"""

    if mode == "simulation":
        return f"""CLONING: Reproduce EXACTLY text/tables from the reference image.
IGNORE logos, stamps, signatures. Do NOT invent data.
⚠️ EXCEPTIONAL SCENARIO: If the image is a SINGLE circular stamp, produce ONLY an inline <svg> element.

{global_rules}

RULE E – NO BORDERS: You MUST NOT add any outer border, stroke, or page-like box.
RULE F – CAMERA DISTORTION: Ignore physical distortion. Reconstruct in its NATURAL format adapting to the canvas."""

    design_base = ""
    if style == "modern":
        design_base = """MODERN/ELEGANT - Professional, clean, harmonious.
TYPOGRAPHY: Title 17px bold, dark slate. Section headings 14px bold.
COLOR PALETTE: Text: #2c3e50, Primary: #1a5276, Accents: #2980b9, Backgrounds: #f8f9fa.
DESIGN ELEMENTS:
- Section headings: color:#1a5276; border-inline-start:4px solid #2980b9; padding-inline-start:10px; margin-top:15px; margin-bottom:10px; background:#ebf5fb; padding-top:6px; padding-bottom:6px; border-radius:4px;
- Tables: th: background:#ebf5fb; color:#1a5276; td: border:1px solid #d5dbdb; color:#2c3e50;"""
    else:
        design_base = """FORMAL/OFFICIAL - Professional Mauritanian document design.
TYPOGRAPHY: Title 16px bold centered. Sections 13px bold. Body 13px.
TABLE DESIGN: th: background:#333; color:white; padding:7px; border:1px solid #333; td: padding:6px 8px; border:1px solid #ddd; Even rows: background:#f7f7f7;"""

    return f"{design_base}\n\n{global_rules}"


def detect_document_type(user_msg):
    msg_lower = user_msg.lower()
    single_page_keywords = ['فاتورة', 'facture', 'invoice', 'devis', 'عرض سعر', 'bon', 'شهادة', 'certificate', 'attestation', 'رسالة', 'letter', 'lettre', 'courrier', 'إيصال', 'receipt', 'reçu', 'تصريح', 'declaration', 'إذن', 'autorisation', 'بطاقة', 'card']
    multi_page_keywords = ['تقرير', 'report', 'rapport', 'دراسة', 'study', 'étude', 'بحث', 'research', 'خطة', 'plan', 'مشروع', 'project', 'تفصيلي', 'detailed', 'شامل', 'comprehensive']

    for kw in single_page_keywords:
        if kw in msg_lower: return "single_page"
    for kw in multi_page_keywords:
        if kw in msg_lower: return "multi_page"
    return "auto"


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V9.6 Server Active"})


@app.route("/gemini", methods=["POST"])
def generate():
    if not get_client(): return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get("message", "")
        mode = data.get("mode", "documents")
        style = data.get("style", "formal")
        page_size = data.get("pageSize", "a4Portrait")
        reference_b64 = data.get("reference_image")
        letterhead_b64 = data.get("letterhead_image")

        style_prompt = get_style_prompt(style, mode)
        doc_type = detect_document_type(user_msg)

        page_dimensions = {
            "a4Portrait": {"w": 595, "h": 842, "orientation": "portrait", "physical": "21.0cm x 29.7cm"},
            "a4Landscape": {"w": 842, "h": 595, "orientation": "landscape", "physical": "29.7cm x 21.0cm"},
            "a3": {"w": 842, "h": 1191, "orientation": "portrait A3", "physical": "29.7cm x 42.0cm"},
            "a5": {"w": 420, "h": 595, "orientation": "portrait A5", "physical": "14.8cm x 21.0cm"},
        }
        page_info = page_dimensions.get(page_size, page_dimensions["a4Portrait"])
        is_landscape = page_info["w"] > page_info["h"]

        landscape_extra = ""
        if is_landscape:
            landscape_extra = f" LANDSCAPE LAYOUT (CRITICAL): The physical canvas is {page_info['physical']}. You MUST ensure the ENTIRE document fits within this width. USE `table-layout: fixed !important; overflow-wrap: anywhere !important; width: 100% !important;` on tables."

        # إخبار النموذج بالأبعاد الفيزيائية بوضوح كما اقترحت
        orientation_instruction = f"PAGE FORMAT: {page_info['orientation']} — Physical Canvas Size: {page_info['physical']} (Target width: {page_info['w']}px). {landscape_extra} SMART LAYOUT DETECTION: You must adapt all fonts and tables to fit inside this exact physical space. ABSOLUTELY NO FIXED PIXEL WIDTHS."
        
        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = "\nATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        doc_type_instruction = ""
        if doc_type == "single_page":
            doc_type_instruction = """SINGLE-PAGE DOCUMENT: Keep content compact but READABLE."""
        elif doc_type == "multi_page":
            doc_type_instruction = """MULTI-PAGE DOCUMENT: Use proper structure."""

        if mode == "simulation":
            svg_rule = "NO `<html>`, `<body>`. (EXCEPTION: `<svg>` is ONLY allowed for the standalone circular stamp scenario)."
        else:
            svg_rule = "NO `<svg>`, `<html>`, `<body>`."

        prompt = f"""You are a Master Document Designer and Expert Typesetter.

{style_prompt}
{orientation_instruction}
{ref_note}
{doc_type_instruction}

CRITICAL RULES - CHOOSE SCENARIO 1 OR 2:

➡ SCENARIO 1: TEXT FORMATTING
If the user provides a draft or text: Make it visually STUNNING using HTML/CSS. DO NOT invent missing elements.

➡ SCENARIO 2: DOCUMENT GENERATION
If the user gives a brief instruction: Generate the FULL professional structure. ZERO HALLUCINATION.

TECHNICAL RULES (STRICT):
1. PURE HTML ONLY. Just `<div>`, `<table>`, `<h1>`, `<p>`. {svg_rule}
2. NO BORDERS AROUND DOCUMENT.
3. GLOBAL LTR LOCK (CRITICAL TO PREVENT REVERSING):
   - The OUTER wrapper MUST use `dir="ltr"`.
   - ALL `<table>` elements MUST use `dir="ltr"`.
   - For Arabic text alignment, apply `dir="rtl" style="text-align:right;"` explicitly on the cell.

OUTPUT: Return raw HTML only."""

        contents = [user_msg] if user_msg else ["Create a formal document."]

        if reference_b64:
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(reference_b64), mime_type="image/jpeg"))

        if letterhead_b64:
            contents.append("Ensure layout fits empty space below this letterhead.")
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(letterhead_b64), mime_type="image/jpeg"))

        gen_config = get_types().GenerateContentConfig(system_instruction=prompt, temperature=0.15, max_output_tokens=20000)

        try:
            resp = call_gemini("gemini-3-flash-preview", contents, gen_config, 55)
        except:
            resp = call_gemini("gemini-2.5-flash", contents, gen_config, 50)

        clean_html = clean_html_output(resp.text or "")
        logger.info(f"✅ Generated HTML (mode: {mode}, page: {page_size})")
        return jsonify({"response": clean_html})

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


@app.route("/modify", methods=["POST"])
def modify():
    if not get_client(): return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json

        current_html = data.get("current_html") or data.get("currentSVG") or data.get("current_svg") or data.get("htmlContent") or ""
        instruction = data.get("instruction") or data.get("prompt") or ""
        ref_b64 = data.get("reference_image")

        if not current_html.strip():
            logger.error("❌ ERROR: current_html is empty!")
            return jsonify({"error": "Failed", "details": "لم يتم العثور على محتوى المستند الحالي لإجراء التعديل الذكي. يرجى المحاولة مرة أخرى."}), 400

        img_note = ""
        if ref_b64:
            img_note = f"\nINSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        sys = f"""You are a STRICT HTML PATCHING ENGINE. You are NOT a designer.
You will receive a <CURRENT_HTML> document and a <USER_REQUEST>.

CRITICAL RULES (DO NOT DISOBEY):
1. EXACT COPY-PASTE: You MUST output the EXACT SAME HTML structure, classes, and styles provided in <CURRENT_HTML>.
2. SURGICAL EDIT: Apply the exact surgical change requested.
3. GLOBAL LTR LOCK & BIDI PROTECTION (CRITICAL): Preserve `dir="ltr"` on wrappers and tables. Keep `dir="ltr" style="display:inline-block; unicode-bidi:bidi-override;"` around phone numbers to prevent reversing.
4. OVERFLOW PROTECTION: Keep `overflow-wrap: anywhere;` and `table-layout: fixed;` on tables.
5. RETURN FULL HTML: Return the complete patched HTML. Do not truncate.
{img_note}

OUTPUT FORMAT:
[MESSAGE]
وصف قصير للتعديل باللغة العربية
[/MESSAGE]
[HTML]
(ضع هنا كود الـ HTML المعدل كاملاً)
[/HTML]"""

        cfg = get_types().GenerateContentConfig(system_instruction=sys, temperature=0.0, max_output_tokens=16384)

        cts = [
            f"<CURRENT_HTML>\n{current_html}\n</CURRENT_HTML>\n\n<USER_REQUEST>\n{instruction}\n</USER_REQUEST>\n\nTASK: Apply the exact surgical change (including mathematical recalculations if needed) and return the FULL updated HTML."
        ]

        if ref_b64:
            cts.append(get_types().Part.from_bytes(data=base64.b64decode(ref_b64), mime_type="image/jpeg"))

        try:
            resp = call_gemini("gemini-3-flash-preview", cts, cfg, 55)
        except:
            resp = call_gemini("gemini-2.5-flash", cts, cfg, 50)

        text = resp.text or ""

        msg_match = re.search(r'\[MESSAGE\](.*?)\[/MESSAGE\]', text, re.DOTALL | re.IGNORECASE)
        html_match = re.search(r'\[HTML\](.*?)\[/HTML\]', text, re.DOTALL | re.IGNORECASE)

        if html_match:
            new_inner = html_match.group(1).strip()
            message = msg_match.group(1).strip() if msg_match else "تم التعديل بنجاح ✨"
        else:
            new_inner = clean_html_output(text)
            new_inner = re.sub(r'\[MESSAGE\].*?\[/MESSAGE\]', '', new_inner, flags=re.DOTALL | re.IGNORECASE).strip()
            message = "تم التعديل بنجاح ✨"

        return jsonify({"response": new_inner, "message": message})

    except Exception as e:
        logger.error(f"Modify Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


@app.route("/format", methods=["POST"])
def smart_format():
    if not get_client(): return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_html = data.get("current_html", "")
        style = data.get("style", "formal")

        style_prompt = get_style_prompt(style, "documents")

        sys = f"""You are a Master Document Editor and Typesetter.
The user has manually edited this document on a mobile device. It may have messy spacing, broken tags, or unstructured loose text.

YOUR MISSION:
1. CLEANUP & STRUCTURE: Wrap any loose text in proper `<p>` tags. Apply logical Text Alignments.
2. STRICT PRESERVATION: NEVER delete or alter the actual facts, numbers, or core meaning.
3. DIRECTIONALITY FIX (CRITICAL): Ensure outermost wrappers and ALL tables use `dir="ltr"` to prevent auto-flipping. Apply `dir="rtl" style="text-align:right"` only on specific paragraphs containing Arabic. Protect phone numbers with `<span dir="ltr" style="display:inline-block; unicode-bidi:bidi-override; white-space:nowrap;">`.
4. OVERFLOW FIX: Ensure tables use `table-layout: fixed; overflow-wrap: anywhere;`.

{style_prompt}

OUTPUT FORMAT:
[MESSAGE]
تم تنسيق وترتيب المستند بنجاح ✨
[/MESSAGE]
[HTML]
(ضع هنا كود الـ HTML المنسق كاملاً)
[/HTML]"""

        cfg = get_types().GenerateContentConfig(system_instruction=sys, temperature=0.1, max_output_tokens=16384)
        cts = [f"<MESSY_HTML>\n{current_html}\n</MESSY_HTML>\n\nPlease format, fix Bidi issues, clean spacing, and align text professionally."]

        try:
            resp = call_gemini("gemini-3-flash-preview", cts, cfg, 55)
        except:
            resp = call_gemini("gemini-2.5-flash", cts, cfg, 50)

        text = resp.text or ""

        msg_match = re.search(r'\[MESSAGE\](.*?)\[/MESSAGE\]', text, re.DOTALL | re.IGNORECASE)
        html_match = re.search(r'\[HTML\](.*?)\[/HTML\]', text, re.DOTALL | re.IGNORECASE)

        if html_match:
            new_inner = html_match.group(1).strip()
            message = msg_match.group(1).strip() if msg_match else "تم التنسيق ✨"
        else:
            new_inner = clean_html_output(text)
            new_inner = re.sub(r'\[MESSAGE\].*?\[/MESSAGE\]', '', new_inner, flags=re.DOTALL | re.IGNORECASE).strip()
            message = "تم التنسيق ✨"

        logger.info("✅ Document Smartly Formatted")
        return jsonify({"response": new_inner, "message": message})

    except Exception as e:
        logger.error(f"Format Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


@app.route("/generate_image", methods=["POST"])
def generate_image():
    import urllib.request
    import urllib.error
    import json

    try:
        k = os.environ.get("GOOGLE_API_KEY2") or os.environ.get("GOOGLE_API_KEY")
        if not k:
            logger.error("❌ API Key is missing!")
            return jsonify({"error": "Failed", "details": "مفتاح API غير موجود."}), 500

        data = request.json
        user_prompt = data.get("prompt", "")
        reference_images = data.get("reference_images", [])
        aspect_ratio = data.get("aspectRatio", "1:1")

        if not user_prompt.strip():
            return jsonify({"error": "Failed", "details": "يرجى كتابة وصف للتصميم."}), 400

        logger.info(f"🎨 Generating Image (Ratio: {aspect_ratio})...")

        system_text = """You are an elite creative designer and art director.
RULES:
1. Generate EXACTLY what the user describes with maximum professional quality.
2. NO MOCKUPS ALLOWED (STRICTLY FORBIDDEN). DO NOT place designs on walls, paper, screens, 3D objects, or merchandise. Provide the RAW, FLAT, modern, and professional design directly.
3. For logos and branding: Clean, scalable, flat professional design with clear typography. NO 3D mockups.
4. For print designs (cards, flyers, posters): Clean layout, negative space, precise text rendering.
5. For social media: Visually striking, commercial studio lighting, vibrant colors.
6. CULTURAL CONTEXT (STRICT): If people or environments are included, they MUST have authentic Mauritanian facial features and reflect Mauritanian culture (Men MUST wear traditional Daraa/Boubou, Women MUST wear traditional Melhfa).
7. Render any Arabic text inside images with perfect spelling and beautiful typography.
8. Always produce 8K quality, cinematic lighting, hyper-realistic or professional graphic style.
9. If reference images are provided, incorporate them naturally into the design or modify them according to instructions."""

        user_parts = [{"text": user_prompt}]

        for b64_img in reference_images:
            clean_b64 = b64_img
            if "," in clean_b64:
                clean_b64 = clean_b64.split(",", 1)[1]
            user_parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": clean_b64
                }
            })

        if reference_images:
            logger.info(f"📎 {len(reference_images)} Reference image(s) attached")

        payload = {
            "contents": [{"role": "user", "parts": user_parts}],
            "systemInstruction": {"parts": [{"text": system_text}]},
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "temperature": 0.7
            }
        }

        headers = {"Content-Type": "application/json"}

        models = [
            ("gemini-3-pro-image-preview", "Nano Banana Pro", 120),
            ("gemini-3.1-flash-image-preview", "Nano Banana 2", 90),
            ("gemini-2.5-flash", "Gemini 2.5 Flash", 90),
        ]

        for model_id, model_name, timeout in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={k}"

            try:
                logger.info(f"🚀 Trying {model_name} ({model_id})...")
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    result = json.loads(response.read().decode('utf-8'))

                parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        logger.info(f"✅ Generated with {model_name}")
                        return jsonify({
                            "response": part["inlineData"]["data"],
                            "message": f"تم التصميم بنجاح ✨ ({model_name})"
                        })

                logger.warning(f"⚠️ {model_name} returned no image")
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                logger.warning(f"❌ {model_name} HTTP {e.code}: {error_body[:300]}")
            except Exception as e:
                logger.warning(f"❌ {model_name} failed: {e}")

        return jsonify({"error": "Failed", "details": "جميع النماذج فشلت في توليد الصورة."}), 500

    except Exception as e:
        logger.error(f"❌ Server Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": f"خطأ في الخادم: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
