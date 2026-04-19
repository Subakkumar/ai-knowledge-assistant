import PyPDF2
import markdown
import re
import io

def extract_text_from_pdf(file_storage):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_storage.read()))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"Could not read PDF: {str(e)}")

def extract_text_from_txt(file_storage):
    try:
        content = file_storage.read()
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                return content.decode(encoding).strip()
            except:
                continue
        raise ValueError("Could not decode text file")
    except Exception as e:
        raise ValueError(f"Could not read text file: {str(e)}")

def extract_text_from_markdown(file_storage):
    try:
        content = file_storage.read().decode('utf-8')
        html = markdown.markdown(content)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    except Exception as e:
        raise ValueError(f"Could not read markdown file: {str(e)}")

def process_file(file_storage, filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    file_storage.seek(0)

    if ext == 'pdf':
        return extract_text_from_pdf(file_storage), 'pdf'
    elif ext in ['txt', 'text']:
        return extract_text_from_txt(file_storage), 'txt'
    elif ext in ['md', 'markdown']:
        return extract_text_from_markdown(file_storage), 'markdown'
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Supported: PDF, TXT, MD")