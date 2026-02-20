import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V27 - UNIVERSAL RULES & BIDI FIX)
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
        logger.info("✅ Document Engine V27 Connected (Universal Rules & Bidi Text)")
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
    return jsonify({"status": "Almonjez V27 is Online 📄🪄"})

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
        
        # 1. إعدادات الورق الرسمي (تحديد مساحة العمل)
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y = width * 0.08, height * 0.15
            fo_w, fo_h = width * 0.84, height * 0.70
            page_logic = f"Page 1: `<foreignObject x=\"{fo_x}\" y=\"{fo_y}\" width=\"{fo_w}\" height=\"{fo_h}\">`. Page 2: `<foreignObject x=\"{fo_x}\" y=\"{height + fo_y}\" ...>`"
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height
            page_logic = f"Page 1: `<foreignObject x=\"0\" y=\"0\" width=\"{width}\" height=\"{height}\">`. Page 2: `<foreignObject x=\"0\" y=\"{height}\" ...>`"

        # 2. الشعار والمحاكاة
        logo_hint = f"\n- LOGO INCLUDED: Place this tag at the top: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 85px; object-fit: contain;\" />`" if logo_b64 else ""
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 PREMIUM CLONE MODE ===
            - Visually analyze the attached reference document.
            - Replicate its structure, tables, columns, and data EXACTLY.
            - Upgrade aesthetics (clean borders, elegant spacing) but keep the exact same number of empty rows if it's an invoice or form.
            """

        # 3. دستور المنجز (الخطوط، الاتجاهات، وتعدد الصفحات)
        system_instruction = f"""
        ROLE: Master Document Typesetter & UI Expert.
        TASK: Generate a strictly formatted, elegant document SVG.
        {logo_hint}
        {ref_hint}

        === 🌍 BILINGUAL & TEXT DIRECTION FIX (CRITICAL) ===
        - You will write mixed Arabic (RTL) and French/English (LTR).
        - To prevent text inversion and broken sentences, you MUST wrap distinct language phrases in `<bdi>` tags or use `dir="auto"`.
        - Example: `<td><bdi>الكمية</bdi> / <bdi>Quantité</bdi></td>`
        - Example: `<p dir="auto">Date: 12/05/2026 التاريخ</p>`

        === 📏 UNIVERSAL TYPOGRAPHY & PAGINATION ===
        - Apply these sizing rules to ALL documents:
          * Main Titles: 20pt to 24pt.
          * Headers/Subtitles: 14pt to 16pt (Bold).
          * Body Text & Cells: 12pt to 14pt.
        - NEVER shrink text below 12pt just to make it fit on one page, UNLESS the user explicitly commands: "صغر الخط" (shrink the text).
        - IF text overflows at these standard sizes: 
          1. Increase the SVG `viewBox` height (e.g., `viewBox="0 0 {width} {height * 2}"`).
          2. Add a NEW `<foreignObject>` for the next page.
          {page_logic}
          3. Draw a separator line between pages: `<line x1="0" y1="{height}" x2="{width}" y2="{height}" stroke="#ccc" stroke-dasharray="10,10"/>`.

        === 📐 ARCHITECTURE ===
        Use pure HTML/CSS inside `<foreignObject>`.
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; min-height: 100%; padding: 40px; box-sizing: border-box; {bg_css} direction: rtl; text-align: right; font-family: 'Arial', sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY THE RAW SVG CODE.
        """

        contents = [user_msg] if user_msg else ["قم بتصميم/محاكاة هذا المستند بأعلى جودة واحرص على عدم انعكاس اللغات."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.25)
        )
        
        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # 4. تكرار الورق الرسمي لكل الصفحات (لو فتح صفحة جديدة)
        if letterhead_b64 and '<svg' in final_svg:
            vb_match = re.search(r'viewBox="0 0 \d+ (\d+)"', final_svg)
            pages = max(1, int(vb_match.group(1)) // height) if vb_match else 1
            
            bg_images = ""
            for p in range(pages):
                y_pos = p * height
                bg_images += f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="{y_pos}" width="{width}" height="{height}" preserveAspectRatio="none" />\n'
            
            final_svg = final_svg.replace('<foreignObject', f'{bg_images}\n<foreignObject', 1)

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
        TASK: Modify the existing document SVG based on user instruction.
        
        RULES:
        1. Keep the elegant CSS styling and Arabic/French bidi fixes (`<bdi>`, `dir="auto"`).
        2. If the user explicitly asks to shrink the text ("صغر الخط"), you may reduce the font sizes to fit everything on one page. Otherwise, maintain readability.
        3. If the user asks to "open a new page" or the text naturally overflows at standard sizes, double the SVG viewBox height and add a new `<foreignObject>`.
        
        OUTPUT FORMAT (STRICT JSON):
        {
            "message": "رد عربي ودود قصير",
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
