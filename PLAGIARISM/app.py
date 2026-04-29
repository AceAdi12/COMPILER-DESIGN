from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os
import json
import io
import ast
import token
import tokenize
import difflib
import keyword
import re
import math
from collections import Counter
import fitz  # PyMuPDF

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
DATA_FILE = 'data/submissions.json'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)

PYTHON_KEYWORDS = set(keyword.kwlist)

# Keywords for C / C++ / Java / JavaScript
C_CPP_KEYWORDS = {
    'auto','break','case','char','const','continue','default','do','double',
    'else','enum','extern','float','for','goto','if','inline','int','long',
    'register','restrict','return','short','signed','sizeof','static','struct',
    'switch','typedef','union','unsigned','void','volatile','while',
    # C++ extras
    'alignas','alignof','and','and_eq','asm','bitand','bitor','bool','catch',
    'class','compl','concept','consteval','constexpr','constinit','co_await',
    'co_return','co_yield','decltype','delete','explicit','export','false',
    'friend','mutable','namespace','new','noexcept','not','not_eq','nullptr',
    'operator','or','or_eq','private','protected','public','reinterpret_cast',
    'requires','static_assert','static_cast','template','this','throw','true',
    'try','typeid','typename','using','virtual','wchar_t','xor','xor_eq',
    'override','final','import','module',
}

JAVA_KEYWORDS = {
    'abstract','assert','boolean','break','byte','case','catch','char','class',
    'const','continue','default','do','double','else','enum','extends','final',
    'finally','float','for','goto','if','implements','import','instanceof','int',
    'interface','long','native','new','package','private','protected','public',
    'return','short','static','strictfp','super','switch','synchronized','this',
    'throw','throws','transient','try','void','volatile','while','var','record',
    'sealed','permits','yield','true','false','null',
}

JS_KEYWORDS = {
    'abstract','arguments','await','boolean','break','byte','case','catch',
    'char','class','const','continue','debugger','default','delete','do',
    'double','else','enum','eval','export','extends','false','final','finally',
    'float','for','function','goto','if','implements','import','in','instanceof',
    'int','interface','let','long','native','new','null','of','package','private',
    'protected','public','return','short','static','super','switch','synchronized',
    'this','throw','throws','transient','true','try','typeof','undefined','var',
    'void','volatile','while','with','yield',
}

# Regex-based generic tokenizer for C/C++/Java/JS
# Order matters: longer/more specific patterns first
_GENERIC_TOKEN_RE = re.compile(
    r'(?P<COMMENT_ML>/\*.*?\*/)|'           # /* ... */
    r'(?P<COMMENT_SL>//[^\n]*)|'             # // ...
    r'(?P<STRING>"(?:[^"\\]|\\.)*"|'        # "..."
    r"'(?:[^'\\]|\\.)*')|"                  # '...'
    r'(?P<NUMBER>\b0[xX][0-9a-fA-F]+\b|'    # hex
    r'\b\d+\.\d*(?:[eE][+-]?\d+)?\b|'      # float
    r'\b\d+\b)|'                             # int
    r'(?P<IDENT>[a-zA-Z_][a-zA-Z_0-9]*)|'   # identifier
    r'(?P<OP>[{}()\[\];,.<>!&|^~+\-*/%=?:]+)|'  # operators/punct
    r'(?P<WS>\s+)',                           # whitespace (skip)
    re.DOTALL
)


def _get_lang(filename: str) -> str:
    """Return a language tag from file extension."""
    ext = os.path.splitext(filename)[-1].lower()
    return {
        '.py': 'python',
        '.c':  'c',
        '.h':  'c',
        '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp',
        '.java': 'java',
        '.js':  'js', '.ts': 'js',
        '.pdf': 'pdf',
    }.get(ext, 'generic')


def _keywords_for_lang(lang: str) -> set:
    if lang == 'python':
        return PYTHON_KEYWORDS
    if lang in ('c', 'cpp'):
        return C_CPP_KEYWORDS
    if lang == 'java':
        return JAVA_KEYWORDS
    if lang == 'js':
        return JS_KEYWORDS
    return set()

# ─────────────────────────────────────────────
#  DATA HELPERS
# ─────────────────────────────────────────────

def load_submissions():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_submissions(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)


# ─────────────────────────────────────────────
#  COMPILER PIPELINE  (Lexer → Normalize → LCS)
# ─────────────────────────────────────────────

def tokenize_source(source: str, lang: str = 'python'):
    """
    Stage 1 — Lexer / Tokenizer
    Routes to Python stdlib tokenizer for .py files,
    and a regex-based tokenizer for C/C++/Java/JS.
    Returns a list of dicts: {type, value, line, col}
    """
    if lang == 'python':
        return _tokenize_python(source)
    return _tokenize_generic(source, lang)


