from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin, urlparse


def extract_clean_article_content(url, output_path=None):
    """
    Generic article extractor using Playwright
    Extracts only: title, main content, and images
    """
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        try:
            page = browser.new_page()
            
            # Set realistic headers
            page.set_extra_http_headers({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            })
            
            print(f"Loading: {url}")
            
            # Navigate and wait for content
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_load_state('domcontentloaded')
            
            # Wait a bit more for dynamic content
            page.wait_for_timeout(2000)
            
            # Extract title
            title = extract_title(page)
            print(f"Title: {title}")
            
            # Extract main content
            main_content = extract_main_content(page, url)
            
            if not main_content:
                print("No main content found")
                return None
                
            # Create clean HTML
            clean_html = create_clean_html(title, main_content)
            
            # Save if output path provided
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(clean_html)
                print(f"Saved to: {output_path}")
            
            return clean_html
            
        finally:
            browser.close()


def extract_title(page):
    """Extract page title using multiple strategies"""
    
    # Strategy 1: Standard title tag
    title = page.title()
    if title and title.strip() and title.lower() not in ['', 'untitled', 'document']:
        return title.strip()
    
    # Strategy 2: Main heading
    h1_selectors = ['h1', 'h1.title', '.title h1', '.entry-title', '.post-title']
    for selector in h1_selectors:
        try:
            element = page.query_selector(selector)
            if element:
                text = element.inner_text().strip()
                if text:
                    return text
        except:
            continue
    
    # Strategy 3: JSON-LD structured data
    try:
        json_scripts = page.query_selector_all('script[type="application/ld+json"]')
        for script in json_scripts:
            content = script.inner_text()
            data = json.loads(content)
            if isinstance(data, list):
                data = data[0]  # Take first item
            if data.get('headline'):
                return data['headline']
            elif data.get('name'):
                return data['name']
    except:
        pass
    
    return "Untitled Article"


def extract_main_content(page, original_url):
    """Extract main article content using multiple strategies"""
    
    # Strategy 1: Try JSON-LD structured data first (best for recipes/articles)
    structured_content = extract_structured_content(page)
    if structured_content:
        return structured_content
    
    # Strategy 2: Common content selectors
    content_selectors = [
        'article',
        'main article',
        '[role="main"]',
        'main',
        '.entry-content',
        '.post-content', 
        '.article-content',
        '.content-body',
        '.article-body',
        '.post-body',
        '.story-content',
        '.recipe-content',
        '#content article',
        '.content article'
    ]
    
    best_candidate = None
    best_score = 0
    
    for selector in content_selectors:
        try:
            elements = page.query_selector_all(selector)
            for element in elements:
                if not element:
                    continue
                
                # Score based on content quality
                text_content = element.inner_text()
                paragraphs = len(page.query_selector_all(f'{selector} p'))
                
                if len(text_content) < 200:  # Too short
                    continue
                
                # Calculate score
                score = len(text_content) + (paragraphs * 50)
                
                # Bonus for article tags
                if 'article' in selector:
                    score += 1000
                
                if score > best_score:
                    best_score = score
                    best_candidate = element
                    
        except:
            continue
    
    if best_candidate:
        html_content = best_candidate.inner_html()
        return clean_extracted_content(html_content, original_url)
    
    # Strategy 3: Fallback - find container with most meaningful content
    print("Using fallback content extraction...")
    containers = page.query_selector_all('div, section, article, main')
    
    for container in containers:
        try:
            text = container.inner_text()
            paragraphs = len(page.query_selector_all('p', container))
            
            if len(text) >= 500 and paragraphs >= 3:
                html_content = container.inner_html()
                return clean_extracted_content(html_content, original_url)
        except:
            continue
    
    return None


def extract_structured_content(page):
    """Extract content from JSON-LD structured data"""
    try:
        json_scripts = page.query_selector_all('script[type="application/ld+json"]')
        
        for script in json_scripts:
            content = script.inner_text()
            data = json.loads(content)
            
            # Handle arrays
            if isinstance(data, list):
                for item in data:
                    if item.get('@type') in ['Recipe', 'Article', 'NewsArticle', 'BlogPosting']:
                        return format_structured_data_to_html(item)
            elif data.get('@type') in ['Recipe', 'Article', 'NewsArticle', 'BlogPosting']:
                return format_structured_data_to_html(data)
                
    except:
        pass
    
    return None


