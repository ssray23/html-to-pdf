from flask import Flask, render_template, request, send_file, url_for, jsonify
import asyncio
from playwright.async_api import async_playwright
import os
import subprocess
import uuid
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- PLAYWRIGHT SETUP ---
def ensure_playwright_installed():
    """
    Ensures Playwright and its browser dependencies are installed.
    This is useful for initial setup or deployment.
    """
    try:
        from playwright.__main__ import main
        # Check if browsers are installed, if not, install them.
        # This is a simplified check. A more robust check might be needed for production.
        playwright_cache_paths = [
            os.path.expanduser('~/.cache/ms-playwright'),  # Linux/Mac
            os.path.expanduser('~/Library/Caches/ms-playwright'),  # Mac alternative
            os.path.expanduser('~/AppData/Local/ms-playwright')  # Windows
        ]
        
        if not any(os.path.exists(path) for path in playwright_cache_paths):
             print("Playwright browsers not found. Installing chromium...")
             subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
    except ImportError:
        print("Playwright not found. Installing...")
        subprocess.run(["pip", "install", "playwright"], check=True)
        print("Installing Playwright chromium browser...")
        subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)

# Only run the installation check if this is the main process (not Flask reloader)
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    ensure_playwright_installed()


# --- UTILITY FUNCTIONS ---
def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def download_webpage(url, output_path):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response.text)
        return True
    except Exception as e:
        print(f"Error downloading webpage: {str(e)}")
        return False

def create_clean_html_template(content, title="Document"):
    """Creates a clean, readable HTML template for the 'Clean Output' mode."""
    return f"""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>{title}</title>
    <style>body{{font-family: Helvetica, Arial, sans-serif;font-size: 18px; line-height: 1.6; color: #333;background: #fff; max-width: 650px; margin: 0 auto;padding: 30px;}}h1, h2, h3, h4, h5, h6{{margin: 1.5em 0 0.5em 0; font-weight: 600;}}h1{{font-size: 32px;}}h2{{font-size: 26px;}}p{{margin-bottom: 1em;}}img{{max-width: 100%; height: auto; margin: 2em 0; display: block;}}pre{{background: #f5f5f5; padding: 15px; border-radius: 5px; overflow-x: auto;}}</style>
    </head><body><h1>{title}</h1>{content}</body></html>
    """

