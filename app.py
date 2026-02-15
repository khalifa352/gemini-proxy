import os
import json
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# 1. إعداد المفتاح
API_KEY = os.environ.get('GOOGLE_API_KEY')
if API_KEY:
    genai.configure(api_key=API_KEY)

# 2. استخدام الموديل المستقر (تم تنظيف الحروف المخفية هنا)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

@app.route('/')
def index():
    return "Almonjez Engine is Online! 🚀"

@app.route('/gemini', methods=['POST'])
def generate():
    try:
        data = request.json
        user_message = data.get('message', '')
        template_from_app = data.get('template_data', '')

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        # بناء الطلب بوضوح
        prompt = f"""
        System: You are 'Almonjez Design Engine'. 
        Task: Generate professional SVG code. 
        Rules: 
        - Use RTL for Arabic text.
        - Output ONLY the SVG code.
        - Start with <svg> and end with </svg>.
        
        Layout Info: {template_from_app}
        User Request: {user_message}
        """
        
        response = model.generate_content(prompt)

        if response.text:
            # تنظيف الكود من أي زوائد
            clean_svg = response.text.replace("```svg", "").replace("```", "").strip()
            return jsonify({"response": clean_svg})
        else:
            return jsonify({"error": "Empty response from AI"}), 500

    except Exception as e:
        print(f"‼️ ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
