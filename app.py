import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V59 - EXECUTIVE SECRETARY)
# SAFE MARGINS + CLOSED TABLES + SMART DRAFTING + MULTI-MODES
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_V59")

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
def index():
    return jsonify({"status": "Almonjez V59 (Executive Secretary) is Online ⚡🛡️"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        mode = data.get('mode', 'documents') # 👈 تحديد مساحة العمل الحالية
        
        reference_b64 = data.get('reference_image') 
        letterhead_b64 = data.get('letterhead_image')
        
        # 📄 قانون الهوامش (Safe Margins Logic)
        # 🚀 التحديث: جعل الخلفية شفافة دائماً لتجنب تغطية الأختام أو الرأسية
        bg_css = "background: transparent;"
        
        if letterhead_b64:
            # هوامش للرأسية المرفقة
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
            letterhead_instruction = "=== 📄 LETTERHEAD ACTIVE ===\n- DO NOT design a top header or logos. Start immediately with the core content."
        else:
            # هوامش افتراضية للطباعة
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.12), int(width * 0.84), int(height * 0.73)
            letterhead_instruction = """
            === 📄 SAFE MARGINS (CRITICAL) ===
            ALWAYS leave the top and bottom of the container empty. Do not fill the entire height. 
            Keep a clean, professional whitespace at the bottom for future stamps and signatures.
            """

        ref_hint = ""
        if reference_b64:
            if mode == "simulation":
                ref_hint = """
                === 👁️ SMART CLONE & INSERT (SIMULATION) ===
                1. CLONE MODE: Replicate the layout, structure, and text of the document accurately.
                2. IGNORE LOGOS: DO NOT copy or generate any logos, stamps, or watermarks. Only textual and structural data.
                3. ADAPT FORM FACTOR: If the original document has a specific shape (like a DL envelope or landscape card), adjust your SVG layout and inner containers to match that proportion.
                """
            else:
                ref_hint = f"""
                === 👁️ SMART CLONE & INSERT ===
                1. CLONE MODE: If copying a document, IGNORE shadows/wrinkles. NO random SVG paths/lines.
                2. INSERT MODE: Embed image using `<img src="data:image/jpeg;base64,{reference_b64}" style="max-width:100%; height:auto; border-radius:4px;" />`
                """

        # 🚀 فصل التعليمات حسب نوع مساحة العمل (Dynamic System Prompts)
        if mode == "resumes":
            core_instruction = """
            === 🎨 RESUMES (CV) CREATIVE & PROFESSIONAL RULES ===
            - ROLE: Expert CV & Resume Designer.
            - CREATIVITY ALLOWED: You MUST be creative. Use modern layouts (Flexbox/Grid), elegant sidebars, and clean dividers.
            - COLORS: Use professional, visually appealing colors (e.g., subtle Blues, Teals, or Dark Greys) to highlight sections and headers. DO NOT be restricted to pure black and white.
            - SHAPES: You can use rounded corners, background tints for specific sections (like skills or contact info), and varying typography weights to make the CV look stunning.
            - STRICT FIT: `width: 100%; box-sizing: border-box;`.
            """
        elif mode == "simulation":
            core_instruction = """
            === 🎨 SIMULATION & CLONING STRICT RULES ===
            - ROLE: Precise Document Typesetter.
            - EXACT COPY: Your goal is to mirror the exact structure, tables, and text of the provided image.
            - NO HALLUCINATION: Do NOT invent missing data, do NOT add extra text or headers not present in the original.
            - TABLES: If tables exist, use `width: 100%; table-layout: fixed; word-break: break-word; border-collapse: collapse;`.
            """
        else:
            # الوضع الافتراضي (Documents / الفواتير والخطابات)
            core_instruction = f"""
            === 🎨 ULTRA-MINIMALISM & FORMATTING (DOCUMENTS) ===
            - DEFAULT STYLE: Extremely simple and official. Use ONLY Black, White, and subtle Greys.
            - NO EXTRA ELEMENTS: Do not add decorative shapes or colored backgrounds.
            - 📊 CLOSED TABLES: All invoice or data tables MUST have CLOSED solid borders. CRITICAL: Use `width: 100%; table-layout: fixed; word-break: break-word; border-collapse: collapse; border: 1px solid black;` to ensure tables NEVER overflow the A4 page width. Text size should be professional (12px to 16px).

            === ✍️ CONTENT GENERATION RULES (CRITICAL) ===
            1. NO HALLUCINATION: If the user provides invoice data, ONLY format that data. DO NOT add "Thank you for visiting", fake stamps, fake dates, or extra columns unless explicitly written by the user.
            2. EXACT DATA: Use the text EXACTLY. 
            3. SMART DRAFTING: Only draft text if the user provides a very generic idea. Otherwise, stick to their data strictly.

            === 📄 SMART PAGINATION (MULTI-PAGE) ===
            - If the tables or text are too long to fit beautifully in one single height (e.g., 842px), you MUST create a multi-page document.
            - How? Double or triple the total `viewBox` height (e.g., `viewBox="0 0 {width} {height * 2}"`), and insert a SECOND `<foreignObject>` below the first one (e.g., `y="{height + fo_y}"`) to continue the text cleanly, making it look like a professional multi-page document.
            """

        sys_prompt = f"""
        ROLE: Master Executive Secretary & Document Typesetter.
        {letterhead_instruction}
        {ref_hint}
        {core_instruction}

        FORMAT EXACTLY:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; overflow: hidden; box-sizing: border-box; padding: 20px; {bg_css} display: flex; flex-direction: column; direction: rtl; font-family: -apple-system, sans-serif; color: #111;">
                    </div>
            </foreignObject>
        </svg>
        """

        contents = [user_msg] if user_msg else ["قم بإنشاء مستند رسمي بسيط، بجداول مغلقة (إن وجدت) ومساحة للأختام."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        gen_config = types.GenerateContentConfig(system_instruction=sys_prompt, temperature=0.35, max_output_tokens=8192) # 👈 تم رفع الـ tokens لدعم الصفحات المتعددة
        
        response = None
        try:
            response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, timeout_sec=45.0)
        except:
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)

        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = ensure_svg_namespaces(svg_match.group(0) if svg_match else raw_text)
        
        final_svg = inject_letterhead(final_svg, letterhead_b64, width, height)
        
        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"❌ [CRITICAL ERROR]: {str(e)}")
        return jsonify({"error": "فشل الاتصال", "details": str(e)}), 500

