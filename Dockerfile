# استخدام نسخة بايثون ونظام (Bookworm) المستقرة
FROM python:3.10-slim-bookworm

# منع بايثون من كتابة ملفات التخزين المؤقت وتوجيه السجلات مباشرة
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# تحديث النظام وتثبيت LibreOffice والجافا (الضرورية لملفات DOCX/XLSX) والخطوط
RUN apt-get update && apt-get install -y \
    libreoffice \
    default-jre \
    fonts-liberation \
    fonts-kacst \
    fonts-hosny-amiri \
    && rm -rf /var/lib/apt/lists/*

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تحديد البورت
EXPOSE 10000

# أمر التشغيل
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "120"]
