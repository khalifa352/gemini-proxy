import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V24 - MULTIPAGE & VISION)
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
        logger.info("✅ Document Engine V24 Connected (Multipage & Vision)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

# ======================================================
# 🧹 HELPER: SVG NAMESPACE INJECTOR
# ======================================================
def ensure_namespaces(svg_code):
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_code:
        svg_code = svg_code.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if 'xmlns:xhtml' not in svg_code:
        svg_code = svg_code.replace('<foreignObject', '<foreignObject xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)
    return svg_code

# ======================================================
# 🚀 ROUTE 1: THE GENERATION ROUTE (NEW DOCUMENTS)
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V24 (Multipage & Vision) is Online 📄🪄"})

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
        
        # 1. إعدادات الورق الرسمي (تأمين الهيدر والفوتر)
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x = width * 0.08
            fo_y_offset = height * 0.15
            fo_w = width * 0.84
            fo_h = height * 0.70
            layout_instruction = f"""
            - LETTERHEAD ATTACHED: You MUST leave space for the user's header and footer.
            - Format each page's `<foreignObject>` exactly like this to protect margins:
              `<foreignObject x="{fo_x}" y="[PAGE_START_Y + {fo_y_offset}]" width="{fo_w}" height="{fo_h}">`
              (Example Page 1: `y="{0 + fo_y_offset}"`, Page 2: `y="{height + fo_y_offset}"`)
            """
        else:
            bg_css = "background: white;"
            layout_instruction = f"""
            - Format each page's `<foreignObject>` exactly like this:
              `<foreignObject x="0" y="[PAGE_START_Y]" width="{width}" height="{height}">`
              (Example Page 1: `y="0"`, Page 2: `y="{height}"`)
            """

        logo_hint = f"\n- LOGO INCLUDED: Place this tag at the top of your HTML: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 80px;\" />`" if logo_b64 else ""
        ref_hint = "\n- REFERENCE ATTACHED: Visually analyze the attached image and replicate its exact layout, tables, and typography." if reference_b64 else ""

        # 2. التوجيهات الصارمة لجيميني (الخطوط + تعدد الصفحات)
        system_instruction = f"""
        ROLE: Master Document Typesetter.
        TASK: Generate a professional document SVG.
        {logo_hint}
        {ref_hint}

        === 🛑 CRITICAL FONT SIZE RULES (NO TINY TEXT) ===
        - Maintain standard readable print typography ALWAYS.
        - Main Titles: 18pt to 24pt MAX.
        - Body text & Tables: 12pt to 16pt. 
        - NEVER shrink the font to fit the content. Do not use giant text.

        === 📄 AUTO-PAGINATION (MULTIPAGE) RULE ===
        If the text is long, DO NOT shrink it. Create multiple pages!
        1. Set the SVG `viewBox` height to match the number of pages (e.g., 2 pages = `viewBox="0 0 {width} {height * 2}"`).
        2. Create a NEW `<foreignObject>` for each page offset by Y={height}.
        {layout_instruction}
        3. Draw a line `<line x1="0" y1="{height}" x2="{width}" y2="{height}" stroke="#ccc" stroke-dasharray="10,10"/>` to visually separate pages.

        === 📐 ARCHITECTURE ===
        Use pure HTML/CSS inside `<foreignObject>`.
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; padding: 40px; box-sizing: border-box; {bg_css} direction: rtl; text-align: right; font-family: 'Arial', sans-serif; color: #111;">
                </div>
        </svg>

        RETURN ONLY THE RAW SVG CODE. NO MARKDOWN.
        """

        contents = [user_msg] if user_msg else ["استنسخ هذا المستند بدقة."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.3)
        )
        
        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # 3. حقن الورق الرسمي لكل الصفحات أوتوماتيكياً
        if letterhead_b64 and '<svg' in final_svg:
            # قراءة عدد الصفحات من الـ viewBox
            vb_match = re.search(r'viewBox="0 0 \d+ (\d+)"', final_svg)
            pages = 1
            if vb_match:
                total_h = int(vb_match.group(1))
                pages = max(1, total_h // height)
            
            # تكرار الخلفية لكل صفحة
            bg_images = ""
            for p in range(pages):
                y_pos = p * height
                bg_images += f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="{y_pos}" width="{width}" height="{height}" preserveAspectRatio="none" />\n'
            
            # وضع الخلفيات خلف الـ foreignObject
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
        ROLE: Friendly Document AI Assistant.
        TASK: The user wants to modify their existing document.
        
        1. Apply the user's instructions to the provided SVG code (e.g. update colors, add rows to table, fix typos).
        2. DO NOT change the structure of the `<foreignObject>` tags or the pagination logic. Keep sizes the same.
        
        OUTPUT FORMAT:
        You MUST return a strictly valid JSON object exactly like this:
        {
            "message": "رد عربي ودود قصير يخبر العميل بالتعديل المنجز",
            "response": "<svg>...the fully updated SVG code...</svg>"
        }
        NO MARKDOWN TICKS. JUST JSON.
        """

        prompt_text = f"CURRENT SVG CODE:\n{current_svg}\n\nUSER INSTRUCTION:\n{instruction}"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2 
            )
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
