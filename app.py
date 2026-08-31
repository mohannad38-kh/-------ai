from flask import Flask, render_template, request, jsonify, send_file
from google import genai
import os
import PyPDF2
import docx
import markdown
import io

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# قاموس لتتبع الاستخدام المجاني بناءً على عنوان IP
user_usage = {}
FREE_LIMIT = 3

def extract_text_from_pdf(file_stream):
    reader = PyPDF2.PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text

def extract_text_from_docx(file_stream):
    doc = docx.Document(file_stream)
    text = "\n".join([p.text for p in doc.paragraphs if p.text])
    return text

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/optimize', methods=['POST'])
def optimize_cv():
    user_ip = request.remote_addr
    current_usage = user_usage.get(user_ip, 0)

    if current_usage >= FREE_LIMIT:
        return jsonify({
            'result': 'لقد استهلكت محاولاتك الـ 3 المجانية لهذا اليوم. يرجى الاشتراك للحصول على استخدام غير محدود!'
        }), 403

    try:
        job_title = request.form.get('job_title', '')
        language = request.form.get('language', 'English')
        cv_text = request.form.get('cv_text', '')

        if 'cv_file' in request.files and request.files['cv_file'].filename != '':
            file = request.files['cv_file']
            filename = file.filename.lower()
            if filename.endswith('.pdf'):
                cv_text = extract_text_from_pdf(file.stream)
            elif filename.endswith('.docx'):
                cv_text = extract_text_from_docx(file.stream)

        if not cv_text.strip():
            return jsonify({'result': 'يرجى إدخال نص أو رفع ملف سيرة ذاتية صالح.'}), 400

        prompt = f"""
You are an expert ATS Resume Optimizer.
Optimize the following CV text specifically for the position of '{job_title}'.
Target Output Language: {language}.

Requirements:
1. Make it fully ATS-friendly with standard headers and keywords.
2. Structure the content with Markdown headings (##), bold text, and bullet points.
3. Highlight relevant technical skills, tools, and achievements.

CV Content:
{cv_text}
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )

        raw_text = response.text
        formatted_html = markdown.markdown(raw_text)

        user_usage[user_ip] = current_usage + 1

        return jsonify({
            'raw_text': raw_text,
            'formatted_html': formatted_html,
            'remaining_tries': FREE_LIMIT - user_usage[user_ip]
        })

    except Exception as e:
        return jsonify({'result': f"حدث خطأ أثناء معالجة الطلب: {str(e)}"}), 500

# مسار لتحميل النتيجة كملف Word (يعمل بكفاءة عالية)
@app.route('/download/word', methods=['POST'])
def download_word():
    content = request.form.get('content', '')
    doc = docx.Document()
    doc.add_heading('Optimized CV', 0)
    for line in content.split('\n'):
        doc.add_paragraph(line)
        
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    
    return send_file(
        file_stream,
        as_attachment=True,
        download_name='Optimized_Resume.docx',
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

if __name__ == '__main__':
    app.run(debug=True)