import os
import json
import re
import subprocess
import numpy as np
from sentence_transformers import SentenceTransformer

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
            
        score = cosine_similarity(query_vector, details["embedding"])
        
        # Safely determine the folder name (fallback to slug if missing)
        folder = details.get("folder")
        if not folder:
            folder = f"{slugify(details.get('title', 'untitled'))}_{num}"
            
        results.append((
            score, 
            num, 
            details.get("title", "Untitled"), 
            folder, 
            details.get("alt", ""), 
            details.get("img_url", "")
        ))

    # Sort descending by similarity score
    results.sort(key=lambda x: x[0], reverse=True)

    # 5. Generate the markdown comment output
    comment_body = f"### 🔎 Search Results for: *\"{query_str}\"*\n\n"
    comment_body += "Here are the top conceptual matches found:\n\n"
    
    # Take top 3 hits
    for score, num, title, folder, alt, img_url in results[:3]:
        match_percentage = score * 100
        # Give a visual warning indicator if context matching is low
        indicator = "🟢" if match_percentage > 45 else "🟡"
        
        comment_body += (
            f"#### {indicator} **[{match_percentage:.1f}% Match]** "
            f"[{title} (#{num})](https://github.com/ilim-cell/.github/tree/main/xkcd/{folder})\n"
            f"> *\"{alt}\"*\n\n"
        )
        if img_url:
            comment_body += f"<img src='{img_url}' alt='{title}' width='350' />\n\n"
            
        comment_body += "---\n"
        
    comment_body += "\n\n---\n"
    comment_body += "🔒 **This thread has been locked to prevent spam.** If this recommendation was helpful, please click the **Close issue** button below! ✨"

    # Write out for the workflow step to read
    with open("search_results.md", "w", encoding="utf-8") as f:
        f.write(comment_body)

if __name__ == "__main__":
    main()