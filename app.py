import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V31 - PERFECT HTML SIZING & BIDI)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_HTML")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine V31 Connected (Dynamic Size & Bidi)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

# ======================================================
# 🚀 ROUTE 1: THE GENERATION ROUTE
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V31 (Perfect Sizing) is Online 📄🪄"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        
        # استلام المقاسات الديناميكية من تطبيق Swift (A3, A4, A5)
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        logo_b64 = data.get('logo_image')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # 1. إعدادات الورق الرسمي والمقاسات
        if letterhead_b64:
            letterhead_css = f"""
            background-image: url('data:image/jpeg;base64,{letterhead_b64}');
            background-size: 100% 100%; /* مطابقة حجم الصفحة بالكامل */
            background-position: center;
            background-repeat: no-repeat;
            padding-top: 15% !important;
            padding-bottom: 15% !important;
            """
        else:
            letterhead_css = "background-color: white;"

        # 2. الشعار والمحاكاة
        logo_hint = f"\n- LOGO INCLUDED: Place this EXACT tag at the top of your document content: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 80px; object-fit: contain; margin-bottom: 20px;\" />`" if logo_b64 else ""
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 STRICT CLONE MODE ===
            - Visually analyze the attached document.
            - Replicate its layout, tables, and data EXACTLY.
            - Keep the exact same number of empty rows.
            """

        # 3. التعليمات الصارمة جداً (مقاسات، صفحات متعددة، ومنع الانعكاس)
        system_instruction = f"""
        ROLE: World-Class Frontend Developer & Document Designer.
        TASK: Generate a COMPLETE, stunning, standalone HTML5 document. DO NOT USE SVG.
        {logo_hint}
        {ref_hint}

        === 🌍 BILINGUAL (BIDI) & ANTI-INVERSION (CRITICAL) ===
        - You MUST prevent Arabic/French mixed text from inverting.
        - Wrap EVERY French/English word, number, or left-to-right phrase in `<span dir="ltr">` or `<bdi>`.
        - Example: `<td><span dir="ltr">Quantité</span> / الكمية</td>`
        - Example: `<p dir="auto"><span dir="ltr">Facture N° 12345</span></p>`

        === 📄 PAGE BOUNDARIES & AUTO-PAGINATION ===
        - The user selected a specific paper size.
        - The document MUST NOT overflow a single page. 
        - If the content is too long to fit in one page, YOU MUST split it into multiple `<div class="page">` elements.
        
        HTML STRUCTURE MUST BE EXACTLY THIS:
        ```html
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link href="[https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap](https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap)" rel="stylesheet">
            <style>
                body {{
                    background-color: transparent; 
                    margin: 0; padding: 20px;
                    display: flex; flex-direction: column; align-items: center; gap: 20px;
                    font-family: 'Cairo', sans-serif; color: #111;
                }}
                .page {{
                    width: {width}px;     /* DYNAMIC WIDTH FROM SWIFT */
                    height: {height}px;   /* STRICT HEIGHT FROM SWIFT */
                    overflow: hidden;     /* PREVENT TEXT ESCAPING BOUNDARIES */
                    box-sizing: border-box;
                    padding: 40px 50px;
                    {letterhead_css}
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    border-radius: 4px;
                    position: relative;
                }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: right; font-size: 14px; }}
                th {{ background-color: #f4f6f8; font-weight: 600; }}
                h1, h2, h3 {{ margin: 0 0 10px 0; }}
            </style>
        </head>
        <body>
            <div class="page">
                </div>
            </body>
        </html>
        ```

        RETURN ONLY THE RAW HTML CODE. Do not use Markdown block ticks.
        """

        contents = [user_msg] if user_msg else ["استنسخ هذا المستند بدقة."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.2)
        )
        
        raw_text = response.text or ""
        clean_html = raw_text.replace("```html", "").replace("```", "").strip()

        return jsonify({"response": clean_html})

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
        current_html = data.get('current_svg', '')
        instruction = data.get('instruction', '')

        system_prompt = """
        ROLE: Friendly Document AI Assistant & Expert Web Developer.
        TASK: Modify the existing HTML document based on user instruction.
        
        RULES:
        1. Keep the `.page` CSS class rules EXACTLY the same (width, height, overflow).
        2. Apply modifications (fix French/Arabic inversions, adjust text, etc.).
        3. ALWAYS wrap French/English words in `<span dir="ltr">`.
        4. If the user asks to open a new page or if text doesn't fit, just add a new `<div class="page">` inside the `<body>`.
        
        OUTPUT FORMAT (STRICT JSON):
        {
            "message": "رد عربي ودود قصير يخبر العميل بالنتيجة",
            "response": "<!DOCTYPE html><html>...updated HTML...</html>"
        }
        NO MARKDOWN TICKS. JUST JSON.
        """

        prompt_text = f"CURRENT HTML:\n{current_html}\n\nINSTRUCTION:\n{instruction}"

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt_text,
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.2)
        )

        raw_text = response.text or ""
        json_str = raw_text.replace("```json", "").replace("```", "").strip()
        result_data = json.loads(json_str)
        
        updated_html = result_data.get("response", "").replace("```html", "").replace("```", "").strip()
        ai_message = result_data.get("message", "تم التعديل بنجاح!")

        return jsonify({
            "response": updated_html,
            "message": ai_message
        })

    except Exception as e:
        logger.error(f"Modify Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
