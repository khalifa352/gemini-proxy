import os
import json
from flask import Flask, request, jsonify
# المكتبة الأحدث لعام 2026
from google import genai
from google.genai import types

app = Flask(__name__)

# 1. إعداد العميل الجديد
API_KEY = os.environ.get('GOOGLE_API_KEY')
client = genai.Client(api_key=API_KEY) if API_KEY else None

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

@app.route('/')
def home(): return "Almonjez Engine 2026 is Live! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        if not client: return jsonify({"error": "API Key missing"}), 500
        
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width, height = int(data.get('width', 800)), int(data.get('height', 600))
        
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        recipe_data = {}
        if os.path.exists(recipe_path):
            with open(recipe_path, 'r', encoding='utf-8') as f:
                recipe_data = json.load(f)

              # تعليمات تجعل الوصفة هي الأساس
        sys_instructions = f"""
        You are the 'Almonjez Design Architect'. 
        You MUST use the attached JSON Recipe as your MASTER BLUEPRINT.
        
        1. STRUCTURE: Draw every 'panel' or 'section' defined in the JSON using <rect> or <path>.
        2. COLORS: Use the 'visual_style' or 'color_vibe' from the JSON.
        3. DIMENSIONS: Your <svg> viewBox must be exactly {recipe_data.get('canvas_size', {}).get('viewBox', f'0 0 {width} {height}')}.
        4. TEXT: Place the user's text ONLY inside the designated safe zones from the JSON.
        
        RECIPE DATA (The Blueprint):
        {json.dumps(recipe_data)}
        
        USER REQUEST:
        {user_msg}
        
        Final Step: Output ONLY the SVG code. Make it look like a finished, professional print-ready file.
        """


        # طلب التوليد باستخدام المكتبة الجديدة
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_msg,
            config=types.GenerateContentConfig(system_instruction=sys_instructions)
        )

        svg_output = response.text.replace("```svg", "").replace("```", "").strip()
        print(f"✅ Design Generated: {len(svg_output)} bytes")
        return jsonify({"response": svg_output})

    except Exception as e:
        print(f"‼️ ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # تأكد من أن السيرفر يفتح المنفذ الصحيح لـ Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
