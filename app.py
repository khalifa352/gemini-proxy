import os
import re
import json
import logging
import base64
import concurrent.futures
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("Monjez_V10")

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
                logger.info("✅ Monjez V10 Active")
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
    raw = raw_text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(html|xml)?\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw)
    div_match = re.search(r'<div[^>]*xmlns="http://www.w3.org/1999/xhtml"[^>]*>(.*?)</div>\s*</foreignObject>', raw, re.DOTALL)
    if div_match:
        raw = div_match.group(1)
    return raw.strip()


# ══════════════════════════════════════════════════════════
#  STYLE PROMPTS
# ══════════════════════════════════════════════════════════
def get_style_prompt(style, mode):
    if mode == "resumes":
        return """RESUME/CV: Creative layout with sidebar, skill bars, icons, color accents.
Colors: navy #1e3a5f, teal #0d9488, charcoal #374151."""

    if mode == "simulation":
        return """CLONING: Reproduce EXACTLY text/tables from the reference image.
IGNORE logos, stamps, signatures. Do NOT invent data."""

    if style == "modern":
        return """MODERN/CONTEMPORARY - Elegant, warm, professional design with personality.

TYPOGRAPHY: Clean headings with color accents. Title 17px bold. Section headings 14px bold.
Body text 13px with good line-height.

COLOR PALETTE (Warm & Harmonious — USE THESE ACTIVELY):
- Primary heading: #1B4965 (deep ocean)
- Secondary accent: #5FA8D3 (sky blue)
- Light fill: #CAE9FF (ice blue) for section backgrounds
- Alt fill: #BEE3DB (soft mint) for alternating table rows
- Surface: #F7F9FC (cloud) for cards
- Text: #2D3748 (charcoal)
- Borders: #E2E8F0 (light gray)

DESIGN ELEMENTS (apply consistently):
- Section headings with colored right-border:
  <h2 style="border-right:4px solid #1B4965; padding:10px 14px 10px 10px; background:#EFF6FF; border-radius:6px; color:#1B4965; font-size:14px; font-weight:bold; margin:16px 0 10px;">
- Important values as soft badges:
  <span style="background:#1B4965; color:white; padding:3px 12px; border-radius:14px; font-size:12px;">
- Content cards:
  <div style="background:#F7F9FC; border:1px solid #E2E8F0; border-radius:8px; padding:14px; margin:10px 0;">
- Tables:
  <table style="width:100%; border-collapse:collapse; table-layout:fixed; margin:12px 0;">
  th: background:#1B4965; color:white; padding:10px 8px; font-size:12px; border:none; text-align:right;
  td: padding:8px; font-size:12px; border-bottom:1px solid #E2E8F0; text-align:right;
  Even rows: background:#F7F9FC;
- Gradient dividers:
  <div style="height:2px; background:linear-gradient(to left, #1B4965, #5FA8D3, #CAE9FF); margin:16px 0; border-radius:2px;"></div>

INVOICE TABLE: Columns RTL: البيان(50%) | السعر | الكمية | الإجمالي
tfoot: background:#1B4965; color:white;"""

    # Default: formal
    return """FORMAL/OFFICIAL - Professional Mauritanian document design.

TYPOGRAPHY: Title 16px bold centered. Sections 13px bold.
Body 13px. Colors: #333, #555, #f7f7f7, #f0f0f0, #ddd.

TABLE DESIGN:
- th: background:#333; color:white; padding:7px; font-size:12px; border:1px solid #333;
- td: padding:6px 8px; font-size:12px; border:1px solid #ddd; text-align:right;
- Even rows: background:#f7f7f7;

INVOICE TABLE: Columns RTL: البيان/الوصف(50%) | السعر | الكمية | الإجمالي
Total in <tfoot>: "الإجمالي المستحق" colspan=3, amount in last column."""


