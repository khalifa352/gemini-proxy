import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V45 - GPT-4o MASTER ARCHITECT)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_GPT4o")

app = Flask(__name__)

# 🚀 تفعيل محرك OpenAI
client = None
try:
    from openai import OpenAI
    OPENAI_KEY = os.environ.get('OPENAI_API_KEY')
    if OPENAI_KEY:
        client = OpenAI(api_key=OPENAI_KEY)
        logger.info("✅ Document Engine Connected (Master Architect: GPT-4o 🧠🏗️)")
    else:
        logger.warning("⚠️ OPENAI_API_KEY is missing in environment variables.")
except Exception as e:
    logger.error(f"❌ OpenAI Initialization Error: {e}")

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
    return jsonify({"status": "Almonjez V45 (GPT-4o Engine) is Online 🧠📄"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "OpenAI API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        logo_b64 = data.get('logo_image')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')

        logger.info(f"🚦 /gemini (GPT-4o) called | size={width}x{height} | has_ref={bool(reference_b64)}")

        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        logo_hint = f"\n- LOGO: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 85px; margin-bottom: 20px;\" />`" if logo_b64 else ""
        
        # ⚠️ نفس القوانين الصارمة التي علمناها لجيميني
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 STRICT CLONE & STRUCTURAL ANALYSIS (NO LAZINESS) ===
            Analyze the uploaded image meticulously. 
            1. **TABLE PROPORTIONS:** Visually estimate column widths (e.g., 'Désignation' should be wider, like `width: 50%`).
            2. **ROW COUNT (CRITICAL):** Count the EXACT number of rows in the original table. You MUST generate ALL those empty rows using `<tr>`. DO NOT stop at 4 or 5 rows. Fill the space.
            3. **DOTTED LINES:** Recreate fill-in-the-blank dots (e.g., Date: ......) using CSS: `border-bottom: 2px dotted #111; display: inline-block; min-width: 150px;`.
            4. **BORDERS & BOXES:** If footer text is inside a drawn box, use CSS `border: 2px solid black; padding: 10px; border-radius: 5px;`.
            """

        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning document SVG. Keep EVERYTHING strictly inside the workspace.
        {logo_hint}
        {ref_hint}

        === 🌍 BILINGUAL SHIELD ===
        - Wrap ALL French/English text or numbers in `<bdi dir="ltr">` or `<span dir="ltr">`.
        - Arabic MUST be aligned right, Latin text aligned left. Use Flexbox `justify-content: space-between` to separate them cleanly.

        === 📏 TYPOGRAPHY & LAYOUT (STRICT BOUNDARIES) ===
        - You have a strict height of {fo_h}px. DO NOT let any text overflow.
        - Fonts MUST be medium and readable: Headers 16pt, Body 14pt-15pt. 
        - Make table borders crisp (`border-collapse: collapse; border: 1px solid #333;`).
        - Use flexbox to organize the document cleanly from top to bottom.

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, Arial, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY RAW SVG CODE. DO NOT WRAP IN MARKDOWN.
        """

        # 🚀 بناء الطلب ليتوافق مع OpenAI Vision
        user_content = []
        if user_msg:
            user_content.append({"type": "text", "text": user_msg})
        else:
            user_content.append({"type": "text", "text": "قم بمحاكاة المستند بدقة هندسية صارمة، وحافظ على التصميم داخل مساحة العمل."})

        if reference_b64:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{reference_b64}",
                    "detail": "high"
                }
            })

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content}
        ]

        logger.info("🛰️ Calling GPT-4o...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.15 # حرارة منخفضة جداً للالتزام الدقيق بالقواعد
        )
        logger.info("✅ GPT-4o returned successfully.")

        raw_text = response.choices[0].message.content or ""
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
        logger.error(f"❌ [GPT-4o ERROR]: {str(e)}")
        return jsonify({"error": "فشل الاتصال بـ OpenAI", "details": str(e)}), 500

@app.route('/modify', methods=['POST'])
def modify():
    if not client: return jsonify({"error": "OpenAI API Offline"}), 500
    try:
        data = request.json
        current_svg = data.get('current_html', '') or data.get('current_svg', '')
        instruction = data.get('instruction', '')

        system_prompt = f"""
        ROLE: Expert Document AI.
        TASK: Modify SVG document perfectly. Keep all design elements strictly inside the workspace.
        OUTPUT STRICT JSON FORMAT:
        {{
            "message": "رد عربي ودود",
            "response": "<svg>...</svg>"
        }}
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}"}
        ]

        logger.info("🛰️ Calling GPT-4o (Modify)...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.15
        )
        logger.info("✅ Modify returned successfully.")

        raw_text = response.choices[0].message.content or ""
        result_data = extract_safe_json(raw_text)
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))

        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل!")})

    except Exception as e:
        logger.error(f"❌ [MODIFY ERROR]: {str(e)}")
        return jsonify({"error": "فشل التعديل", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
