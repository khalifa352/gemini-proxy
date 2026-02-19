import os
import re
import logging
from flask import Flask, request, jsonify

# ======================================================
# ⚙️ SMART DOCUMENT ENGINE (INVOICES & LETTERS)
# ======================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Almonjez_Docs")

app = Flask(__name__)

client = None
try:
    from google import genai
    from google.genai import types
    API_KEY = os.environ.get('GOOGLE_API_KEY')
    if API_KEY:
        client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1beta'})
        logger.info("✅ Document Engine Connected (Gemini 2.0 Flash)")
except Exception as e:
    logger.error(f"❌ API Error: {e}")

# ======================================================
# 🚀 THE GENERATION ROUTE
# ======================================================
@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Almonjez Document Engine is Online 📄✅"})

@app.route('/gemini', methods=['POST'])
def generate():
    if not client: return jsonify({"error": "AI Offline"}), 500

    try:
        data = request.json
        user_msg = data.get('message', '')
        category = data.get('category', 'officialDocument')
        width = int(data.get('width', 595))
        height = int(data.get('height', 842))
        
        # 1. تخصيص التعليمات حسب النوع القادم من التطبيق
        doc_type_hints = ""
        if category == "invoice":
            doc_type_hints = """
            - You are designing an INVOICE / RECEIPT.
            - MUST include a professional HTML <table> for items, quantities, prices, and Total.
            - Include placeholders for 'Invoice Number', 'Date', and 'Customer Name'.
            - Use a structured, clean, corporate layout (e.g., header with logo placeholder, company details).
            """
        else:
            doc_type_hints = """
            - You are designing an OFFICIAL LETTER or CERTIFICATE.
            - Use a formal layout: Header, Date, Recipient, Body paragraphs, and Signature area.
            - Typography should be elegant and formal.
            """

        # 2. النظام الصارم للتصميم (HTML داخل SVG)
        system_instruction = f"""
        ROLE: Expert Document Designer & Frontend Developer.
        TASK: Generate a professional document SVG for an iOS App.
        
        {doc_type_hints}

        === 📐 ARCHITECTURE (CRITICAL) ===
        Since this is a document, DO NOT draw vector paths manually. 
        You MUST use a single massive `<foreignObject>` that acts as the paper canvas, and write pure HTML/CSS inside it.

        Format:
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">
            <foreignObject x="0" y="0" width="{width}" height="{height}">
                <div xmlns="http://www.w3.org/1999/xhtml" style="width: 100%; height: 100%; padding: 40px; box-sizing: border-box; background: white; direction: rtl; text-align: right; font-family: Arial, sans-serif; color: #333;">
                    </div>
            </foreignObject>
        </svg>

        === 🎨 DESIGN RULES ===
        - Make it look incredibly professional (borders, soft background colors for table headers, clean padding).
        - Write REAL, context-appropriate Arabic text based on the user's prompt (No dummy text unless requested).
        - For Arabic typography, ensure readability (font-size 14px to 24px generally).
        - Ensure high contrast.

        RETURN ONLY THE SVG CODE. NO MARKDOWN, NO EXPLANATIONS.
        """

        # 3. طلب التصميم
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.3 # حرارة منخفضة لأننا نحتاج هيكلة جداول صارمة
            )
        )
        
        # 4. الاستخراج والتنظيف
        raw_text = response.text or ""
        svg_match = re.search(r'(?s)<svg[^>]*>.*?</svg>', raw_text)
        final_svg = svg_match.group(0) if svg_match else raw_text

        # ضمان توافق iOS
        if 'xmlns="http://www.w3.org/2000/svg"' not in final_svg:
            final_svg = final_svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"', 1)
        if 'xmlns:xhtml' not in final_svg:
            final_svg = final_svg.replace('<foreignObject', '<foreignObject xmlns:xhtml="http://www.w3.org/1999/xhtml"', 1)

        return jsonify({
            "response": final_svg,
            "meta": {"engine": "Smart_Document_Engine", "category": category}
        })

    except Exception as e:
        logger.error(f"Execution Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
