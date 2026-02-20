import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V30 - PURE HTML/CSS EDITION)
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
        logger.info("✅ Document Engine V30 Connected (Pure HTML Engine)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

# ======================================================
# 🚀 ROUTE 1: THE GENERATION ROUTE
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V30 (HTML Engine) is Online 📄🪄"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        
        logo_b64 = data.get('logo_image')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # 1. إعدادات الورق الرسمي (Background CSS)
        if letterhead_b64:
            letterhead_css = f"""
            background-image: url('data:image/jpeg;base64,{letterhead_b64}');
            background-size: cover;
            background-position: top center;
            background-repeat: no-repeat;
            /* حماية الهيدر والفوتر بزيادة المساحات الفارغة */
            padding-top: 15% !important;
            padding-bottom: 15% !important;
            """
        else:
            letterhead_css = "background-color: white;"

        # 2. الشعار والمحاكاة
        logo_hint = f"\n- LOGO INCLUDED: Place this tag exactly at the top of the document content: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 80px; object-fit: contain; margin-bottom: 20px;\" />`" if logo_b64 else ""
        
        ref_hint = ""
        if reference_b64:
            ref_hint = """
            === 📸 PREMIUM CLONE MODE ===
            - Visually analyze the attached document.
            - Replicate its layout, tables, and data EXACTLY using HTML/CSS.
            - Upgrade the aesthetics (use beautiful table borders, subtle background colors for headers).
            - Keep the exact same number of rows for forms/invoices.
            """

        # 3. التعليمات الصارمة (HTML النقي)
        system_instruction = f"""
        ROLE: World-Class Frontend Developer & Document Designer.
        TASK: Generate a COMPLETE, stunning, standalone HTML5 document. DO NOT USE SVG.
        {logo_hint}
        {ref_hint}

        === 🎨 AESTHETICS & TYPOGRAPHY ===
        - MUST use Google Fonts for Arabic (e.g., Cairo): `<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap" rel="stylesheet">`
        - Base font size should be `14px` or `16px`. Titles should be `24px` to `28px`.
        - Make tables look highly professional: `border-collapse: collapse; width: 100%;`. Add padding `12px` to cells. Give table headers a soft background (e.g., `#f8f9fa` or similar).

        === 🌍 BILINGUAL (BIDI) RULES ===
        - The whole document MUST have `dir="rtl"`.
        - Wrap distinct French/English words or numbers in `<bdi>` to prevent text inversion. Example: `<td><bdi>Quantité</bdi> / <bdi>الكمية</bdi></td>`

        === 📄 A4 PAGE SIMULATION (CSS ARCHITECTURE) ===
        You must structure the HTML exactly like this:
        ```html
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link href="[https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap](https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;800&display=swap)" rel="stylesheet">
            <style>
                body {{
                    background-color: transparent; /* Native App Background */
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    font-family: 'Cairo', sans-serif;
                    color: #111;
                }}
                .a4-page {{
                    width: 210mm;
                    min-height: 297mm;
                    {letterhead_css}
                    padding: 40px 50px;
                    box-sizing: border-box;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                    border-radius: 4px;
                    background-color: white; /* Fallback */
                    overflow: hidden;
                }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: right; }}
                th {{ background-color: #f4f6f8; font-weight: 600; }}
            </style>
        </head>
        <body>
            <div class="a4-page">
                </div>
        </body>
        </html>
        ```

        RETURN ONLY THE RAW HTML CODE. Do not use Markdown block ticks.
        """

        contents = [user_msg] if user_msg else ["قم بتصميم هذا المستند بأعلى جودة واحرص على تنسيق الجداول بشكل فاخر."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.25)
        )
        
        raw_text = response.text or ""
        # تنظيف استخراج الـ HTML
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
        current_html = data.get('current_svg', '') # احتفظنا بنفس اسم المتغير لتجنب تعديل كل شيء في Swift
        instruction = data.get('instruction', '')

        system_prompt = """
        ROLE: Friendly Document AI Assistant & Expert Web Developer.
        TASK: Modify the existing HTML document based on user instruction.
        
        RULES:
        1. Keep the overall HTML/CSS structure (the `.a4-page` class, Google Fonts, etc.) intact.
        2. Apply the modifications requested (e.g. change colors, fix typos, add table rows).
        
        OUTPUT FORMAT (STRICT JSON):
        {
            "message": "رد عربي ودود قصير يخبر العميل بالنتيجة",
            "response": "<!DOCTYPE html><html>...updated code...</html>"
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
