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
    
    # Clean up double quotes in the alt text to avoid breaking our HTML attributes
    safe_alt_text = alt_text.replace('"', '&quot;')
    
    # 2. Download and overwrite the local image asset
    os.makedirs("img", exist_ok=True)
    img_response = requests.get(img_url)
    if img_response.status_code == 200:
        with open("img/xkcd.png", "wb") as f:
            f.write(img_response.content)
    else:
        raise Exception("Failed to download xkcd image file")

    # 3. Rebuild the README block with full title/hover text support
    new_block = (
        "<!-- xkcd-start -->\n"
        f'<a href="https://xkcd.com" target="_blank" rel="noopener noreferrer" title="{safe_alt_text}">\n'
        f'  <img src="https://raw.githubusercontent.com/ilim-cell/.github/main/img/xkcd.png" alt="Latest xkcd: {safe_alt_text}" title="{safe_alt_text}" />\n'
        "</a>\n"
        "<!-- xkcd-end -->"
    )
    
    # 4. Target the profile/README.md path explicitly
    readme_path = "profile/README.md"
    
    if not os.path.exists(readme_path):
        raise FileNotFoundError(f"Could not find the file at {readme_path}")

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # The clean replacement regex bounds
    pattern = r"<!-- xkcd-start -->.*<!-- xkcd-end -->"
    updated_content = re.sub(pattern, new_block, content, flags=re.DOTALL)
    
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated_content)

if __name__ == "__main__":
    main()