@app.route('/modify', methods=['POST'])
def modify():
    if not client: return jsonify({"error": "Gemini API Offline"}), 500
    try:
        data = request.json
        current_svg = data.get('current_html', '') or data.get('current_svg', '')
        instruction = data.get('instruction', '')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        width_match = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        width = int(width_match.group(1)) if width_match else 595
        height = int(width_match.group(2)) if width_match else 842

        mod_hint = ""
        if reference_b64:
            mod_hint += f"\n- INSERT IMAGE EXACTLY HERE: `<img src=\"data:image/jpeg;base64,{reference_b64}\" style=\"max-width:100%; height:auto; border-radius:4px;\" />`"
        if letterhead_b64:
            fo_x, fo_y, fo_w, fo_h = int(width * 0.08), int(height * 0.18), int(width * 0.84), int(height * 0.70)
            mod_hint += f"\n- USER ADDED LETTERHEAD: You MUST update the `<foreignObject>` tags to: `x=\"{fo_x}\" y=\"{fo_y}\" width=\"{fo_w}\" height=\"{fo_h}\"`. Shrink font sizes if needed."

        system_prompt = f"""
        ROLE: Expert Document AI.
        TASK: Modify SVG document perfectly based on user instruction.
        
        CRITICAL RULES:
        1. You must NOT remove, break, or lose any existing code or features.
        2. Only apply the requested change and keep everything else exactly the same.
        3. Maintain minimalist design (no colors unless requested) and ensure width is 100%.
        4. If adding tables, they MUST be closed with solid borders. {mod_hint}
        
        OUTPUT STRICT JSON: {{"message": "رد عربي قصير", "response": "<svg>...</svg>"}}
        """

        gen_config = types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2, max_output_tokens=4096)
        contents = [f"CURRENT SVG:\n{current_svg}\n\nINSTRUCTION:\n{instruction}"]

        response = None
        try:
            response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, timeout_sec=45.0)
        except:
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)

        result_data = extract_safe_json(response.text if response.text else "")
        updated_svg = ensure_svg_namespaces(result_data.get("response", ""))
        
        updated_svg = inject_letterhead(updated_svg, letterhead_b64, width, height)
        
        return jsonify({"response": updated_svg, "message": result_data.get("message", "تم التعديل!")})

    except Exception as e:
        logger.error(f"❌ [MODIFY ERROR]: {str(e)}")
        return jsonify({"error": "فشل التعديل", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True)
