from flask import Flask, render_template, request, send_file, url_for, jsonify
import asyncio
from playwright.async_api import async_playwright
import os
import subprocess
import uuid
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

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
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none'
                  }
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
# async def html_to_pdf_playwright(source, pdf_file):
#     """
#     Converts a given source (URL or file path) to a PDF using Playwright,
#     creating an exact replica as a single-page PDF without modifying the visual appearance.
#     """
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=True)
#         page = await browser.new_page()
        
#         try:
#             # Navigate to the source
#             if source.startswith('http://') or source.startswith('https://'):
#                 await page.goto(source, wait_until='networkidle', timeout=30000)
#             else:
#                 await page.goto(f"file:///{os.path.abspath(source)}", wait_until='networkidle', timeout=30000)

#             # Wait for page to fully load
#             await page.wait_for_timeout(3000)

#             # Get the actual visible content boundaries more precisely
#             dimensions = await page.evaluate("""() => {
#                 // Force a layout recalculation
#                 document.body.offsetHeight;
                
#                 // Find all elements with actual content
#                 const allElements = document.querySelectorAll('*');
#                 let minLeft = Infinity;
#                 let maxRight = 0;
#                 let maxBottom = 0;
#                 let hasContent = false;
                
#                 for (let element of allElements) {
#                     const rect = element.getBoundingClientRect();
#                     const style = window.getComputedStyle(element);
                    
#                     // Skip hidden, empty, or structural elements
#                     if (style.display === 'none' || style.visibility === 'hidden' || 
#                         rect.width === 0 || rect.height === 0) {
#                         continue;
#                     }
                    
#                     // Skip elements that are likely containers without visual content
#                     const tagName = element.tagName.toLowerCase();
#                     if (['html', 'body'].includes(tagName) && element.children.length > 0) {
#                         continue;
#                     }
                    
#                     // Check if element has actual content or visual styling
#                     const hasText = element.textContent && element.textContent.trim().length > 0;
#                     const hasBackground = style.backgroundColor !== 'rgba(0, 0, 0, 0)' && 
#                                          style.backgroundColor !== 'transparent';
#                     const hasBorder = style.borderWidth !== '0px';
#                     const hasImage = tagName === 'img' || style.backgroundImage !== 'none';
                    
#                     if (hasText || hasBackground || hasBorder || hasImage) {
#                         minLeft = Math.min(minLeft, rect.left);
#                         maxRight = Math.max(maxRight, rect.right);
#                         maxBottom = Math.max(maxBottom, rect.bottom);
#                         hasContent = true;
#                     }
#                 }
                
#                 // If no content found, fallback to body dimensions
#                 if (!hasContent || minLeft === Infinity) {
#                     const bodyRect = document.body.getBoundingClientRect();
#                     return {
#                         width: Math.max(bodyRect.width, 300),
#                         height: Math.max(bodyRect.height, 400),
#                         leftOffset: 0
#                     };
#                 }
                
#                 // Calculate tight content boundaries
#                 const contentWidth = maxRight - minLeft;
#                 const contentHeight = maxBottom;
                
#                 return {
#                     width: Math.max(contentWidth, 300),
#                     height: Math.max(contentHeight, 400),
#                     leftOffset: Math.max(0, minLeft)
#                 };
#             }""")

#             print(f"Content boundaries: width={dimensions['width']}px, height={dimensions['height']}px, leftOffset={dimensions.get('leftOffset', 0)}px")

#             # Set viewport to exact content size to eliminate all whitespace
#             await page.set_viewport_size({"width": int(dimensions['width']), "height": int(dimensions['height'])})

#             # If there's a left offset, scroll to align content to the left edge
#             if dimensions.get('leftOffset', 0) > 0:
#                 await page.evaluate(f"window.scrollTo({dimensions['leftOffset']}, 0)")
#                 print(f"Scrolled to eliminate left offset: {dimensions['leftOffset']}px")

#             # Add print styles to ensure exact replica and prevent page breaks
#             await page.add_style_tag(content='''
#                 @media print {
#                     @page { 
#                         size: auto;
#                         margin: 0;
#                     }
#                     * { 
#                         -webkit-print-color-adjust: exact !important;
#                         color-adjust: exact !important;
#                         print-color-adjust: exact !important;
#                         page-break-after: avoid !important;
#                         page-break-before: avoid !important;
#                         page-break-inside: avoid !important;
#                         break-after: avoid !important;
#                         break-before: avoid !important;
#                         break-inside: avoid !important;
#                     }
#                     body {
#                         -webkit-print-color-adjust: exact !important;
#                         color-adjust: exact !important;
#                         print-color-adjust: exact !important;
#                         margin: 0 !important;
#                         padding: 0 !important;
#                         width: fit-content !important;
#                         max-width: none !important;
#                     }
#                     html {
#                         margin: 0 !important;
#                         padding: 0 !important;
#                         width: fit-content !important;
#                         max-width: none !important;
#                     }
#                 }
#             ''')

