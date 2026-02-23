import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V55 - CLEAN & ANTI-ARTIFACTS)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_V55")

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
    return jsonify({"status": "Almonjez V55 (Clean Layout & Anti-Artifacts) is Online ⚡🛡️"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        reference_b64 = data.get('reference_image') 
        letterhead_b64 = data.get('letterhead_image')
        
        # 📄 معالجة الرأسية
        letterhead_instruction = ""
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
            letterhead_instruction = """
            === 📄 LETTERHEAD ACTIVE (STRICT OVERRIDE) ===
            The user provided a pre-designed letterhead. 
            - DO NOT design a top header (No company logos/names at the very top).
            - DO NOT design a footer unless it is the document total/signatures.
            - Start immediately with the document title and core content.
            """
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height
            letterhead_instruction = """
            === 📄 FULL PAGE DESIGN ===
            Design the entire document from top to bottom, including professional headers and footers.
            """

        # 📸 معالجة المحاكاة والصور + 🚫 منع الضوضاء (Anti-Noise)
        ref_hint = ""
        if reference_b64:
            ref_hint = f"""
            === 👁️ SMART VISUAL CONTEXT & ANTI-NOISE ===
            1. CLONE MODE: If the image is a document, extract its text and structure perfectly.
               - 🚫 STRICT: IGNORE shadows, wrinkles, watermarks, dust, or background noise.
               - 🚫 STRICT: DO NOT draw random SVG `<path>`, `<circle>`, or `<line>` elements to mimic paper textures. Use CLEAN HTML/CSS borders for tables and lines.
            2. INSERT MODE: If the image is a logo/photo to add, embed it using:
               `<img src="data:image/jpeg;base64,{reference_b64}" style="max-width:100%; height:auto; border-radius:8px;" />`
            """

        # 🚀 قوانين التحجيم الصارم (Anti-Oversize)
        core_instruction = f"""
        === 📏 STRICT SCALING & FIT (CRITICAL) ===
        - You have a MAXIMUM canvas of {fo_w}px width and {fo_h}px height.
        - 🚫 NEVER use absolute fixed widths/heights larger than the canvas (e.g., `width: 1500px` is FORBIDDEN).
        - Use `width: 100%` for all main tables and containers to ensure nothing is cut off.
        - If there is a lot of data, use smaller fonts (e.g., 11pt-12pt) and tighter padding so EVERYTHING fits inside without overflowing.

        === 🎨 CREATIVITY vs 🛑 STRICT DATA ===
        - DESIGN: Clean, professional, modern business UI.
        - DATA: ZERO HALLUCINATION. Do not invent fake names, items, or prices.

        === 🪞 ANTI-REFLECTION BILINGUAL LAYOUT ===
        NEVER write Arabic and English inline like `محمد: Mohamed`. ALWAYS use Flexbox with `justify-content: space-between` and `direction: rtl` for bilingual rows.
        """

        system_instruction = f"""
        ROLE: Master UI/UX Designer & Document Typesetter.
        TASK: Generate a stunning document SVG. Keep EVERYTHING inside the workspace.
        
        {letterhead_instruction}
        {ref_hint}
        {core_instruction}

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, Arial, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>

        RETURN ONLY RAW SVG CODE. DO NOT WRAP IN MARKDOWN.
        """

        contents = [user_msg] if user_msg else ["صمم المستند بإبداع، وتأكد أن كل شيء يظهر داخل الإطار بدون قص."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        gen_config = types.GenerateContentConfig(
            system_instruction=system_instruction, 
            temperature=0.3, # ⚖️ تخفيض طفيف لتقليل "تأليف الرسومات" العشوائية
            max_output_tokens=4096 
        )

        response = None
        try:
            logger.info("🛰️ Calling Vanguard: gemini-3-flash-preview...")
            response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, timeout_sec=45.0)
        except concurrent.futures.TimeoutError:
            logger.warning("⚠️ Vanguard Timed Out! Switching to Fallback...")
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)
        except Exception as primary_error:
            logger.warning(f"⚠️ Vanguard Failed. Switching to Fallback...")
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)

        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # 🧩 دمج الرأسية في الخلفية
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
        TASK: Modify SVG document perfectly based on user instruction. 
        - DO NOT invent new data. Use what the user explicitly asks for.
        - ENSURE the layout does not break or exceed 100% width.
        OUTPUT STRICT JSON: {{"message": "رد عربي قصير يوضح ما تم إنجازه", "response": "<svg>...</svg>"}}
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
        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل بنجاح!")})

    except Exception as e:
        logger.error(f"❌ [CRITICAL MODIFY ERROR]: {str(e)}")
        return jsonify({"error": "فشل التعديل", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True)
