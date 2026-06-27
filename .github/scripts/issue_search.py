import os
import json
import re
import numpy as np
from sentence_transformers import SentenceTransformer

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def main():
    # 1. Fetch query passed from the GitHub Action environment variable
    query_str = os.getenv("SEARCH_QUERY", "").strip()
    if not query_str:
        print("Error: No search query provided.")
        return

    index_path = "xkcd_embeddings.json"
    if not os.path.exists(index_path):
        print(f"Error: Database index {index_path} not found.")
        with open("search_results.md", "w") as f:
            f.write("⚠️ The semantic search database is currently empty or rebuilding. Please try again later!")
        return

    # 2. Vectorize the user's issue text
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_vector = model.encode(query_str)

    with open(index_path, "r", encoding="utf-8") as f:
        archive_index = json.load(f)

    # 3. Score all archive entries
    results = []
    for num, details in archive_index.items():
        score = cosine_similarity(query_vector, details["embedding"])
        results.append((score, num, details["title"], details["folder"], details["alt"]))

    # Sort descending by similarity score
    results.sort(key=lambda x: x[0], reverse=True)

    # 4. Generate the markdown comment output
    comment_body = f"### 🔎 Semantic Search Results for: *\"{query_str}\"*\n\n"
    comment_body += "Here are the top conceptual matches found in the archive:\n\n"
    
    # Take top 3 hits
    for score, num, title, folder, alt in results[:3]:
        match_percentage = score * 100
        # Give a visual warning indicator if context matching is quite low
        indicator = "🟢" if match_percentage > 45 else "🟡"
        
        comment_body += (
            f"#### {indicator} **[{match_percentage:.1f}% Match]** "
            f"[{title} (#{num})](https://github.com/ilim-cell/.github/tree/main/xkcd/{folder})\n"
            f"> *\"{alt}\"*\n\n"
        )
        
    comment_body += "---\n*🤖 This lookup was processed completely serverless using sentence-transformers on a GitHub runner.*"

    # Write out for the workflow step to read
    with open("search_results.md", "w", encoding="utf-8") as f:
        f.write(comment_body)

if __name__ == "__main__":
    main()
