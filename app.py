import os
import re
import json
import logging
import concurrent.futures
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V60 - ENHANCED)
# DYNAMIC MARGINS + ADAPTIVE PAGINATION + SMOOTH MODIFY
# ======================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_V60")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine Connected (Gemini 3 Flash)")
    else:
        logger.warning("⚠️ GOOGLE_API_KEY is missing.")
except Exception as e:
    logger.error(f"❌ Gemini Error: {e}")

def extract_safe_json(text):
    try:
        match = re.search(r'\{.*\}', text.replace('\n', ' '), re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except:
        pass
    return {}

def ensure_svg_namespaces(svg_code):
    if 'xmlns="http://www.w3.org/2000/svg"' not in svg_code:
        svg_code = svg_code.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if 'xmlns:xhtml' not in svg_code:
        svg_code = svg_code.replace('<foreignObject', '<foreignObject xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)
    return svg_code

def calculate_adaptive_margins(width, height, letterhead_active, content_type="documents"):
    """
    حساب الهوامش الديناميكية بناءً على نوع المحتوى
    """
    margin_left = int(width * 0.06)
    margin_right = int(width * 0.06)
    margin_bottom = int(height * 0.08)  # مساحة للأختام والتواقيع

    if letterhead_active:
        # مساحة أقل للرأسية (10-15% فقط، وليس 25%)
        margin_top = int(height * 0.12)
    else:
        margin_top = int(height * 0.08)

    content_width = width - (margin_left + margin_right)
    content_height = height - (margin_top + margin_bottom)

    return {
        "x": margin_left,
        "y": margin_top,
        "width": content_width,
        "height": content_height,
        "margin_top": margin_top,
        "margin_bottom": margin_bottom
    }

def inject_letterhead_smart(svg_code, letterhead_b64, width, height):
    """
    إدراج الرأسية بذكاء مع تعديل الهوامش
    """
    if not letterhead_b64 or '<svg' not in svg_code:
        return svg_code

    # استخراج عدد الصفحات من viewBox
    vb_match = re.search(r'viewBox="0 0 \d+ (\d+)"', svg_code)
    total_height = int(vb_match.group(1)) if vb_match else height
    pages = max(1, (total_height + height - 1) // height)

    bg_images = ""
    for p in range(pages):
        y_pos = p * height
        # الرأسية تظهر فقط في الصفحة الأولى
        if p == 0:
            bg_images += f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="{y_pos}" width="{width}" height="{height}" preserveAspectRatio="none" />\n'

    # إضافة الرأسيات قبل أول foreignObject
    return svg_code.replace('<foreignObject', f'{bg_images}<foreignObject', 1)

def call_gemini_with_timeout(model_name, contents, config, timeout_sec):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            client.models.generate_content, model=model_name, contents=contents, config=config
        )
        return future.result(timeout=timeout_sec)

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V60 (Enhanced) is Online ⚡"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client:
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        mode = data.get('mode', 'documents')
        
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # 📐 حساب الهوامش الديناميكية
        margins = calculate_adaptive_margins(width, height, bool(letterhead_b64), mode)
        fo_x, fo_y = margins["x"], margins["y"]
        fo_w, fo_h = margins["width"], margins["height"]
        
        bg_css = "background: transparent;"
        
        # تحديد التعليمات بناءً على الرأسية
        if letterhead_b64:
            letterhead_instruction = f"""
            === 📄 LETTERHEAD ACTIVE ===
            - LETTERHEAD SPACE: Reserved at the top ({margins['margin_top']}px).
            - START CONTENT: Begin immediately below the reserved space.
            - NO DECORATIVE ELEMENTS: No logos, no top borders, no design fluff.
            - Transparent backgrounds only.
            """
        else:
            letterhead_instruction = """
            === 📄 NO LETTERHEAD ===
            - Full page available for content.
            - Leave clean whitespace at bottom (8%) for signatures and stamps.
            """

        ref_hint = ""
        if reference_b64:
            if mode == "simulation":
                ref_hint = """
                === 👁️ SMART CLONE MODE ===
                1. Clone the exact structure and text layout from the image.
                2. NO LOGOS or decorative elements - only text and tables.
                3. Match the document's form factor exactly.
                4. DO NOT hallucinate missing data.
                """
            else:
                ref_hint = f"""
                === 👁️ REFERENCE IMAGE INSERT ===
                - Embed: <img src="data:image/jpeg;base64,{reference_b64}" style="max-width:100%; height:auto; border-radius:4px; margin: 10px 0;" />
                - Center aligned.
                """

        if mode == "resumes":
            core_instruction = """
            === 🎨 RESUMES (CREATIVE MODE) ===
            - ROLE: Professional CV Designer.
            - YOU MUST BE CREATIVE: Modern layouts, sidebars, color schemes.
            - STRICT FIT: width: 100%; box-sizing: border-box;
            - Professional colors encouraged.
            """
        elif mode == "simulation":
            core_instruction = """
            === 🎨 DOCUMENT CLONING (SIMULATION) ===
            - ROLE: Precision Document Typesetter.
            - EXACT COPY: Mirror the structure, tables, and text exactly.
            - NO INVENTION: Do not add missing data or extra headers.
            - TABLES: width: 100%; table-layout: fixed; border-collapse: collapse;
            """
        else:
            core_instruction = f"""
            === 🚫 DOCUMENTS (STRICT ANTI-HALLUCINATION) ===
            1. EXACT DATA ONLY: Format text exactly as provided.
            2. NO FAKE ELEMENTS: No invented greetings, dates, stamps, or signatures.
            3. MINIMALIST DESIGN: Black text, transparent background.
            
            === 📊 TABLES ===
            - Style: width: 100%; table-layout: fixed; border-collapse: collapse; border: 1px solid #333;
            - Cells: padding: 6px 8px; font-size: 12px;
            - NO EXCESSIVE HEIGHT.
            
            === 📄 SMART PAGINATION ===
            - Available content height: {fo_h}px
            - If content exceeds this, create a second page by extending viewBox.
            - NEW PAGE = New <foreignObject> at y="{height}" with same width/height as current.
            - Each page must be INDEPENDENT (not stretched).
            """

        sys_prompt = f"""
        ROLE: Master Executive Secretary & Document Engine.
        {letterhead_instruction}
        {ref_hint}
        {core_instruction}

        RETURN EXACTLY THIS SVG STRUCTURE:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; box-sizing: border-box; padding: 15px; {bg_css} direction: rtl; font-family: -apple-system, BlinkMacSystemFont, sans-serif; color: #111; line-height: 1.5;">
                    [CONTENT HERE]
                </div>
            </foreignObject>
        </svg>
        """

        contents = [user_msg] if user_msg else ["إنشاء مستند رسمي بسيط بجداول مغلقة."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        gen_config = types.GenerateContentConfig(
            system_instruction=sys_prompt, 
            temperature=0.2,
            max_output_tokens=8192
        )
        
        response = None
        try:
            response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, timeout_sec=45.0)
        except Exception as e:
            logger.warning(f"⚠️ Gemini 3 failed, falling back to 2.5: {e}")
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=40.0)

        raw_text = response.text or ""
        
        # استخراج SVG
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text
        
        # تنظيف الألوان البيضاء
        final_svg = re.sub(
            r'<rect[^>]*fill=["\'](?:white|#FFF|#ffffff|#fff|#FFFFFF)["\'][^>]*>', 
            '', 
            final_svg
        )
        final_svg = final_svg.replace('background-color: white;', 'background-color: transparent;')
        final_svg = final_svg.replace('background: white;', 'background: transparent;')
        
        # ضمان الـ namespaces الصحيحة
        final_svg = ensure_svg_namespaces(final_svg)
        final_svg = inject_letterhead_smart(final_svg, letterhead_b64, width, height)
        
        logger.info(f"✅ Generated document (mode: {mode}, letterhead: {bool(letterhead_b64)})")
        return jsonify({"response": final_svg})

    except Exception as e:
        logger.error(f"❌ [CRITICAL ERROR]: {str(e)}", exc_info=True)
        return jsonify({"error": "خطأ في إنشاء المستند", "details": str(e)}), 500

@app.route('/modify', methods=['POST'])
def modify():
    """
    تعديل محسّن مع فهم أفضل للسياق والهوامش والصور
    """
    if not client:
        return jsonify({"error": "Gemini API Offline"}), 500

    try:
        data = request.json
        current_svg = data.get('current_html', '') or data.get('current_svg', '')
        instruction = data.get('instruction', '')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # استخراج الأبعاد من SVG الحالي
        width_match = re.search(r'viewBox="0 0 (\d+) (\d+)"', current_svg)
        width = int(width_match.group(1)) if width_match else 595
        height = int(width_match.group(2)) if width_match else 842
        
        # 📐 حساب الهوامش الديناميكية للتعديل
        margins = calculate_adaptive_margins(width, height, bool(letterhead_b64), "documents")
        fo_x, fo_y = margins["x"], margins["y"]
        fo_w, fo_h = margins["width"], margins["height"]
        
        # بناء تعليمات التعديل بذكاء
        mod_instruction = f"""
        === 🔧 SMART MODIFY MODE ===
        CURRENT DOCUMENT CONSTRAINTS:
        - Page size: {width}x{height}px
        - Content area: {fo_w}x{fo_h}px (at x={fo_x}, y={fo_y})
        - Letterhead active: {bool(letterhead_b64)}
        
        MODIFICATION RULES:
        1. PRESERVE STRUCTURE: Keep all existing code, do NOT remove or break anything.
        2. APPLY CHANGE: Only modify what the user requested.
        3. ADAPT TO SPACE: If adding content (images/text), ensure it fits within {fo_h}px height.
        4. INTELLIGENT PAGINATION: If new content exceeds available height:
           - Create a second page by extending viewBox height to {height * 2}
           - Add a NEW <foreignObject> at y="{height}" with same dimensions
           - This is NOT stretching the current page, it's creating a real new page
        5. IMAGE INSERTION: {f'Insert image: <img src="data:image/jpeg;base64,{reference_b64}" style="max-width:100%; height:auto; margin:10px 0; border-radius:4px;" />' if reference_b64 else 'No image provided'}
        6. LETTERHEAD UPDATE: {f'Update <foreignObject> to x="{fo_x}" y="{fo_y}" width="{fo_w}" height="{fo_h}"' if letterhead_b64 else 'No letterhead changes'}
        """
        
        system_prompt = f"""
        ROLE: Expert Document Modifier & Intelligent Architect.
        {mod_instruction}
        
        RESPONSE FORMAT - STRICT JSON:
        {{
            "message": "ملخص التعديل بالعربية",
            "response": "<svg>...</svg>"
        }}
        
        IMPORTANT:
        - Must return valid JSON with "message" and "response" keys
        - SVG must be complete and valid
        - Do NOT truncate output
        """

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt, 
            temperature=0.15,
            max_output_tokens=16384
        )
        
        contents = [f"""CURRENT SVG:
{current_svg}

USER INSTRUCTION:
{instruction}

MODIFY THIS DOCUMENT INTELLIGENTLY."""]

        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = None
        try:
            response = call_gemini_with_timeout("gemini-3-flash-preview", contents, gen_config, timeout_sec=50.0)
        except Exception as e:
            logger.warning(f"⚠️ Modify failed on Gemini 3: {e}")
            response = call_gemini_with_timeout("gemini-2.5-flash", contents, gen_config, timeout_sec=45.0)

        # استخراج JSON من الرد
        result_data = extract_safe_json(response.text if response.text else "")
        raw_svg = result_data.get("response", "")
        message = result_data.get("message", "تم التعديل بنجاح")
        
        # تنظيف الألوان البيضاء
        raw_svg = re.sub(
            r'<rect[^>]*fill=["\'](?:white|#FFF|#ffffff|#fff|#FFFFFF)["\'][^>]*>', 
            '', 
            raw_svg
        )
        raw_svg = raw_svg.replace('background-color: white;', 'background-color: transparent;')
        raw_svg = raw_svg.replace('background: white;', 'background: transparent;')
        
        # ضمان الـ namespaces
        updated_svg = ensure_svg_namespaces(raw_svg)
        updated_svg = inject_letterhead_smart(updated_svg, letterhead_b64, width, height)
        
        logger.info(f"✅ Modified document successfully")
        return jsonify({
            "response": updated_svg, 
            "message": message
        })

    except Exception as e:
        logger.error(f"❌ [MODIFY ERROR]: {str(e)}", exc_info=True)
        return jsonify({
            "error": "فشل التعديل", 
            "details": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)
