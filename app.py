import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V28 - PERFECT CLONE & BEAUTIFUL UI)
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
        logger.info("✅ Document Engine V28 Connected (Perfect Layout & Typography)")
except Exception as e:
    logger.error(f"❌ API Error: {}")

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
    return jsonify({"status": "Almonjez V28 is Online 📄🪄"})

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
            page_logic = f"Page 1: `<foreignObject x=\"{}\" y=\"{}\" width=\"{}\" height=\"{}\">`."
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height
            page_logic = f"Page 1: `<foreignObject x=\"0\" y=\"0\" width=\"{}\" height=\"{}\">`."

        # 2. الشعار والمحاكاة
        logo_hint = f"\n- LOGO INCLUDED: Place this tag at the top layout: `<img src=\"data:image/jpeg;base64,{}\" style=\"max-height: 85px; object-fit: contain;\" />`" if logo_b64 else ""
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 PREMIUM EXACT CLONE MODE ===
            - Visually analyze the attached reference document meticulously.
            - Replicate its visual hierarchy, alignments, and structure EXACTLY using CSS Flexbox/Grid.
            - DO NOT skip any fields, signatures, or columns.
            - If it's a table/invoice, keep the exact same number of empty rows/cells.
            - Eliminate unnatural empty gaps. Distribute elements elegantly using logical margins and padding.
            """

        # 3. دستور المنجز (التنسيق الجمالي، الخطوط، الجداول، وتعدد الصفحات)
        system_instruction = f"""
        ROLE: Master Document Typesetter & UI Expert.
        TASK: Generate a strictly formatted, visually perfect document SVG.

        {}
        {}

        === 🌍 BILINGUAL & TEXT DIRECTION FIX (CRITICAL) ===
        - You will write mixed Arabic (RTL) and French/English (LTR).
        - To prevent text inversion and broken sentences, you MUST wrap distinct language phrases in `<bdi>` tags or use `dir="auto"`.
        - Example: `<td><bdi>الكمية</bdi> / <bdi>Quantité</bdi></td>`

        === 📏 UNIVERSAL TYPOGRAPHY & AESTHETICS (STRICT CSS) ===
        You MUST use beautiful, modern CSS inside the `<style>` tag or inline:
        1. Typography: Base font-size MUST be 14px to 16px. Main Titles: 22px-26px. NEVER shrink text below 13px under any circumstance. Ensure perfect readability.
        2. Tables (CRITICAL): Tables must look professional. 
           - CSS: `border-collapse: collapse; width: 100%; margin: 20px 0;`
           - Cells (`th`, `td`): `border: 1px solid #777; padding: 10px 12px; text-align: center; font-size: 14px;`
           - Headers (`th`): `background-color: #f0f4f8; font-weight: bold; color: #333;`
        3. Layout: Use `display: flex; justify-content: space-between; align-items: flex-start;` for headers (like logo on one side, details on the other).
        4. Colors: Use deep professional colors (e.g., `#1a202c` for text, `#2d3748` for subtext).

        === 📐 PAGINATION & OVERFLOW ===
        - NEVER shrink the text to fit the page. 
        - If the text, tables, or layout needs more vertical space, simply MULTIPLY the SVG `viewBox` height and `<foreignObject>` height. 
        - Example for 2 pages: `viewBox="0 0 {} {height * 2}"` and `<foreignObject height="{height * 2}">`.
        - Do not compress elements. Let them breathe with proper spacing (`line-height: 1.6; padding: 10px;`).

        === 🏗️ ARCHITECTURE ===
        Use pure HTML/CSS inside `<foreignObject>`.
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {} {}" width="100%" height="100%">
          <foreignObject x="{}" y="{}" width="{}" height="{}">
            <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; min-height: 100%; {} padding: 30px; box-sizing: border-box; direction: rtl; text-align: right; font-family: 'Segoe UI', Tahoma, Arial, sans-serif; color: #1a202c; line-height: 1.6;">
              <!-- Inject beautifully styled HTML here (Flexbox, styled Tables, BDI tags) -->
            </div>
          </foreignObject>
        </svg>

        RETURN ONLY THE RAW SVG CODE. NO MARKDOWN. NO EXPLANATIONS.
        """

        contents = [user_msg] if user_msg else ["قم بتصميم/محاكاة هذا المستند بأعلى جودة بصرية، واحرص على جمالية الجداول وحجم الخط المقروء وعدم انعكاس اللغات."]
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

        # 4. تكرار الورق الرسمي لكل الصفحات (لو فتح صفحة جديدة بناءً على الـ ViewBox)
        if letterhead_b64 and '<svg' in final_svg:
            vb_match = re.search(r'viewBox="0\s+0\s+\d+\s+(\d+)"', final_svg)
            svg_total_height = int(vb_match.group(1)) if vb_match else height
            pages = max(1, svg_total_height // height)
            
            bg_images = ""
            for p in range(pages):
                y_pos = p * height
                bg_images += f'<image href="data:image/jpeg;base64,{}" x="0" y="{}" width="{}" height="{}" preserveAspectRatio="none" />\n'
            
            final_svg = final_svg.replace('<foreignObject', f'\n{}<foreignObject', 1)

        final_svg = ensure_namespaces(final_svg)
        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"Generate Error: {}")
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
        1. Maintain the HIGH-QUALITY CSS styling: beautiful tables (`border-collapse`, padded cells, colored headers), appropriate font sizes (min 13px), and logical Flexbox/Grid layouts.
        2. Keep the Arabic/French bidi fixes (`<bdi>`, `dir="auto"`).
        3. If the user asks for more content and it doesn't fit, DO NOT shrink the text. Instead, increase the SVG `viewBox` height and `<foreignObject>` height.
        
        OUTPUT FORMAT (STRICT JSON):
        {
          "message": "رد عربي ودود قصير يوضح ما تم تعديله",
          "response": "<svg>...updated code...</svg>"
        }
        """

        prompt_text = f"CURRENT SVG:\n{}\n\nINSTRUCTION:\n{}"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2)
        )

        raw_text = response.text or ""
        json_str = raw_text.replace("```json", "").replace("```", "").strip()
        result_data = json.loads(json_str)
        
        updated_svg = ensure_namespaces(result_data.get("response", ""))
        ai_message = result_data.get("message", "تم التعديل بنجاح وبأفضل تنسيق ممكن!")

        return jsonify({
            "response": updated_svg,
            "message": ai_message
        })

    except Exception as e:
        logger.error(f"Modify Error: {}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
