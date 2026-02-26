import os
import re
import json
import logging
import base64
import concurrent.futures
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez_V9_HTML")

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
                logger.info("✅ Monjez V9 (Unified HTML + Smart Pagination)")
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

def clean_html_output(raw_text):
    """Clean output from any Markdown wrapping and extract pure HTML"""
    raw = raw_text.strip()
    if raw.startswith("```"): 
        raw = re.sub(r"^```(?:html|xml)?\n?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\n?```$", "", raw)

    # If Gemini wrapped in SVG by mistake, extract inner HTML
    div_match = re.search(r'<div[^>]*xmlns="[http://www.w3.org/1999/xhtml](http://www.w3.org/1999/xhtml)"[^>]*>(.*?)</div>\s*</foreignObject>', raw, re.DOTALL)
    if div_match:
        raw = div_match.group(1)
        
    return raw.strip()

# ══════════════════════════════════════════════════════════
# STYLE PROMPTS - FORMAL vs MODERN (Harmonious & Elegant)
# ══════════════════════════════════════════════════════════

def get_style_prompt(style, mode):
    if mode == "simulation":
        return """CLONING: Reproduce EXACTLY text/tables from the reference image.
IGNORE logos, stamps, signatures. Do NOT invent data."""

    if style == "modern":
        # 🚀 التصميم العصري المريح للعين والمتناسق
        return """MODERN/ELEGANT - Professional, clean, harmonious, and very comfortable on the eyes.

TYPOGRAPHY: Title 17px bold, dark slate. Section headings 14px bold with a subtle colored right-border.

COLOR PALETTE (Harmonious & Comfortable):
- Text: #2c3e50 (Dark slate, softer and more elegant than pure black)
- Primary/Headings: #1a5276 (Deep elegant blue)
- Accents/Borders: #2980b9 (Calm professional blue)
- Subtle Backgrounds: #f8f9fa (Off-white/light gray), #ebf5fb (Very pale blue for table headers & section backgrounds)
- Dividers/Borders: #d5dbdb (Soft gray-blue)

DESIGN ELEMENTS:
- Section headings: color:#1a5276; border-right:3px solid #2980b9; padding-right:10px; margin-top:15px; margin-bottom:10px; background:#ebf5fb; padding-top:6px; padding-bottom:6px; border-radius:4px;
- Tables: Soft and clean styling.
  th: background:#ebf5fb; color:#1a5276; padding:8px; font-size:12px; border:1px solid #d5dbdb; font-weight:bold;
  td: padding:8px; font-size:12px; border:1px solid #d5dbdb; color:#2c3e50; text-align:right;
  Even rows: background:#fcfcfc;
- Cards/Highlights: Use very subtle backgrounds.
  Example: <div style="background:#f8f9fa; border-right:3px solid #16a085; padding:12px; border-radius:4px; margin:10px 0;">
- Dividers: <div style="height:1px; background:linear-gradient(to left, #2980b9, transparent); margin:14px 0;"></div>

INVOICE TABLE (فاتورة/facture/devis):
Columns right-to-left: البيان/الوصف(50%) | السعر | الكمية | الإجمالي
Total row in <tfoot> with background:#ebf5fb; color:#1a5276; font-weight:bold."""

    # Default: formal
    return """FORMAL/OFFICIAL - Professional Mauritanian document design.

TYPOGRAPHY: Title 16px bold centered. Sections 13px bold.
Body 13px. NO bright colors. Colors: #333, #555, #f7f7f7, #f0f0f0, #ddd.

TABLE DESIGN:
- th: background:#333; color:white; padding:7px; font-size:12px; border:1px solid #333;
- td: padding:6px 8px; font-size:12px; border:1px solid #ddd; text-align:right;
- Even rows: background:#f7f7f7;

INVOICE TABLE (فاتورة/facture/devis):
Columns right-to-left: البيان/الوصف(50%) | السعر | الكمية | الإجمالي
Total row in <tfoot>: "الإجمالي المستحق" colspan=3, amount in last column only."""

# ══════════════════════════════════════════════════════════
# DOCUMENT TYPE DETECTION
# ══════════════════════════════════════════════════════════

def detect_document_type(user_msg):
    """Detect if document is likely single-page (invoice, letter) or multi-page (report)"""
    msg_lower = user_msg.lower()

    single_page_keywords = [
        'فاتورة', 'facture', 'invoice', 'devis', 'عرض سعر', 'bon',
        'شهادة', 'certificate', 'attestation',
        'رسالة', 'letter', 'lettre', 'courrier',
        'إيصال', 'receipt', 'reçu', 'bon de',
        'تصريح', 'declaration', 'déclaration',
        'إذن', 'autorisation', 'permission',
        'بطاقة', 'card', 'carte',
    ]

    multi_page_keywords = [
        'تقرير', 'report', 'rapport',
        'دراسة', 'study', 'étude',
        'بحث', 'research', 'recherche',
        'خطة', 'plan', 'عمل',
        'مشروع', 'project', 'projet',
        'تفصيلي', 'detailed', 'détaillé', 'مفصل',
        'شامل', 'comprehensive', 'complet',
    ]

    for kw in single_page_keywords:
        if kw in msg_lower:
            return "single_page"

    for kw in multi_page_keywords:
        if kw in msg_lower:
            return "multi_page"

    return "auto"

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V9 (Unified HTML + Smart Pagination ⚡)"})

