import os
import re
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
DB_FILE = "xkcd_embeddings.json"
OUTPUT_DIR = "xkcd"
MAX_WORKERS = 10  # Number of concurrent downloads (balanced speed and server etiquette)

# Standard browser headers to bypass strict CDN block rules on dynamic comics (like 1608 and 1663)
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://xkcd.com/"
}

def slugify(text):
    """Generates a clean directory-safe name from comic titles."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '_', text)
    return text.strip('_')

def process_comic(num_str, data):
    """Processes a single comic: recreates folder, text files, and fetches image if missing."""
    try:
        num = int(num_str)
        title = data.get("title", "Untitled")
        alt = data.get("alt", "")
        img_url = data.get("img_url") or data.get("img")  # support either database format key
        
        # Dual-key fallback: Check both "ocr_text" and "transcript" to ensure data recovery
        ocr_text = data.get("ocr_text") or data.get("transcript") or ""
        
        # Fallback: If the transcript is empty or contains the sample boilerplate,
        # fetch the real, official transcript live from xkcd's API!
        is_placeholder = ocr_text.strip().startswith("Sample transcript or OCR output")
        if not ocr_text.strip() or is_placeholder:
            try:
                api_url = f"https://xkcd.com/{num}/info.0.json"
                res = requests.get(api_url, headers=REQUEST_HEADERS, timeout=10)
                if res.status_code == 200:
                    api_data = res.json()
                    official_transcript = api_data.get("transcript", "")
                    if official_transcript:
                        ocr_text = official_transcript
            except Exception:
                # Silently ignore connection errors so the rest of the pool keeps running
                pass

        # Enforce standard folder organization format: number_comicname
        title_slug = slugify(title)
        folder = f"{num}_{title_slug}"

        comic_dir = os.path.join(OUTPUT_DIR, folder)
        os.makedirs(comic_dir, exist_ok=True)

        # 1. Regenerate text.txt transcript
        text_dest_path = os.path.join(comic_dir, "text.txt")
        full_searchable_content = (
            f"Title: {title}\n"
            f"Comic Number: {num}\n"
            f"Alt Text: {alt}\n"
            f"Transcript: {ocr_text}"
        )
        with open(text_dest_path, "w", encoding="utf-8") as f:
            f.write(full_searchable_content)

        # 2. Download Image Asset (only if it is a valid image file URL)
        downloaded_new = False
        if img_url:
            clean_url = img_url.split('?')[0].strip()
            ext = os.path.splitext(clean_url)[-1].lower()
            
            # Check if the URL is just a generic directory path (e.g. ending with '/comics/' or lacking a filename)
            is_directory_endpoint = clean_url.endswith("/comics/") or clean_url.endswith("/comics") or not ext
            
            if is_directory_endpoint:
                # Silently skip download for interactive comics that don't have static image CDN assets
                return True, num, title, False

            img_dest_path = os.path.join(comic_dir, f"{num}{ext}")

            # Download only if the image doesn't already exist to save bandwidth and time
            if not os.path.exists(img_dest_path):
                try:
                    # Added custom browser-mimicking headers to avoid 403 Forbidden responses
                    img_response = requests.get(img_url, headers=REQUEST_HEADERS, timeout=15)
                    if img_response.status_code == 200:
                        with open(img_dest_path, "wb") as f:
                            f.write(img_response.content)
                        downloaded_new = True
                    else:
                        print(f"\n⚠️ Warning: Got HTTP status {img_response.status_code} for comic #{num}")
                except Exception as e:
                    print(f"\n⚠️ Error downloading image for comic #{num}: {e}")
                
        return True, num, title, downloaded_new
    except Exception as e:
        print(f"\n❌ Error processing comic key {num_str}: {e}")
        return False, None, None, False

def main():
    if not os.path.exists(DB_FILE):
        print(f"❌ Error: Database file '{DB_FILE}' not found in the current directory.")
        print("Please make sure you run this script from the root folder where your database is stored.")
        return

    print(f"📖 Loading database index '{DB_FILE}'...")
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            database = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing database: {e}")
            return

    total_comics = len(database)
    print(f"✅ Loaded {total_comics} comic definitions. Starting multi-threaded recovery pool with {MAX_WORKERS} workers...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    restored_count = 0
    new_downloads = 0
    start_time = time.time()

    # We use ThreadPoolExecutor to perform concurrent downloads
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all jobs to the thread pool
            futures = {
                executor.submit(process_comic, num_str, data): num_str 
                for num_str, data in database.items()
            }

            for future in as_completed(futures):
                success, num, title, downloaded_new = future.result()
                if success:
                    restored_count += 1
                    if downloaded_new:
                        new_downloads += 1

                # Clean, single-line dynamic progress meter
                elapsed = time.time() - start_time
                rate = restored_count / elapsed if elapsed > 0 else 0
                remaining = (total_comics - restored_count) / rate if rate > 0 else 0
                
                # Format the status line text
                status_line = (
                    f"🔄 Progress: {restored_count}/{total_comics} ({restored_count/total_comics*100:.1f}%) "
                    f"| Restored: #{num if num else '?'}: {(title[:15] if title else '?')} "
                    f"| Speed: {rate:.1f} item/s "
                    f"| Est. Time: {remaining:.0f}s "
                    f"| New DLs: {new_downloads}"
                )
                # Pad the printed line to completely erase lingering text from previous lines
                print(f"\r{status_line:<115}", end="", flush=True)

        print(f"\n\n🎉 Success! Rebuilt all local directories under '/{OUTPUT_DIR}' in {time.time() - start_time:.1f}s.")
        print(f"📥 Recreated folder layout and downloaded {new_downloads} missing images!")

    except KeyboardInterrupt:
        print("\n\n🛑 Recovery paused by user. Folders generated up to this point remain saved.")

if __name__ == "__main__":
    main()