import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V36 - CSS GRID FORCED LAYOUT)
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
        logger.info("✅ Document Engine V36 Connected (CSS Grid Layout)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

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
    return jsonify({"status": "Almonjez V36 is Online 📄🪄"})

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
        
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y = int(width * 0.08), int(height * 0.18)
            fo_w, fo_h = int(width * 0.84), int(height * 0.70)
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        logo_hint = f"\n- LOGO: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 80px; margin-bottom: 15px;\" />`" if logo_b64 else ""
        ref_hint = "\n=== 📸 PREMIUM CLONE MODE ===\nReplicate the layout EXACTLY. You MUST output a fully expanded table." if reference_b64 else ""

        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning document SVG.
        {logo_hint}
        {ref_hint}

        === 📏 FORCED FULL-PAGE LAYOUT (CRITICAL) ===
        - You MUST stretch the content to fill the {fo_h}px height. 
        - The container uses CSS Grid: `grid-template-rows: auto 1fr auto;`.
        - You MUST organize your HTML inside the container into 3 parts:
          1. `<header>` (Info, Dates, Logos)
          2. `<main style="height: 100%; min-height: 300px;">` (The Table) - Make sure the table stretches! 
             - Add an empty `<tr><td colspan="10" style="height: 100%;"></td></tr>` at the end of the table if it is too short, to push the footer down!
          3. `<footer>` (Totals, Signatures, Notes)

        === 🌍 STRICT BILINGUAL ALIGNMENT ===
        - You MUST use this exact snippet for bilingual table headers:
          `<th> <div style="display: flex; justify-content: space-between; align-items: center;"> <span dir="ltr">French</span> <span>عربي</span> </div> </th>`
        - All French text MUST be wrapped in `<span dir="ltr">`.

        === 🎨 TYPOGRAPHY ===
        - Main Titles: 20pt to 24pt.
        - Body & Cells: 13pt to 15pt.

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; box-sizing: border-box; padding: 30px; {bg_css} display: grid; grid-template-rows: auto 1fr auto; gap: 20px; direction: rtl; font-family: -apple-system, Arial, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY RAW SVG CODE.
        """

        contents = [user_msg] if user_msg else ["صمم المستند ليملأ الورقة، استخدم CSS Grid وتأكد من فصل اللغات."]
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

        if letterhead_b64 and '<svg' in final_svg:
            bg_image_tag = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="{width}" height="{height}" preserveAspectRatio="none" />'
            final_svg = final_svg.replace('<foreignObject', f'{bg_image_tag}\n<foreignObject', 1)

        final_svg = ensure_svg_namespaces(final_svg)

        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"Generate Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/modify', methods=['POST'])
def modify():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        current_svg = data.get('current_html', '') or data.get('current_svg', '')
        instruction = data.get('instruction', '')

        system_prompt = """
        ROLE: Expert Document AI.
        TASK: Modify SVG document.
        RULES: Keep the CSS Grid layout (`grid-template-rows: auto 1fr auto;`). Keep French left (`dir="ltr"`) and Arabic right. 
        OUTPUT (JSON): {"message": "رد عربي", "response": "<svg>...</svg>"}
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
            "message": result_data.get("message", "تم التعديل!")
        })

    except Exception as e:
        logger.error(f"Modify Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
