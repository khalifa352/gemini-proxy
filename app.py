import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V25 - PERFECT TYPOGRAPHY & CLONE)
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
        logger.info("✅ Document Engine V25 Connected (Typography & Clone Mode)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

def ensure_namespaces(svg_code):
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
    return jsonify({"status": "Almonjez V25 is Online 📄🪄"})

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
        
        # 1. إعدادات الورق الرسمي (Letterhead Logic)
        if letterhead_b64:
            bg_css = "background: transparent;"
            # تقليص المساحة لتجنب الهيدر والفوتر الخاص بالعميل
            fo_x = width * 0.08
            fo_y = height * 0.15
            fo_w = width * 0.84
            fo_h = height * 0.70
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        # 2. الاستنساخ والشعار
        logo_hint = f"\n- LOGO INCLUDED: Place this tag at the top of your HTML: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 85px; object-fit: contain;\" />`" if logo_b64 else ""
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 STRICT CLONE MODE (CRITICAL) ===
            - The user attached a reference document. You MUST act as a PERFECT CLONE ENGINE.
            - Replicate the exact visual layout, table structures, column widths, borders, shading, and visual hierarchy of the attached image.
            - ONLY deviate to correct obvious technical or linguistic/spelling errors. Do not redesign it, just digitize it flawlessly.
            """

        # 3. التوجيهات الصارمة (Typography & Overflow Logic)
        system_instruction = f"""
        ROLE: Master Document Typesetter & UI Expert.
        TASK: Generate a strictly formatted document SVG.
        {logo_hint}
        {ref_hint}

        === 📏 TYPOGRAPHY & SPACE UTILIZATION (CRITICAL) ===
        1. EXACT SIZING: NEVER use fonts smaller than 13pt. 
           - Main Titles: 20pt to 28pt.
           - Subtitles/Table Headers: 14pt to 16pt (Bold).
           - Body Text & Cells: 13pt to 15pt.
        2. SMART SPACING: The document MUST utilize the available space elegantly. Use `display: flex; flex-direction: column; min-height: 100%;` and appropriate padding/margins so it doesn't look empty if text is short.
        3. OVERFLOW WARNING: If the provided text is too long and cannot fit perfectly inside the container with the sizes above, DO NOT SHRINK THE TEXT. Instead, add a visually distinct note at the very bottom of the document: 
           `<div style="color: red; text-align: center; margin-top: 20px; font-weight: bold;">💡 ملاحظة من المنجز: النص طويل جداً، اطلب مني في المحادثة توزيعه على صفحتين.</div>`

        === 📐 ARCHITECTURE ===
        Use pure HTML/CSS inside a SINGLE `<foreignObject>`.
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; min-height: 100%; display: flex; flex-direction: column; padding: 40px; box-sizing: border-box; {bg_css} direction: rtl; text-align: right; font-family: 'Arial', sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY THE RAW SVG CODE.
        """

        contents = [user_msg] if user_msg else ["استنسخ هذا المستند بدقة."]
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

        # 4. حقن الورق الرسمي في الخلفية
        if letterhead_b64 and '<svg' in final_svg:
            bg_image = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="none" />\n'
            final_svg = final_svg.replace('<foreignObject', f'{bg_image}<foreignObject', 1)

        final_svg = ensure_namespaces(final_svg)

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
        current_svg = data.get('current_svg', '')
        instruction = data.get('instruction', '')

        system_prompt = """
        ROLE: Friendly Document AI Assistant.
        TASK: Modify the existing document SVG based on user instruction.
        
        RULES:
        1. Apply the modification (e.g., adding a new page, changing colors, editing text).
        2. If the user asks to "open a new page" or "توزيعه على صفحتين":
           - Double the SVG viewBox height.
           - Add a new `<foreignObject>` for the second page offset by the original height.
           - Move the overflow text to the new page.
        3. Do not shrink font sizes to fit.
        
        OUTPUT FORMAT:
        Return ONLY valid JSON:
        {
            "message": "رد عربي ودود قصير يخبر العميل بالنتيجة",
            "response": "<svg>...updated code...</svg>"
        }
        """

        prompt_text = f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2)
        )

        raw_text = response.text or ""
        json_str = raw_text.replace("```json", "").replace("```", "").strip()
        result_data = json.loads(json_str)
        
        updated_svg = ensure_namespaces(result_data.get("response", ""))
        ai_message = result_data.get("message", "تم التعديل بنجاح!")

        return jsonify({
            "response": updated_svg,
            "message": ai_message
        })

    except Exception as e:
        logger.error(f"Modify Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
