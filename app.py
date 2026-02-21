import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V44 - SMART VISION & STRICT LAYOUT)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_V44")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine Connected (Fast & Smart: Gemini 2.0 Flash ⚡)")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY is missing.")
except Exception as e:
    logger.error(f"❌ Gemini Error: {e}")

def extract_safe_json(text):
    try:
        match = re.search(r'\{.*\}', text.replace('\n', ' '), re.DOTALL)
        if match: return json.loads(match.group(0))
    except: pass
    return {}

def ensure_svg_namespaces(svg_code):
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_code:
        svg_code = svg_code.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if 'xmlns:xhtml' not in svg_code:
        svg_code = svg_code.replace('<foreignObject', '<foreignObject xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)
    return svg_code

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V44 is Online ⚡📄"})

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

        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        logo_hint = f"\n- LOGO: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 85px; margin-bottom: 20px;\" />`" if logo_b64 else ""
        
        # ⚠️ القوانين الديناميكية الصارمة جداً للمحاكاة (لمنع كسل الموديل)
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 STRICT CLONE & STRUCTURAL ANALYSIS (NO LAZINESS) ===
            Analyze the uploaded image meticulously. DO NOT USE GENERIC TEMPLATES.
            1. **TABLE PROPORTIONS (CRITICAL):** Visually estimate column widths. If one column (like 'Item' or 'Désignation') is huge, assign it `width: 50%` or similar in HTML. DO NOT make all columns equal.
            2. **ROW COUNT (CRITICAL):** Count the EXACT number of rows in the original table. If there are 15 or 16 empty rows, you MUST write the `<tr>` tag 15 or 16 times. DO NOT stop at 4 or 5 rows. Fill the space just like the image.
            3. **DOTTED LINES:** Recreate fill-in-the-blank dots (e.g., Date: ......) using CSS: `border-bottom: 2px dotted #111; display: inline-block; min-width: 150px;`. DO NOT scatter them.
            4. **BORDERS & BOXES:** If footer text is inside a drawn box, you MUST use CSS `border: 2px solid black; padding: 10px; border-radius: 5px;` to recreate it exactly.
            5. **TOTAL ROW:** Keep the 'Total' or 'المجموع' merged correctly INSIDE the table grid at the bottom using `colspan`.
            """

        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning document SVG.
        {logo_hint}
        {ref_hint}

        === 🌍 BILINGUAL SHIELD ===
        - Wrap ALL French/English text or numbers in `<bdi dir="ltr">` or `<span dir="ltr">`.
        - Arabic MUST be aligned right, Latin text aligned left. 

        === 📏 TYPOGRAPHY & LAYOUT ===
        - Make table borders crisp (`border-collapse: collapse; border: 1px solid #333;`).
        - Font sizes: Headers 16pt, Body 14pt-15pt.
        - Use flexbox to organize headers cleanly.

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, Arial, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY RAW SVG CODE.
        """

        contents = [user_msg] if user_msg else ["قم بمحاكاة المستند بدقة هندسية صارمة."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash", 
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.15) # حرارة منخفضة جداً للالتزام الدقيق
        )

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

        system_prompt = f"""
        ROLE: Expert Document AI.
        TASK: Modify SVG document perfectly.
        OUTPUT (JSON): {{"message": "رد عربي", "response": "<svg>...</svg>"}}
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}",
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.15)
        )

        result_data = extract_safe_json(response.text if response.text else "")
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))

        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل!")})

    except Exception as e:
        logger.error(f"❌ [MODIFY ERROR]: {str(e)}")
        return jsonify({"error": "فشل التعديل", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
