import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

API_KEY = os.environ.get('GOOGLE_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

def get_recipe_lenient(category_name, user_prompt):
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()
    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json",
        "brochure": "print/brochures.json",
        "menu": "print/menus.json",
        "invoice": "print/invoices.json"
    }
    for key, path in flexible_map.items():
        if key in cat or key in prompt:
            full_path = os.path.join(base_path, path)
            if os.path.exists(full_path): return full_path
    return os.path.join(base_path, "print/flyers.json")

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width = int(data.get('width', 800))
        height = int(data.get('height', 600))
        
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        recipe_data = {}
        if os.path.exists(recipe_path):
            with open(recipe_path, 'r', encoding='utf-8') as f:
                recipe_data = json.load(f)

        # 🧠 هندسة النصوص الجديدة (استخدام HTML داخل SVG)
        system_instruction = f"""
        Context: You are the 'Almonjez Design Engine'.
        Canvas Size: {width}x{height} (ViewBox: 0 0 {width} {height})
        
        STRICT RULES FOR TEXT:
        1. NO <text> TAGS: Do not use standard SVG <text> tags for long sentences.
        2. USE <foreignObject>: For every text block, use:
           <foreignObject x="10%" y="Y_COORDINATE" width="80%" height="auto">
             <div xmlns="http://www.w3.org/1999/xhtml" style="direction: rtl; text-align: right; color: COLOR; font-family: sans-serif; font-size: FONT_SIZE; word-wrap: break-word;">
                YOUR_ARABIC_TEXT
             </div>
           </foreignObject>
        3. FONT SIZES: 
           - Titles: {int(min(width, height) * 0.06)}px
           - Details: {int(min(width, height) * 0.035)}px
        4. SPACING: Ensure enough vertical space (y) between foreignObjects so they don't overlap.
        5. SAFE ZONE: Keep all content within x=10% to x=90%.
        
        User Request: {user_msg}
        Recipe Geometry: {json.dumps(recipe_data)}
        
        Return ONLY pure SVG code.
        """

        response = model.generate_content(system_instruction)
        clean_svg = response.text.replace("```svg", "").replace("```", "").strip()
        return jsonify({"response": clean_svg})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
