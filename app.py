import os
import re
import json
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (V33 - ENTERPRISE GRADE)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs_SaaS")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine V33 Connected (Enterprise Security & Layouts)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

# ======================================================
# 🛡️ SYSTEM VALIDATORS & SANITIZERS (THE FIREWALL)
# ======================================================
def sanitize_html_security(html_content):
    """منع حقن الأكواد الخبيثة (XSS)"""
    # إزالة أي وسوم script
    clean = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html_content, flags=re.IGNORECASE)
    # إزالة الأحداث المدمجة (onclick, onerror, etc)
    clean = re.sub(r'(?i)\s*on[a-z]+\s*=\s*(["\']).*?\1', '', clean)
    return clean

def extract_safe_json(text):
    """استخراج JSON بأمان حتى لو أضاف النموذج نصوصاً أو فواصل غير صالحة"""
    try:
        # البحث عن أول قوس { وآخر قوس }
        match = re.search(r'\{.*\}', text.replace('\n', ' '), re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
    except Exception as e:
        logger.error(f"JSON Parsing Error: {e}")
    return {}

def enforce_page_structure(html_content, width, height, letterhead_css):
    """ضمان وجود هيكل HTML السليم (Version Control)"""
    if 'class="page"' not in html_content:
        logger.warning("⚠️ Model failed to return .page structure. Auto-wrapping applied.")
        # تغليف إجباري إذا فشل الذكاء الاصطناعي
        return f"""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width={width}, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, "SF Arabic", "Geeza Pro", sans-serif; margin: 0; padding: 20px; background: transparent; }}
                .page {{ width: {width}px; min-height: {height}px; box-sizing: border-box; {letterhead_css} padding: 40px; background-color: white; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 10px; }}
            </style>
        </head>
        <body>
            <div class="page">{html_content}</div>
        </body>
        </html>
        """
    return html_content

# ======================================================
# 🚀 ROUTE 1: THE GENERATION ROUTE
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez V33 (Enterprise) is Online 📄🪄"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        logo_b64 = data.get('logo_image')
        reference_b64 = data.get('reference_image')
        letterhead_b64 = data.get('letterhead_image')
        
        # 1. حسابات الحواف الديناميكية (Dynamic Padding)
        pad_top = int(height * 0.18)
        pad_bottom = int(height * 0.12)
        
        if letterhead_b64:
            letterhead_css = f"""
            background-image: url('data:image/jpeg;base64,{letterhead_b64}');
            background-size: {width}px {height}px;
            background-position: center top;
            background-repeat: no-repeat;
            padding-top: {pad_top}px !important;
            padding-bottom: {pad_bottom}px !important;
            """
        else:
            letterhead_css = "background-color: white;"

        logo_hint = f"\n- Place LOGO exactly here: `<img src=\"data:image/jpeg;base64,{logo_b64}\" style=\"max-height: 80px;\" />`" if logo_b64 else ""
        ref_hint = "\n=== CLONE MODE ===\nExtract structure and data EXACTLY. Limit tables to 15 rows max per page." if reference_b64 else ""

        # 2. الهيكل المعماري (Templates & System Rules)
        system_instruction = f"""
        ROLE: Enterprise System Templater.
        TASK: Output a production-ready HTML5 document.
        {logo_hint}
        {ref_hint}

        === 🌍 BILINGUAL & TYPOGRAPHY SYSTEM ===
        - Font: System Native Only (NO Google Fonts).
        - Bidi: Wrap ALL Latin text/numbers in `<bdi>` tags to prevent inversion.

        === 📄 HARD PAGINATION RULES (NO OVERFLOW HIDDEN) ===
        - MAX ROWS: Tables MUST NOT exceed 15 rows per `<div class="page">`.
        - If content exceeds page limits, close `</div>` and open a NEW `<div class="page">`.
        
        === 🏗️ STRICT HTML SKELETON ===
        ```html
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width={width}, initial-scale=1.0">
            <style>
                :root {{ color-scheme: light; }}
                body {{
                    background-color: transparent; margin: 0; padding: 20px 0;
                    display: flex; flex-direction: column; align-items: center; gap: 20px;
                    /* NATIVE IOS FONTS */
                    font-family: -apple-system, "SF Arabic", "SF Pro Arabic", "Geeza Pro", Tahoma, Arial, sans-serif; 
                    color: #111;
                }}
                /* BIDI ISOLATION */
                bdi {{ unicode-bidi: isolate; }}
                .page {{
                    width: {width}px; min-height: {height}px;
                    box-sizing: border-box; padding: 50px;
                    background-color: white; {letterhead_css}
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1); position: relative;
                }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; page-break-inside: auto; }}
                tr {{ page-break-inside: avoid; page-break-after: auto; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: start; font-size: 14px; unicode-bidi: plaintext; }}
                th {{ background-color: #f4f6f8; font-weight: 600; }}
                
                /* PRINT QUALITY CSS */
                @media print {{
                    body {{ padding: 0; background: white; }}
                    .page {{ box-shadow: none; border: none; margin: 0; page-break-after: always; }}
                }}
            </style>
        </head>
        <body>
            <div class="page">
                </div>
        </body>
        </html>
        ```
        RETURN ONLY RAW HTML.
        """

        contents = [user_msg] if user_msg else ["أنشئ المستند."]
        if reference_b64:
            contents.append({"inline_data": {"mime_type": "image/jpeg", "data": reference_b64}})

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction, temperature=0.1)
        )
        
        raw_html = response.text.replace("```html", "").replace("```", "").strip() if response.text else ""
        
        # 3. Post-Processing & Validation Pipeline
        clean_html = sanitize_html_security(raw_html)
        final_html = enforce_page_structure(clean_html, width, height, letterhead_css)

        return jsonify({"response": final_html})

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
        # NOTE: Updated variable name as requested by CTO!
        current_html = data.get('current_html', '') 
        instruction = data.get('instruction', '')

        system_prompt = """
        ROLE: AI HTML Modifier.
        TASK: Update the HTML based on user command. Do NOT change CSS classes or structure.
        Ensure `<bdi>` wraps all Latin text.
        
        OUTPUT STRICT JSON:
        {"message": "رد بالعربية", "response": "<!DOCTYPE html>..."}
        """

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"CURRENT HTML:\n{current_html}\n\nINSTRUCTION:\n{instruction}",
            config=types.GenerateContentConfig(system_instruction=system_prompt, temperature=0.1)
        )

        # 4. JSON Safe Parsing (No more crashing on bad JSON)
        result_data = extract_safe_json(response.text if response.text else "")
        
        raw_updated_html = result_data.get("response", "").replace("```html", "").replace("```", "").strip()
        final_updated_html = sanitize_html_security(raw_updated_html)

        return jsonify({
            "response": final_updated_html,
            "message": result_data.get("message", "تم التحديث بنجاح.")
        })

    except Exception as e:
        logger.error(f"Modify Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
