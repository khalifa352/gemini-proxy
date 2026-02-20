import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V26 - AESTHETICS & PREMIUM CLONE)
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
        logger.info("✅ Document Engine V26 Connected (Aesthetics Restored)")
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
    return jsonify({"status": "Almonjez V26 is Online 📄🪄"})

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
        
        # 1. إعدادات الورق الرسمي
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x = width * 0.08
            fo_y = height * 0.15
            fo_w = width * 0.84
            fo_h = height * 0.70
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        # 2. الشعار والمحاكاة الفاخرة
        logo_hint = f"\n- LOGO: Place this exactly at the top: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 85px; object-fit: contain;\" />`" if logo_b64 else ""
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 PREMIUM CLONE MODE ===
            - Visually analyze the attached reference document.
            - Replicate its layout, tables, and data accurately.
            - HOWEVER, upgrade its aesthetics! Make it look like a highly professional, modern digital document (use elegant table borders, soft background colors for headers, subtle shadows if needed, and clean padding). Do not just make it a boring wireframe.
            """

        # 3. عودة اللمسات الجمالية + حماية الخطوط
        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning, visually appealing document SVG.
        {logo_hint}
        {ref_hint}

        === 🎨 AESTHETICS & DESIGN (CRITICAL) ===
        - Make the document look expensive and official. Use beautiful CSS styling for tables, dividers, and headers.
        - Ensure high contrast and excellent readability.

        === 📏 TYPOGRAPHY (NO GIANT OR TINY TEXT) ===
        - You MUST maintain standard printed document font sizes. 
        - Main Titles: 18pt to 24pt MAX.
        - Subtitles & Table Headers: 14pt to 16pt (Bold).
        - Body Text & Table Cells: 12pt to 14pt.
        - NEVER blow up the font to giant sizes just to fill empty space. NEVER shrink the font to microscopic sizes.
        - OVERFLOW RULE: If the text is too long for the page, add this exact warning at the very bottom: 
          `<div style="color: #D32F2F; text-align: center; margin-top: 20px; font-weight: bold; background: #FFEBEE; padding: 10px; border-radius: 8px;">💡 ملاحظة من المنجز: النص طويل جداً، اطلب مني في المحادثة توزيعه على صفحتين.</div>`

        === 📐 ARCHITECTURE ===
        Use pure HTML/CSS inside a SINGLE `<foreignObject>`.
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; min-height: 100%; padding: 40px; box-sizing: border-box; {bg_css} direction: rtl; text-align: right; font-family: 'Arial', sans-serif; color: #222;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY THE RAW SVG CODE.
        """

        contents = [user_msg] if user_msg else ["قم بتصميم هذا المستند بأعلى جودة بصرية."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.4) # رفعنا الحرارة قليلاً ليعود لإبداعه الفني
        )
        
        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # 4. حقن الورق الرسمي
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
        ROLE: Friendly Document AI Assistant & UI Expert.
        TASK: Modify the existing document SVG based on user instruction while keeping it beautiful.
        
        RULES:
        1. Apply the modification perfectly (e.g., adding rows, changing colors, fixing text).
        2. Keep the elegant CSS styling intact.
        3. If the user asks to "open a new page" or "توزيعه على صفحتين":
           - Double the SVG viewBox height.
           - Add a new `<foreignObject>` for the second page offset by the original height.
        
        OUTPUT FORMAT (STRICT JSON):
        {
            "message": "رد عربي ودود قصير يخبر العميل بالنتيجة",
            "response": "<svg>...updated code...</svg>"
        }
        """

        prompt_text = f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.3)
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