def format_structured_data_to_html(data):
    """Convert structured data to clean HTML"""
    html_parts = []
    
    # Description/summary
    if data.get('description'):
        html_parts.append(f'<p class="article-summary">{data["description"]}</p>')
    
    # Recipe-specific content
    if data.get('@type') == 'Recipe':
        # Ingredients
        if data.get('recipeIngredient'):
            html_parts.append('<h2>Ingredients</h2>')
            html_parts.append('<ul class="ingredients">')
            for ingredient in data['recipeIngredient']:
                html_parts.append(f'<li>{ingredient}</li>')
            html_parts.append('</ul>')
        
        # Instructions
        if data.get('recipeInstructions'):
            html_parts.append('<h2>Instructions</h2>')
            html_parts.append('<ol class="instructions">')
            for instruction in data['recipeInstructions']:
                if isinstance(instruction, dict):
                    text = instruction.get('text', str(instruction))
                else:
                    text = str(instruction)
                html_parts.append(f'<li>{text}</li>')
            html_parts.append('</ol>')
    
    # Article body
    if data.get('articleBody'):
        html_parts.append(f'<div class="article-body">{data["articleBody"]}</div>')
    
    return ''.join(html_parts) if html_parts else None

def is_truly_empty_element(element, check_recursive=True):
    """
    Enhanced check for truly empty elements with recursive checking
    """
    if not element:
        return True
    
    # Get all text content, stripped
    text_content = element.get_text(strip=True)
    
    # Remove zero-width characters and non-breaking spaces
    import unicodedata
    cleaned_text = ''.join(char for char in text_content 
                          if unicodedata.category(char) not in ['Zs', 'Zl', 'Zp', 'Cc', 'Cf'])
    
    # Check if there's any meaningful text
    if cleaned_text:
        return False
    
    # Check for meaningful child elements (images, videos, etc.)
    meaningful_tags = ['img', 'video', 'audio', 'iframe', 'embed', 'object', 'canvas', 'svg', 'picture']
    if element.find_all(meaningful_tags):
        return False
    
    # Check for links with meaningful href (not just anchors)
    links = element.find_all('a')
    for link in links:
        href = link.get('href', '').strip()
        if href and href not in ['#', 'javascript:void(0)', 'javascript:;']:
            # Check if the link itself has content
            if link.get_text(strip=True) or link.find_all(meaningful_tags):
                return False
    
    # Check for form elements
    form_elements = element.find_all(['input', 'button', 'select', 'textarea'])
    if form_elements:
        return False
    
    # Recursive check: check if ALL children are also empty
    if check_recursive:
        children = element.find_all(recursive=False)
        if children:
            # If it has children, it's only empty if ALL children are empty
            for child in children:
                if not is_truly_empty_element(child, check_recursive=True):
                    return False
    
    return True


def aggressive_empty_list_cleanup(soup):
    """
    More aggressive approach specifically for lists
    """
    print("\n" + "="*60)
    print("AGGRESSIVE LIST CLEANUP")
    print("="*60)
    
    # Multiple passes to handle nested empty structures
    for pass_num in range(3):
        print(f"\nPass {pass_num + 1}:")
        changes_made = False
        
        # First, clean up any empty nested containers within list items
        all_lis = soup.find_all('li')
        for li in all_lis:
            # Remove empty divs/spans within list items first
            for empty_container in li.find_all(['div', 'span']):
                if is_truly_empty_element(empty_container, check_recursive=True):
                    empty_container.decompose()
                    changes_made = True
        
        # Now check list items themselves
        empty_lis_removed = 0
        all_lis = soup.find_all('li')
        for li in all_lis:
            if is_truly_empty_element(li, check_recursive=True):
                print(f"  Removing empty <li>: classes={li.get('class', [])}, id={li.get('id', 'none')}")
                # Get the parent list before removing
                parent_list = li.parent
                li.decompose()
                empty_lis_removed += 1
                changes_made = True
                
                # Check if parent list is now empty
                if parent_list and parent_list.name in ['ul', 'ol']:
                    remaining_items = parent_list.find_all('li', recursive=False)
                    if not remaining_items:
                        print(f"    Parent list now empty, removing: <{parent_list.name}>")
                        parent_list.decompose()
        
        # Remove lists that have become empty
        empty_lists_removed = 0
        all_lists = soup.find_all(['ul', 'ol'])
        for lst in all_lists:
            # Check both for no items and for all items being empty
            items = lst.find_all('li', recursive=False)
            if not items:
                print(f"  Removing empty list: <{lst.name}> (no items)")
                lst.decompose()
                empty_lists_removed += 1
                changes_made = True
            elif all(is_truly_empty_element(item, check_recursive=True) for item in items):
                print(f"  Removing list with all empty items: <{lst.name}>")
                lst.decompose()
                empty_lists_removed += 1
                changes_made = True
        
        print(f"  Empty <li> elements removed: {empty_lis_removed}")
        print(f"  Empty lists removed: {empty_lists_removed}")
        
        if not changes_made:
            print(f"  No changes in pass {pass_num + 1}, stopping early")
            break
    
    print("\n" + "="*60)
    print("CLEANUP COMPLETE")
    print("="*60)