@app.route("/gemini", methods=["POST"])
def generate():
    if not get_client():
        return jsonify({"error": "Gemini API Offline"}), 500

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

        # Document type specific instructions
        doc_type_instruction = ""
        if doc_type == "single_page":
            doc_type_instruction = """
SINGLE-PAGE DOCUMENT DETECTED (Invoice/Certificate/Letter):
- Design to fit ONE page. Keep content compact but READABLE (minimum font-size: 11px).
- You may reduce spacing between elements slightly (margin: 6px instead of 12px).
- You may reduce table cell padding slightly (padding: 5px instead of 7px).
- NEVER make font smaller than 11px. Keep it readable.
- If the content naturally fits one page, great. If it absolutely cannot fit, let it overflow naturally."""
        elif doc_type == "multi_page":
            doc_type_instruction = """
MULTI-PAGE DOCUMENT DETECTED (Report/Study):
- Use proper structure with clear section headings.
- Each section heading MUST have at least 2-3 lines of content after it on the same page.
- NEVER place a heading at the very bottom of a page with no content following it.
- Tables should NOT be split across pages - the app handles this automatically.
- Use generous spacing for readability."""

        prompt = f"""You are an Expert Document Typesetter in Mauritania.

{style_prompt}
{ref_note}
{doc_type_instruction}

CRITICAL RULES (MANDATORY):
1. RETURN PURE HTML ONLY. Do NOT wrap the output in `<svg>` or `<foreignObject>`.
2. NO SHORTENING: NEVER summarize or omit the user's data. Write everything out fully.
3. NO LONG LINES: Do NOT use `<hr>` tags.
4. PARAGRAPHS: Use proper `<p style="margin-bottom: 10px; text-align: justify; line-height: 1.65;">` for all text.
5. Do NOT include `<html>`, `<head>`, or `<body>` tags. Just the structural elements (`<div>`, `<table>`, `<h1>`, `<p>`).
6. NO PAGE WRAPPERS: DO NOT wrap the content in an outer page container (like `<div style="width:21cm...">`). DO NOT add black borders, shadows, or fixed width/height simulating a paper. The app handles the A4 paper UI natively. Just output the flowing text/tables.
7. HEADINGS: Every heading (h1, h2, h3) must be followed by content. Never end a section with just a heading.
8. TABLES: Always use `style="width:100%; border-collapse:collapse; table-layout:fixed;"` on tables.

OUTPUT: Return raw HTML only."""

        contents = [user_msg] if user_msg else ["Create a formal document."]
        
        if reference_b64:
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(reference_b64), mime_type="image/jpeg"))
        
        if letterhead_b64:
            contents.append("I have attached the Letterhead design image. Ensure your layout fits its empty space.")
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(letterhead_b64), mime_type="image/jpeg"))

        gen_config = get_types().GenerateContentConfig(
            system_instruction=prompt,
            temperature=0.15,
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

        clean_html = clean_html_output(resp.text or "")
        
        logger.info(f"✅ Generated HTML (mode: {mode}, style: {style}, type: {doc_type})")
        return jsonify({"response": clean_html})

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500


@app.route("/modify", methods=["POST"])
def modify():
    if not get_client():
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_html = data.get("current_html", "") or data.get("current_svg", "") or data.get("current_content", "")
        instruction = data.get("instruction", "")
        ref_b64 = data.get("reference_image")
        lh_b64 = data.get("letterhead_image")

        img_note = ""
        if ref_b64:
            img_note = f"\nINSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%; height:auto; margin:8px auto; display:block;' />"

        sys = f"""Expert document modifier for Mauritanian documents.

CRITICAL RULES:
1. Preserve everything including recent manual user edits. Apply ONLY the requested AI change.
2. Return ONLY the modified PURE HTML content.
3. DO NOT output `<svg>`, `<html>`, or `<body>` tags. Only inner HTML elements.
4. TABLES: `width:100%; table-layout:fixed; word-wrap:break-word;`
5. NO LONG LINES: Do not use `<hr>` tags.
6. NO PAGE WRAPPERS: DO NOT wrap the content in an outer page container with fixed heights or borders.
7. HEADINGS: Never leave a heading as the last element. Always ensure content follows.
{img_note}

OUTPUT FORMAT - JSON:
{{"message": "وصف التعديل بالعربية", "content": "<modified HTML here>"}}"""

        cfg = get_types().GenerateContentConfig(
            system_instruction=sys, temperature=0.15, max_output_tokens=16384,
        )

        cts = [f"CURRENT HTML:\n{current_html}\n\nREQUEST:\n{instruction}\n\nMODIFY:"]
        if ref_b64:
            cts.append(get_types().Part.from_bytes(data=base64.b64decode(ref_b64), mime_type="image/jpeg"))

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
            new_inner = clean_html_output(raw)
            if not new_inner: new_inner = current_html

        logger.info(f"✅ Modified document successfully")
        return jsonify({"response": new_inner, "message": msg})

    except Exception as e:
        logger.error(f"Modify: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
