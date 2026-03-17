# استخدام بيئة بايثون خفيفة كأساس
FROM python:3.10-slim

# تحديث النظام وتثبيت LibreOffice والخطوط (الخطوط ضرورية لدعم اللغة العربية)
RUN apt-get update && apt-get install -y \
    libreoffice \
    fonts-noto \
    fonts-mscorefonts-base \
    && rm -rf /var/lib/apt/lists/*

# تعيين مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت المكتبات (تأكد أن لديك ملف requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع (مثل app.py)
COPY . .

# فتح المنفذ الذي يعمل عليه السيرفر
EXPOSE 10000

# تشغيل السيرفر (يمكنك استخدام gunicorn إذا كنت تفضل ذلك)
CMD ["python", "app.py"]
