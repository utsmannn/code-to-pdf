#!/usr/bin/env python3
import fnmatch
import os
import shutil
from collections import defaultdict
from io import BytesIO
from typing import Union

from PyPDF2 import PdfWriter, PdfReader
from pygments import highlight, lexers
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import IniLexer
from pygments.util import ClassNotFound
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from xhtml2pdf import pisa


def code_to_pdf(input_file: str, output_pdf: str):
    with open(input_file, 'r') as file:
        try:
            code_lines = file.readlines()
        except UnicodeDecodeError:
            return

    numbered_code = ''.join(f"{str(i + 1).rjust(4)}: {line}" for i, line in enumerate(code_lines))
    filename = input_file.split('/')[-1]
    file_path_split = input_file.split('/')

    if len(file_path_split) > 1:
        file_location = input_file.replace(f'/{filename}', '/')
    else:
        file_location = '.'

    title_html = f'<h6 style="font-family: Menlo, monospace; font-size: 16px; color: #6e6e6e; margin-bottom: 0;"># {filename}</h6>'
    subtitle_html = f'<p style="font-family: Menlo, monospace; font-size: 14px; color: #6e6e6e; margin-top: 0;"># Location: {file_location}</p>'

    max_line_length = max(len(line) for line in code_lines)
    is_landscape = max_line_length > 140

    print(f'> Processing :{input_file}')

    css_style_landscape = """
        @page {
            size: A4 landscape;
            margin: 2cm;
        }
        h1 {
            font-family: Menlo, monospace;
            color: #6e6e6e;
        }
        """

    css_style_portrait = """
            @page {
                size: A4 portrait;
                margin: 2cm;
            }
            h1 {
                font-family: Menlo, monospace;
                color: #6e6e6e;
            }
            """

    css_style = css_style_landscape if is_landscape else css_style_portrait

    formatter = HtmlFormatter(full=True, style="colorful")
    try:
        lexer = lexers.get_lexer_for_filename(input_file)
    except ClassNotFound:
        lexer = IniLexer()

    highlighted_code = highlight(f'...\n\n{numbered_code}', lexer, formatter)

    full_content = f"<style>{css_style}</style>{title_html}{subtitle_html}{highlighted_code}"

    with open(output_pdf, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(full_content,  dest=result_file)

    if pisa_status.err:
        print(f"Error: {pisa_status.err}")


def load_ignore_patterns(ignore_file: str) -> list[str]:
    with open(ignore_file, 'r') as f:
        patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return patterns


def is_ignored(file_path: Union[str, os.PathLike], patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(os.path.basename(file_path), pattern):
            return True
        if os.path.commonpath([file_path, pattern]) == pattern.rstrip('/'):
            return True
    return False


def get_files_to_include(base_dir: Union[str, os.PathLike], ignore_file: str) -> list[str]:
    ignore_patterns = load_ignore_patterns(ignore_file)
    included_files = []
    for root, dirs, files in os.walk(base_dir):
        root_rel_path = os.path.relpath(root, base_dir)

        if is_ignored(root_rel_path, ignore_patterns):
            dirs[:] = []
            continue

        for file_name in files:
            file_path = os.path.relpath(os.path.join(root, file_name), base_dir)
            if not is_ignored(file_path, ignore_patterns):
                included_files.append(file_path)
    return included_files


base_directory = '.'
ignore_file = '.pdfignore'

files_to_include = get_files_to_include(base_directory, ignore_file)
for file in files_to_include:
    name = file.replace('/', '{divider}')
    output_page_path = 'output/page/'
    if not os.path.exists(output_page_path):
        os.makedirs(output_page_path)

    code_to_pdf(file, f'{output_page_path}{name}.pdf')

index_files = []


def build_tree(files_with_pages_in):
    tree = lambda: defaultdict(tree)
    root = tree()

    for path, page in files_with_pages_in:
        parts = path.split('{divider}')
        current = root
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = page

    return root


def create_tree_index_pdf(index_files_in, output_pdf):
    # Bangun tree dari index_files
    files_with_pages = [(entry.split(' .......................... ')[0], entry.split(' .......................... ')[1])
                        for entry in index_files_in]
    tree = build_tree(files_with_pages)

    # Konversi tree ke HTML
    def tree_to_html(d, indent=0):
        html = ""
        for key, value in sorted(d.items()):
            key_fix = key.replace('output/page/', '').replace('.pdf', '')
            if isinstance(value, dict):
                html += f'<div style="margin-left: {indent * 20}px;">{key_fix}/</div>'
                html += tree_to_html(value, indent + 1)
            else:
                html += f'<div style="margin-left: {indent * 20}px;">{key_fix} .......................... {value}</div>'
        return html

    tree_html = tree_to_html(tree)

    # Buat PDF dari tree HTML
    css_style = """
    body {
        font-family: Menlo, monospace;
        font-size: 12px;
        color: #6e6e6e;
    }
    """

    current_directory = os.getcwd()
    project_title = os.path.basename(current_directory)

    title_project_html = f"<h3 style='font-family: Menlo monospace; font-size: 28px; color: #6e6e6e;'>{project_title}</h3><br>"
    title_index_html = "<h5 style='font-family: Menlo monospace; font-size: 17px; color: #6e6e6e;'>Index of Files</h5>"

    title_html = title_project_html + title_index_html

    full_content = f"<style>{css_style}</style>{title_html}{tree_html}"

    with open(output_pdf, "w+b") as result_file:
        pisa_status = pisa.CreatePDF(full_content, dest=result_file)

    if pisa_status.err:
        print(f"Error: {pisa_status.err}")


def merge_pdfs_in_directory(directory: str, output_pdf: str, draw_number=True):
    pdf_writer = PdfWriter()

    current_page = 1

    for filename in sorted(os.listdir(directory)):
        if filename.endswith('.pdf'):
            filepath = os.path.join(directory, filename)
            pdf_reader = PdfReader(filepath)

            index_files.append(f'{filepath} .......................... {current_page}')

            for page in pdf_reader.pages:
                orientation = page.mediabox.width > page.mediabox.height
                if draw_number:
                    packet = BytesIO()
                    can = canvas.Canvas(packet, pagesize=(letter[1], letter[0]) if orientation else letter)
                    can.setFont("Helvetica", 10)

                    page_width = letter[1] if orientation else letter[0]
                    x_position = page_width / 2

                    can.drawString(x_position, 30, f"({current_page})")
                    can.save()

                    packet.seek(0)
                    new_pdf = PdfReader(packet)
                    page.merge_page(new_pdf.pages[0])

                pdf_writer.add_page(page)
                current_page += 1

    with open(output_pdf, 'wb') as output_file:
        pdf_writer.write(output_file)

    if draw_number:
        create_tree_index_pdf(index_files, 'output/index-file.pdf')

current_directory = os.getcwd()
project_title = os.path.basename(current_directory)

merge_pdfs_in_directory('output/page/', 'output/page.pdf', draw_number=True)
merge_pdfs_in_directory('output', f'{project_title}.pdf', draw_number=False)

shutil.rmtree('output', ignore_errors=True)

print(f"All done...")
