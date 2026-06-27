import os
import json
import re
import subprocess
import requests
import numpy as np
from sentence_transformers import SentenceTransformer

# Standard common words to filter out during keyword matching
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", 
    "with", "by", "about", "against", "between", "into", "through", "during", 
    "before", "after", "above", "below", "of", "up", "down", "out", "off", 
    "over", "under", "again", "further", "then", "once", "here", "there", 
    "when", "where", "why", "how", "all", "any", "both", "each", "few", 
    "more", "most", "other", "some", "such", "no", "nor", "not", "only", 
    "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", 
    "just", "don", "should", "now"
}

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def slugify(text):
    """Generates a clean directory-safe name from comic titles."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s-]+', '_', text)
    return text.strip('_')

def parse_query_from_event():
    """Reads the GitHub Event JSON payload to extract and parse the query."""
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path or not os.path.exists(event_path):
        print("Warning: GITHUB_EVENT_PATH not found.")
        return "", None

    with open(event_path, "r", encoding="utf-8") as f:
        event_data = json.load(f)

    issue = event_data.get("issue", {})
    issue_body = issue.get("body", "")
    issue_number = issue.get("number")

    # Look for the query under the form field markdown header
    pattern = r"### What are you looking for\?\s*\n+(.*?)(?=\n+###|$)"
    match = re.search(pattern, issue_body, re.DOTALL | re.IGNORECASE)
    
    if match and match.group(1).strip():
        query_str = match.group(1).strip()
    else:
        title = issue.get("title", "")
        query_str = title[7:].strip() if title.lower().startswith("search:") else title.strip()

    return query_str, issue_number

def calculate_keyword_boost(query_str, title, alt, ocr_text):
    """Calculates a massive score boost based on exact keyword and phrase matches."""
    clean_query = re.sub(r'[^a-z0-9\s]', ' ', query_str.lower())
    query_words = [w for w in clean_query.split() if w not in STOP_WORDS and len(w) > 1]
    
    if not query_words:
        return 0.0

    # Clean punctuation and build sets for bulletproof word boundary checking
    title_pool = re.sub(r'[^a-z0-9\s]', ' ', title.lower())
    general_pool = re.sub(r'[^a-z0-9\s]', ' ', f"{alt} {ocr_text}".lower())
    
    title_set = set(title_pool.split())
    general_set = set(general_pool.split())

    # Build singular stemming sets for plural flexibility
    title_singulars = {w[:-1] if w.endswith('s') else w for w in title_set}
    general_singulars = {w[:-1] if w.endswith('s') else w for w in general_set}

    matches, title_matches = 0, 0

    for word in query_words:
        singular = word[:-1] if word.endswith('s') else word
        
        # Check Title Set
        if word in title_set or singular in title_singulars:
            title_matches += 1
            matches += 1
        # Check General Body Set
        elif word in general_set or singular in general_singulars:
            matches += 1
            
    match_ratio = matches / len(query_words)
    boost = match_ratio * 0.40
    boost += (title_matches / len(query_words)) * 0.30
    
    # Exact phrase checks (handles raw quotes smoothly)
    raw_clean_phrase = " ".join(clean_query.split())
    if len(raw_clean_phrase) > 5:
        if raw_clean_phrase in " ".join(title_pool.split()):
            boost += 0.80  
        elif raw_clean_phrase in " ".join(general_pool.split()):
            boost += 0.60  
            
    return boost

def rename_issue(issue_number, query_str):
    """Renames the GitHub issue to the search query."""
    if os.getenv("GH_TOKEN") and issue_number:
        try:
            print(f"Updating issue #{issue_number} title to: '{query_str}'")
            subprocess.run(
                ["gh", "issue", "edit", str(issue_number), "--title", query_str],
                check=True,
                env=os.environ
            )
        except Exception as e:
            print(f"Warning: Failed to auto-rename issue via CLI: {e}")

def generate_query_vector(query_str):
    """Encodes the search query into a semantic vector."""
    print(f"🧠 Encoding query: '{query_str}'")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    return model.encode(query_str)

def score_comics(archive_index, query_str, query_vector):
    """Evaluates all comics against the hybrid scoring criteria."""
    results = []
    for num, details in archive_index.items():
        if "embedding" not in details:
            continue
            
        semantic_score = cosine_similarity(query_vector, details["embedding"])
        
        title = details.get("title", "Untitled")
        alt = details.get("alt", "")
        ocr_text = details.get("ocr_text") or details.get("transcript") or ""
        
        # Live Recovery Fallback: Grab the real transcript if the database text is a placeholder!
        is_placeholder = ocr_text.strip().startswith("Sample transcript or OCR output")
        if not ocr_text.strip() or is_placeholder:
            try:
                res = requests.get(f"https://xkcd.com/{num}/info.0.json", timeout=3)
                if res.status_code == 200:
                    api_data = res.json()
                    official_transcript = api_data.get("transcript", "")
                    if official_transcript:
                        ocr_text = official_transcript
            except Exception:
                pass # Continue with whatever local data is available on timeout

        keyword_boost = calculate_keyword_boost(query_str, title, alt, ocr_text)
        final_score = min(1.0, semantic_score + keyword_boost)
        
        folder = details.get("folder") or f"{num}_{slugify(title)}"
            
        results.append((final_score, num, title, folder, alt, details.get("img_url", "")))

    results.sort(key=lambda x: x[0], reverse=True)
    return results

def generate_markdown(query_str, results):
    """Formats the sorted results into a markdown response block."""
    comment_body = f"### 🔎 Hybrid Search Results for: *\"{query_str}\"*\n\n"
    comment_body += "Here are the top conceptual and keyword matches found in the archive:\n\n"
    
    for score, num, title, folder, alt, img_url in results[:3]:
        match_percentage = score * 100
        indicator = "🟢" if match_percentage > 48 else "🟡"
        
        comment_body += (
            f"#### {indicator} **[{match_percentage:.1f}% Match]** "
            f"[{title} (#{num})](https://github.com/ilim-cell/.github/tree/main/xkcd/{folder})\n"
            f"> *\"{alt}\"*\n\n"
        )
        if img_url:
            comment_body += f"<img src='{img_url}' alt='{title}' width='350' />\n\n"
            
        comment_body += "---\n"
        
    comment_body += "\n*🤖 This lookup was processed serverless using a hybrid semantic vector + keyword overlap search strategy on a GitHub runner.*"
    comment_body += "\n\n---\n"
    comment_body += "🔒 **This thread has been locked to prevent spam.** If this recommendation was helpful, please click the **Close issue** button below! ✨"
    
    return comment_body

def write_error(message):
    """Helper to write error outputs to markdown."""
    print(f"Error: {message}")
    with open("search_results.md", "w", encoding="utf-8") as f:
        f.write(f"⚠️ {message}")

def main():
    """Main execution pipeline."""
    # 1. Parse Data
    query_str, issue_number = parse_query_from_event()
    if not query_str:
        return write_error("Search query was empty. Please try again with a descriptive sentence!")

    # 2. Rename Issue
    rename_issue(issue_number, query_str)

    # 3. Load Database
    index_path = "xkcd_embeddings.json"
    if not os.path.exists(index_path):
        return write_error("The semantic search database is currently empty or rebuilding. Please try again later!")

    with open(index_path, "r", encoding="utf-8") as f:
        archive_index = json.load(f)

    # 4. Generate Vectors & Calculate Scores
    query_vector = generate_query_vector(query_str)
    results = score_comics(archive_index, query_str, query_vector)

    # 5. Format & Output
    comment_body = generate_markdown(query_str, results)
    with open("search_results.md", "w", encoding="utf-8") as f:
        f.write(comment_body)

if __name__ == "__main__":
    main()
