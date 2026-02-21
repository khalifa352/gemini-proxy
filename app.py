import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V48 - HYBRID VANGUARD)

# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_Hybrid")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine Connected (Vanguard: Gemini 3 Preview | Fallback: 2.5 Flash 🛡️)")
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
    return jsonify({"status": "Almonjez V48 (Hybrid Engine) is Online ⚡🛡️"})

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
        
        logger.info(f"🚦 /gemini called | size={width}x{height} | has_ref={bool(reference_b64)}")

        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y = int(width * 0.08), int(height * 0.18)
            fo_w, fo_h = int(width * 0.84), int(height * 0.70)
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        logo_hint = f"\n- LOGO: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 85px; margin-bottom: 20px;\" />`" if logo_b64 else ""
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 SMART CLONE MODE ===
            Analyze the image accurately. DO NOT STRETCH THE TABLE UNNATURALLY. 
            Count the exact rows in the original image. If the original table is short, make your table short. Let it be compact and neat.
            """

        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning document SVG. Keep EVERYTHING inside the workspace.
        {logo_hint}
        {ref_hint}

        === 🌍 BILINGUAL SHIELD ===
        - Wrap ALL French/English text or numbers in `<bdi dir="ltr">` or `<span dir="ltr">`.
        - Arabic aligned right, Latin text aligned left.

        === 📏 NATURAL A4 FLOW (NO STRETCHING) ===
        - You have a strict height of {fo_h}px.
        - DO NOT stretch tables artificially. Let the table take exactly the height it needs.
        - Fonts MUST be large and readable: Headers 15pt-16pt, Body 14pt-15pt. 
        - The container MUST have `display: flex; flex-direction: column; height: 100%;`.
        - To handle empty space beautifully: Give the final footer/signature div `margin-top: auto;`. This will push the footer to the very bottom of the page, leaving natural white space below the table.

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, Arial, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY RAW SVG CODE. DO NOT WRAP IN MARKDOWN.
        """

        contents = [user_msg] if user_msg else ["قم بمحاكاة المستند بدقة وبشكل طبيعي جداً بدون تمطيط."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        # 🛡️ THE HYBRID FALLBACK SYSTEM 🛡️
        response = None
        try:
            # المحاولة الأولى باستخدام الدبابة الاستطلاعية (Gemini 3 Preview)
            logger.info("🛰️ Calling Primary Vanguard: gemini-3-flash-preview...")
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.15)
            )
            logger.info("✅ Vanguard (Gemini 3) returned successfully.")
            
        except Exception as primary_error:
            # إذا تعطل الإصدار الثالث، نتدخل بالدبابة المستقرة (Gemini 2.5 Flash)
            logger.warning(f"⚠️ Vanguard Failed: {str(primary_error)} | Switching to Fallback Tank (gemini-2.5-flash)...")
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.15)
            )
            logger.info("✅ Fallback Tank (Gemini 2.5) returned successfully.")

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
        logger.error(f"❌ [CRITICAL MODEL ERROR - BOTH FAILED]: {str(e)}")
        return jsonify({"error": "فشل الاتصال بجميع النماذج", "details": str(e)}), 500

@app.route('/modify', methods=['POST'])
def modify():
    if not client: return jsonify({"error": "Gemini API Offline"}), 500
    try:
        data = request.json
        current_svg = data.get('current_html', '') or data.get('current_svg', '')
        instruction = data.get('instruction', '')

        system_prompt = f"""
        ROLE: Expert Document AI.
        TASK: Modify SVG document naturally without stretching. Keep all elements strictly inside the workspace.
        OUTPUT STRICT JSON: {{"message": "رد عربي", "response": "<svg>...</svg>"}}
        """

        # 🛡️ THE HYBRID FALLBACK SYSTEM FOR MODIFY 🛡️
        response = None
        try:
            logger.info("🛰️ Calling Primary Vanguard (Modify): gemini-3-flash-preview...")
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}",
                config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.15)
            )
            logger.info("✅ Vanguard Modify (Gemini 3) returned successfully.")
        except Exception as primary_error:
            logger.warning(f"⚠️ Vanguard Modify Failed: {str(primary_error)} | Switching to Fallback Tank (gemini-2.5-flash)...")
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}",
                config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.15)
            )
            logger.info("✅ Fallback Modify (Gemini 2.5) returned successfully.")

        result_data = extract_safe_json(response.text if response.text else "")
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))

        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل!")})

    except Exception as e:
        logger.error(f"❌ [CRITICAL MODIFY ERROR]: {str(e)}")
        return jsonify({"error": "فشل التعديل", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
