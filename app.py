import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. إعداد مفتاح API
API_KEY = os.environ.get('GOOGLE_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

# 2. استخدام الموديل الأحدث لعام 2026
# تم تنظيف السطر تماماً من أي حروف مخفية
model = genai.GenerativeModel("gemini-2.0-flash")

@app.route('/')
def index():
    return "Almonjez Design Engine (2026 Edition) is Online! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_message = data.get('message', '')
        template_from_app = data.get('template_data', '')

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # طلب التصميم من Gemini
        prompt = f"""
        Context: You are the Almonjez Design Engine.
        Task: Create a professional SVG design.
        Rules:
        - Use Arabic language with RTL direction for text.
        - Return ONLY the raw SVG code.
        - Layout reference: {template_from_app}
        
        User Request: {user_message}
        """
        
        response = model.generate_content(prompt)

        if response.text:
            # تنظيف الكود البرمجي من علامات التنسيق
            clean_svg = response.text.replace("```svg", "").replace("```", "").strip()
            return jsonify({"response": clean_svg})
        else:
            return jsonify({"error": "AI returned empty response"}), 500

    except Exception as e:
        print(f"‼️ ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