def detect_document_type(user_msg):
    msg = user_msg.lower()
    single = ['فاتورة','facture','invoice','devis','عرض سعر','bon','شهادة','certificate',
              'attestation','رسالة','letter','lettre','courrier','إيصال','receipt','reçu',
              'تصريح','declaration','إذن','autorisation','بطاقة','card','carte']
    multi = ['تقرير','report','rapport','دراسة','study','étude','بحث','research',
             'خطة','plan','مشروع','project','projet','تفصيلي','detailed','مفصل','شامل','comprehensive']
    for k in single:
        if k in msg: return "single_page"
    for k in multi:
        if k in msg: return "multi_page"
    return "auto"


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Monjez V10 Active ⚡"})


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
            ref_note = "\nATTACHED IMAGE: Insert using <img src='data:image/jpeg;base64,...' style='max-width:80%;height:auto;margin:8px auto;display:block;'/>"

        type_note = ""
        if doc_type == "single_page":
            type_note = """
SINGLE-PAGE DOCUMENT (Invoice/Certificate/Letter):
- Fit in ONE page. Keep compact but readable (min font: 11px).
- Reduce spacing slightly (margin:6-8px, padding:5-6px).
- NEVER shrink font below 11px."""
        elif doc_type == "multi_page":
            type_note = """
MULTI-PAGE DOCUMENT (Report/Study):
- Clear section headings with content after each.
- NEVER leave a heading at page bottom with no content after it.
- Tables must not be split — app handles pagination."""

        prompt = f"""You are an Expert Document Typesetter in Mauritania.

{style_prompt}
{ref_note}
{type_note}

CRITICAL RULES:
1. RETURN PURE HTML ONLY. No <svg>, no <foreignObject>.
2. NO SHORTENING: Write ALL user data fully.
3. No <hr> tags.
4. Paragraphs: <p style="margin-bottom:10px;text-align:justify;line-height:1.65;">
5. No <html>, <head>, <body> tags. Only structural elements.
6. NO PAGE WRAPPERS: No outer div with fixed width/height/borders/shadows.
7. Every heading MUST be followed by content.
8. Tables: style="width:100%;border-collapse:collapse;table-layout:fixed;"

OUTPUT: Raw HTML only."""

        contents = [user_msg] if user_msg else ["Create a formal document."]
        if reference_b64:
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(reference_b64), mime_type="image/jpeg"))
        if letterhead_b64:
            contents.append("Letterhead attached. Layout must fit its empty space.")
            contents.append(get_types().Part.from_bytes(data=base64.b64decode(letterhead_b64), mime_type="image/jpeg"))

        gen_config = get_types().GenerateContentConfig(
            system_instruction=prompt, temperature=0.15, max_output_tokens=16000)

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
        logger.info(f"✅ Generated (mode:{mode}, style:{style}, type:{doc_type})")
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
            img_note = f"\nINSERT image: <img src='data:image/jpeg;base64,{ref_b64}' style='max-width:80%;height:auto;margin:8px auto;display:block;'/>"

        sys = f"""Expert document modifier for Mauritanian documents.

RULES:
1. Preserve everything including manual edits. Apply ONLY the requested change.
2. Return ONLY modified pure HTML.
3. No <svg>, <html>, <body> tags.
4. Tables: width:100%;table-layout:fixed;word-wrap:break-word;
5. No <hr> tags. No page wrappers.
6. Headings must be followed by content.
{img_note}

OUTPUT JSON:
{{"message": "وصف التعديل بالعربية", "content": "<modified HTML>"}}"""

        cfg = get_types().GenerateContentConfig(
            system_instruction=sys, temperature=0.15, max_output_tokens=16384)

        cts = [f"CURRENT HTML:\n{current_html}\n\nREQUEST:\n{instruction}\n\nMODIFY:"]
        if ref_b64:
            cts.append(get_types().Part.from_bytes(data=base64.b64decode(ref_b64), mime_type="image/jpeg"))
        if lh_b64:
            cts.append("NEW Letterhead attached. Layout must fit its empty space.")
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

        logger.info("✅ Modified OK")
        return jsonify({"response": new_inner, "message": msg})

    except Exception as e:
        logger.error(f"Modify: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)