def remove_empty_toc_items(soup):
    """
    Specifically target TOC items that might be empty after link removal
    """
    toc_lists = soup.find_all(['ul', 'ol'], class_=lambda x: x and 'toc' in ' '.join(x).lower() if isinstance(x, list) else 'toc' in str(x).lower())
    
    for toc_list in toc_lists:
        items = toc_list.find_all('li', recursive=False)
        for item in items:
            # Check if the item has any meaningful content after cleaning
            links = item.find_all('a')
            has_valid_link = False
            for link in links:
                href = link.get('href', '').strip()
                text = link.get_text(strip=True)
                if href and text:
                    has_valid_link = True
                    break
            
            if not has_valid_link and is_truly_empty_element(item, check_recursive=True):
                item.decompose()


def is_truly_empty_element(element):
    """
    Enhanced check for truly empty elements that accounts for various edge cases
    """
    if not element:
        return True
    
    # Get all text content, stripped
    text_content = element.get_text(strip=True)
    
    # Remove zero-width characters and non-breaking spaces
    import unicodedata
    cleaned_text = ''.join(char for char in text_content 
                          if unicodedata.category(char) not in ['Zs', 'Zl', 'Zp'])
    
    # Check if there's any meaningful text
    if cleaned_text:
        return False
    
    # Check for meaningful child elements (images, videos, etc.)
    meaningful_tags = ['img', 'video', 'audio', 'iframe', 'embed', 'object', 'canvas', 'svg']
    if element.find_all(meaningful_tags):
        return False
    
    # Check for links with href (even if empty text)
    links = element.find_all('a')
    for link in links:
        if link.get('href') and link.get('href').strip():
            return False
    
    # Check for form elements
    form_elements = element.find_all(['input', 'button', 'select', 'textarea'])
    if form_elements:
        return False
    
    return True


def aggressive_empty_list_cleanup(soup):
    """
    More targeted approach to remove empty lists without affecting document structure
    """
    print("\n" + "="*60)
    print("STARTING TARGETED EMPTY LIST CLEANUP")
    print("="*60)
    
    # Only target lists and list items - don't touch other structural elements
    for pass_num in range(2):  # Reduced passes
        print(f"\nPass {pass_num + 1}:")
        
        # Remove empty list items
        empty_lis_removed = 0
        all_lis = soup.find_all('li')
        for li in all_lis:
            if is_truly_empty_element(li):
                print(f"  Removing empty <li>: classes={li.get('class', [])}, id={li.get('id', 'none')}")
                li.decompose()
                empty_lis_removed += 1
        
        # Remove lists that are now empty
        empty_lists_removed = 0
        all_lists = soup.find_all(['ul', 'ol'])
        for lst in all_lists:
            remaining_lis = lst.find_all('li', recursive=False)
            if not remaining_lis:
                print(f"  Removing empty list: <{lst.name}> classes={lst.get('class', [])}, id={lst.get('id', 'none')}")
                lst.decompose()
                empty_lists_removed += 1
        
        print(f"  Empty <li> elements removed: {empty_lis_removed}")
        print(f"  Empty lists removed: {empty_lists_removed}")
        
        if empty_lis_removed == 0 and empty_lists_removed == 0:
            print(f"  No changes in pass {pass_num + 1}, stopping early")
            break
    
    print("\n" + "="*60)
    print("TARGETED CLEANUP COMPLETE")
    print("="*60)


