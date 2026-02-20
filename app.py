import os
import re
import json
import base64
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V23 - VISION & CHAT-TO-EDIT)
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
        logger.info("✅ Document Engine V2 Connected (Gemini 2.0 Flash - Multimodal)")
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
    return jsonify({"status": "Almonjez V23 (Vision & Edit) is Online 📄🪄"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        category = data.get('category', 'officialDocument')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        # استخراج الصور (Base64)
        logo_b64 = data.get('logo_image')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # 1. تخصيص التعليمات
        doc_hints = "- You are designing an INVOICE. Include an HTML <table> for items/prices." if category == "invoice" else "- You are designing an OFFICIAL LETTER. Use formal typography and paragraphs."
        
        # 2. حماية الورق الرسمي (Letterhead Logic)
        if letterhead_b64:
            # إذا كان هناك ورق رسمي، نمنع الـ CSS من وضع خلفية بيضاء، ونقلص مساحة النص لتجنب الهيدر والفوتر (y=15%, height=70%)
            bg_css = "background: transparent;"
            foreign_obj = f'<foreignObject x="{width * 0.08}" y="{height * 0.15}" width="{width * 0.84}" height="{height * 0.70}">'
        else:
            bg_css = "background: white;"
            foreign_obj = f'<foreignObject x="0" y="0" width="{width}" height="{height}">'

        # 3. حقن الشعار (Logo Logic)
        logo_hint = f"\n- LOGO INCLUDED: Place this EXACT image tag at the top of your HTML: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 80px; object-fit: contain;\" />`" if logo_b64 else ""

        # 4. محاكاة المستند (Vision Reference)
        ref_hint = "\n- REFERENCE ATTACHED: The user attached an image of a document. You MUST visually analyze it and replicate its layout structure, table style, and color scheme accurately in your HTML." if reference_b64 else ""

        system_instruction = f"""
        ROLE: Expert Document Designer & Frontend Developer.
        TASK: Generate a professional document SVG.
        {doc_hints}
        {logo_hint}
        {ref_hint}

        === 📐 ARCHITECTURE ===
        Use pure HTML/CSS inside a SINGLE `<foreignObject>`.
        {foreign_obj}
            <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; padding: 40px; box-sizing: border-box; {bg_css} direction: rtl; text-align: right; font-family: Arial, sans-serif; color: #333;">
                </div>
        </foreignObject>

        RETURN ONLY THE RAW SVG CODE.
        """

        # 5. تجهيز المحتوى لـ Gemini (نص + صورة الرؤية إن وجدت)
        contents = [user_msg]
        if reference_b64:
            contents.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": reference_b64
                }
            })

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.3)
        )
        
        # 6. استخراج الـ SVG
        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # 7. حقن الورق الرسمي كخلفية مطلقة (خلف الـ foreignObject)
        if letterhead_b64 and '<foreignObject' in final_svg:
            bg_image_tag = f'<image href="data:image/jpeg;base64,{letterhead_b64}" x="0" y="0" width="100%" height="100%" preserveAspectRatio="none" />'
            final_svg = final_svg.replace('<foreignObject', f'{bg_image_tag}\n<foreignObject', 1)

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
        
        1. Apply the user's instructions to the provided SVG code (update colors, text, or layout).
        2. Keep the overall SVG structure intact (especially the foreignObject and namespaces).
        
        OUTPUT FORMAT:
        You MUST return a strictly valid JSON object matching this structure EXACTLY. Do not use Markdown block ticks (```json).
        {
            "message": "رد عربي ودود وقصير يخبر العميل بما تم تعديله (مثال: تم تغيير لون الجدول إلى الأزرق كما طلبت!)",
            "response": "<svg>...the fully updated SVG code here...</svg>"
        }
        """

        prompt_text = f"CURRENT SVG CODE:\n{current_svg}\n\nUSER INSTRUCTION:\n{instruction}"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2 # منخفضة جداً لضمان عدم إفساد الكود القديم
            )
        )

        raw_text = response.text or ""
        
        # تنظيف الـ JSON من الـ Markdown إذا أصر الموديل على إضافتها
        json_str = raw_text.replace("```json", "").replace("```", "").strip()
        
        result_data = json.loads(json_str)
        
        # ضمان الـ Namespaces للكود المحدث
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
