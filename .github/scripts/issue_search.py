import os
import json
import re
import subprocess
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

    # Look for the query under the form field markdown header: "### What are you looking for?"
    pattern = r"### What are you looking for\?\s*\n+(.*?)(?=\n+###|$)"
    match = re.search(pattern, issue_body, re.DOTALL | re.IGNORECASE)
    
    if match and match.group(1).strip():
        query_str = match.group(1).strip()
    else:
        # Fallback: if form parsing fails, clean up the issue title
        title = issue.get("title", "")
        if title.lower().startswith("search:"):
            query_str = title[7:].strip()
        else:
            query_str = title.strip()

    return query_str, issue_number

def calculate_keyword_boost(query_str, title, alt, ocr_text):
    """Calculates a massive score boost based on exact keyword and phrase matches."""
    # 1. Clean punctuation from both the query and the comic text pools
    clean_query = re.sub(r'[^a-z0-9\s]', ' ', query_str.lower())
    query_words = [w for w in clean_query.split() if w not in STOP_WORDS and len(w) > 1]
    
    if not query_words:
        return 0.0

    # Remove punctuation from pools so exact quotes match perfectly
    title_pool = re.sub(r'[^a-z0-9\s]', ' ', title.lower())
    general_pool = re.sub(r'[^a-z0-9\s]', ' ', f"{alt} {ocr_text}".lower())
    
    matches = 0
    title_matches = 0

    # 2. Score individual words with basic plural stemming
    for word in query_words:
        singular = word[:-1] if word.endswith('s') else word
        
        # Check title pool with word boundaries
        if f" {word} " in f" {title_pool} " or (len(singular) > 2 and f" {singular} " in f" {title_pool} "):
            title_matches += 1
            matches += 1
        # Check general text pool with word boundaries
        elif f" {word} " in f" {general_pool} " or (len(singular) > 2 and f" {singular} " in f" {general_pool} "):
            matches += 1
            
    match_ratio = matches / len(query_words)
    
    # 3. Base Boost: Up to +0.40 for hitting all keywords (double the previous amount)
    boost = match_ratio * 0.40
    
    # 4. Title Bonus: Up to +0.30 extra for hitting title words specifically
    boost += (title_matches / len(query_words)) * 0.30
    
    # 5. Exact Phrase Bonus: Massive rocket boost for quoting a comic exactly
    raw_clean_phrase = " ".join(clean_query.split())
    if len(raw_clean_phrase) > 5:
        if raw_clean_phrase in title_pool:
            boost += 0.80  # Automatic top result for exact title match
        elif raw_clean_phrase in general_pool:
            boost += 0.60  # Automatic top result for exact transcript quote
            
    return boost

def main():
    # 1. Retrieve the query and issue number natively from the event context
    query_str, issue_number = parse_query_from_event()

    if not query_str:
        print("Error: No search query could be extracted.")
        with open("search_results.md", "w") as f:
            f.write("⚠️ Search query was empty. Please try again with a descriptive sentence!")
        return

    # 2. Rename the issue to the query using the GitHub CLI (gh)
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

    index_path = "xkcd_embeddings.json"
    if not os.path.exists(index_path):
        print(f"Error: Database index {index_path} not found.")
        with open("search_results.md", "w") as f:
            f.write("⚠️ The semantic search database is currently empty or rebuilding. Please try again later!")
        return

    # 3. Vectorize the extracted search query
    print(f"🧠 Encoding query: '{query_str}'")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_vector = model.encode(query_str)

    with open(index_path, "r", encoding="utf-8") as f:
        archive_index = json.load(f)

    # 4. Score all archive entries
    results = []
    for num, details in archive_index.items():
        # Prevent crashes if a comic entry doesn't have an embedding yet
        if "embedding" not in details:
            continue
            
        # Base Semantic Cosine Score (ranges from 0.0 to 1.0)
        semantic_score = cosine_similarity(query_vector, details["embedding"])
        
        # Calculate Keyword Match Boost (up to +0.20)
        title = details.get("title", "Untitled")
        alt = details.get("alt", "")
        ocr_text = details.get("ocr_text") or details.get("transcript") or ""
        
        keyword_boost = calculate_keyword_boost(query_str, title, alt, ocr_text)
        
        # Combined Hybrid Score (capped at 1.0)
        final_score = min(1.0, semantic_score + keyword_boost)
        
        # Safely determine the folder name (fallback to slug if missing)
        folder = details.get("folder")
        if not folder:
            folder = f"{num}_{slugify(title)}"
            
        results.append((
            final_score, 
            num, 
            title, 
            folder, 
            alt, 
            details.get("img_url", "")
        ))

    # Sort descending by our new Hybrid score
    results.sort(key=lambda x: x[0], reverse=True)

    # 5. Generate the markdown comment output
    comment_body = f"### 🔎 Hybrid Search Results for: *\"{query_str}\"*\n\n"
    comment_body += "Here are the top conceptual and keyword matches found in the archive:\n\n"
    
    # Take top 3 hits
    for score, num, title, folder, alt, img_url in results[:3]:
        match_percentage = score * 100
        # Give a visual indicator based on score strength
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

    # Write out for the workflow step to read
    with open("search_results.md", "w", encoding="utf-8") as f:
        f.write(comment_body)

if __name__ == "__main__":
    main()