def _tokenize_python(source: str):
    tokens = []
    try:
        reader = io.StringIO(source).readline
        for tok in tokenize.generate_tokens(reader):
            if tok.type in (
                tokenize.NEWLINE, tokenize.NL,
                tokenize.COMMENT, tokenize.ENCODING,
                tokenize.ENDMARKER
            ):
                continue
            tokens.append({
                "type": token.tok_name.get(tok.type, "UNKNOWN"),
                "value": tok.string,
                "line": tok.start[0],
                "col": tok.start[1],
            })
    except tokenize.TokenError:
        pass
    return tokens


def _tokenize_generic(source: str, lang: str):
    """Regex-based tokenizer for C, C++, Java, JavaScript."""
    kw = _keywords_for_lang(lang)
    tokens = []
    line_num = 1
    for m in _GENERIC_TOKEN_RE.finditer(source):
        kind = m.lastgroup
        val  = m.group()
        if kind in ('COMMENT_ML', 'COMMENT_SL', 'WS'):
            line_num += val.count('\n')
            continue          # skip comments & whitespace
        if kind == 'IDENT':
            if lang == 'pdf':
                tok_type = 'TEXT_WORD'
                val = val.lower()
            else:
                tok_type = 'KEYWORD' if val in kw else 'NAME'
        elif kind == 'NUMBER':
            tok_type = 'NUMBER'
        elif kind == 'STRING':
            tok_type = 'STRING'
        elif kind == 'OP':
            tok_type = 'OP'
        else:
            tok_type = 'UNKNOWN'
        tokens.append({
            "type": tok_type,
            "value": val,
            "line": line_num,
            "col": m.start() - source.rfind('\n', 0, m.start()),
        })
        line_num += val.count('\n')
    return tokens


def normalize_tokens(raw_tokens):
    """
    Stage 2 — Normalization
    Maps user-defined identifiers → VAR, strings → STR, numbers → NUM.
    Works for Python, C, C++, Java, JS — keywords are already tagged
    as KEYWORD by the respective tokenizer, so we only abstract NAMEs.
    """
    normalized = []
    for t in raw_tokens:
        typ, val = t["type"], t["value"]
        if typ == "NAME":           # user-defined identifier (any language)
            normalized.append("VAR")
        elif typ == "STRING":
            normalized.append("STR")
        elif typ == "NUMBER":
            normalized.append("NUM")
        elif typ in ("INDENT", "DEDENT"):
            continue
        else:
            normalized.append(val)
    return normalized


def get_ast_summary(source: str):
    """
    Stage 3 — AST Analysis
    Counts structural elements: functions, classes, loops, conditions.
    """
    summary = {
        "functions": 0,
        "classes": 0,
        "loops": 0,
        "conditions": 0,
        "imports": 0,
        "total_nodes": 0,
    }
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            summary["total_nodes"] += 1
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                summary["functions"] += 1
            elif isinstance(node, ast.ClassDef):
                summary["classes"] += 1
            elif isinstance(node, (ast.For, ast.While)):
                summary["loops"] += 1
            elif isinstance(node, ast.If):
                summary["conditions"] += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                summary["imports"] += 1
    except SyntaxError:
        pass
    return summary