# --- CORE PDF CONVERSION LOGIC ---
async def html_to_pdf_playwright(source, pdf_file):
    """
    Converts a given source (URL or file path) to a PDF using Playwright,
    creating an exact replica as a single-page PDF without modifying the visual appearance.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Navigate to the source
            if source.startswith('http://') or source.startswith('https://'):
                await page.goto(source, wait_until='networkidle', timeout=30000)
            else:
                await page.goto(f"file:///{os.path.abspath(source)}", wait_until='networkidle', timeout=30000)

            # Wait for page to fully load
            await page.wait_for_timeout(3000)

            # Get the actual visible content boundaries more precisely
            dimensions = await page.evaluate("""() => {
                // Force a layout recalculation
                document.body.offsetHeight;
                
                // Find all elements with actual content
                const allElements = document.querySelectorAll('*');
                let minLeft = Infinity;
                let maxRight = 0;
                let maxBottom = 0;
                let hasContent = false;
                
                for (let element of allElements) {
                    const rect = element.getBoundingClientRect();
                    const style = window.getComputedStyle(element);
                    
                    // Skip hidden, empty, or structural elements
                    if (style.display === 'none' || style.visibility === 'hidden' || 
                        rect.width === 0 || rect.height === 0) {
                        continue;
                    }
                    
                    // Skip elements that are likely containers without visual content
                    const tagName = element.tagName.toLowerCase();
                    if (['html', 'body'].includes(tagName) && element.children.length > 0) {
                        continue;
                    }
                    
                    // Check if element has actual content or visual styling
                    const hasText = element.textContent && element.textContent.trim().length > 0;
                    const hasBackground = style.backgroundColor !== 'rgba(0, 0, 0, 0)' && 
                                         style.backgroundColor !== 'transparent';
                    const hasBorder = style.borderWidth !== '0px';
                    const hasImage = tagName === 'img' || style.backgroundImage !== 'none';
                    
                    if (hasText || hasBackground || hasBorder || hasImage) {
                        minLeft = Math.min(minLeft, rect.left);
                        maxRight = Math.max(maxRight, rect.right);
                        maxBottom = Math.max(maxBottom, rect.bottom);
                        hasContent = true;
                    }
                }
                
                // If no content found, fallback to body dimensions
                if (!hasContent || minLeft === Infinity) {
                    const bodyRect = document.body.getBoundingClientRect();
                    return {
                        width: Math.max(bodyRect.width, 300),
                        height: Math.max(bodyRect.height, 400),
                        leftOffset: 0
                    };
                }
                
                // Calculate tight content boundaries
                const contentWidth = maxRight - minLeft;
                const contentHeight = maxBottom;
                
                return {
                    width: Math.max(contentWidth, 300),
                    height: Math.max(contentHeight, 400),
                    leftOffset: Math.max(0, minLeft)
                };
            }""")

            print(f"Content boundaries: width={dimensions['width']}px, height={dimensions['height']}px, leftOffset={dimensions.get('leftOffset', 0)}px")

            # Set viewport to exact content size to eliminate all whitespace
            await page.set_viewport_size({"width": int(dimensions['width']), "height": int(dimensions['height'])})

            # If there's a left offset, scroll to align content to the left edge
            if dimensions.get('leftOffset', 0) > 0:
                await page.evaluate(f"window.scrollTo({dimensions['leftOffset']}, 0)")
                print(f"Scrolled to eliminate left offset: {dimensions['leftOffset']}px")

            # Add print styles to ensure exact replica and prevent page breaks
            await page.add_style_tag(content='''
                @media print {
                    @page { 
                        size: auto;
                        margin: 0;
                    }
                    * { 
                        -webkit-print-color-adjust: exact !important;
                        color-adjust: exact !important;
                        print-color-adjust: exact !important;
                        page-break-after: avoid !important;
                        page-break-before: avoid !important;
                        page-break-inside: avoid !important;
                        break-after: avoid !important;
                        break-before: avoid !important;
                        break-inside: avoid !important;
                    }
                    body {
                        -webkit-print-color-adjust: exact !important;
                        color-adjust: exact !important;
                        print-color-adjust: exact !important;
                        margin: 0 !important;
                        padding: 0 !important;
                        width: fit-content !important;
                        max-width: none !important;
                    }
                    html {
                        margin: 0 !important;
                        padding: 0 !important;
                        width: fit-content !important;
                        max-width: none !important;
                    }
                }
            ''')

            # Calculate PDF dimensions to fit actual content exactly
            # Convert pixels to inches (assuming 96 DPI)
            width_inches = dimensions['width'] / 96
            height_inches = dimensions['height'] / 96
            
            print(f"PDF dimensions: {width_inches:.2f}\" x {height_inches:.2f}\"")

            # Generate PDF with exact viewport size (no extra whitespace possible)
            await page.pdf(
                path=pdf_file,
                width=f"{width_inches}in",
                height=f"{height_inches}in",
                print_background=True,
                margin={
                    "top": "0",
                    "right": "0", 
                    "bottom": "0",
                    "left": "0"
                },
                prefer_css_page_size=False,
                page_ranges="1"  # Ensure single page
            )
            
            print(f"Single-page exact replica PDF generated successfully")
            
        except Exception as e:
            print(f"Playwright PDF conversion error: {str(e)}")
            raise
        finally:
            await browser.close()

# --- FLASK ROUTES ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url_input = request.form.get("url", "").strip()
        uploaded_file = request.files.get("file")
        unique_id = str(uuid.uuid4())
        os.makedirs("uploads", exist_ok=True)

        if url_input and is_valid_url(url_input):
            domain = urlparse(url_input).netloc.replace("www.", "")
            filename = f"{domain}_{unique_id}.html"
            html_path = os.path.join("uploads", filename)
            if download_webpage(url_input, html_path):
                return render_template("index.html", filename=filename, display_name=f"{domain}.html", base_name=domain, uploaded=True, is_url=True, original_url=url_input)
            else:
                return render_template("index.html", error="Failed to download webpage.", uploaded=False)
        
        elif uploaded_file and uploaded_file.filename.endswith(('.html', '.htm')):
            original_name = uploaded_file.filename
            base_name = os.path.splitext(original_name)[0]
            internal_filename = f"{unique_id}_{original_name}"
            html_path = os.path.join("uploads", internal_filename)
            uploaded_file.save(html_path)
            return render_template("index.html", filename=internal_filename, display_name=original_name, base_name=base_name, uploaded=True, is_url=False)
        else:
            return render_template("index.html", error="Please provide a valid URL or upload an HTML file.", uploaded=False)

    return render_template("index.html", uploaded=False)

@app.route("/convert", methods=["POST"])
def convert_to_pdf():
    filename = request.form.get("filename")
    base_name = request.form.get("base_name")
    clean_output = request.form.get("clean_output") == "true"
    is_url = request.form.get("is_url") == "true"
    original_url = request.form.get("original_url")
    
    html_path = os.path.join("uploads", filename)
    pdf_filename = f"{base_name}.pdf"
    pdf_path = os.path.join("uploads", pdf_filename)
    
    if not os.path.exists(html_path):
        return jsonify({"error": "Source HTML file not found on server."}), 404
    
    try:
        source_for_pdf = html_path
        temp_clean_file = None

        if clean_output:
            # Create a temporary cleaned HTML file to feed to Playwright
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            
            main_content = soup.select_one('article, [role="main"], .post-content, .entry-content') or soup.body
            if main_content:
                for tag in main_content.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    tag.decompose()
                content_html = main_content.decode_contents()
                title = soup.title.string if soup.title else base_name
                clean_html = create_clean_html_template(content_html, title)
                
                temp_clean_file = html_path.replace('.html', '_clean.html')
                with open(temp_clean_file, 'w', encoding='utf-8') as f:
                    f.write(clean_html)
                source_for_pdf = temp_clean_file
            else:
                 return jsonify({"error": "Could not find any content to clean."}), 500
        elif is_url:
            source_for_pdf = original_url # Use the original URL for a perfect replica

        # Run the Playwright conversion
        asyncio.run(html_to_pdf_playwright(source_for_pdf, pdf_path))

        # Clean up temporary file if it was created
        if temp_clean_file and os.path.exists(temp_clean_file):
            os.remove(temp_clean_file)

        if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
            raise Exception("PDF generation failed or resulted in an empty file.")
            
        return jsonify({"success": True, "pdf_filename": pdf_filename})
    
    except Exception as e:
        error_msg = f"Conversion failed: {str(e)}"
        print(error_msg)
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)