# This script removes unnecessary whitespace from an HTML file.
# It uses the BeautifulSoup library to parse the HTML and clean it up.
#
# To use this script, you need to install the required library:
# pip install beautifulsoup4 lxml

import re
from bs4 import BeautifulSoup, NavigableString

def remove_extra_whitespace(html_content):
    """
    Parses HTML content and removes redundant whitespace from text nodes.

    Args:
        html_content (str): The string containing the HTML content.

    Returns:
        str: The cleaned HTML content as a string.
    """
    soup = BeautifulSoup(html_content, 'lxml')

    # Iterate over all text elements found by BeautifulSoup
    for text_element in soup.find_all(string=True):
        # We don't want to modify content in tags where whitespace is significant,
        # like <pre> for preformatted text or <script>/<style> for code.
        if text_element.parent.name in ['pre', 'code', 'script', 'style']:
            continue

        # Check if the element is a NavigableString (i.e., text, not a tag)
        if isinstance(text_element, NavigableString):
            # Use regex to replace multiple whitespace characters 
            # (including newlines, tabs, etc.) with a single space.
            # .strip() removes leading/trailing whitespace.
            cleaned_text = re.sub(r'\s+', ' ', text_element).strip()
            
            # To avoid modifying the soup object unnecessarily, 
            # we only replace the text if it has actually changed.
            if cleaned_text != text_element:
                text_element.replace_with(cleaned_text)

    # Return the cleaned HTML as a pretty-printed string.
    # The prettify() method helps maintain a readable structure.
    return soup.prettify()

def process_file(input_path, output_path):
    """
    Reads an HTML file, cleans it, and writes the result to a new file.

    Args:
        input_path (str): The path to the input HTML file.
        output_path (str): The path where the cleaned HTML file will be saved.
    """
    try:
        print(f"Reading from '{input_path}'...")
        with open(input_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        print("Processing and removing extra spaces...")
        cleaned_html = remove_extra_whitespace(html_content)

        print(f"Writing cleaned HTML to '{output_path}'...")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_html)

        print("\nSuccessfully cleaned the HTML file!")
        print(f"Input:  {input_path}")
        print(f"Output: {output_path}")

    except FileNotFoundError:
        print(f"Error: The file '{input_path}' was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # --- Instructions ---
    # To use this script, change the file paths below to match your files.
    # The 'r' before the string is important - it tells Python to treat
    # backslashes as normal characters, which is needed for Windows paths.

    # 1. Set the path for the HTML file you want to clean.
    input_file = r"C:\Users\su.ray\OneDrive - Reply\Suddha\Personal Projects\html-to-pdf\clean_article_improved.html"

    # 2. Set the path for where you want to save the cleaned HTML file.
    output_file = r"C:\Users\su.ray\OneDrive - Reply\Suddha\Personal Projects\html-to-pdf\cleaned_output.html"

    # Process the files with the paths you set above.
    process_file(input_file, output_file)

