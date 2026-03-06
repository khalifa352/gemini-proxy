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
                logger.info("✅ Monjez V9.6 Server (Smart Formatting & Bidi Protection Ready 🪄)")
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
    """Clean output from any Markdown wrapping, extract pure HTML, and remove editor artifacts"""
    raw = raw_text.strip()
    if raw.startswith("```"): 
        raw = re.sub(r"^```(?:html|xml)?\n?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\n?```$", "", raw)

    # Extract inner HTML if wrapped in SVG
    div_match = re.search(r'<div[^>]*xmlns="[http://www.w3.org/1999/xhtml](http://www.w3.org/1999/xhtml)"[^>]*>(.*?)</div>\s*</foreignObject>', raw, re.DOTALL)
    if div_match:
        raw = div_match.group(1)
        
    # 🧹 تنظيف الأكواد المتبقية من وضع التعديل
    raw = re.sub(r'\s?contenteditable="[^"]*"', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s?contenteditable=\'[^\']*\'', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s?contenteditable', '', raw, flags=re.IGNORECASE)
        
    return raw.strip()

# ══════════════════════════════════════════════════════════
# STYLE PROMPTS - FORMAL vs MODERN
# ══════════════════════════════════════════════════════════

def get_style_prompt(style, mode):
    if mode == "simulation":
        return """CLONING: Reproduce EXACTLY text/tables from the reference image.
IGNORE logos, stamps, signatures. Do NOT invent data.

⚠️ EXCEPTIONAL SCENARIO – STANDALONE CIRCULAR STAMP (MANDATORY):
If the attached image is a SINGLE circular stamp (rubber stamp, official seal) and NOT a full document page, the following rules override everything else:
1. ABSOLUTELY FORBIDDEN to invent, fabricate, or hallucinate any certificate, document body, or surrounding text. You must produce ONLY the stamp reproduction.
2. You MUST reproduce the stamp as an inline <svg> element:
   - Use <circle> elements for the stamp's circular borders (outer ring, inner ring, etc.).
   - Use <path> with arc definitions and <textPath> to render curved/circular text exactly as it appears in the original image, preserving the correct reading direction and curvature.
   - Place any center text (names, emblems, stars, symbols) using <text> with x/y positioning centered inside the SVG.
   - Match colors faithfully (typically dark blue, red, or black).
   - Set a reasonable viewBox (e.g., "0 0 250 250") and width/height.
3. This is the ONLY scenario where <svg> output is permitted. For all other document types, <svg> remains strictly forbidden.
4. Output the <svg> element directly with NO surrounding HTML wrapper, NO invented document, NO certificate text.

⚠️ BILINGUAL DOCUMENT LAYOUT LOCK (Arabic + French/English – MANDATORY):
If the reference image contains a dual-language side-by-side layout (e.g., Arabic on the right side and French/English on the left side, or vice versa), you MUST strictly lock the visual column positions to prevent any horizontal flip:
1. The OUTER wrapper container MUST use dir="ltr" to establish a stable left-to-right column order that matches the original image. NEVER use dir="rtl" on the outer wrapper for bilingual documents.
2. Use a two-column structure (CSS flexbox with `display:flex;` or a two-cell `<table>`) where each column has its OWN explicit direction:
   - Left column: dir="ltr" style="text-align:left;" → for French/English content.
   - Right column: dir="rtl" style="text-align:right;" → for Arabic content.
3. If the original image has Arabic on the LEFT and French on the RIGHT (reversed layout), reproduce that exact arrangement – always match the image's visual positioning.
4. Each column must be self-contained with its own dir attribute. Do NOT rely on CSS float or any property that could be affected by a parent RTL context.
5. This layout lock ensures the cloned document visually matches the original reference image pixel-for-pixel in column arrangement."""

    if style == "modern":
        return """MODERN/ELEGANT - Professional, clean, harmonious, and very comfortable on the eyes.

TYPOGRAPHY: Title 17px bold, dark slate. Section headings 14px bold with a subtle colored right-border.

COLOR PALETTE (Harmonious & Comfortable):
- Text: #2c3e50 (Dark slate, softer and more elegant than pure black)
- Primary/Headings: #1a5276 (Deep elegant blue)
- Accents/Borders: #2980b9 (Calm professional blue)
- Subtle Backgrounds: #f8f9fa (Off-white/light gray), #ebf5fb (Very pale blue for table headers & section backgrounds)
- Dividers/Borders: #d5dbdb (Soft gray-blue)

DESIGN ELEMENTS:
- Section headings: color:#1a5276; border-inline-start:4px solid #2980b9; padding-inline-start:10px; margin-top:15px; margin-bottom:10px; background:#ebf5fb; padding-top:6px; padding-bottom:6px; border-radius:4px;
- Tables: Soft and clean styling.
  th: background:#ebf5fb; color:#1a5276; padding:8px; font-size:12px; border:1px solid #d5dbdb; font-weight:bold; text-align:start;
  td: padding:8px; font-size:12px; border:1px solid #d5dbdb; color:#2c3e50; text-align:start;
  Even rows: background:#fcfcfc;
- Dividers: <div style="height:1px; background:linear-gradient(to right, #2980b9, transparent); opacity:0.5; margin:14px 0;"></div>

INVOICE TABLE (If applicable):
Columns: Description | Price | Qty | Total (MUST translate these headers to match the user's requested language. Order LTR for French, RTL for Arabic).
Total row in <tfoot> with background:#ebf5fb; color:#1a5276; font-weight:bold."""

    # Default: formal
    return """FORMAL/OFFICIAL - Professional Mauritanian document design.

TYPOGRAPHY: Title 16px bold centered. Sections 13px bold.
Body 13px. NO bright colors. Colors: #333, #555, #f7f7f7, #f0f0f0, #ddd.

TABLE DESIGN:
- th: background:#333; color:white; padding:7px; font-size:12px; border:1px solid #333; text-align:start;
- td: padding:6px 8px; font-size:12px; border:1px solid #ddd; text-align:start;
- Even rows: background:#f7f7f7;

INVOICE TABLE (If applicable):
Columns: Description | Price | Qty | Total (MUST translate these headers to match the user's requested language. Order LTR for French, RTL for Arabic).
Total row in <tfoot>: "Total" colspan=3, amount in last column only."""

def detect_document_type(user_msg):
    msg_lower = user_msg.lower()
    single_page_keywords = ['فاتورة', 'facture', 'invoice', 'devis', 'عرض سعر', 'bon', 'شهادة', 'certificate', 'attestation', 'رسالة', 'letter', 'lettre', 'courrier', 'إيصال', 'receipt', 'reçu', 'تصريح', 'declaration', 'إذن', 'autorisation', 'بطاقة', 'card']
    multi_page_keywords = ['تقرير', 'report', 'rapport', 'دراسة', 'study', 'étude', 'بحث', 'research', 'خطة', 'plan', 'مشروع', 'project', 'تفصيلي', 'detailed', 'شامل', 'comprehensive']

    for kw in single_page_keywords:
        if kw in msg_lower: return "single_page"
    for kw in multi_page_keywords:
        if kw in msg_lower: return "multi_page"
    return "auto"

# ══════════════════════════════════════════════════════════
# API ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V9.6 Server Active ⚡"})

@app.route("/gemini", methods=["POST"])
def generate():
    if not get_client(): return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get("message", "")
        mode = data.get("mode", "documents")
        style = data.get("style", "formal")
        reference_b64 = data.get("reference_image")
        letterhead_b64 = data.get("letterhead_image")

        style_prompt = get_style_prompt(style, mode)
        doc_type = detect_document_type(user_msg)

        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = "\nATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        doc_type_instruction = ""
        if doc_type == "single_page":
            doc_type_instruction = """SINGLE-PAGE DOCUMENT: Keep content compact but READABLE. Reduce margins slightly if needed. NEVER make font smaller than 11px."""
        elif doc_type == "multi_page":
            doc_type_instruction = """MULTI-PAGE DOCUMENT: Use proper structure. Tables shouldn't be nested complexly."""

        # ── قاعدة SVG: مسموح فقط لسيناريو الختم في وضع المحاكاة ──
        if mode == "simulation":
            svg_rule = "NO `<html>`, `<body>`. (EXCEPTION: `<svg>` is ONLY allowed for the standalone circular stamp scenario described above in the style instructions. For all other simulation documents, `<svg>` remains forbidden)."
        else:
            svg_rule = "NO `<svg>`, `<html>`, `<body>`."

        # 🛠 تم دمج كافة القواعد الصارمة + التوزيع الرأسي الذكي للمستندات القصيرة
        prompt = f"""You are a Master Document Designer and Expert Typesetter.

{style_prompt}
{ref_note}
{doc_type_instruction}

CRITICAL RULES - CHOOSE SCENARIO 1 OR 2:

➡ SCENARIO 1: TEXT FORMATTING (USER PROVIDED THE CONTENT)
If the user provides a draft, text, article, or letter:
- YOUR GOAL: Make their exact text look visually STUNNING and PROFESSIONAL using HTML/CSS.
- RULE 1 (STYLE THE EXISTING): If the user included titles, dates, or addresses in their text, you MUST format them beautifully (e.g., use <h1> for their titles, proper alignment for their addresses). Elevate their content!
- RULE 2 (NO INVENTIONS): STRICTLY FORBIDDEN to invent or append missing elements. If the user didn't write a signature block, DO NOT add one. If they didn't write a subject line (Objet), DO NOT invent one.
- RULE 3: Fix spelling/grammar, organize paragraphs, and apply elegant typography, but the actual textual content must remain 100% faithful to their input.

➡ SCENARIO 2: DOCUMENT GENERATION (USER ASKS YOU TO WRITE IT FROM SCRATCH)
If the user gives a brief instruction (e.g., "Create an invoice", "Write a letter for X"):
- Act as an Expert Content Creator. Generate the FULL professional structure (tables, fields, subject lines).
- Use elegant blank underlines `<span style="border-bottom:1px solid #111; display:inline-block; min-width:120px;"></span>` for missing data. NO brackets like [Name].
- ZERO HALLUCINATION: No fake names, numbers, or companies.

TECHNICAL RULES & DESIGN RESTRICTIONS (STRICT):
1. PURE HTML ONLY. Just `<div>`, `<table>`, `<h1>`, `<p>`. {svg_rule}
2. NO BORDERS AROUND DOCUMENT (CRITICAL ❌): DO NOT wrap the content in any outer page container, card, or div with borders (NO STROKE), shadows, or fixed heights. The background must remain entirely transparent and free of bounding boxes.
3. NO FAKE LETTERHEADS: Assume the document will be printed on a beautiful, pre-designed official letterhead paper. DO NOT simulate logos, company names, or header contact info at the very top unless explicitly written by the user.
4. SMART VERTICAL DISTRIBUTION (ADAPTIVE LAYOUT ⚖️): Evaluate the content length before generating HTML. If the document is VERY SHORT (e.g., a brief letter, certificate, or single paragraph), center it elegantly on the page to avoid an ugly empty bottom half. Use a wrapper like `<div style="display: flex; flex-direction: column; justify-content: center; min-height: 550px;">`. If the document is long, just let it flow naturally.
5. PARAGRAPHS: `<p style="margin-bottom: 10px; line-height: 1.65;">`
6. BIDI PROTECTION: Wrap phone numbers & Latin words in `<span dir="ltr" style="unicode-bidi: isolate; display: inline-block;">...</span>`.
7. EXACT LANGUAGE MATCH: Keep the user's language.
8. DIRECTION & ALIGNMENT: French/English -> `<div dir="ltr" style="text-align: left;">`. Arabic -> `<div dir="rtl" style="text-align: right;">`.
9. BILINGUAL DOCUMENT LAYOUT LOCK (CRITICAL FOR DUAL-LANGUAGE CONTENT ⚠️): If the document contains TWO languages side by side (e.g., Arabic + French, Arabic + English), you MUST prevent horizontal flipping by following these strict rules:
   - The OUTER wrapper MUST use `dir="ltr"` to establish a stable, predictable column order. NEVER use `dir="rtl"` on the outer wrapper of a bilingual document.
   - Use a two-column layout (CSS `display:flex;` or a two-cell `<table>`) where:
     • LEFT column: `dir="rtl" style="text-align:right; width:50%;"` → Arabic content.
     • RIGHT column: `dir="ltr" style="text-align:left; width:50%;"` → French/English content.
   - Each column MUST have its own explicit `dir` attribute. Do NOT rely on inheritance from a parent RTL context.
   - Shared headers or titles that span both columns should be centered and wrapped in their own `dir`-appropriate container.
   - This rule applies to invoices, certificates, contracts, letters, or ANY document the user requests in two languages side by side.

OUTPUT: Return raw HTML only."""

        contents = [user_msg] if user_msg else ["Create a formal document."]
        
        if reference_b64:
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(reference_b64), mime_type="image/jpeg"))
        
        if letterhead_b64:
            contents.append("Ensure layout fits empty space below this letterhead.")
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(letterhead_b64), mime_type="image/jpeg"))

        gen_config = get_types().GenerateContentConfig(system_instruction=prompt, temperature=0.15, max_output_tokens=16000)

        try:
            resp = call_gemini("gemini-3-flash-preview", contents, gen_config, 55)
        except:
            resp = call_gemini("gemini-2.5-flash", contents, gen_config, 50)

        clean_html = clean_html_output(resp.text or "")
        logger.info(f"✅ Generated HTML (mode: {mode})")
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
            logger.error("❌ ERROR: current_html is empty! AI will hallucinate if allowed.")
            return jsonify({"error": "Failed", "details": "لم يتم العثور على محتوى المستند الحالي لإجراء التعديل الذكي. يرجى المحاولة مرة أخرى."}), 400

        img_note = ""
        if ref_b64:
            img_note = f"\nINSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        sys = f"""You are a STRICT HTML PATCHING ENGINE. You are NOT a designer.
