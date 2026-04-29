# Compiler Design Plagiarism Detector 🚀

A robust, compiler-aware plagiarism detection application built with Flask. This tool goes beyond simple text comparison by utilizing lexical analysis (tokenization) and Abstract Syntax Tree (AST) metrics to detect structural similarities in source code, making it highly resilient to simple variable renaming or formatting changes. It also supports exact sequence matching and highlighting for PDF documents.

## ✨ Features

*   **Compiler-Aware Code Analysis**:
    *   **Lexical Analysis (Tokenizer)**: Breaks down source code into tokens, classifying them as keywords, identifiers, strings, etc.
    *   **Normalization**: Maps user-defined identifiers (variables, functions) to generic tags (`VAR`), removing bias from simple renaming attempts.
    *   **AST Summarization**: Analyzes code structure by counting functions, classes, loops, conditions, and imports to gauge structural similarity.
*   **Multi-Language Support**:
    *   Python (`.py`)
    *   C / C++ (`.c`, `.cpp`, `.h`, `.hpp`, etc.)
    *   Java (`.java`)
    *   JavaScript (`.js`, `.ts`)
*   **PDF Support**: 
    *   Extracts text and performs sequence matching to detect copied content.
    *   Generates downloadable **highlighted PDF reports** showing the exact plagiarized sections.
*   **Interactive Web Interface**:
    *   **Dashboard**: Overview of all submissions, flagged files, and average plagiarism percentage.
    *   **Upload Portal**: Simple form to upload student code/documents.
    *   **Visualization**: Stage-by-stage pipeline visualization (Raw Source -> Tokens -> AST Metrics).
    *   **Side-by-Side Diff**: Compare two submissions directly in the browser with highlighted differences.
    *   **Feedback System**: Leave feedback on flagged submissions.

## 🛠️ Technology Stack

*   **Backend**: Python, Flask
*   **Lexing & Parsing**: `tokenize`, `ast` (Python Stdlib), Regex (for C/C++/Java/JS)
*   **PDF Processing**: `PyMuPDF` (`fitz`)
*   **Comparison**: `difflib`, Cosine Similarity (Token frequency)
*   **Frontend**: HTML/CSS Templates, Jinja2

## 🚀 Getting Started

### Prerequisites

*   Python 3.8+
*   pip (Python package installer)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/AceAdi12/COMPILER-DESIGN.git
    cd COMPILER-DESIGN/PLAGIARISM/PLAGIARISM
    ```

2.  **Install dependencies**:
    ```bash
    pip install Flask PyMuPDF
    ```
    *(If you have a `requirements.txt`, run `pip install -r requirements.txt` instead)*

3.  **Run the application**:
    ```bash
    python app.py
    ```

4.  **Access the application**:
    Open your web browser and navigate to `http://127.0.0.1:5000`

## 🧠 How It Works (The Pipeline)

When a source code file is uploaded, it goes through a multi-stage pipeline:

1.  **Lexer (Tokenizer)**: The code is read and converted into a stream of tokens. Keywords specific to the language are identified.
2.  **Normalization**: User-defined names (variables, functions) are anonymized into generic tokens. Strings and numbers are also normalized. This prevents students from bypassing the checker by simply renaming variables.
3.  **AST Analysis**: Structural components (loops, conditionals, function definitions) are counted.
4.  **Similarity Calculation**: The normalized token frequencies are compared against existing submissions using vector math (Cosine Similarity) to determine a plagiarism percentage.

For **PDFs**, the text is extracted and compared using a strict sequence matcher to avoid false positives, and matching blocks are highlighted in a generated report.

## 📂 Project Structure

```
PLAGIARISM/
├── app.py                 # Main Flask application and logic
├── data/                  # Stores JSON data of submissions
│   └── submissions.json
├── uploads/               # Directory for uploaded student files
├── templates/             # HTML templates for the web interface
│   ├── dashboard.html
│   ├── upload.html
│   ├── visualize.html
│   ├── compare.html
│   └── feedback_form.html
└── static/                # Static assets (CSS, JS, Images)
```

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.
