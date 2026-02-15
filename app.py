import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. إعداد Gemini مع التحقق من المفتاح
API_KEY = os.environ.get('GOOGLE_API_KEY')
if not API_KEY:
    print("❌ CRITICAL: GOOGLE_API_KEY is not set in Render Environment Variables!")
else:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-2.0-flash")

# 2. وظيفة البحث المتساهل (مع طباعة المسار للتأكد)
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
            if os.path.exists(full_path):
                print(f"📂 Recipe Found: {full_path}")
                return full_path
    
    fallback = os.path.join(base_path, "print/flyers.json")
    print(f"⚠️ No specific recipe found, using fallback: {fallback}")
    return fallback

@app.route('/')
def health_check():
    return "Almonjez AI Engine: Online 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_msg = data.get('message', '')
        cat_name = data.get('category', 'general')
        width = int(data.get('width', 800))
        height = int(data.get('height', 600))
        
        print(f"📥 New Request: {cat_name} ({width}x{height})")
        
        # جلب الوصفة
        recipe_path = get_recipe_lenient(cat_name, user_msg)
        recipe_data = {}
        if os.path.exists(recipe_path):
            with open(recipe_path, 'r', encoding='utf-8') as f:
                recipe_data = json.load(f)

        # التعليمات البرمجية (هندسة foreignObject)
        system_instruction = f"""
        Context: You are the 'Almonjez Design Engine'.
        Canvas: {width}x{height}
        
        STRICT RULES:
        1. TEXT: NEVER use <text> tags. ALWAYS use <foreignObject>.
        2. WRAPPING: Use this structure for text:
           <foreignObject x="10%" y="Y" width="80%" height="auto">
             <div xmlns="http://www.w3.org/1999/xhtml" style="direction:rtl; text-align:right; color:white; font-family:sans-serif; font-size:24px; word-wrap:break-word;">
               ARABIC_TEXT_HERE
             </div>
           </foreignObject>
        3. FONT SIZES: Title: {int(height * 0.07)}px, Body: {int(height * 0.04)}px.
        4. NO MARKDOWN: Output ONLY the raw SVG code starting with <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">.
        
        Recipe Data: {json.dumps(recipe_data)}
        User Query: {user_msg}
        """

        print("🤖 Calling Gemini AI...")
        response = model.generate_content(system_instruction)
        
        if not response.text:
            print("❌ AI returned empty response")
            return jsonify({"error": "AI returned empty response"}), 500

        # تنظيف الكود
        clean_svg = response.text.replace("```svg", "").replace("```", "").strip()
        
        print(f"✅ Generation Successful! (Size: {len(clean_svg)} bytes)")
        return jsonify({"response": clean_svg})

    except Exception as e:
        print(f"‼️ SERVER ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
