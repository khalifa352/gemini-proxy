import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V34 - THE STRICT SVG RETURN)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_SVG")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine V34 Connected (Strict SVG Edition)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

# ======================================================
# 🛡️ SYSTEM VALIDATORS
# ======================================================
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

# ======================================================
# 🚀 ROUTE 1: THE GENERATION ROUTE
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V34 (SVG Masterpiece) is Online 📄🪄"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        logo_b64 = data.get('logo_image')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # 1. حماية الورق الرسمي (تحديد الإحداثيات الصارمة)
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x = int(width * 0.08)
            fo_y = int(height * 0.18)
            fo_w = int(width * 0.84)
            fo_h = int(height * 0.70)
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        logo_hint = f"\n- LOGO INCLUDED: Place this tag at the top of your HTML: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 80px; margin-bottom: 15px;\" />`" if logo_b64 else ""
        ref_hint = "\n=== 📸 PREMIUM CLONE MODE ===\nVisually analyze the attached image. Replicate its layout, tables, and typography EXACTLY. Upgrade its design to look expert and highly professional." if reference_b64 else ""

        # 2. الهيكل المعماري الصارم للـ SVG
        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning, visually appealing document using SVG.
        {logo_hint}
        {ref_hint}

        === 📐 SVG ARCHITECTURE & BOUNDARIES (CRITICAL) ===
        - You MUST use a single `<foreignObject>` inside the SVG to handle text and tables perfectly. DO NOT use native SVG `<text>` elements for paragraphs.
        - The document MUST NOT overflow. 
        - Strict Dimensions: `<foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">`

        === 🎨 EXPERT DESIGN & TYPOGRAPHY ===
        - Make it look expensive and official.
        - Tables MUST have `border-collapse: collapse; width: 100%;`.
        - Table headers (`th`) must have a soft background color (e.g., `#f4f6f8`) and borders.
        - Main Titles: 20pt to 24pt MAX.
        - Body Text & Table Cells: 12pt to 15pt. (NEVER use tiny unreadable text).

        === 🌍 BILINGUAL & ANTI-SCATTERING ===
        - Wrap EVERY French/English word or number in `<bdi>` to prevent RTL/LTR inversion.
        - Text must be clear and aligned (`text-align: right; direction: rtl;`).

        FORMAT MUST BE EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} direction: rtl; text-align: right; font-family: -apple-system, Arial, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY THE RAW SVG CODE.
        """

        contents = [user_msg] if user_msg else ["قم بتصميم هذا المستند بأعلى جودة بصرية، ولا تخرج عن الحدود."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
        )
        
        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # 3. حقن الورق الرسمي كخلفية مطلقة (خلف الـ foreignObject)
        if letterhead_b64 and '<svg' in final_svg:
            bg_image_tag = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="none" />'
            final_svg = final_svg.replace('<foreignObject', f'{bg_image_tag}\n<foreignObject', 1)

        final_svg = ensure_svg_namespaces(final_svg)

        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"Generate Error: {e}")
        return jsonify({"error": str(e)}), 500

# ======================================================
# 💬 ROUTE 2: THE MODIFY ROUTE (CHAT-TO-EDIT)
# ======================================================
@app.route('/modify', methods=['POST'])
def modify():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        current_svg = data.get('current_html', '') # نستخدم نفس المفتاح الذي عدلناه في التطبيق
        if not current_svg:
            current_svg = data.get('current_svg', '') # توافق رجعي
            
        instruction = data.get('instruction', '')

        system_prompt = """
        ROLE: Expert Document AI Assistant.
        TASK: Modify the existing SVG document based on user instruction.
        
        RULES:
        1. Keep the overall SVG structure, `viewBox`, and `<foreignObject>` dimensions EXACTLY the same.
        2. Apply modifications to the HTML/CSS inside the foreignObject (e.g., fixing typos, changing colors, adjusting tables).
        3. Keep the design expert and unscattered.
        
        OUTPUT FORMAT (STRICT JSON):
        {
            "message": "رد عربي ودود قصير",
            "response": "<svg>...updated code...</svg>"
        }
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}",
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2)
        )

        result_data = extract_safe_json(response.text if response.text else "")
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))

        return jsonify({
            "response": updated_svg,
            "message": result_data.get("message", "تم التعديل بنجاح!")
        })

    except Exception as e:
        logger.error(f"Modify Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
