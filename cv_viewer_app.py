import os
import pandas as pd
import streamlit as st
import fitz  # PyMuPDF
from docx import Document
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import sqlite3
from datetime import datetime

# --- تدريب النموذج من بيانات التدريب ---
df_train = pd.read_csv("training_data.csv")
vectorizer = TfidfVectorizer(stop_words='english')
X = vectorizer.fit_transform(df_train["Resume_Text"])
y = df_train["Match"]
model = LogisticRegression(class_weight='balanced')
model.fit(X, y)

# --- تعريف مجموعات الوظائف ---
job_groups = {
    "تحليل البيانات": ["Data Analyst", "Business Analyst", "Reporting Analyst"],
    "تطوير برمجيات": ["Software Developer", "Backend Engineer", "Full Stack Developer"],
    "دعم فني": ["IT Support", "Helpdesk", "Technical Support"],
    "هندسة نظم": ["Systems Engineer", "Infrastructure Engineer", "DevOps"],
    "إدارة مشاريع": ["Project Manager", "Project Coordinator", "Scrum Master"],
    "وظائف التأمين": ["Insurance Specialist", "Insurance Analyst", "Underwriter", "Claims Processor", "Insurance Coordinator"]
}

# --- تحميل بيانات التحليل السابقة ---
df = pd.read_excel("batch_prediction_by_city.xlsx")

st.title("📋 لوحة إدارة السير الذاتية")

# --- اختيار المدينة والوظيفة ---
cities = sorted(df["City"].dropna().unique())
selected_city = st.selectbox("🏙️ اختر المدينة", cities)

selected_job_group = st.selectbox("🧳 اختر نوع الوظيفة", list(job_groups.keys()))
related_titles = job_groups[selected_job_group]

# --- تصفية البيانات وعرضها ---
filtered_df = df[
    (df["City"] == selected_city) &
    (df["Job_Title"].isin(related_titles))
]

st.write(f"🔍 عدد السير المطابقة: {len(filtered_df)}")
st.dataframe(filtered_df)

# --- تحميل البيانات كـ Excel ---
from io import BytesIO
output = BytesIO()
with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
    filtered_df.to_excel(writer, index=False, sheet_name='Resumes')
output.seek(0)

st.download_button(
    label="📥 تحميل النتائج كـ Excel",
    data=output,
    file_name=f"{selected_city}_{selected_job_group}_resumes.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# --- إنشاء قاعدة البيانات وجدول التخزين ---
conn = sqlite3.connect("cv_results.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS resumes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        city TEXT,
        job_group TEXT,
        result TEXT,
        timestamp TEXT
    )
''')
conn.commit()

# --- رفع وتحليل سيرة جديدة ---
st.header("📤 تحليل سيرة ذاتية جديدة")

uploaded_file = st.file_uploader("ارفع سيرة ذاتية (PDF أو Word)", type=["pdf", "docx"])

def extract_text(file):
    if file.name.endswith(".pdf"):
        text = ""
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text
    elif file.name.endswith(".docx"):
        doc = Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    return None

if uploaded_file:
    st.info(f"📄 تم رفع: {uploaded_file.name}")
    resume_text = extract_text(uploaded_file)

    if resume_text:
        vector = vectorizer.transform([resume_text])
        prediction = model.predict(vector)[0]
        result = "✅ مناسب" if prediction == 1 else "❌ غير مناسب"
        st.success(f"النتيجة: {result}")

        # --- حفظ النتيجة في قاعدة البيانات ---
        cursor.execute('''
            INSERT INTO resumes (file_name, city, job_group, result, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            uploaded_file.name,
            selected_city,
            selected_job_group,
            result,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        st.info("📝 تم حفظ النتيجة في قاعدة البيانات.")
    else:
        st.warning("⚠️ لم نتمكن من قراءة النص من هذا الملف.")

# --- لوحة عرض قاعدة البيانات ---
st.header("📚 عرض السجلات المحفوظة")

df_db = pd.read_sql_query("SELECT * FROM resumes ORDER BY timestamp DESC", conn)
st.dataframe(df_db)
