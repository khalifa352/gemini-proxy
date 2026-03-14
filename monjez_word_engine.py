import base64
import io
import logging
import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt
from bs4 import BeautifulSoup, NavigableString

logger = logging.getLogger("Monjez_Word_Engine")

def generate_local_word(html_content, letterhead_b64):
    doc = docx.Document()
    
    # 1. ضبط الإعدادات الافتراضية للمستند (حل مشكلة الخط الصغير)
    style = doc.styles['Normal']
    style.font.name = 'Arial'
    style.font.size = Pt(14)  # تكبير الخط ليتناسب مع الصفحة بشكل رسمي
    
    # 2. إدراج الرأسية في أعلى الصفحة
    if letterhead_b64:
        try:
            img_data = base64.b64decode(letterhead_b64)
            img_stream = io.BytesIO(img_data)
            doc.add_picture(img_stream, width=Inches(6.0))
            # توسيط صورة الرأسية
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception as e:
            logger.error(f"خطأ في دمج الرأسية: {e}")

    # 3. تحليل هيكل HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # العناصر التي تُعتبر كتلة واحدة (لكي لا يتم كسر السطر للكلمات المتجاورة)
    block_elements = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']
    
    def process_block(element):
        """تجميع النصوص المتجاورة (مثل التوقيع والتاريخ) في نفس السطر"""
        text_parts = []
        # البحث عن كل النصوص داخل هذه الكتلة وتجريدها من المسافات الزائدة
        for string in element.stripped_strings:
            text_parts.append(string)
        
        full_text = " ".join(text_parts)
        if full_text:
            p = doc.add_paragraph(full_text)
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT # فرض اتجاه اليمين لليسار (حل الانعكاس)

    # التصفح الذكي للعناصر
    for element in soup.body.children if soup.body else soup.children:
        if isinstance(element, NavigableString):
            continue
            
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            text = element.get_text(strip=True)
            if text:
                level = int(element.name[1])
                p = doc.add_heading(text, level=min(level, 9))
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
        elif element.name == 'table':
            rows = element.find_all('tr')
            if rows:
                cols = max((len(row.find_all(['td', 'th'])) for row in rows), default=0)
                if cols > 0:
                    table = doc.add_table(rows=len(rows), cols=cols)
                    table.style = 'Table Grid'
                    for i, row in enumerate(rows):
                        cells = row.find_all(['td', 'th'])
                        for j, cell in enumerate(cells):
                            if j < cols:
                                cell_obj = table.cell(i, j)
                                # التقاط كل النصوص داخل الخلية ودمجها
                                cell_text = " ".join([text for text in cell.stripped_strings])
                                cell_obj.text = cell_text
                                for paragraph in cell_obj.paragraphs:
                                    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                                    
        elif element.name in ['ul', 'ol']:
            for li in element.find_all('li', recursive=False):
                p = doc.add_paragraph(li.get_text(strip=True), style='List Bullet')
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
        elif element.name in block_elements:
            process_block(element)

    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()