def clean_extracted_content(html_content, original_url):
    """Clean and process extracted HTML content with enhanced empty list removal."""
    from bs4 import BeautifulSoup
    import re
    from urllib.parse import urljoin, urlparse

    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove unwanted elements
    unwanted_elements = [
        'script', 'style', 'noscript', 'iframe', 'embed', 'object',
        'form', 'input', 'button', 'select', 'textarea'
    ]
    for tag_name in unwanted_elements:
        for element in soup.find_all(tag_name):
            element.decompose()

    # Remove elements by class/id patterns
    removal_patterns = [
        r'\bads?\b', r'\bpromo\b', r'\bpopup\b', r'\bmodal\b',
        r'\bshare\b', r'\bsocial\b', r'\bcomment\b', r'\bfooter\b',
        r'\bheader\b', r'\bnav\b', r'\bmenu\b', r'\bsidebar\b',
        r'\bnewsletter\b', r'\bsubscribe\b', r'\brelated\b',
        r'\bauthor-bio\b', r'\bbreadcrumb\b'
    ]
    for pattern in removal_patterns:
        for element in soup.find_all(class_=re.compile(pattern, re.I)):
            element.decompose()
        for element in soup.find_all(id=re.compile(pattern, re.I)):
            element.decompose()

    # Normalize whitespace globally
    def normalize_whitespace():
        """Strip all text nodes and remove empty ones."""
        for text in list(soup.find_all(string=True)):
            if text.parent.name not in ['script', 'style']:
                stripped = text.strip()
                if stripped:
                    text.replace_with(stripped)
                else:
                    text.extract()

    # Remove elements that are effectively empty (multiple passes)
    def remove_all_empty_elements():
        changed = True
        while changed:
            changed = False
            for element in soup.find_all(lambda tag: tag.name not in ['img', 'br', 'hr']):
                if is_truly_empty_element(element):
                    element.decompose()
                    changed = True

    # Clean empty siblings around images
    def clean_around_images():
        # Only remove truly problematic empty elements around images
        # Don't remove elements that might be providing necessary spacing
        for img in soup.find_all('img'):
            # Only clean up direct empty siblings that are clearly problematic
            # (like empty divs with no content or styling)
            
            # Before image - only remove empty divs/spans with no classes/ids
            prev_sibling = img.previous_sibling
            if (getattr(prev_sibling, "name", None) in ['div', 'span'] and 
                is_truly_empty_element(prev_sibling) and 
                not prev_sibling.get('class') and 
                not prev_sibling.get('id')):
                prev_sibling.decompose()
            
            # After image - same selective approach
            next_sibling = img.next_sibling
            if (getattr(next_sibling, "name", None) in ['div', 'span'] and 
                is_truly_empty_element(next_sibling) and 
                not next_sibling.get('class') and 
                not next_sibling.get('id')):
                next_sibling.decompose()

    # Apply cleaning steps in order - but be more conservative
    normalize_whitespace()
    
    # Only apply targeted empty list cleanup - don't remove all empty elements
    aggressive_empty_list_cleanup(soup)
    
    # Only clean around images very selectively
    clean_around_images()

    # Specific TOC cleanup
    remove_empty_toc_items(soup)
    
    # Then do the aggressive list cleanup
    aggressive_empty_list_cleanup(soup)
    
    # Final pass only for clearly problematic empty containers
    def remove_only_problematic_empties():
        """Only remove elements that are clearly problematic without content or structure"""
        for element in soup.find_all(['div', 'span', 'p']):
            # Only remove if completely empty AND has no styling classes/ids
            if (is_truly_empty_element(element) and 
                not element.get('class') and 
                not element.get('id') and
                not element.get('style')):
                element.decompose()
    
    remove_only_problematic_empties()

    # Normalize and fix images
    for img in soup.find_all('img'):
        src = img.get('src', '')
        data_src = img.get('data-src', '')
        if (not src or 'placeholder' in src.lower()) and data_src:
            src = data_src
            img['src'] = src
        if not src:
            img.decompose()
            continue
        if src.startswith('//'):
            img['src'] = 'https:' + src
        elif src.startswith('/') and not src.startswith('//'):
            parsed_url = urlparse(original_url)
            img['src'] = f"{parsed_url.scheme}://{parsed_url.netloc}{src}"
        elif not src.startswith(('http://', 'https://', 'data:')):
            img['src'] = urljoin(original_url, src)
        essential_attrs = ['src', 'alt', 'width', 'height', 'title']
        img.attrs = {k: v for k, v in img.attrs.items() if k in essential_attrs}
        if not img.get('alt'):
            img['alt'] = 'Article image'

    return str(soup)


