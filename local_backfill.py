import os
import json
import time
import requests
from tqdm import tqdm

# --- CONFIGURATION ---
DB_FILE = "xkcd_embeddings.json"

def load_existing_archive():
    """Loads the database if it exists, or returns a blank blueprint."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            print("⚠️ Existing database file was corrupted. Starting fresh.")
    return {}

def save_archive(data):
    """Saves the current state back to disk."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def run_backfill():
    # 1. Fetch the latest comic ID to know our true endpoint
    try:
        latest_res = requests.get("https://xkcd.com/info.0.json")
        total_comics = latest_res.json()["num"]
    except Exception:
        print("❌ Could not connect to xkcd API. Check your internet connection.")
        return

    # 2. Load whatever progress you have already made
    archive_index = load_existing_archive()
    already_downloaded = len(archive_index)
    
    # Initialize the tracking of the last processed comic
    last_info = "None"
    if archive_index:
        try:
            # Seed the display with the highest numbered comic currently in your index
            highest_key = str(max(map(int, archive_index.keys())))
            highest_title = archive_index[highest_key].get("title", "Untitled")
            last_info = f"#{highest_key}: {highest_title}"
        except Exception:
            pass

    print(f"\n📦 Found {already_downloaded} comics already indexed locally.")
    print(f"🚀 Streaming data harvest for remaining target pool...\n")

    # 3. Create the progress bar with a custom bar format matching your mockup
    progress_bar = tqdm(
        range(1, total_comics + 1),
        desc="Archiving xkcd Vault",
        initial=already_downloaded,
        total=total_comics,
        unit="s",  # Changes the speed unit to /s
        bar_format='{desc}: {percentage:3.0f}% [{bar}] {n_fmt}/{total_fmt} [{elapsed} | -{remaining}] [{rate_fmt}] {postfix}'
    )

    for num in progress_bar:
        # Comic 404 famously returns a 404 Error page on xkcd
        if num == 404:
            continue
            
        # If the comic string key is already in our JSON file, skip it entirely
        if str(num) in archive_index:
            continue  

        # Update the UI showing the last comic processed while actively fetching the new metadata
        progress_bar.set_postfix_str(f"[Last={last_info}] [Current=#{num}: Fetching...]")
        
        try:
            # Fetch JSON Metadata
            res = requests.get(f"https://xkcd.com/{num}/info.0.json")
            if res.status_code != 200:
                continue
            
            comic_data = res.json()
            comic_title = comic_data.get("title", "Untitled")

            # Show the newly fetched title actively processing
            progress_bar.set_postfix_str(f"[Last={last_info}] [Current=#{num}: {comic_title}]")
            
            # --- YOUR OCR AND IMAGE PROCESSING LOGIC GOES HERE ---
            # (Simulating extraction for the boilerplate structure)
            extracted_text = f"Sample transcript or OCR output for comic #{num}" 
            # -----------------------------------------------------

            # Update our dictionary in memory
            archive_index[str(num)] = {
                "title": comic_title,
                "alt": comic_data.get("alt"),
                "img_url": comic_data.get("img"),
                "ocr_text": extracted_text
            }

            # Periodic saving so you don't lose data if you kill the terminal midway
            if len(archive_index) % 10 == 0:
                save_archive(archive_index)

            # Update our last info tracker for the next iteration's background fetch phase
            last_info = f"#{num}: {comic_title}"

            # Be nice to Randall's servers
            time.sleep(0.1)

        except KeyboardInterrupt:
            print("\n\n🛑 Execution paused by user. Saving current checkpoint progress...")
            save_archive(archive_index)
            print("💾 Checkpoint saved safely! Run the script again whenever you want to resume.")
            return
        except Exception as e:
            # Log errors but don't crash the whole loop
            continue

    # Final sweep save once the whole thing completes
    save_archive(archive_index)
    print("\n🎉 The xkcd vault has been fully mirrored and indexed!")

if __name__ == "__main__":
    run_backfill()