You will receive a <CURRENT_HTML> document and a <USER_REQUEST>.

CRITICAL RULES (DO NOT DISOBEY):
1. ZERO HALLUCINATION: Do NOT invent a new document. Do NOT rewrite from scratch.
2. EXACT COPY-PASTE: You MUST output the EXACT SAME HTML structure, classes, and styles provided in <CURRENT_HTML>.
3. SURGICAL EDIT & LOGICAL CONSISTENCY (CRITICAL): Find the specific element mentioned in <USER_REQUEST> and change it. IF your change affects other parts of the document (e.g., changing a price/quantity means the "Total" MUST be recalculated and mathematically updated, or changing a name/date means updating it across connected paragraphs), you MUST apply these cascading secondary updates automatically so the document remains logically accurate.
4. NO REDESIGN: Keep all fonts, colors, layouts, and tables entirely untouched unless the user explicitly asks to change them.
5. RETURN FULL HTML: Return the complete patched HTML. Do not truncate or use placeholders.
6. LANGUAGE & BIDI: Keep the original language. Preserve all `dir="ltr"` and `dir="rtl"`.
{img_note}

OUTPUT FORMAT:
Do NOT output JSON. You MUST output exactly like this:
[MESSAGE]
وصف قصير للتعديل باللغة العربية (مثال: تم تعديل السعر المطلوب)
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
1. CLEANUP & STRUCTURE: Wrap any loose text in proper `<p>` tags. Ensure headings are used logically. Apply logical Text Alignments.
2. FIX TABLES: If a table is broken, fix its HTML structure.
3. STRICT PRESERVATION: NEVER delete or alter the actual facts, numbers, or core meaning. ONLY improve presentation.
4. BIDI PROTECTION & LANGUAGE: Wrap phone numbers in `<span dir="ltr"...>`. DO NOT translate the text.
5. DIRECTIONALITY: If document is French/English, wrap ENTIRE output in `<div dir="ltr" style="text-align: left;">`. If Arabic, use `dir="rtl"`.

