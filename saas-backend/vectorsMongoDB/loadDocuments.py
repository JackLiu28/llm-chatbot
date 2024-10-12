'''
This file is used to load documents from the file system into the Vector generation script

@Author: Sanjit Verma
@Author: Dinesh Kannan (dkannan)
'''
import os
import fitz
import pandas as pd
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from tqdm import tqdm

def extract_tables_from_page(page):
    """
    Extract tables from a PDF page using PyMuPDF.
    Args:
    - page: A PDF page object.
    
    Returns:
    - tables: List of DataFrames representing the tables.
    - table_boxes: List of bounding boxes of the tables.
    """
    tables = []
    table_boxes = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" in b:
            table = []
            for l in b["lines"]:
                span_texts = [span["text"] for span in l["spans"] if span["text"].strip()]
                table.append(span_texts)
            if table:
                df = pd.DataFrame(table)
                tables.append(df)
                table_boxes.append(fitz.Rect(b['bbox']))
    return tables, table_boxes

def extract_text_and_table_from_page(page):
    """
    Extract text and tables from a PDF page.
    Args:
    - page: A PDF page object.
    
    Returns:
    - A combined string of text and table data.
    """
    # Extract tables and their bounding boxes
    tables, table_boxes = extract_tables_from_page(page)

    # Extract text from blocks not overlapping with table bounding boxes
    text_blocks = []
    code_blocks = []
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        box = fitz.Rect(b['bbox'])
        if not any(box.intersects(tb) for tb in table_boxes) and 'text' in b:
            block_text = b["text"].strip()
            if block_text:
                # Check if the block is a code block by detecting typical code indentation/pattern
                if any(line.strip().startswith(tuple("0123456789")) for line in block_text.splitlines()):
                    code_blocks.append(block_text)
                else:
                    text_blocks.append(block_text)
    
    text = "\n".join(text_blocks).replace("None", "").strip()  # Combine text blocks into a single string

    table_texts = []
    for table in tables:
        table_text = table.to_string(index=False, header=False)
        table_texts.append(table_text)

    # Combine text, code blocks, and table texts
    result = text + "\n\n" + "\n\n".join(code_blocks) + "\n\n" + "\n\n".join(table_texts)
    return result.strip()

def load_pdfs(directory):
    """
    Load all PDFs from a directory, extract content, and return document chunks.
    Args:
    - directory: Path to the directory containing PDF files.
    
    Returns:
    - List of document chunks.
    """
    documents = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1048, chunk_overlap=100)
    unique_contents = set()  # To track unique document content

    # List all PDF files in the directory, filter out non-PDF files
    pdf_files = [f for f in os.listdir(directory) if f.endswith('.pdf')]

    # Loop over all the PDF files in the directory
    for filename in tqdm(pdf_files, desc="Processing PDFs", unit="file"):
        pdf_path = os.path.join(directory, filename)

        try:
            pdf_document = fitz.open(pdf_path)
            for page_num in range(pdf_document.page_count):  # Process all pages
                page = pdf_document.load_page(page_num)
                text = extract_text_and_table_from_page(page)
                print(text)
                if text.strip() and text not in unique_contents:  # Only proceed if there is text content
                    unique_contents.add(text)
                    doc = Document(page_content=text, metadata={"page_number": page_num, "source": filename})
                    docs = text_splitter.split_documents([doc])
                    documents.extend(docs)
                else:
                    tqdm.write(f"No text or duplicate text extracted from page {page_num} of {filename}.")
            pdf_document.close()
            tqdm.write(f"Loaded and processed {len(docs)} chunks from {filename}.")
        except Exception as e:
            tqdm.write(f"Failed to process {filename}: {e}")

    return documents

def load_json(directory):
    documents = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1048, chunk_overlap=100)

    unique_contents = set()  # To track unique document content

    try:
        # Load JSON file
        with open(directory, 'r') as file:
            data = json.load(file)
        
        # Extract content from the nested structure (e.g., under "content", or any other relevant field)
        if 'main_page' in data and 'content' in data['main_page']:
            content = data['main_page']['content']  # Adjust this path based on your structure

            # If 'content' contains lists of strings, join them to form a text document
            if isinstance(content, dict) and 'lists' in content:
                for idx, content_list in enumerate(content['lists']):
                    # Combine the list of strings into one text document
                    full_text = " ".join(content_list).strip()

                    # Ensure that the content is unique and non-empty
                    if full_text and full_text not in unique_contents:
                        unique_contents.add(full_text)
                        doc = Document(page_content=full_text, metadata={"document_number": idx})
                        docs = text_splitter.split_documents([doc])
                        documents.extend(docs)
                    else:
                        tqdm.write(f"Duplicate or empty content in document {idx}.")
        else:
            raise ValueError("JSON file does not contain expected 'main_page' -> 'content' structure.")
        
        tqdm.write(f"Loaded and processed {len(documents)} chunks from {directory}.")
    
    except Exception as e:
        tqdm.write(f"Failed to process {directory}: {e}")

    return documents
# current_script_dir = os.path.dirname(os.path.abspath(__file__))
# base_dir = os.path.dirname(current_script_dir) # navigate to the parent directory
# pdf_directory = os.path.join(base_dir, 'pdfData') # navigate to the pdfData directory

# docs = load_pdfs(pdf_directory)
