import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V53 - CREATIVE ANTI-REFLECTION)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_V53")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine Connected (Vanguard: Gemini 3 | Fallback: 2.5 Flash 🛡️)")
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

def call_gemini_with_timeout(model_name, contents, config, timeout_sec):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.models.generate_content,
            model=model_name,
            contents=contents,
            config=config
        )
        return future.result(timeout=timeout_sec)

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V53 (Creative Anti-Reflection) is Online ⚡🛡️"})

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
        
        letterhead_instruction = ""
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
            letterhead_instruction = """
            === 📄 LETTERHEAD ACTIVE (STRICT OVERRIDE) ===
            The user provided a pre-designed letterhead. 
            - DO NOT design a top header (No company logos/names at the very top).
            - Start immediately with the document title and core content.
            """
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height
            letterhead_instruction = """
            === 📄 FULL PAGE DESIGN ===
            Design the entire document from top to bottom, including professional headers and footers.
            """

        image_hint = ""
        if logo_b64:
            image_hint = f"""
            === 🖼️ ATTACHED MEDIA ===
            `<img src="data:image/jpeg;base64,{logo_b64}" style="max-width: 100%; height: auto; max-height: 150px; border-radius: 8px;" />`
            Place this image where it logically belongs contextually.
            """
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 SMART CLONE MODE ===
            Analyze the image accurately. Count the exact rows. Let the layout be compact and neat.
            """

        # 🚀 التحديث السحري: فصل الإبداع عن البيانات + حل الانعكاس
        creative_bidi_instruction = """
        === 🎨 CREATIVITY vs STRICT DATA ===
        - DESIGN: UNLEASH YOUR CREATIVITY! Use highly modern, elegant UI/UX, premium colors, soft shadows, and rounded borders.
        - DATA: NEVER invent fake data. Use ONLY the data provided by the user. Be a creative designer, but a strict accountant.

        === 🪞 ANTI-REFLECTION BILINGUAL LAYOUT (CRITICAL) ===
        NEVER write Arabic and English inline like `محمد: Mohamed` or `Date: تاريخ`. It causes text reflection bugs!
        ALWAYS use Flexbox with a middle spacer for bilingual rows. Example:
        <div style="display: flex; justify-content: space-between; align-items: flex-end; width: 100%; margin-bottom: 10px; direction: rtl;">
            <span style="font-weight: bold; font-size: 15pt;">محمد</span>
            <span style="flex-grow: 1; border-bottom: 1px dotted #ccc; margin: 0 10px; position: relative; top: -5px;"></span>
            <span dir="ltr" style="font-weight: bold; font-size: 14pt; color: #555;">Mohamed</span>
        </div>
        """

        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning document SVG. Keep EVERYTHING inside the workspace.
        
        {letterhead_instruction}
        {image_hint}
        {ref_hint}
        {creative_bidi_instruction}

        === 📏 NATURAL FLOW ===
        - You have a strict height of {fo_h}px.
        - The container MUST have `display: flex; flex-direction: column; height: 100%;`.
        - Give the final footer/signature div `margin-top: auto;` to push it down naturally.

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, Arial, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY RAW SVG CODE. DO NOT WRAP IN MARKDOWN.
        """

        contents = [user_msg] if user_msg else ["صمم المستند بإبداع بناءً على المعطيات فقط."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        gen_config = types.GenerateContentConfig(
            system_instruction=system_instruction, 
            temperature=0.45, # 📈 رفعنا الحرارة ليعود الإبداع في التصميم والألوان!
            max_output_tokens=4096 
        )

        response = None
        try:
            logger.info("🛰️ Calling Vanguard: gemini-3-flash-preview...")
            response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, timeout_sec=45.0)
            logger.info("✅ Vanguard returned successfully.")
        except concurrent.futures.TimeoutError:
            logger.warning("⚠️ Vanguard Timed Out! Switching to Fallback...")
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)
            logger.info("✅ Fallback Tank returned successfully.")
        except Exception as primary_error:
            logger.warning(f"⚠️ Vanguard Failed. Switching to Fallback...")
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)
            logger.info("✅ Fallback Tank returned successfully.")

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
        TASK: Modify SVG document perfectly. 
        OUTPUT STRICT JSON: {{"message": "رد عربي", "response": "<svg>...</svg>"}}
        """

        gen_config = types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.35, max_output_tokens=4096)
        contents = [f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}"]

        response = None
        try:
            logger.info("🛰️ Calling Vanguard Modify...")
            response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, timeout_sec=45.0)
        except:
            logger.warning("⚠️ Vanguard Modify Failed! Switching to Fallback...")
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)

        result_data = extract_safe_json(response.text if response.text else "")
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))
        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل!")})

    except Exception as e:
        logger.error(f"❌ [CRITICAL MODIFY ERROR]: {str(e)}")
        return jsonify({"error": "فشل التعديل", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True)