#             # Calculate PDF dimensions to fit actual content exactly
#             # Convert pixels to inches (assuming 96 DPI)
#             width_inches = dimensions['width'] / 96
#             height_inches = dimensions['height'] / 96
            
#             print(f"PDF dimensions: {width_inches:.2f}\" x {height_inches:.2f}\"")

#             # Generate PDF with exact viewport size (no extra whitespace possible)
#             await page.pdf(
#                 path=pdf_file,
#                 width=f"{width_inches}in",
#                 height=f"{height_inches}in",
#                 print_background=True,
#                 margin={
#                     "top": "0",
#                     "right": "0", 
#                     "bottom": "0",
#                     "left": "0"
#                 },
#                 prefer_css_page_size=False,
#                 page_ranges="1"  # Ensure single page
#             )
            
#             print(f"Single-page exact replica PDF generated successfully")
            
#         except Exception as e:
#             print(f"Playwright PDF conversion error: {str(e)}")
#             raise
#         finally:
#             await browser.close()

#################################################################################

async def html_to_pdf_exact_replica(source, pdf_file, margin_inches=0.3):
    """
    Creates a single-page PDF with exact 0.3" margins by wrapping content in a positioned container.
    Uses a different approach: create a wrapper div with exact positioning.
    
    Args:
        source: URL or file path to convert
        pdf_file: Output PDF file path
        margin_inches: Margin in inches from edge of page (default: 0.3)
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
            await page.wait_for_function("document.fonts.ready")

            # STEP 1: Get the ORIGINAL content dimensions
            original_dimensions = await page.evaluate("""() => {
                const body = document.body;
                const bodyRect = body.getBoundingClientRect();
                const scrollWidth = body.scrollWidth;
                const scrollHeight = body.scrollHeight;
                const offsetWidth = body.offsetWidth;
                const offsetHeight = body.offsetHeight;
                
                console.log('Body measurements:', {
                    rect: bodyRect.width + 'x' + bodyRect.height,
                    scroll: scrollWidth + 'x' + scrollHeight,
                    offset: offsetWidth + 'x' + offsetHeight
                });
                
                const naturalWidth = Math.max(bodyRect.width, offsetWidth);
                const naturalHeight = Math.max(bodyRect.height, offsetHeight, scrollHeight);
                
                return {
                    width: Math.ceil(naturalWidth),
                    height: Math.ceil(naturalHeight)
                };
            }""")

            print(f"ORIGINAL HTML content: {original_dimensions['width']}px x {original_dimensions['height']}px")

            # STEP 2: Wrap content in a positioned container with exact margins
            await page.evaluate(f"""() => {{
                // Create wrapper div with exact margin positioning
                const wrapper = document.createElement('div');
                wrapper.style.cssText = `
                    position: absolute;
                    top: {margin_inches * 72}pt;
                    left: {margin_inches * 72}pt;
                    width: {original_dimensions['width']}px;
                    height: auto;
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                `;
                
                // Move all body content into wrapper
                while (document.body.firstChild) {{
                    wrapper.appendChild(document.body.firstChild);
                }}
                
                // Clear body and add wrapper
                document.body.innerHTML = '';
                document.body.appendChild(wrapper);
                
                // Reset body completely
                document.body.style.cssText = `
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                    position: relative;
                    overflow: visible;
                `;
                
                console.log('Content wrapped with exact positioning');
            }}""")

            # STEP 3: Calculate PDF dimensions using POINTS (more precise for PDF)
            margin_points = margin_inches * 72  # 72 points per inch
            content_width_points = original_dimensions['width'] * 72 / 96  # Convert px to points
            content_height_points = original_dimensions['height'] * 72 / 96
            
            pdf_width_points = content_width_points + (2 * margin_points)
            pdf_height_points = content_height_points + (2 * margin_points)
            
            pdf_width_inches = pdf_width_points / 72
            pdf_height_inches = pdf_height_points / 72
            
            print(f"=== PRECISE POINT CALCULATIONS ===")
            print(f"Content: {original_dimensions['width']}px x {original_dimensions['height']}px")
            print(f"Content in points: {content_width_points:.1f}pt x {content_height_points:.1f}pt")
            print(f"Margin: {margin_inches}\" = {margin_points}pt")
            print(f"PDF: {pdf_width_points:.1f}pt x {pdf_height_points:.1f}pt")
            print(f"PDF: {pdf_width_inches:.3f}\" x {pdf_height_inches:.3f}\"")
            print(f"Wrapper positioned at: {margin_points}pt from top/left")
            print("=================================")

            # STEP 4: Set viewport to accommodate the wrapper
            await page.set_viewport_size({
                "width": int(pdf_width_points * 96 / 72),  # Convert back to pixels for viewport
                "height": max(800, int(pdf_height_points * 96 / 72))
            })

            await page.wait_for_timeout(1000)

            # STEP 5: Apply minimal print styles - just prevent page breaks
            await page.add_style_tag(content=f'''
                @media print {{
                    @page {{ 
                        size: {pdf_width_inches:.6f}in {pdf_height_inches:.6f}in !important;
                        margin: 0 !important;
                    }}
                    
                    html, body {{
                        margin: 0 !important;
                        padding: 0 !important;
                        -webkit-print-color-adjust: exact !important;
                        color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }}
                    
                    /* Prevent page breaks */
                    * {{
                        page-break-inside: avoid !important;
                        break-inside: avoid !important;
                        page-break-after: avoid !important;
                        break-after: avoid !important;
                        page-break-before: avoid !important;
                        break-before: avoid !important;
                        -webkit-print-color-adjust: exact !important;
                        color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }}
                }}
            ''')

            await page.wait_for_timeout(1000)

            # STEP 6: Generate PDF with ZERO margins (wrapper handles positioning)
            await page.pdf(
                path=pdf_file,
                width=f"{pdf_width_inches:.6f}in",
                height=f"{pdf_height_inches:.6f}in",
                print_background=True,
                margin={"top": "0in", "right": "0in", "bottom": "0in", "left": "0in"},
                prefer_css_page_size=False,
                display_header_footer=False,
                page_ranges="1",
                scale=1.0,
                format=None
            )
            
            # Verify the PDF was created
            if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
                print(f"✓ WRAPPER-BASED PDF generated successfully!")
                print(f"✓ PDF dimensions: {pdf_width_inches:.3f}\" x {pdf_height_inches:.3f}\"")
                print(f"✓ Content wrapped and positioned with exact {margin_inches}\" margins")
                print(f"✓ Wrapper approach eliminates Playwright margin inconsistencies")
            else:
                raise Exception("PDF file was not created or is empty")
            
        except Exception as e:
            print(f"Error during conversion: {str(e)}")
            raise
        finally:
            await browser.close()


# Flask route remains the same
@app.route("/convert", methods=["POST"])
def convert_to_pdf():
    """
    Flask route to convert HTML files to PDF with exact visual replica.
    Uses wrapper div approach for precise margin control.
    """
    try:
        filename = request.form.get("filename")
        base_name = request.form.get("base_name")
        is_url_derived = request.form.get("is_url") == "true"
        
        if not filename or not base_name:
            return jsonify({"error": "Missing filename or base_name parameter."}), 400
        
        html_path = os.path.join("uploads", filename)
        pdf_filename = f"{base_name}.pdf"
        pdf_path = os.path.join("uploads", pdf_filename)
        
        if not os.path.exists(html_path):
            return jsonify({"error": f"Source HTML file not found: {filename}"}), 404
        
        print(f"Starting WRAPPER-BASED conversion: {filename} -> {pdf_filename}")
        print("Approach: Wrap content in positioned div for exact margin control")
        
        # Run the conversion
        asyncio.run(html_to_pdf_exact_replica(html_path, pdf_path, margin_inches=0.3))

        # Verify success
        if not os.path.exists(pdf_path):
            raise Exception("PDF file was not created")
            
        if os.path.getsize(pdf_path) == 0:
            raise Exception("PDF file is empty")
            
        print(f"✓ WRAPPER-BASED conversion completed: {pdf_filename}")
        return jsonify({
            "success": True, 
            "pdf_filename": pdf_filename,
            "message": "Exact visual replica with wrapper-based precise margin control"
        })
    
    except Exception as e:
        error_msg = f"PDF conversion failed: {str(e)}"
        print(f"✗ {error_msg}")
        return jsonify({"error": error_msg}), 500

###################################################################################


def extract_title_from_url_content(soup):
    """Extract the cleanest possible article title from URL content"""
    title_candidates = []
    
    # Try h1 tags first
    h1_tags = soup.find_all('h1')
    for h1 in h1_tags:
        h1_text = h1.get_text().strip()
        if 15 <= len(h1_text) <= 200:
            if not any(nav_word in h1_text.lower() for nav_word in ['home', 'menu', 'search']):
                title_candidates.append((h1_text, 100))
    
    # Try meta tags
    for meta_name in ['title', 'og:title', 'twitter:title']:
        if meta_name.startswith('og:') or meta_name.startswith('twitter:'):
            meta_tag = soup.find('meta', property=meta_name) or soup.find('meta', attrs={'name': meta_name})
        else:
            meta_tag = soup.find('meta', attrs={'name': meta_name})
        
        if meta_tag and meta_tag.get('content'):
            title_text = meta_tag.get('content').strip()
            if 15 <= len(title_text) <= 200:
                priority = 90 if meta_name == 'title' else 85
                title_candidates.append((title_text, priority))
    
    # Try page title (cleaned)
    if soup.title and soup.title.string:
        page_title = soup.title.string.strip()
        for separator in [' | ', ' - ', ' :: ', ' • ', ' — ', ' – ']:
            if separator in page_title:
                parts = page_title.split(separator)
                if len(parts[0].strip()) >= 15:
                    title_candidates.append((parts[0].strip(), 70))
                break
        else:
            if 15 <= len(page_title) <= 200:
                title_candidates.append((page_title, 60))
    
    if title_candidates:
        seen = set()
        unique_candidates = []
        for title, priority in sorted(title_candidates, key=lambda x: x[1], reverse=True):
            if title not in seen:
                seen.add(title)
                unique_candidates.append((title, priority))
        return unique_candidates[0][0]
    
    return "Article"

def calculate_readability_score(element):
    """Calculate readability score using text-to-link ratio and other heuristics"""
    if not element:
        return 0
    
    text_content = element.get_text(strip=True)
    if len(text_content) < 100:  # Too short to be main content
        return 0
    
    # Count links vs text
    links = element.find_all('a')
    link_chars = sum(len(link.get_text(strip=True)) for link in links)
    text_chars = len(text_content)
    
    if text_chars == 0:
        return 0
    
    # Readability heuristics
    link_ratio = link_chars / text_chars if text_chars > 0 else 1
    comma_count = text_content.count(',')
    paragraph_count = len(element.find_all('p'))
    
    # Higher score for more text, fewer links, more paragraphs
    score = text_chars * (1 - min(link_ratio, 0.8))  # Penalize high link ratio
    score += comma_count * 2  # Commas indicate natural prose
    score += paragraph_count * 50  # Multiple paragraphs good
    
    # Bonus for article-like elements
    if element.name in ['article', 'main']:
        score *= 1.5
    
    return score

def extract_article_content_from_url(soup, original_url):
    """Extract main article content using advanced readability algorithm"""
    
    if not soup:
        return None
    
    # Remove all non-content elements
    elements_to_remove = [
        'script', 'style', 'noscript', 'link', 'meta', 'nav', 'header', 'footer', 
        'aside', 'form', 'input', 'button', 'select', 'textarea', 'iframe', 'embed'
    ]
    
    for tag_name in elements_to_remove:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    
    # More aggressive removal patterns for extra content
    removal_patterns = [
        r'\bnav\b', r'\bmenu\b', r'\bheader\b', r'\bfooter\b', r'\bsidebar\b',
        r'\bsocial\b', r'\bshare\b', r'\bcomment\b', r'\bad\b', r'\bpromo\b',
        r'\bpopup\b', r'\bmodal\b', r'\bbreadcrumb\b', r'\brelated\b',
        r'\bnewsletter\b', r'\bsubscribe\b', r'\bauthor\b', r'\bmeta\b',
        r'\btrial\b', r'\bsignup\b', r'\bregister\b', r'\bcta\b', r'\bbanner\b',
        r'\bwidget\b', r'\bexpertise\b', r'\binterested\b', r'\barticles\b',
        r'\bview-all\b', r'\bmore-articles\b', r'\bsuggested\b', r'\brecommend\b'
    ]
    
    for pattern in removal_patterns:
        try:
            for element in soup.find_all(class_=re.compile(pattern, re.I)):
                if element:
                    element.decompose()
            for element in soup.find_all(id=re.compile(pattern, re.I)):
                if element:
                    element.decompose()
        except Exception:
            continue
    
    # Find main article content
    content_selectors = [
        'article', '[role="main"]', 'main', '.entry-content', '.post-content',
        '.article-content', '.content-body', '.article-body', '#content',
        '.post-body', '.story-content', '.text-content'
    ]
    
    candidates = []
    for selector in content_selectors:
        try:
            elements = soup.select(selector)
            for element in elements:
                if not element:
                    continue
                    
                paragraphs = element.find_all('p')
                text_content = element.get_text(strip=True)
                
                if len(paragraphs) >= 2 and len(text_content) >= 300:
                    score = len(text_content) + len(paragraphs) * 50
                    if element.name == 'article':
                        score += 1000
                    candidates.append((element, score))
        except Exception:
            continue
    
    if candidates:
        main_content = max(candidates, key=lambda x: x[1])[0]
    else:
        # Fallback 1: find container with most paragraphs
        containers = soup.find_all(['div', 'section', 'article', 'main'])
        paragraph_scores = []
        
        for container in containers:
            if not container:
                continue
            paragraphs = container.find_all('p')
            if len(paragraphs) >= 3:
                total_text = sum(len(p.get_text(strip=True)) for p in paragraphs if p)
                if total_text >= 500:
                    paragraph_scores.append((container, total_text))
        
        if paragraph_scores:
            main_content = max(paragraph_scores, key=lambda x: x[1])[0]
        else:
            # Fallback 2: More aggressive search for any content with text
            print("Primary content extraction failed, trying fallback methods...")
            all_containers = soup.find_all(['div', 'section', 'article', 'main', 'body'])
            fallback_scores = []
            
            for container in all_containers:
                if not container:
                    continue
                text_content = container.get_text(strip=True)
                if len(text_content) >= 200:  # Lower threshold
                    # Count paragraphs, headings, and other content elements
                    content_elements = container.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
                    score = len(text_content) + len(content_elements) * 25
                    fallback_scores.append((container, score))
                    print(f"Found potential content container with {len(text_content)} chars and {len(content_elements)} elements")
            
            if fallback_scores:
                main_content = max(fallback_scores, key=lambda x: x[1])[0]
                print("Using fallback content extraction")
            else:
                print("All content extraction methods failed")
                return None
    
    # After finding main content, aggressively remove non-article sections
    if main_content:
        # Remove author bio sections, related articles, and promotional content
        unwanted_sections = []
        
        # Find elements that look like promotional/non-article content
        for element in main_content.find_all(['div', 'section']):
            element_text = element.get_text(strip=True).lower()
            element_classes = ' '.join(element.get('class', [])).lower()
            element_id = element.get('id', '').lower()
            
            # Check for promotional/non-article content indicators
            unwanted_indicators = [
                'start free', 'free trial', 'create account', 'sign up', 'register',
                'expertise', 'view all articles', 'you might also be interested',
                'technical writer', 'years experience', 'follow', 'subscribe',
                'related articles', 'more articles', 'suggested reading',
                'bright data', 'proxy services', 'web scraper apis',
                'min read', 'also be interested', 'discover how to build'
            ]
            
            should_remove = False
            for indicator in unwanted_indicators:
                if indicator in element_text or indicator in element_classes or indicator in element_id:
                    should_remove = True
                    break
            
            # Also remove if it's a short section at the end with promotional links
            if len(element_text) < 200 and any(word in element_text for word in ['start', 'trial', 'account', 'free']):
                should_remove = True
            
            if should_remove:
                unwanted_sections.append(element)
        
        # Remove unwanted sections
        for section in unwanted_sections:
            section.decompose()
    
    # Clean and fix image URLs with better validation and download attempt
    if main_content:
        for img in main_content.find_all('img'):
            if not img:
                continue
                
            src = img.get('src', '')
            data_src = img.get('data-src', '')  # Handle lazy loading
            
            # Use data-src if src is empty or a placeholder
            if not src or 'placeholder' in src.lower() or 'loading' in src.lower():
                if data_src:
                    src = data_src
                    img['src'] = src
            
            if not src:
                img.decompose()
                continue
            
            # Fix relative URLs
            try:
                if src.startswith('//'):
                    img['src'] = 'https:' + src
                elif src.startswith('/') and not src.startswith('//'):
                    parsed_url = urlparse(original_url)
                    img['src'] = f"{parsed_url.scheme}://{parsed_url.netloc}{src}"
                elif not src.startswith(('http://', 'https://', 'data:')):
                    img['src'] = urljoin(original_url, src)
                
                # Skip HTTP validation - let Playwright handle image loading
                # Removed aggressive image validation that was preventing images from loading
            except Exception as e:
                print(f"Error fixing image URL {src}: {e}")
                img.decompose()
                continue
            
            # Only remove truly tiny images (likely icons/decorative elements)
            try:
                width = int(img.get('width', 0) or 0)
                height = int(img.get('height', 0) or 0)
                # Only remove if explicitly set to very small size
                if (width > 0 and width < 20) or (height > 0 and height < 20):
                    img.decompose()
                    continue
            except (ValueError, TypeError):
                # If we can't determine size, keep the image
                pass
            
            # Clean up attributes and add loading attribute
            allowed_attrs = ['src', 'alt', 'width', 'height', 'title']
            img.attrs = {k: v for k, v in img.attrs.items() if k in allowed_attrs}
            
            if not img.get('alt'):
                img['alt'] = 'Article image'
            
            # Removed crossorigin attribute as it can cause CORS issues
    
    return main_content

def create_beautiful_url_html(title, content_html):
    """Create beautiful HTML template with proper paragraph breaks and spacing"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 2;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 20px;
            line-height: 1.8;
            color: #2c2c2c;
            background: #ffffff;
            width: 100%;
            min-height: 100vh;
            padding: 40px;
        }}
        
        .container {{
            max-width: 700px;
            margin: 0 auto;
            width: 100%;
        }}
        
        h1 {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 36px;
            font-weight: 700;
            line-height: 1.2;
            color: #1a1a1a;
            margin: 0 0 30px 0;
            text-align: left;
            border-bottom: 3px solid #e0e0e0;
            padding-bottom: 20px;
        }}
        
        h2 {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 26px;
            font-weight: 600;
            margin: 40px 0 20px 0;
            color: #333;
            line-height: 1.3;
        }}
        
        h3 {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 22px;
            font-weight: 600;
            margin: 30px 0 15px 0;
            color: #333;
            line-height: 1.3;
        }}
        
        h4, h5, h6 {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-weight: 600;
            margin: 25px 0 12px 0;
            color: #333;
            line-height: 1.3;
        }}
        
        /* ENHANCED PARAGRAPH STYLING WITH BETTER BREAKS */
        p {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            margin: 0 0 24px 0;
            text-align: justify;
            hyphens: auto;
            line-height: 1.8;
        }}
        
        /* First paragraph after headings gets extra space */
        h1 + p, h2 + p, h3 + p, h4 + p, h5 + p, h6 + p {{
            margin-top: 8px;
        }}
        
        /* Last paragraph in sections gets extra bottom margin */
        p:last-child {{
            margin-bottom: 32px;
        }}
        
        /* Paragraph following another paragraph gets standard spacing */
        p + p {{
            margin-top: 0;
            margin-bottom: 24px;
        }}
        
        /* Special styling for first paragraph */
        p:first-of-type {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 22px;
            line-height: 1.7;
            margin: 0 0 28px 0;
            color: #1a1a1a;
            font-weight: 400;
        }}
        
        /* Paragraph breaks around different content types */
        p + h2, p + h3, p + h4 {{
            margin-top: 48px;
        }}
        
        ul + p, ol + p, table + p, blockquote + p {{
            margin-top: 24px;
        }}
        
        p + ul, p + ol, p + table, p + blockquote {{
            margin-top: 20px;
        }}
        
        ul, ol {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            margin: 24px 0;
            padding-left: 30px;
        }}
        
        li {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            margin: 0 0 12px 0;
            line-height: 1.7;
        }}
        
        /* IMAGE STYLING WITH ZERO SPACING */
        img {{
            max-width: 100%;
            height: auto;
            margin: 0 !important;
            padding: 0;
            display: block;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        /* Figure elements with zero spacing */
        figure {{
            margin: 0 !important;
            padding: 0;
            text-align: center;
        }}
        
        figure img {{
            margin: 0 !important;
        }}
        
        figcaption {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 16px;
            color: #666666;
            font-style: italic;
            margin: 4px 0 0 0;
            text-align: center;
            line-height: 1.5;
        }}
        
        /* RESTORE paragraph spacing when NOT adjacent to images */
        p:not(img + *):not(figure + *) {{
            margin-bottom: 24px !important;
        }}
        
        /* Zero spacing only between paragraphs and images */
        p + img, p + figure {{
            margin-top: 0 !important;
        }}
        
        img + p, figure + p {{
            margin-top: 0 !important;
        }}
        
        /* BUT maintain spacing between consecutive paragraphs */
        p + p {{
            margin-top: 0 !important;
            margin-bottom: 24px !important;
        }}
        
        /* Override ALL problematic classes with zero spacing */
        .img-placeholder,
        .figure-media,
        .primary-image__media,
        .figure-wrapper--article__container,
        .figure-landscape,
        .primary-image,
        .figure-low-res,
        .figure-high-res,
        .mntl-sc-block-image,
        .lifestyle-sc-block-image,
        .mntl-universal-primary-image,
        [class*="figure"],
        [class*="image"],
        [class*="mntl-sc-block"],
        [class*="lifestyle-sc-block"] {{
            margin: 0 !important;
            padding: 0 !important;
        }}
        
        /* Force zero spacing around special blocks */
        [class*="mntl-sc-block"] + p,
        [class*="lifestyle-sc-block"] + p {{
            margin-top: 0 !important;
            margin-bottom: 24px !important;
        }}
        
        /* Nuclear option: any div containing an image gets zero margin */
        div:has(img) {{
            margin: 0 !important;
        }}
        
        table {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            width: 100%;
            border-collapse: collapse;
            margin: 32px 0;
            font-size: 16px;
            border: 2px solid #000000;
            border-radius: 8px;
            overflow: hidden;
        }}
        
        th, td {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            border: 1px solid #000000;
            padding: 12px 15px;
            text-align: left;
            vertical-align: top;
            line-height: 1.6;
        }}
        
        th {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            background-color: #f8f9fa;
            font-weight: 600;
            color: #333;
            border: 1px solid #000000;
        }}
        
        tr {{
            border: 1px solid #000000;
        }}
        
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        tr:hover {{
            background-color: #f5f5f5;
        }}
        
        blockquote {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            margin: 32px 0;
            padding: 24px 28px;
            border-left: 5px solid #007acc;
            background-color: #f8f9fa;
            font-style: italic;
            color: #555555;
            font-size: 19px;
            line-height: 1.7;
        }}
        
        blockquote p {{
            margin-bottom: 16px;
        }}
        
        blockquote p:last-child {{
            margin-bottom: 0;
        }}
        
        a {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            color: #007acc;
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: border-color 0.2s;
        }}
        
        a:hover {{
            border-bottom-color: #007acc;
        }}
        
        strong, b {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-weight: 600;
            color: #1a1a1a;
        }}
        
        em, i {{
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-style: italic;
        }}
        
        code {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background-color: #f1f1f1;
            padding: 3px 8px;
            font-size: 16px;
            border-radius: 4px;
            color: #d63384;
        }}
        
        pre {{
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background-color: #f8f8f8;
            padding: 24px;
            margin: 32px 0;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 15px;
            border: 1px solid #e1e1e1;
            line-height: 1.6;
        }}
        
        /* Horizontal rule with proper spacing */
        hr {{
            border: none;
            height: 1px;
            background: linear-gradient(to right, transparent, #ccc, transparent);
            margin: 48px 0;
        }}
        
        /* Section breaks */
        .section-break {{
            margin: 48px 0;
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 24px;
        }}
        
        @media print {{
            * {{
                -webkit-print-color-adjust: exact !important;
                color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
            
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                font-size: 16px;
                line-height: 1.6;
                padding: 40px !important;
                margin: 0 !important;
                width: 100% !important;
                max-width: none !important;
                min-height: auto !important;
            }}
            
            .container {{
                max-width: none !important;
                margin: 0 !important;
                width: 100% !important;
            }}
            
            h1 {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                font-size: 28px;
                margin-bottom: 25px;
            }}
            
            h2 {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                font-size: 22px;
                margin: 30px 0 15px 0;
            }}
            
            p {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                margin-bottom: 18px;
                line-height: 1.6;
            }}
            
            img {{
                margin: 20px 0;
                box-shadow: 0 2px 6px rgba(0,0,0,0.1);
                page-break-inside: avoid;
            }}
            
            figure {{
                margin: 20px 0;
                page-break-inside: avoid;
            }}
            
            table {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                border: 2px solid #000000 !important;
                margin: 20px 0;
            }}
            
            th, td {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                border: 1px solid #000000 !important;
            }}
        }}
        
        @media screen and (max-width: 768px) {{
            body {{
                padding: 20px;
                font-size: 18px;
            }}
            
            .container {{
                padding: 0;
            }}
            
            h1 {{
                font-size: 28px;
                margin-bottom: 20px;
            }}
            
            h2 {{
                font-size: 22px;
            }}
            
            p {{
                margin-bottom: 20px;
                line-height: 1.7;
            }}
            
            img, figure {{
                margin: 0 !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        {content_html}
    </div>
</body>
</html>"""

def download_and_extract_url_content(url, output_path):
    """Download URL and extract clean article content for beautiful PDF creation"""
    try:
        print(f"Downloading URL: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print("Parsing HTML content...")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if not soup:
            print("Error: Failed to parse HTML")
            return False
        
        # Extract title and content
        print("Extracting title...")
        title = extract_title_from_url_content(soup)
        print(f"Extracted title: {title}")
        
        print("Extracting article content...")
        main_content = extract_article_content_from_url(soup, url)
        if not main_content:
            print("Warning: Could not find main article content")
            return False
        
        print("Creating beautiful HTML...")
        content_html = main_content.decode_contents()
        
        # Debug: Check if content is actually extracted
        if len(content_html.strip()) < 100:
            print(f"Warning: Very little content extracted ({len(content_html)} chars)")
            print(f"Content preview: {content_html[:200]}")
            # Try to get fallback content from body
            fallback_content = soup.body
            if fallback_content:
                # Remove script, style, nav, header, footer
                for tag in fallback_content.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    tag.decompose()
                fallback_html = fallback_content.decode_contents()
                if len(fallback_html) > len(content_html):
                    print("Using fallback body content")
                    content_html = fallback_html
        
        beautiful_html = create_beautiful_url_html(title, content_html)
        
        # Save the beautiful HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(beautiful_html)
        
        print("Successfully created beautiful HTML from URL")
        return True
        
    except Exception as e:
        print(f"Error downloading/extracting URL content: {str(e)}")
        return False

async def html_to_pdf_beautiful_url(source, pdf_file):
    """Convert beautiful URL HTML to PDF with uniform margins and proper image loading"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            # Set a longer timeout for image loading
            page.set_default_timeout(60000)
            
            if source.startswith('http'):
                await page.goto(source, wait_until='networkidle', timeout=30000)
            else:
                await page.goto(f"file:///{os.path.abspath(source)}", wait_until='networkidle', timeout=30000)
            
            # Wait longer for images to load and force image loading
            await page.wait_for_timeout(5000)
            
            # Simplified image loading - let browser handle naturally
            await page.evaluate("""
                () => {
                    // Simple wait for images with shorter timeout
                    const images = document.querySelectorAll('img');
                    console.log(`Found ${images.length} images on page`);
                    
                    // Force layout recalculation
                    document.body.offsetHeight;
                    
                    console.log('Image loading check completed');
                }
            """)
            
            # Additional wait after image loading
            await page.wait_for_timeout(3000)
            
            # Inject CSS to ensure proper margins and colors
            await page.add_style_tag(content='''
                @media print {
                    @page {
                        margin: 0.787in !important;  /* 2cm margins */
                        size: A4 !important;
                    }
                    
                    body {
                        margin: 0 !important;
                        padding: 0 !important;
                        width: 100% !important;
                        max-width: none !important;
                    }
                    
                    .container {
                        margin: 0 !important;
                        padding: 0 !important;
                        width: 100% !important;
                        max-width: none !important;
                    }
                    
                    img {
                        max-width: 100% !important;
                        height: auto !important;
                        page-break-inside: avoid !important;
                        -webkit-print-color-adjust: exact !important;
                        color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }
                    
                    table {
                        border: 2px solid #000000 !important;
                        page-break-inside: avoid !important;
                    }
                    
                    th, td {
                        border: 1px solid #000000 !important;
                    }
                    
                    * {
                        -webkit-print-color-adjust: exact !important;
                        color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }
                }
            ''')
            
            # Generate PDF with 2cm margins as required by PRD
            await page.pdf(
                path=pdf_file,
                format='A4',
                print_background=True,
                margin={
                    "top": "0.787in",    # 2cm = 0.787in
                    "right": "0.787in",  # 2cm = 0.787in
                    "bottom": "0.787in", # 2cm = 0.787in
                    "left": "0.787in"    # 2cm = 0.787in
                },
                prefer_css_page_size=True,
                display_header_footer=False
            )
            
            print("Beautiful URL PDF generated successfully with uniform margins")
            
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
            
            # Use the new beautiful URL content extraction
            if download_and_extract_url_content(url_input, html_path):
                return render_template("index.html", 
                    filename=filename, 
                    display_name=f"{domain}.html", 
                    base_name=domain, 
                    uploaded=True, 
                    is_url=True, 
                    original_url=url_input)
            else:
                return render_template("index.html", error="Failed to download or extract webpage content.", uploaded=False)
        
        elif uploaded_file and uploaded_file.filename.endswith(('.html', '.htm')):
            original_name = uploaded_file.filename
            base_name = os.path.splitext(original_name)[0]
            internal_filename = f"{unique_id}_{original_name}"
            html_path = os.path.join("uploads", internal_filename)
            uploaded_file.save(html_path)
            return render_template("index.html", 
                filename=internal_filename, 
                display_name=original_name, 
                base_name=base_name, 
                uploaded=True, 
                is_url=False)
        else:
            return render_template("index.html", error="Please provide a valid URL or upload an HTML file.", uploaded=False)

    return render_template("index.html", uploaded=False)



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