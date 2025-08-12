from flask import Flask, render_template, request, send_file, url_for, jsonify
import asyncio
from playwright.async_api import async_playwright
import os
import subprocess
import uuid

app = Flask(__name__)

# Ensure Playwright browser is installed
def ensure_playwright_installed():
    try:
        from playwright.__main__ import main
    except ImportError:
        subprocess.run(["pip", "install", "playwright"])
    subprocess.run(["python", "-m", "playwright", "install", "chromium"])

ensure_playwright_installed()

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        uploaded_file = request.files.get("file")
        if uploaded_file and uploaded_file.filename.endswith(".html"):
            # Generate unique filename to avoid conflicts but keep original name structure
            unique_id = str(uuid.uuid4())
            original_name = uploaded_file.filename
            base_name = os.path.splitext(original_name)[0]  # Remove .html extension
            
            # Store with unique ID for internal use
            internal_filename = f"{unique_id}_{original_name}"
            html_path = os.path.join("uploads", internal_filename)
            os.makedirs("uploads", exist_ok=True)
            uploaded_file.save(html_path)
            
            return render_template("index.html", 
                                 filename=internal_filename,
                                 display_name=original_name,
                                 base_name=base_name,
                                 uploaded=True)

    return render_template("index.html", uploaded=False)

@app.route("/convert", methods=["POST"])
def convert_to_pdf():
    filename = request.form.get("filename")
    base_name = request.form.get("base_name")
    
    if not filename or not base_name:
        return jsonify({"error": "Missing filename or base name"}), 400
    
    html_path = os.path.join("uploads", filename)
    # Create PDF with clean name: myfile.html -> myfile.pdf
    pdf_filename = f"{base_name}.pdf"
    pdf_path = os.path.join("uploads", pdf_filename)
    
    if not os.path.exists(html_path):
        return jsonify({"error": "HTML file not found"}), 404
    
    try:
        print(f"Converting {html_path} to {pdf_path}")  # Debug log
        asyncio.run(html_to_pdf(html_path, pdf_path))
        
        # Verify PDF was created
        if not os.path.exists(pdf_path):
            return jsonify({"error": "PDF file was not created"}), 500
            
        print(f"PDF created successfully: {pdf_path}")  # Debug log
        return jsonify({"success": True, "pdf_filename": pdf_filename})
    except Exception as e:
        error_msg = f"Conversion failed: {str(e)}"
        print(error_msg)  # Debug log
        return jsonify({"error": error_msg}), 500

@app.route("/download/<filename>")
def download_pdf(filename):
    pdf_path = os.path.join("uploads", filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    return "File not found", 404

@app.route("/preview/<filename>")
def preview_html(filename):
    html_path = os.path.join("uploads", filename)
    if os.path.exists(html_path):
        return send_file(html_path)
    return "File not found", 404

async def html_to_pdf(html_file, pdf_file):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-web-security'
            ]
        )
        page = await browser.new_page()
        
        try:
            # Load the HTML file
            await page.goto(f"file:///{os.path.abspath(html_file)}")
            
            # Wait for page to load completely
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            # Get the actual content dimensions
            dimensions = await page.evaluate("""
                () => {
                    const body = document.body;
                    const html = document.documentElement;
                    
                    const width = Math.max(
                        body.scrollWidth, body.offsetWidth, 
                        html.clientWidth, html.scrollWidth, html.offsetWidth
                    );
                    const height = Math.max(
                        body.scrollHeight, body.offsetHeight, 
                        html.clientHeight, html.scrollHeight, html.offsetHeight
                    );
                    
                    return { width, height };
                }
            """)
            
            # Set viewport to match content
            await page.set_viewport_size({
                "width": dimensions["width"],
                "height": dimensions["height"]
            })
            
            # Generate PDF with exact dimensions - no page breaks
            await page.pdf(
                path=pdf_file,
                width=f"{dimensions['width']}px",
                height=f"{dimensions['height']}px",
                print_background=True,
                margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"},
                prefer_css_page_size=True
            )
            
        except Exception as e:
            print(f"PDF conversion error: {str(e)}")
            raise
        finally:
            await browser.close()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)