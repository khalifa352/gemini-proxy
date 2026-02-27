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
IGNORE logos, stamps, signatures. Do NOT invent data."""

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

        prompt = f"""You are an Expert Document Typesetter in Mauritania.

{style_prompt}
{ref_note}
{doc_type_instruction}

CRITICAL RULES:
1. RETURN PURE HTML ONLY. NO `<svg>`, NO `<html>`, NO `<body>`. Just `<div>`, `<table>`, `<h1>`, `<p>`.
2. NO SHORTENING: NEVER summarize data. Write everything fully.
3. NO PAGE WRAPPERS: DO NOT wrap content in an outer page container with fixed heights or borders.
4. PARAGRAPHS: `<p style="margin-bottom: 10px; line-height: 1.65;">`
5. BIDI PROTECTION (CRITICAL): Wrap ALL phone numbers (e.g., +222...) and Latin/French words in `<span dir="ltr" style="unicode-bidi: isolate; display: inline-block;">...</span>` to prevent RTL text flipping.
6. EXACT LANGUAGE MATCH (CRITICAL): You MUST generate the document in the EXACT LANGUAGE requested by the user. If the user writes in French, the entire output MUST be in French. DO NOT translate to Arabic unless explicitly told to do so.
7. DIRECTIONALITY & ALIGNMENT (CRITICAL): If the requested language is French or English, you MUST wrap the ENTIRE output in exactly ONE `<div dir="ltr" style="text-align: left;">...</div>`. If Arabic, wrap it in `<div dir="rtl" style="text-align: right;">...</div>`.

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
        current_html = data.get("current_html", "")
        instruction = data.get("instruction", "")
        ref_b64 = data.get("reference_image")

        img_note = ""
        if ref_b64:
            img_note = f"\nINSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        sys = f"""You are a STRICT HTML Code Editor and Find-and-Replace Engine.
You do NOT design. You do NOT create from scratch. You ONLY patch existing HTML.

CRITICAL RULES:
1. ZERO HALLUCINATION (CRITICAL): Do NOT invent fake data. Use ONLY the data provided in the <CURRENT_HTML>.
2. EXACT COPY-PASTE (CRITICAL): Output the EXACT SAME HTML structure as <CURRENT_HTML>, but with the requested edit applied.
3. NO REDESIGN: Do not change colors, fonts, or CSS classes.
4. FULL DOCUMENT RETURN: Return the COMPLETE HTML. Do not truncate.
5. LANGUAGE & BIDI: Keep the original language. Preserve all `dir="ltr"` and `dir="rtl"`.
{img_note}

OUTPUT FORMAT:
Do NOT output JSON. You MUST output exactly like this:
[MESSAGE]
وصف قصير للتعديل باللغة العربية
[/MESSAGE]
[HTML]
(ضع هنا كود الـ HTML المعدل كاملاً)
[/HTML]"""

        # الحرارة 0.0 تضمن الدقة المتناهية
        cfg = get_types().GenerateContentConfig(system_instruction=sys, temperature=0.0, max_output_tokens=16384)
        
        cts = [
            f"<CURRENT_HTML>\n{current_html}\n</CURRENT_HTML>\n\n<USER_REQUEST>\n{instruction}\n</USER_REQUEST>\n\nTASK: Apply the exact change and return the FULL HTML."
        ]
        
        if ref_b64:
            cts.append(get_types().Part.from_bytes(data=base64.b64decode(ref_b64), mime_type="image/jpeg"))

        try:
            resp = call_gemini("gemini-3-flash-preview", cts, cfg, 55)
        except:
            resp = call_gemini("gemini-2.5-flash", cts, cfg, 50)

        text = resp.text or ""
        
        # 🚀 استخراج الكود بأمان تام بعيداً عن أخطاء الـ JSON
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
        
        # 🚀 استخراج الكود بأمان
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