def get_c_cpp_ast_summary(source: str):
    """ Regex-based pseudo-AST summary for C/C++ metrics """
    summary = {
        "functions": 0, "classes": 0, "loops": 0,
        "conditions": 0, "imports": 0, "total_nodes": 0
    }
    summary["functions"] = len(re.findall(r'\b\w+(?:<[^>]*>)?\s+\w+\s*\([^)]*\)\s*\{', source)) + len(re.findall(r'\bint\s+main\s*\(', source))
    summary["classes"] = len(re.findall(r'\b(?:class|struct)\s+\w+', source))
    summary["loops"] = len(re.findall(r'\b(?:for|while)\s*\(|\bdo\s*\{', source))
    summary["conditions"] = len(re.findall(r'\b(?:if|switch)\s*\(', source))
    summary["imports"] = len(re.findall(r'#include\s*[<"][^>"]+[>"]', source))
    
    # Heuristic for total nodes
    summary["total_nodes"] = (summary["functions"] * 15 + summary["classes"] * 20 + 
                              summary["loops"] * 10 + summary["conditions"] * 5 + 
                              summary["imports"] * 2 + len(source.split()) // 2)
    return summary


def token_frequency(raw_tokens):
    """Returns frequency dict of token types for charts."""
    freq = {}
    for t in raw_tokens:
        typ = t["type"]
        freq[typ] = freq.get(typ, 0) + 1
    return freq


def compute_similarity(source1: str, source2: str,
                        lang1: str = 'python', lang2: str = 'python'):
    """
    Full compiler-aware plagiarism check for code, and exact sequence matching for PDFs.
    """
    if lang1 == 'pdf' or lang2 == 'pdf':
        matcher = difflib.SequenceMatcher(None, source1, source2, autojunk=False)
        match_len = sum(m.size for m in matcher.get_matching_blocks() if m.size > 20)
        min_len = min(len(source1), len(source2))
        if min_len == 0:
            return 0
        return int((match_len / min_len) * 100)

    tokens1 = normalize_tokens(tokenize_source(source1, lang1))
    tokens2 = normalize_tokens(tokenize_source(source2, lang2))

    if not tokens1 or not tokens2:
        return 0

    freq1 = Counter(tokens1)
    freq2 = Counter(tokens2)
    
    intersection = set(freq1.keys()) & set(freq2.keys())
    dot_product = sum(freq1[x] * freq2[x] for x in intersection)
    
    mag1 = math.sqrt(sum(freq1[x]**2 for x in freq1.keys()))
    mag2 = math.sqrt(sum(freq2[x]**2 for x in freq2.keys()))
    
    if mag1 * mag2 == 0:
        return 0
        
    ratio = dot_product / (mag1 * mag2)
    return int(ratio * 100)


def extract_text_from_pdf(filepath: str) -> str:
    try:
        doc = fitz.open(filepath)
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""


def read_file_source(filepath: str) -> str:
    if filepath.lower().endswith('.pdf'):
        return extract_text_from_pdf(filepath)
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def compare_files(file1: str, file2: str) -> int:
    src1 = read_file_source(file1)
    src2 = read_file_source(file2)
    if not src1 or not src2:
        return 0
    lang1 = _get_lang(file1)
    lang2 = _get_lang(file2)
    return compute_similarity(src1, src2, lang1, lang2)


def generate_highlighted_pdf(student_filepath: str, match_filepath: str, output_path: str):
    try:
        doc = fitz.open(student_filepath)
        student_text = read_file_source(student_filepath)
        match_text = read_file_source(match_filepath)
        
        matcher = difflib.SequenceMatcher(None, student_text, match_text, autojunk=False)
        matches = matcher.get_matching_blocks()
        
        for match in matches:
            if match.size > 30: 
                match_str = student_text[match.a:match.a + match.size]
                # Use a set to avoid searching for the exact same line multiple times
                lines = set(line.strip() for line in match_str.split('\n') if len(line.strip()) > 30)
                for page in doc:
                    for line in lines:
                        text_instances = page.search_for(line)
                        for inst in text_instances:
                            try:
                                highlight = page.add_highlight_annot(inst)
                                highlight.update()
                            except Exception:
                                pass
        
        doc.save(output_path)
        doc.close()
    except Exception as e:
        print(f"Error highlighting PDF: {e}")


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.route('/')
def dashboard():
    submissions = load_submissions()
    total = len(submissions)
    flagged = sum(1 for s in submissions if s.get("plagiarism_percent", 0) > 70)
    avg = (
        int(sum(s.get("plagiarism_percent", 0) for s in submissions) / total)
        if total else 0
    )
    stats = {"total": total, "flagged": flagged, "avg": avg}
    return render_template('dashboard.html', submissions=submissions, stats=stats)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        student_id = request.form.get('student_id', '').strip()
        file = request.files.get('code_file')

        if file and student_name and student_id:
            filename = f"{student_id}_{file.filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            submissions = load_submissions()
            highest_match = 0
            matched_student = "None"

            for sub in submissions:
                existing_filename = f"{sub['student_id']}_{sub.get('filename', '')}"
                existing_path = os.path.join(app.config['UPLOAD_FOLDER'], existing_filename)
                if os.path.exists(existing_path):
                    pct = compare_files(filepath, existing_path)
                    if pct > highest_match:
                        highest_match = pct
                        matched_student = sub['student_name']

            submissions.append({
                "student_name": student_name,
                "student_id": student_id,
                "filename": file.filename,
                "plagiarism_percent": highest_match,
                "match_found": matched_student,
                "feedback": "",
            })
            save_submissions(submissions)
            return redirect(url_for('dashboard'))

    return render_template('upload.html')


@app.route('/feedback_form/<student_id>', methods=['GET', 'POST'])
def feedback_form(student_id):
    submissions = load_submissions()
    submission = next((s for s in submissions if s['student_id'] == student_id), None)

    if request.method == 'POST':
        feedback = request.form.get('feedback', '')
        for entry in submissions:
            if entry['student_id'] == student_id:
                entry['feedback'] = feedback
                break
        save_submissions(submissions)
        return redirect(url_for('dashboard'))

    return render_template('feedback_form.html', student_id=student_id, submission=submission)


@app.route('/visualize/<student_id>')
def visualize(student_id):
    """Stage-by-stage compiler pipeline visualization for a submission."""
    submissions = load_submissions()
    submission = next((s for s in submissions if s['student_id'] == student_id), None)
    if not submission:
        return redirect(url_for('dashboard'))

    filepath = os.path.join(
        app.config['UPLOAD_FOLDER'],
        f"{submission['student_id']}_{submission.get('filename', '')}"
    )
    source = read_file_source(filepath) if os.path.exists(filepath) else "// File not found"
    lang = _get_lang(submission.get('filename', ''))

    raw_tokens = tokenize_source(source, lang)
    normalized = normalize_tokens(raw_tokens)
    
    if lang == 'python':
        ast_summary = get_ast_summary(source)
    elif lang in ('c', 'cpp'):
        ast_summary = get_c_cpp_ast_summary(source)
    else:
        ast_summary = {
            "functions": 0, "classes": 0, "loops": 0,
            "conditions": 0, "imports": 0, "total_nodes": 0
        }

    freq = token_frequency(raw_tokens)

    return render_template(
        'visualize.html',
        submission=submission,
        source=source,
        raw_tokens=raw_tokens,
        normalized_tokens=normalized,
        ast_summary=ast_summary,
        token_freq=freq,
        lang=lang,
    )


@app.route('/compare/<id1>/<id2>')
def compare(id1, id2):
    """Side-by-side token diff between two submissions."""
    submissions = load_submissions()
    sub1 = next((s for s in submissions if s['student_id'] == id1), None)
    sub2 = next((s for s in submissions if s['student_id'] == id2), None)

    if not sub1 or not sub2:
        return redirect(url_for('dashboard'))

    def load_data(sub):
        fp = os.path.join(app.config['UPLOAD_FOLDER'],
                          f"{sub['student_id']}_{sub.get('filename', '')}")
        src  = read_file_source(fp) if os.path.exists(fp) else ""
        lang = _get_lang(sub.get('filename', ''))
        raw  = tokenize_source(src, lang)
        norm = normalize_tokens(raw)
        return src, raw, norm, lang

    src1, raw1, norm1, lang1 = load_data(sub1)
    src2, raw2, norm2, lang2 = load_data(sub2)

    # Diff lines for side-by-side view
    lines1 = src1.splitlines()
    lines2 = src2.splitlines()
    differ = difflib.HtmlDiff(wrapcolumn=80)
    diff_table = differ.make_table(lines1, lines2,
                                   fromdesc=sub1['student_name'],
                                   todesc=sub2['student_name'],
                                   context=True, numlines=3)

    similarity = compute_similarity(src1, src2, lang1, lang2)

    return render_template(
        'compare.html',
        sub1=sub1, sub2=sub2,
        src1=src1, src2=src2,
        norm1=norm1, norm2=norm2,
        diff_table=diff_table,
        similarity=similarity,
    )


@app.route('/report/<student_id>')
def download_report(student_id):
    submissions = load_submissions()
    submission = next((s for s in submissions if s['student_id'] == student_id), None)
    if not submission or not submission.get("match_found") or submission["match_found"] == "None":
        return redirect(url_for('dashboard'))
        
    match_student = next((s for s in submissions if s['student_name'] == submission['match_found']), None)
    if not match_student:
        return redirect(url_for('dashboard'))
        
    student_filename = f"{submission['student_id']}_{submission.get('filename', '')}"
    student_filepath = os.path.join(app.config['UPLOAD_FOLDER'], student_filename)
    
    match_filename = f"{match_student['student_id']}_{match_student.get('filename', '')}"
    match_filepath = os.path.join(app.config['UPLOAD_FOLDER'], match_filename)
    
    if not os.path.exists(student_filepath) or not os.path.exists(match_filepath):
        return redirect(url_for('dashboard'))
        
    if not student_filepath.lower().endswith('.pdf'):
        return "Report generation is currently supported for PDF submissions only.", 400
        
    report_filename = f"report_{student_filename}"
    report_filepath = os.path.join(app.config['UPLOAD_FOLDER'], report_filename)
    
    generate_highlighted_pdf(student_filepath, match_filepath, report_filepath)
    
    if os.path.exists(report_filepath):
        return send_file(report_filepath, as_attachment=True, download_name=f"Plagiarism_Report_{submission['student_name']}.pdf")
    return "Error generating report.", 500


@app.route('/api/stats')
def api_stats():
    submissions = load_submissions()
    buckets = {"low": 0, "medium": 0, "high": 0}
    for s in submissions:
        p = s.get("plagiarism_percent", 0)
        if p > 70:
            buckets["high"] += 1
        elif p > 40:
            buckets["medium"] += 1
        else:
            buckets["low"] += 1
    return jsonify({"buckets": buckets, "submissions": submissions})


if __name__ == '__main__':
    print("Compiler Design Plagiarism Detector -- starting on http://127.0.0.1:5000")
    app.run(debug=True)