def create_clean_html(title, content):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        /* HIDE ALL EMPTY LIST ITEMS */
        li:empty,
        li:not(:has(*)):not(:has(text)),
        li:has(> :empty:only-child) {{
            display: none !important;
        }}
        /* Hide lists with only empty items */
        ul:not(:has(li:not(:empty))),
        ol:not(:has(li:not(:empty))) {{
            display: none !important;
        }}
        /* Alternative approach - remove list-style from empty items */
        li:empty::before {{
            content: none !important;
        }}
        /* Hide list items that only contain whitespace */
        li {{
            min-height: 0.1px; /* Force layout calculation */
        }}
        li:not(:has(*)):not(:has(img)):not(:has(a)) {{
            display: none !important;
        }}
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 14pt;
            line-height: 145%;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        
        /* NUCLEAR SOLUTION: All three methods combined */
        img {{
            display: block !important;           /* Method 1: Block element */
            vertical-align: bottom !important;   /* Method 2: Align to baseline bottom */
            margin: 1em 0 0 0 !important;      /* Zero bottom margin */
            padding: 0 !important;
            max-width: 100%;
            height: auto;
            font-size: 0 !important;           /* Method 3: Zero font size */
            line-height: 0 !important;         /* Method 3: Zero line height */
        }}
        
        /* Parent container fixes */
        .content, div, p, section, article {{
            font-size: 0;                      /* Eliminates descender space */
            line-height: 0;                   /* Eliminates line spacing */
        }}
        
        /* Reset text elements to proper typography */
        .content p, .content h1, .content h2, .content h3, 
        .content h4, .content h5, .content h6,
        .content ul, .content ol, .content li,
        .content table, .content th, .content td,
        .content blockquote {{
            font-family: Helvetica, Arial, sans-serif !important;
            font-size: 14pt !important;
            line-height: 145% !important;
        }}
        
        /* Specific parent elements that might contain images */
        div:has(img), p:has(img), section:has(img), article:has(img) {{
            font-size: 0 !important;
            line-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        
        h1 {{ 
            font-size: 24pt !important;
            color: #2c3e50; 
            border-bottom: 2px solid #3498db; 
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        
        h2, h3, h4, h5, h6 {{ 
            color: #34495e; 
            margin-top: 2em; 
            margin-bottom: 1em;
        }}
        
        p {{ margin: 1em 0; }}
        ul, ol {{ margin: 1em 0; padding-left: 2em; }}
        li {{ margin: 0.5em 0; }}
        
        /* Tables */
        table {{ border-collapse: collapse; width: 100%; margin: 1em 0; border: 2px solid #000; }}
        th, td {{ border: 1px solid #000; padding: 12px 8px; text-align: left; vertical-align: top; }}
        th {{ background-color: #f0f0f0; font-weight: bold; border-bottom: 2px solid #000; }}
        tr:nth-child(even) {{ background-color: #f8f8f8; }}
        tr:nth-child(odd) {{ background-color: #ffffff; }}
        thead tr, tr:first-child {{ background-color: #f0f0f0 !important; }}
        
        blockquote {{ margin: 1em 0; padding-left: 1em; border-left: 3px solid #3498db; }}
        
        /* Eliminate ANY spacing after images */
        img + *, img ~ * {{
            margin-top: 0 !important;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="content">
        {content}
    </div>
</body>
</html>"""


# Usage example
if __name__ == "__main__":
    url = "https://www.thespruceeats.com/classic-tomato-pasta-sauce-recipe-3992836"
    result = extract_clean_article_content(url, "clean_article_improved.html")
    
    if result:
        print("Successfully extracted clean article content")
    else:
        print("Failed to extract content")