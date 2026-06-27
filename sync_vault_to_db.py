import os
import json

DB_FILE = "xkcd_embeddings.json"
VAULT_DIR = "xkcd"

def main():
    if not os.path.exists(DB_FILE):
        print(f"❌ Error: {DB_FILE} not found.")
        return
        
    print("📖 Loading master database...")
    with open(DB_FILE, "r", encoding="utf-8") as f:
        database = json.load(f)

    print("🔄 Syncing rich transcripts from local vault folders...")
    synced_count = 0

    # Scan the local /xkcd directories
    for folder_name in os.listdir(VAULT_DIR):
        folder_path = os.path.join(VAULT_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue
            
        # Extract the comic number from the folder name (e.g., "327_exploits_of_a_mom" -> "327")
        parts = folder_name.split("_")
        num_str = parts[0]
        
        text_file_path = os.path.join(folder_path, "text.txt")
        if os.path.exists(text_file_path):
            with open(text_file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Extract the transcript line from text.txt
            transcript_content = ""
            for line in lines:
                if line.startswith("Transcript:"):
                    transcript_content = line.replace("Transcript:", "").strip()
                    break
            
            # If we found a real transcript that isn't a placeholder
            if transcript_content and not transcript_content.startswith("Sample transcript or OCR output"):
                if num_str in database:
                    # Update database text
                    database[num_str]["ocr_text"] = transcript_content
                    # DELETE the old placeholder embedding so the generator knows to rebuild it!
                    if "embedding" in database[num_str]:
                        del database[num_str]["embedding"]
                    synced_count += 1

    # Save the cleaned database back to disk
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(database, f, indent=4)

    print(f"✅ Successfully synced {synced_count} real transcripts into '{DB_FILE}' and cleared outdated embeddings!")
    print("\n👉 Next Step: Run 'python generate_embeddings.py' to generate perfect new vectors!")

if __name__ == "__main__":
    main()