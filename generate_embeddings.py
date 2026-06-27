import os

# Disable laggy download progress bars and symlink warnings from Hugging Face
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import json
import numpy as np
from sentence_transformers import SentenceTransformer

# --- CONFIGURATION ---
DB_FILE = "xkcd_embeddings.json"

def main():
    if not os.path.exists(DB_FILE):
        print(f"❌ Error: {DB_FILE} not found. Please run your scraper first!")
        return

    # 1. Load your raw scraped database
    print("📖 Loading scraper database...")
    with open(DB_FILE, "r", encoding="utf-8") as f:
        database = json.load(f)

    # 2. Initialize the Sentence Transformer model
    print("🧠 Loading SentenceTransformer model (all-MiniLM-L6-v2) silently...")
    # This model runs fast on CPU and outputs compact 384-dimensional vectors
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # 3. Find comics that need embeddings
    backlog = []
    for num, data in database.items():
        if "embedding" not in data:
            # Combine all descriptive text into one rich conceptual text block
            text_payload = (
                f"Title: {data.get('title', '')}\n"
                f"Alt Text: {data.get('alt', '')}\n"
                f"Transcript: {data.get('ocr_text', '')}"
            )
            backlog.append((num, text_payload))

    total_backlog = len(backlog)
    if total_backlog == 0:
        print("✨ All indexed comics already have semantic embeddings!")
        return

    print(f"⚡ Found {total_backlog} comics waiting to be vectorized. Processing in batches...")

    # 4. Generate embeddings in parallel batches for high efficiency
    batch_size = 64
    for i in range(0, total_backlog, batch_size):
        batch = backlog[i:i + batch_size]
        batch_ids = [item[0] for item in batch]
        batch_texts = [item[1] for item in batch]

        print(f"🧱 Vectorizing batch {i // batch_size + 1}/{-(-total_backlog // batch_size)}...", end="\r")
        
        # Calculate embeddings for the entire batch at once
        embeddings = model.encode(batch_texts, show_progress_bar=False)

        # Map vectors back into our database memory
        for idx, comic_id in enumerate(batch_ids):
            # Convert numpy array to standard list of floats for JSON serialization
            database[comic_id]["embedding"] = embeddings[idx].tolist()

    # 5. Save the updated database back to disk
    print("\n💾 Writing updated semantic database to disk...")
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(database, f, indent=4)

    print("🎉 Done! All comics are now semantically indexed and ready for web search!")

if __name__ == "__main__":
    main()