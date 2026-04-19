"""utils/pdf_utils.py"""
import io

def extract_text_from_pdf(uploaded_file) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
        pages  = []
        for i, page in enumerate(reader.pages):
            t = page.extract_text()
            if t: pages.append(f"--- Page {i+1} ---\n{t}")
        return "\n\n".join(pages)
    except ImportError:
        return "ERROR: Run: pip install PyPDF2"
    except Exception as e:
        return f"ERROR: {e}"

def extract_topics_from_excel(uploaded_file) -> list:
    try:
        import pandas as pd
        fn = uploaded_file.name.lower()
        df = pd.read_csv(uploaded_file) if fn.endswith(".csv") else pd.read_excel(uploaded_file)
        col = next((c for c in df.columns if c.lower() in ["topic","topics","chapter","unit","subject"]), None)
        return df[col].dropna().astype(str).tolist() if col else df.iloc[:,0].dropna().astype(str).tolist()
    except Exception as e:
        return [f"ERROR: {e}"]
