import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. إعداد الاتصال بـ Gemini
API_KEY = os.environ.get('GOOGLE_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

# 2. نظام البحث المتساهل عن الوصفات
def get_recipe_lenient(category_name, user_prompt):
    base_path = "recipes"
    cat = (category_name or "").lower()
    prompt = (user_prompt or "").lower()
    
    flexible_map = {
        "card": "print/business_cards.json",
        "flyer": "print/flyers.json",
        "print": "print/flyers.json",
        "brochure": "print/brochures.json",
        "depliant": "print/brochures.json",
        "banner": "print/signage.json",
        "rollup": "print/signage.json",
        "menu": "print/menus.json",
        "social": "core/layout_sets.json",
        "post": "core/layout_sets.json",
        "invoice": "print/invoices.json",
        "فاتورة": "print/invoices.json",
        "كارت": "print/business_cards.json",
        "منيو": "print/menus.json",
        "مطوية": "print/brochures.json"
    }
    
    selected_path = None
    for key, rel_path in flexible_map.items():
        if key in cat or key in prompt:
            selected_path = os.path.join(base_path, rel_path)
            break
                
    if not selected_path or not os.path.exists(selected_path):
        selected_path = os.path.join(base_path, "print/flyers.json")
        
    return selected_path

@app.route('/')
def index():
    return "Almonjez Design Engine is Live! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width = int(data.get('width', 800))
        height = int(data.get('height', 600))
        
        # حساب أحجام خطوط متناسبة (تجنب الخطوط الضخمة)
        base_dim = min(width, height)
        max_h_font = int(base_dim * 0.08) # العنوان 8% من أصغر ضلع
        max_b_font = int(base_dim * 0.04) # النص 4% من أصغر ضلع
        
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        recipe_data = {}
        if os.path.exists(recipe_path):
            with open(recipe_path, 'r', encoding='utf-8') as f:
                recipe_data = json.load(f)
        
        # بناء تعليمات النظام (تصحيح تداخل Swift)
        system_instruction = f"""
        Context: You are the 'Almonjez Design Engine'.
        Canvas Size: {width}x{height}
        
        STRICT TYPOGRAPHY RULES:
        1. MARGINS: Keep all elements within a 10% safety margin.
        2. FONT SIZE: Headlines MAX {max_h_font}px, Body MAX {max_b_font}px. Keep it elegant.
        3. ARABIC RTL: Use x="{width * 0.9}" with 'text-anchor: end' and 'direction: rtl' for all Arabic.
        4. TEXT WRAPPING: Use <tspan> for long sentences. Never let text exceed {width * 0.8}px in width.
        5. VIEWBOX: Ensure <svg viewBox="0 0 {width} {height}">.
        
        Recipe: {json.dumps(recipe_data)}
        User Request: {user_msg}
        
        Output ONLY the raw SVG code.
        """
        
        response = model.generate_content(system_instruction)

        if response.text:
            clean_svg = response.text.replace("```svg", "").replace("```", "").strip()
            return jsonify({"response": clean_svg})
        else:
            return jsonify({"error": "Empty response"}), 500

    except Exception as e:
        print(f"‼️ ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
