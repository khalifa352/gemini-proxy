import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V57 - STRICT MODIFY & LAYOUT)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_V57")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Connected (Vanguard: Gemini 3 | Fallback: 2.5 Flash 🛡️)")
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

def inject_letterhead(svg_code, letterhead_b64, width, height):
    if not letterhead_b64 or '<svg' not in svg_code:
        return svg_code
    vb_match = re.search(r'viewBox="0 0 \d+ (\d+)"', svg_code)
    pages = max(1, int(vb_match.group(1)) // height) if vb_match else 1
    bg_images = ""
    for p in range(pages):
        y_pos = p * height
        bg_images += f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="{y_pos}" width="{width}" height="{height}" preserveAspectRatio="none" />\n'
    return svg_code.replace('<foreignObject', f'{bg_images}\n<foreignObject', 1)

def call_gemini_with_timeout(model_name, contents, config, timeout_sec):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.models.generate_content, model=model_name, contents=contents, config=config
        )
        return future.result(timeout=timeout_sec)

@app.route('/', methods=['GET'])
def index(): return jsonify({"status": "Almonjez V57 is Online ⚡🛡️"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Offline"}), 500
    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        reference_b64 = data.get('reference_image') 
        letterhead_b64 = data.get('letterhead_image')
        
        letterhead_instruction = ""
        if letterhead_b64:
            bg_css = "background: transparent;"
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
            letterhead_instruction = "=== 📄 LETTERHEAD ===\nDO NOT design top header/logos. Start immediately with core content."
        else:
            bg_css = "background: white;"
            fo_x, fo_y, fo_w, fo_h = 0, 0, width, height

        ref_hint = f"=== 👁️ SMART CLONE ===\nIGNORE shadows/wrinkles. CLEAN HTML only.\n" if reference_b64 else ""

        core_instruction = f"""
        === 🎨 AESTHETICS & SCALING ===
        - DEFAULT STYLE: ULTRA-MINIMALIST. ONLY Black, White, and Greys.
        - CONTRAST: Use TYPOGRAPHY (Bold vs Regular). 
        - 🚫 FORBIDDEN: Fixed widths larger than the canvas.
        - MANDATORY: Use `width: 100%; box-sizing: border-box;`.
        - Ensure NOTHING is cut off. Use smaller fonts if needed.
        """

        sys_prompt = f"""
        ROLE: Master Document AI.
        {letterhead_instruction}\n{ref_hint}\n{core_instruction}
        FORMAT:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 30px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>
        """

        contents = [user_msg] if user_msg else ["صمم المستند."]
        if reference_b64: contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        gen_config = types.GenerateContentConfig(system_instruction=sys_prompt, temperature=0.35, max_output_tokens=4096)
        response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, 45.0)

        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = ensure_svg_namespaces(svg_match.group(0) if svg_match else raw_text)
        final_svg = inject_letterhead(final_svg, letterhead_b64, width, height)
        
        return jsonify({"response": final_svg})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/modify', methods=['POST'])
def modify():
    if not client: return jsonify({"error": "Offline"}), 500
    try:
        data = request.json
        current_svg = data.get('current_html', '') or data.get('current_svg', '')
        instruction = data.get('instruction', '')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        width_match = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        width = int(width_match.group(1)) if width_match else 595
        height = int(width_match.group(2)) if width_match else 842

        # 🚀 قوانين التعديل الصارمة (لن يكسر الكود أو يغير التصميم الجيد)
        mod_hint = ""
        if reference_b64:
            mod_hint += f"\n- INSERT IMAGE EXACTLY HERE: `<img src=\"data:image/jpeg;base64,{reference_b64}\" style=\"max-width:100%; height:auto; border-radius:4px;\" />`"
        if letterhead_b64:
            # إذا أضاف رأسية أثناء التعديل، نجبره على تعديل أبعاد الصندوق لتجنب تداخل النصوص
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
            mod_hint += f"\n- USER ADDED LETTERHEAD: You MUST update the `<foreignObject>` tags to: `x=\"{fo_x}\" y=\"{fo_y}\" width=\"{fo_w}\" height=\"{fo_h}\"`. Shrink font sizes slightly if needed so content fits."

        system_prompt = f"""
        ROLE: Expert Document AI.
        TASK: Modify SVG document perfectly based on user instruction.
        
        CRITICAL RULES:
        1. You must NOT remove, break, or lose any existing code or features.
        2. Only apply the requested change and keep everything else exactly the same.
        3. Do not restructure the project or hallucinate new data.
        4. Maintain minimalist design (no colors unless requested) and ensure width is 100%.{mod_hint}
        
        OUTPUT STRICT JSON: {{"message": "رد عربي قصير", "response": "<svg>...</svg>"}}
        """

        contents = [f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}"]
        gen_config = types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2, max_output_tokens=4096)
        
        response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, 45.0)

        result_data = extract_safe_json(response.text if response.text else "")
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))
        updated_svg = inject_letterhead(updated_svg, letterhead_b64, width, height)
        
        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل!")})
    except Exception as e: return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True)
