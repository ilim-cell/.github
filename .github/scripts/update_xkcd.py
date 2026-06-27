import os
import re
import requests

def main():
    # 1. Fetch latest comic metadata
    response = requests.get("https://xkcd.com/info.0.json")
    if response.status_code != 200:
        raise Exception("Failed to fetch xkcd API data")
        
    comic_data = response.json()
    img_url = comic_data["img"]
    alt_text = comic_data["alt"]
    
    # 2. Download and overwrite the local image asset
    img_response = requests.get(img_url)
    if img_response.status_code == 200:
        # Ensure directory exists just in case
        os.makedirs("img", exist_ok=True)
        with open("img/xkcd.png", "wb") as f:
            f.write(img_response.content)
    else:
        raise Exception("Failed to download xkcd image file")

    # 3. Rebuild the README block matching your exact HTML layout
    new_block = (
        "\n"
        '<a href="https://xkcd.com" target="_blank" rel="noopener noreferrer">\n'
        '  <img src="https://raw.githubusercontent.com/ilim-cell/.github/main/img/xkcd.png" alt="Latest xkcd" />\n'
        "</a>\n"
        f"<details><summary>Hover text</summary>{alt_text}</details>\n"
        ""
    )
    
    # 4. Update the README file
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()
        
    pattern = r".*?"
    updated_content = re.sub(pattern, new_block, content, flags=re.DOTALL)
    
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated_content)

if __name__ == "__main__":
    main()