{style_prompt}

OUTPUT FORMAT:
Do NOT output JSON. You MUST output exactly like this:
[MESSAGE]
تم تنسيق وترتيب المستند بنجاح ✨
[/MESSAGE]
[HTML]
(ضع هنا كود الـ HTML المنسق كاملاً)
[/HTML]"""

        cfg = get_types().GenerateContentConfig(system_instruction=sys, temperature=0.1, max_output_tokens=16384)
        cts = [f"<MESSY_HTML>\n{current_html}\n</MESSY_HTML>\n\nPlease format, fix Bidi issues, and align text professionally."]

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
        # 🛠 التعديل الأول: استخدام المفتاح الأساسي كبديل احتياطي لمنع الانهيار الفوري
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
2. NO MOCKUPS ALLOWED (STRICTLY FORBIDDEN). DO NOT place designs on walls, paper, screens, 3D objects, or merchandise. Provide the RAW, FLAT, modern, and professional design directly. This section is dedicated to modern professional logos, print materials, and social media.
3. For logos and branding: Clean, scalable, flat professional design with clear typography. NO 3D mockups.
4. For print designs (cards, flyers, posters): Clean layout, negative space, precise text rendering.
5. For social media: Visually striking, commercial studio lighting, vibrant colors.
6. CULTURAL CONTEXT (STRICT): If people or environments are included, they MUST have authentic Mauritanian facial features and reflect Mauritanian culture (Men MUST wear traditional Daraa/Boubou, Women MUST wear traditional Melhfa). The vibe should be distinctly Mauritanian.
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

        # 🛠 التعديل الثاني: ضبط Payload لتوافق سيرفرات Gemini وعدم رفضها
        payload = {
            "contents": [{"role": "user", "parts": user_parts}],
            "systemInstruction": {"parts": [{"text": system_text}]},
            "generationConfig": {
                "responseModalities": ["IMAGE"], # يجب أن تكون IMAGE فقط
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
            # 🛠 التعديل الثالث: استخدام الرابط الصحيح الذي يقبل المفاتيح (generativelanguage)
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
