import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (DEBUGGING EDITION)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_Pro")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine Connected (Gemini 1.5 Pro - DEBUG MODE 🧠🔥)")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY is missing in environment variables.")
except Exception as e:
    logger.error(f"❌ Gemini Initialization Error: {e}")

def extract_safe_json(text):
    try:
        match = re.search(r'\{.*\}', text.replace('\n', ' '), re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        logger.error(f"JSON Parsing Error: {e}")
    return {}

def ensure_svg_namespaces(svg_code):
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_code:
        svg_code = svg_code.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if 'xmlns:xhtml' not in svg_code:
        svg_code = svg_code.replace('<foreignObject', '<foreignObject xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)
    return svg_code

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez Debug Engine is Online 📄🪄"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        logo_b64 = data.get('logo_image')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # 🟢 1. مجسات التتبع الأولى (دخول الطلب)
        logger.info("🚦 /gemini called")
        logger.info(f"keys={list((data or {}).keys())}")
        logger.info(f"user_msg_len={len(user_msg or '')}  size={width}x{height}")
        logger.info(f"has_logo={bool(logo_b64)} has_ref={bool(reference_b64)} has_letterhead={bool(letterhead_b64)}")

        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y = int(width * 0.08), int(height * 0.18)
            fo_w, fo_h = int(width * 0.84), int(height * 0.70)
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        logo_hint = f"\n- LOGO: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 85px; margin-bottom: 20px;\" />`" if logo_b64 else ""
        ref_hint = "\n=== 📸 ACCURATE CLONE MODE ===\nReplicate the attached document accurately. Generate ALL rows of the table." if reference_b64 else ""

        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning document SVG.
        {logo_hint}
        {ref_hint}

        === 🌍 BILINGUAL SHIELD ===
        - Wrap ALL French/English text or numbers in `<bdi dir="ltr">` or `<span dir="ltr">`.
        - Arabic MUST be aligned right, Latin text aligned left. Use Flexbox to separate them.

        === 📏 LONG TEXT & OVERFLOW WARNING ===
        - Height limit: {fo_h}px.
        - DO NOT shrink the font to microscopic sizes. Keep it between 14pt and 18pt.
        - IF content exceeds this height, stop elegantly and add this EXACT warning at the bottom:
          `<div style="margin-top:20px; padding:15px; background:#fff3cd; color:#856404; border:1px solid #ffeeba; border-radius:8px; text-align:center; font-weight:bold; font-size:14pt;">💡 تنبيه من المنجز: النص طويل! اطلب مني فتح صفحة جديدة.</div>`

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, Arial, sans-serif; color: #222;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY RAW SVG CODE.
        """

        contents = [user_msg] if user_msg else ["قم بتصميم المستند بأعلى جودة جمالية."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        # 🟢 2. مجس التتبع الثاني (قبل الاتصال بجوجل)
        logger.info("🛰️ calling Gemini now...")

        response = client.models.generate_content(
            model="Gemini 1.5 Pro", 
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
        )
        
        # 🟢 3. مجس التتبع الثالث (بعد عودة الرد)
        logger.info("✅ Gemini returned")
        logger.info(f"raw_len={len((response.text or ''))}")

        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        if letterhead_b64 and '<svg' in final_svg:
            vb_match = re.search(r'viewBox="0 0 \d+ (\d+)"', final_svg)
            pages = max(1, int(vb_match.group(1)) // height) if vb_match else 1
            
            bg_images = ""
            for p in range(pages):
                y_pos = p * height
                bg_images += f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="{y_pos}" width="{width}" height="{height}" preserveAspectRatio="none" />\n'
            
            final_svg = final_svg.replace('<foreignObject', f'{bg_images}\n<foreignObject', 1)

        final_svg = ensure_svg_namespaces(final_svg)

        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"❌ [MODEL ERROR]: {str(e)}")
        return jsonify({"error": "فشل الاتصال", "details": str(e)}), 500

@app.route('/modify', methods=['POST'])
def modify():
    if not client: return jsonify({"error": "Gemini API Offline"}), 500
    try:
        data = request.json
        current_svg = data.get('current_html', '') or data.get('current_svg', '')
        instruction = data.get('instruction', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))

        system_prompt = f"""
        ROLE: Expert Document AI.
        TASK: Modify SVG document perfectly.
        === 📄 NEW PAGE LOGIC ===
        If asked to open a new page or text overflows: Double viewBox height, create second foreignObject.
        OUTPUT (JSON): {{"message": "رد عربي", "response": "<svg>...</svg>"}}
        """

        logger.info("🛰️ calling Gemini (Modify) now...")
        response = client.models.generate_content(
            model="gemini-1.5-pro",
            contents=f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}",
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2)
        )
        logger.info("✅ Gemini (Modify) returned")

        result_data = extract_safe_json(response.text if response.text else "")
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))

        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل!")})

    except Exception as e:
        logger.error(f"❌ [MODIFY ERROR]: {str(e)}")
        return jsonify({"error": "فشل التعديل", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
