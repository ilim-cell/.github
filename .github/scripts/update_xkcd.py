import os
import re
import json
import requests
import pytesseract
from PIL import Image
import numpy as np
from sentence_transformers import SentenceTransformer

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '_', text)
    return text.strip('_')

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def main():
    # 1. Fetch latest comic metadata
    response = requests.get("https://xkcd.com/info.0.json")
    if response.status_code != 200:
        raise Exception("Failed to fetch xkcd API data")
        
    comic_data = response.json()
    img_url = comic_data["img"]
    alt_text = comic_data["alt"]
    comic_num = comic_data["num"]
    comic_title = comic_data["title"]
    
    title_slug = slugify(comic_title)
    folder_name = f"{title_slug}_{comic_num}"
    comic_dir = os.path.join("xkcd", folder_name)
    os.makedirs(comic_dir, exist_ok=True)
    
    ext = os.path.splitext(img_url)[-1] or ".png"
    img_dest_path = os.path.join(comic_dir, f"{comic_num}{ext}")
    text_dest_path = os.path.join(comic_dir, "text.txt")
    
    # 2. Download Image
    img_response = requests.get(img_url)
    if img_response.status_code == 200:
        with open(img_dest_path, "wb") as f:
            f.write(img_response.content)
    else:
        raise Exception("Failed to download image")

    # 3. Perform OCR
    try:
        img = Image.open(img_dest_path)
        ocr_text = pytesseract.image_to_string(img).strip()
    except Exception as e:
        print(f"OCR failed: {e}")
        ocr_text = ""

    # Compile text payload for semantic parsing
    full_searchable_content = (
        f"Title: {comic_title}\n"
        f"Comic Number: {comic_num}\n"
        f"Alt Text: {alt_text}\n"
        f"Transcript: {ocr_text}"
    )
    
    with open(text_dest_path, "w", encoding="utf-8") as f:
        f.write(full_searchable_content)

    # 4. Generate Semantic Vector Embedding
    # This model converts text into a 384-dimension vector representing context/intent
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embedding = model.encode(full_searchable_content).tolist()

    # Load existing semantic registry index
    index_path = "xkcd_embeddings.json"
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            try:
                archive_index = json.load(f)
            except json.JSONDecodeError:
                archive_index = {}
    else:
        archive_index = {}

    # Store or update the entry
    archive_index[str(comic_num)] = {
        "title": comic_title,
        "folder": folder_name,
        "alt": alt_text,
        "embedding": embedding
    }

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(archive_index, f, indent=2)

    # 5. Handle Profile README image mirroring
    os.makedirs("img", exist_ok=True)
    with open("img/xkcd.png", "wb") as f:
        f.write(img_response.content)

    safe_alt_text = alt_text.replace('"', '&quot;')
    new_block = (
        "\n"
        f"### xkcd #{comic_num}: {comic_title}\n"
        f'<a href="https://xkcd.com/{comic_num}" target="_blank" rel="noopener noreferrer" title="{safe_alt_text}">\n'
        f'  <img src="https://raw.githubusercontent.com/ilim-cell/.github/main/img/xkcd.png" alt="{comic_title}" title="{safe_alt_text}" />\n'
        "</a>\n"
        ""
    )
    
    readme_path = "profile/README.md"
    if os.path.exists(readme_path):
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        pattern = r".*"
        updated_content = re.sub(pattern, new_block, content, flags=re.DOTALL)
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

if __name__ == "__main__":
    main()
