import os
import json
import base64
import time
import urllib.request
import urllib.error
import logging
from flask import Blueprint, request, jsonify

# إنشاء المخطط المستقل
magic_bp = Blueprint('magic_bp', __name__)
logger = logging.getLogger("Monjez_Magic_Converter")

def cloudconvert_magic(file_bytes, input_format, output_format):
    """دالة مساعدة لتحويل أي صيغة إلى أي صيغة أخرى مباشرة عبر CloudConvert"""
    raw_api_key = os.environ.get("CLOUDCONVERT_API_KEY")
    if not raw_api_key:
        raise ValueError("CLOUDCONVERT_API_KEY غير مُعرّف.")

    api_key = raw_api_key.strip().replace('\n', '').replace('\r', '').replace(' ', '')
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    logger.info(f"⚙️ Magic Convert: {input_format.upper()} -> {output_format.upper()}...")
    job_payload = {
        "tasks": {
            "import-it": {"operation": "import/upload"},
            "convert-it": {"operation": "convert", "input_format": input_format, "output_format": output_format, "input": ["import-it"]},
            "export-it": {"operation": "export/url", "input": ["convert-it"]}
        }
    }

    try:
        req = urllib.request.Request("https://api.cloudconvert.com/v2/jobs", data=json.dumps(job_payload).encode('utf-8'), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            job_data = json.loads(resp.read().decode('utf-8'))['data']
        job_id = job_data['id']
        upload_task = next(t for t in job_data['tasks'] if t['name'] == 'import-it')
        upload_url = upload_task['result']['form']['url']
        upload_params = upload_task['result']['form']['parameters']
    except Exception as e:
        raise ValueError(f"فشل بدء المهمة: {str(e)}")

    try:
        boundary = f"----CloudConvertBoundary{int(time.time() * 1000)}"
        body = b""
        for k, v in upload_params.items():
            body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        
        filename = f"document.{input_format}".encode()
        content_type = b"application/pdf" if input_format == "pdf" else b"text/html"

        body += f"--{boundary}\r\n".encode()
        body += b"Content-Disposition: form-data; name=\"file\"; filename=\"" + filename + b"\"\r\n"
        body += b"Content-Type: " + content_type + b"\r\n\r\n" + file_bytes + b"\r\n"
        body += f"--{boundary}--\r\n".encode()

        upload_req = urllib.request.Request(upload_url, data=body, method='POST')
        upload_req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        with urllib.request.urlopen(upload_req, timeout=60) as resp:
            pass
    except Exception as e:
        raise ValueError(f"فشل الرفع: {str(e)}")

    download_url = None
    attempts = 0
    while attempts < 40:
        time.sleep(3)
        attempts += 1
        try:
            poll_req = urllib.request.Request(f"https://api.cloudconvert.com/v2/jobs/{job_id}", headers=headers)
            with urllib.request.urlopen(poll_req, timeout=15) as resp:
                status_data = json.loads(resp.read().decode('utf-8'))['data']
            status = status_data['status']
            if status == 'finished':
                export_task = next(t for t in status_data['tasks'] if t['name'] == 'export-it')
                download_url = export_task['result']['files'][0]['url']
                break
            elif status == 'error':
                raise ValueError("فشل التحويل داخل CloudConvert.")
        except urllib.error.HTTPError:
            continue
    
    if not download_url:
        raise ValueError("انتهى وقت الانتظار.")

    try:
        req_dl = urllib.request.Request(download_url)
        with urllib.request.urlopen(req_dl, timeout=60) as resp:
            output_bytes = resp.read()
        return output_bytes
    except Exception as e:
        raise ValueError(f"فشل التحميل: {str(e)}")


@magic_bp.route("/magic_convert", methods=["POST"])
def magic_convert():
    # استدعاء دوال الجيميني من السيرفر الأساسي محلياً لمنع تعارض الاستيراد
    # (تأكد أن ملفك الأساسي اسمه server.py)
    try:
        from server import call_gemini, get_types, clean_html_output
    except ImportError:
        return jsonify({"error": "Failed", "details": "لا يمكن الوصول لملف server.py. تأكد من اسم الملف."}), 500

    try:
        data = request.json
        pdf_b64 = data.get("pdf_base64", "")
        target_format = data.get("target_format", "word").lower()
        is_arabic = data.get("is_arabic", False)

        if not pdf_b64:
            return jsonify({"error": "Failed", "details": "لم يتم إرسال ملف PDF."}), 400

        pdf_bytes = base64.b64decode(pdf_b64)
        
        # 1. حالة التحويل المباشر (PowerPoint أو مستند لاتيني)
        if target_format == "ppt" or target_format == "powerpoint" or not is_arabic:
            logger.info(f"⚡ Direct Fast Path: PDF to {target_format.upper()}")
            out_fmt = "pptx" if "ppt" in target_format else ("xlsx" if target_format == "excel" else "docx")
            
            output_bytes = cloudconvert_magic(pdf_bytes, "pdf", out_fmt)
            output_b64 = base64.b64encode(output_bytes).decode('utf-8')
            
            return jsonify({
                "file_base64": output_b64, 
                "extension": out_fmt,
                "message": f"تم التحويل المباشر إلى {out_fmt.upper()} بنجاح ✨"
            })

        # 2. حالة الذكاء الاصطناعي (عربي -> Word أو Excel)
        logger.info(f"🧠 AI Simulation Path: Arabic PDF to {target_format.upper()}")
        
        prompt = """You are a precise data extraction engine. 
Read the provided document and convert its entire content into clean, plain HTML.
- For EXCEL: Use ONLY <table>, <tr>, <td>, <th>. Extract all data into a single structured table.
- For WORD: Use <p>, <h1>, <table>. Maintain the exact reading order.
- CRITICAL: Do NOT invent data. Maintain Arabic text perfectly. Add dir="rtl" to the main wrapper."""

        contents = [
            prompt,
            get_types().Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        ]
        
        gen_config = get_types().GenerateContentConfig(temperature=0.0, max_output_tokens=20000)
        
        try:
            resp = call_gemini("gemini-2.5-flash", contents, gen_config, 60)
        except Exception as e:
            logger.error(f"Gemini PDF Read Error: {e}")
            return jsonify({"error": "Failed", "details": "فشل الذكاء الاصطناعي في قراءة الملف."}), 500

        clean_html = clean_html_output(resp.text or "")
        
        # تغليف הـ HTML بأساسيات الجدول ليقبله CloudConvert بسلاسة
        full_html = f"""<html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>table{{border-collapse:collapse;width:100%;}}th,td{{border:1px solid #000;padding:5px;}}</style></head><body>{clean_html}</body></html>"""
        html_bytes = full_html.encode('utf-8')

        out_fmt = "xlsx" if target_format == "excel" else "docx"
        
        output_bytes = cloudconvert_magic(html_bytes, "html", out_fmt)
        output_b64 = base64.b64encode(output_bytes).decode('utf-8')

        return jsonify({
            "file_base64": output_b64, 
            "extension": out_fmt,
            "message": f"تمت المحاكاة والتحويل إلى {out_fmt.upper()} بنجاح ✨"
        })

    except Exception as e:
        logger.error(f"Magic Convert Error: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed", "details": f"فشل التحويل: {str(e)}"}), 500
