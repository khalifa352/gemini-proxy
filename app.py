import os
import re
import json
import logging
import base64
import io
import time
import concurrent.futures
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez_V10_Server")

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
                logger.info("✅ Monjez V10 Server (with Word Export via CloudConvert API)")
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
# CloudConvert API — PDF to Word (DOCX)
# ══════════════════════════════════════════════════════════

def cloudconvert_pdf_to_word(pdf_bytes):
    """
    Full CloudConvert API v2 flow via REST.
    No external libraries needed. Uses native urllib.
    Returns: DOCX file bytes
    """
    import urllib.request
    import urllib.error
    import urllib.parse

    raw_api_key = os.environ.get("CLOUDCONVERT_API_KEY")
    if not raw_api_key:
        raise ValueError("CLOUDCONVERT_API_KEY غير مُعرّف في متغيرات البيئة")

    # تنظيف المفتاح من أي أسطر جديدة أو مسافات مخفية لمنع خطأ Invalid Header
    api_key = raw_api_key.strip().replace('\n', '').replace('\r', '').replace(' ', '')

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # ── Step 1: Create Job ──
    logger.info("⚙️ CloudConvert: Creating Job...")
    job_payload = {
        "tasks": {
            "import-it": {"operation": "import/upload"},
            "convert-it": {
                "operation": "convert",
                "input_format": "pdf",
                "output_format": "docx",
                "input": ["import-it"]
            },
            "export-it": {"operation": "export/url", "input": ["convert-it"]}
        }
    }

    try:
        req = urllib.request.Request("https://api.cloudconvert.com/v2/jobs", data=json.dumps(job_payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            job_data = json.loads(resp.read().decode('utf-8'))['data']
        job_id = job_data['id']
        
        # استخراج تفاصيل الرفع
        upload_task = next(t for t in job_data['tasks'] if t['name'] == 'import-it')
        upload_url = upload_task['result']['form']['url']
        upload_params = upload_task['result']['form']['parameters']
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        logger.error(f"❌ Job creation failed ({e.code}): {error_body}")
        raise ValueError(f"فشل بدء مهمة التحويل مع CloudConvert: {error_body[:100]}")
    except Exception as e:
        raise ValueError(f"فشل إنشاء المهمة: {str(e)}")

    # ── Step 2: Upload File ──
    logger.info("📤 CloudConvert: Uploading PDF...")
    try:
        boundary = f"----CloudConvertBoundary{int(time.time() * 1000)}"
        body = b""
        
        for k, v in upload_params.items():
            body += f"--{boundary}\r\n".encode()
            body += f"Content-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode()
            body += f"{v}\r\n".encode()
        
        body += f"--{boundary}\r\n".encode()
        body += b"Content-Disposition: form-data; name=\"file\"; filename=\"document.pdf\"\r\n"
        body += b"Content-Type: application/pdf\r\n\r\n"
        body += pdf_bytes + b"\r\n"
        body += f"--{boundary}--\r\n".encode()

        upload_req = urllib.request.Request(upload_url, data=body, method='POST')
        upload_req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        with urllib.request.urlopen(upload_req, timeout=60) as resp:
            pass # تم الرفع بنجاح
        logger.info("✅ PDF Uploaded")
    except Exception as e:
        raise ValueError(f"فشل رفع الملف إلى الخادم: {str(e)}")

    # ── Step 3: Poll Job Status ──
    logger.info("⏳ CloudConvert: Polling job status...")
    download_url = None
    attempts = 0
    while attempts < 40: # انتظار بحد أقصى دقيقتين
        time.sleep(3)
        attempts += 1
        try:
            poll_req = urllib.request.Request(f"https://api.cloudconvert.com/v2/jobs/{job_id}", headers=headers)
            with urllib.request.urlopen(poll_req, timeout=15) as resp:
                status_data = json.loads(resp.read().decode('utf-8'))['data']
            
            status = status_data['status']
            if status == 'finished':
                export_task = next(t for t in status_data['tasks'] if t['name'] == 'export-it')
                download_url = export_task['result']['files'][0]['url']
                logger.info("✅ Conversion done!")
                break
            elif status == 'error':
                raise ValueError("فشلت عملية التحويل داخل CloudConvert.")
        except urllib.error.HTTPError as e:
            continue
    
    if not download_url:
        raise ValueError("انتهى وقت الانتظار. استغرقت عملية التحويل وقتاً طويلاً.")

    # ── Step 4: Download DOCX ──
    logger.info("📥 CloudConvert: Downloading Word file...")
    try:
        req_dl = urllib.request.Request(download_url)
        with urllib.request.urlopen(req_dl, timeout=60) as resp:
            docx_bytes = resp.read()
        logger.info(f"✅ Word downloaded: {len(docx_bytes)} bytes")
        return docx_bytes
    except Exception as e:
        raise ValueError(f"فشل تحميل ملف الوورد: {str(e)}")


# ══════════════════════════════════════════════════════════
# STYLE PROMPTS
# ══════════════════════════════════════════════════════════

def get_style_prompt(style, mode):
    global_rules = """
⚠️ STRICT PRESERVATION RULE (CRITICAL - DO NOT HALLUCINATE):
1. If the user provides text, names, numbers, or a draft: You MUST NOT add, modify, or remove a single letter of their content. Your ONLY job is to format their exact text into professional HTML. 
2. DO NOT invent fake data, placeholders, or dummy text.
3. DO NOT CREATE FAKE LETTERHEADS: Never invent fake company names, logos, or headers at the top of the document. The user has their own letterhead tool. Start directly with the document title and content.
4. ONLY DRAFT IF EXPLICITLY ASKED: You may generate/write text ONLY if the user explicitly uses words like "write for me", "draft", "research", or asks you to create content from scratch based on a topic.

⚠️ SMART HTML STRUCTURE & TABLE USAGE (HUMAN DESIGNER LOGIC):
1. TABLES FOR TABULAR DATA ONLY: Act like a professional human designer. Use `<table>` ONLY for true tabular data (invoices, price lists, data grids, schedules). NEVER put standard paragraphs, messages, letters, or general text inside tables.
2. ENHANCED READABILITY (FONTS): Make the default text slightly larger and exceptionally clear. Use a baseline font size of 15px-16px for `<p>`, `<li>`, and `<span>`. Keep headings proportionately larger. Do not randomly shrink or enlarge fonts.

⚠️ SMART SPACE UTILIZATION & NATURAL FLOW (ANTI-SQUISH RULE):
1. EXTEND HORIZONTALLY: Use the full width of the page naturally. DO NOT artificially compress or squish the content. Let it breathe from left to right.
2. SHORT DOCUMENTS (Invoices, Receipts, Letters): Distribute content elegantly to fit beautifully on ONE page.
3. LONG DOCUMENTS (Articles, Research, Reports): DO NOT force them into one page! Allow the content to flow naturally across multiple pages. Maintain the beautiful, large, readable default font sizes. DO NOT shrink fonts just to fit a long text into a single page.
4. If a table has many columns, ensure it fits horizontally, but let the document flow vertically as needed.

⚠️ BIDI & LAYOUT LOCKS (MANDATORY TO PREVENT REVERSALS):
- Outermost wrapper & ALL `<table>` elements MUST use `dir="ltr"`.
- Arabic text MUST explicitly use `dir="rtl" style="text-align: right;"` on the specific cell/paragraph ONLY.
- French/English text MUST explicitly use `dir="ltr" style="text-align: left;"`.
- Phone numbers or spaced numbers MUST be wrapped in: `<span dir="ltr" style="display:inline-block; unicode-bidi:bidi-override; white-space:nowrap;"></span>`
- TABLES MUST COMPLY: `width: 100%; max-width: 100%; table-layout: fixed; word-wrap: break-word; overflow-wrap: anywhere; word-break: break-word;`.
- PUNCTUATION SEPARATION (e.g., for Dates/Signatures): NEVER put the label and dots in the same text node. Use this LTR structure: `<div style="display:flex; direction:ltr;"><div style="flex-grow:1; border-bottom:1px dotted #333;"></div><div style="margin:0 5px;">:</div><div dir="rtl" style="text-align:right;">التاريخ</div></div>`
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
TYPOGRAPHY: Dynamic sizes. Title bold, dark slate.
COLOR PALETTE: Text: #2c3e50, Primary: #1a5276, Accents: #2980b9, Backgrounds: #f8f9fa.
DESIGN ELEMENTS:
- Section headings: color:#1a5276; border-inline-start:4px solid #2980b9; padding-inline-start:10px; margin-top:15px; margin-bottom:10px; background:#ebf5fb; padding-top:6px; padding-bottom:6px; border-radius:4px;
- Tables: th: background:#ebf5fb; color:#1a5276; td: border:1px solid #d5dbdb; color:#2c3e50;"""
    else:
        design_base = """FORMAL/OFFICIAL - Professional Mauritanian document design.
TYPOGRAPHY: Dynamic sizes. Title bold centered.
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
    return jsonify({"status": "Monjez V10 Server Active", "features": ["documents", "simulation", "design", "word_export"]})


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
            landscape_extra = f" LANDSCAPE LAYOUT: Tables MUST fit within this width horizontally, but text can flow naturally downwards."

        orientation_instruction = f"PAGE FORMAT: {page_info['orientation']} — Physical Canvas Size: {page_info['physical']} (Target width: {page_info['w']}px). {landscape_extra} SMART LAYOUT: Do not squash long texts. Let it breathe."
        
        ref_note = ""
        if reference_b64 and mode != "simulation":
            ref_note = "\nATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        doc_type_instruction = ""
        if doc_type == "single_page":
            doc_type_instruction = """SINGLE-PAGE DOCUMENT: Optimize space beautifully on one page. Keep the structure simple and direct; DO NOT overcomplicate with unnecessary tables if it is just a letter or certificate."""
        elif doc_type == "multi_page":
            doc_type_instruction = """MULTI-PAGE DOCUMENT: Allow natural flow across multiple pages. Maintain the beautifully large and readable default font sizes (15px-16px)."""

        if mode == "simulation":
            svg_rule = "NO `<html>`, `<body>`. (EXCEPTION: `<svg>` is ONLY allowed for the standalone circular stamp scenario)."
        else:
            svg_rule = "NO `<svg>`, `<html>`, `<body>`."

        prompt = f"""You are a STRICT Document Formatter.

{style_prompt}
{orientation_instruction}
{ref_note}
{doc_type_instruction}

TECHNICAL RULES:
1. PURE HTML ONLY. Just `<div>`, `<table>`, `<h1>`, `<p>`. {svg_rule}
2. NO BORDERS AROUND DOCUMENT.
3. WRAPPER CONFIG: The outermost wrapper MUST NOT have excessive padding. Use `<div style="width:100%; max-width:100%; margin:0 auto; padding:5px; box-sizing:border-box; direction:ltr; overflow-wrap:anywhere; word-break:break-word; overflow:hidden;">`.

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

CRITICAL RULES:
1. EXACT COPY-PASTE: Output the EXACT SAME HTML structure provided. DO NOT delete unrelated text.
2. SURGICAL EDIT: Apply the exact surgical change requested. DO NOT hallucinate or add fake elements.
3. BIDI PROTECTION: Preserve `dir="ltr"` on wrappers/tables and protect phone numbers with `<span dir="ltr" style="display:inline-block; unicode-bidi:bidi-override; white-space:nowrap;">`.
4. RETURN FULL HTML: Return the complete patched HTML. Do not truncate.
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
            f"<CURRENT_HTML>\n{current_html}\n</CURRENT_HTML>\n\n<USER_REQUEST>\n{instruction}\n</USER_REQUEST>\n\nTASK: Apply the exact surgical change and return FULL updated HTML."
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

        sys = f"""You are a STRICT Document Editor. The user has manually edited this document.

YOUR MISSION:
1. CLEANUP & STRUCTURE: Wrap loose text in proper tags. Apply logical Alignments.
2. STRICT PRESERVATION: NEVER delete, alter, or add to the actual facts, text, or meaning. NO HALLUCINATION.
3. BIDI FIX: Ensure wrappers/tables use `dir="ltr"`. Arabic text uses `dir="rtl" style="text-align:right"`. Protect phone numbers.

OUTPUT FORMAT:
[MESSAGE]
تم تنسيق وترتيب المستند بنجاح ✨
[/MESSAGE]
[HTML]
(ضع هنا كود الـ HTML المنسق كاملاً)
[/HTML]"""

        cfg = get_types().GenerateContentConfig(system_instruction=sys, temperature=0.0, max_output_tokens=16384)
        cts = [f"<MESSY_HTML>\n{current_html}\n</MESSY_HTML>\n\nPlease format and fix Bidi issues professionally without changing text."]

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


# ══════════════════════════════════════════════════════════
# 📄 PDF → Word (DOCX) via CloudConvert API
# ══════════════════════════════════════════════════════════

@app.route("/convert_to_word", methods=["POST"])
def convert_to_word():
    """
    Receives PDF as base64 → converts to DOCX via CloudConvert API → returns DOCX as base64.
    """
    try:
        if not os.environ.get("CLOUDCONVERT_API_KEY"):
            return jsonify({"error": "Failed", "details": "مفتاح CLOUDCONVERT_API_KEY غير مُعرّف."}), 500

        data = request.json
        pdf_b64 = data.get("pdf_base64", "")

        if not pdf_b64:
            return jsonify({"error": "Failed", "details": "لم يتم إرسال ملف PDF."}), 400

        pdf_bytes = base64.b64decode(pdf_b64)
        logger.info(f"📄 Converting PDF to Word via CloudConvert ({len(pdf_bytes)} bytes)...")

        docx_bytes = cloudconvert_pdf_to_word(pdf_bytes)
        docx_b64 = base64.b64encode(docx_bytes).decode('utf-8')

        logger.info(f"✅ Word conversion complete ({len(docx_bytes)} bytes)")
        return jsonify({"docx_base64": docx_b64, "message": "تم التحويل إلى Word بنجاح ✨"})

    except Exception as e:
        logger.error(f"Word Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": f"فشل التحويل: {str(e)}"}), 500


@app.route("/generate_image", methods=["POST"])
def generate_image():
    import urllib.request

    try:
        k = os.environ.get("GOOGLE_API_KEY2") or os.environ.get("GOOGLE_API_KEY")
        if not k:
            return jsonify({"error": "Failed", "details": "مفتاح API غير موجود."}), 500

        data = request.json
        user_prompt = data.get("prompt", "")
        reference_images = data.get("reference_images", [])
        aspect_ratio = data.get("aspectRatio", "1:1")

        if not user_prompt.strip():
            return jsonify({"error": "Failed", "details": "يرجى كتابة وصف للتصميم."}), 400

        system_text = """You are an elite creative designer.
RULES: Generate exactly what is described. NO MOCKUPS. Flat professional design. Cultural context: Mauritanian features if people are included. 8K quality."""

        user_parts = [{"text": user_prompt}]
        for b64_img in reference_images:
            clean_b64 = b64_img.split(",", 1)[1] if "," in b64_img else b64_img
            user_parts.append({"inlineData": {"mimeType": "image/jpeg", "data": clean_b64}})

        payload = {
            "contents": [{"role": "user", "parts": user_parts}],
            "systemInstruction": {"parts": [{"text": system_text}]},
            "generationConfig": {"responseModalities": ["IMAGE"], "temperature": 0.7}
        }

        headers = {"Content-Type": "application/json"}
        models = [("gemini-3-pro-image-preview", "Nano Banana Pro", 120), ("gemini-3.1-flash-image-preview", "Nano Banana 2", 90), ("gemini-2.5-flash", "Gemini 2.5 Flash", 90)]

        for model_id, model_name, timeout in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={k}"
            try:
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    result = json.loads(response.read().decode('utf-8'))
                parts = result.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        return jsonify({"response": part["inlineData"]["data"], "message": f"تم التصميم بنجاح ✨ ({model_name})"})
            except: continue

        return jsonify({"error": "Failed", "details": "جميع النماذج فشلت في توليد الصورة."}), 500
    except Exception as e:
        return jsonify({"error": "Failed", "details": f"خطأ في الخادم: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
