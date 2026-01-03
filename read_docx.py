import docx
import os

def read_docx(file_path):
    try:
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        return f"Error reading {file_path}: {str(e)}"

# Read project report
project_report = read_docx(r"e:\PARK_HERE\Concept\Park_Here_Project_Report.docx")
print("Project Report Content:")
print(project_report[:2000])  # Print first 2000 characters

# Read database schema
db_schema = read_docx(r"e:\PARK_HERE\Concept\Park_Here_Database_Schema.docx")
print("\nDatabase Schema Content:")
print(db_schema[:2000])  # Print first 2000 characters
