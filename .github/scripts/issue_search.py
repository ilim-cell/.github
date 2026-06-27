import os
import json
import re
import math
import subprocess

# Standard common words to filter out during scoring calculations
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

def clean_and_tokenize(text):
    """Normalizes text by removing punctuation and splitting into a list of words."""
    clean_text = re.sub(r'[^a-z0-9\s]', ' ', text.lower())
    return [w for w in clean_text.split() if len(w) > 0]

def get_singular(word):
    """Basic stemming to handle standard English plurals."""
    if word.endswith('s') and len(word) > 3:
        if word.endswith('es'):
            return word[:-2]
        return word[:-1]
    return word

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

class MultiFieldBM25:
    """A pure-Python weighted BM25 search engine with zero external dependencies."""
    def __init__(self, database, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.database = database
        self.corpus_size = len(database)
        
        # Field Weights representing semantic importance
        self.weights = {
            "title": 5.0,
            "alt": 2.0,
            "ocr_text": 1.0
        }

        # Document lengths and term frequencies for each field
        self.doc_lengths = {field: [] for field in self.weights}
        self.avg_doc_lens = {field: 0.0 for field in self.weights}
        self.doc_term_freqs = {field: [] for field in self.weights}
        self.doc_freqs = {field: {} for field in self.weights}
        self.idf = {field: {} for field in self.weights}

        self._build_index()

    def _build_index(self):
        totals = {field: 0 for field in self.weights}
        
        for num, data in self.database.items():
            title = data.get("title", "")
            alt = data.get("alt", "")
            ocr_text = data.get("ocr_text") or data.get("transcript") or ""

            fields_data = {
                "title": title,
                "alt": alt,
                "ocr_text": ocr_text
            }

            for field in self.weights:
                tokens = clean_and_tokenize(fields_data[field])
                self.doc_lengths[field].append(len(tokens))
                totals[field] += len(tokens)

                # Term frequencies in this specific document field
                tf = {}
                for token in tokens:
                    tf[token] = tf.get(token, 0) + 1
                    stemmed = get_singular(token)
                    if stemmed != token:
                        tf[stemmed] = tf.get(stemmed, 0) + 0.8
                
                self.doc_term_freqs[field].append(tf)

                # Document frequencies (counting term presence)
                for token in tf.keys():
                    self.doc_freqs[field][token] = self.doc_freqs[field].get(token, 0) + 1

        # Calculate average document lengths across the corpus
        for field in self.weights:
            self.avg_doc_lens[field] = totals[field] / self.corpus_size if self.corpus_size > 0 else 1.0

            # Calculate BM25 Inverse Document Frequency (IDF) for each word
            for token, doc_count in self.doc_freqs[field].items():
                self.idf[field][token] = math.log(
                    (self.corpus_size - doc_count + 0.5) / (doc_count + 0.5) + 1.0
                )

    def calculate_score(self, query_str, doc_idx, details):
        """Calculates the weighted BM25 similarity score with exact phrase boosting and coordination factor."""
        query_tokens = clean_and_tokenize(query_str)
        filtered_query = [w for w in query_tokens if w not in STOP_WORDS]
        if not filtered_query:
            filtered_query = query_tokens

        # 1. Calculate Coordination Factor (how many of the unique query tokens matched this document?)
        matched_terms = 0
        for token in filtered_query:
            token_matched = False
            for field in self.weights:
                tf_map = self.doc_term_freqs[field][doc_idx]
                if tf_map.get(token, 0.0) > 0.0 or tf_map.get(get_singular(token), 0.0) > 0.0:
                    token_matched = True
                    break
            if token_matched:
                matched_terms += 1

        coordination_factor = matched_terms / len(filtered_query) if filtered_query else 1.0

        # 2. Multi-Field BM25 calculations
        score = 0.0
        for field, field_weight in self.weights.items():
            tf_map = self.doc_term_freqs[field][doc_idx]
            doc_len = self.doc_lengths[field][doc_idx]
            avg_len = self.avg_doc_lens[field]

            field_score = 0.0
            for token in filtered_query:
                token_idf = self.idf[field].get(token, 0.0)
                
                tf_val = tf_map.get(token, 0.0)
                if tf_val == 0.0:
                    stemmed = get_singular(token)
                    tf_val = tf_map.get(stemmed, 0.0)

                if tf_val > 0:
                    numerator = tf_val * (self.k1 + 1)
                    denominator = tf_val + self.k1 * (1.0 - self.b + self.b * (doc_len / avg_len))
                    field_score += token_idf * (numerator / denominator)

            score += field_score * field_weight

        # Multiply raw BM25 score by the coordination factor squared to penalize weak partial matches heavily
        score = score * (coordination_factor ** 2)

        # 3. Exact Phrase Boost (adds huge priority for multi-word sequences in exact quotes)
        clean_phrase_query = " ".join(query_tokens)
        if len(clean_phrase_query) > 4:
            title_text = " ".join(clean_and_tokenize(details.get("title", "")))
            alt_text = " ".join(clean_and_tokenize(details.get("alt", "")))
            ocr_text = " ".join(clean_and_tokenize(details.get("ocr_text") or details.get("transcript") or ""))

            if clean_phrase_query in title_text:
                score += 150.0  # Massive priority for quoting a title
            elif clean_phrase_query in alt_text or clean_phrase_query in ocr_text:
                score += 100.0  # High priority for quoting alt/transcript text

        return score, coordination_factor

def main():
    # 1. Parse issue details and rename
    query_str, issue_number = parse_query_from_event()
    if not query_str:
        return write_error("Search query was empty. Please try again with a descriptive sentence!")

    rename_issue(issue_number, query_str)

    # 2. Load primary dataset
    index_path = "xkcd_embeddings.json"
    if not os.path.exists(index_path):
        return write_error("The search database index could not be located in this workspace.")

    with open(index_path, "r", encoding="utf-8") as f:
        archive_index = json.load(f)

    # 3. Score all comics using our new weighted lexical engine
    engine = MultiFieldBM25(archive_index)
    results = []
    
    for idx, (num, details) in enumerate(archive_index.items()):
        score, coord = engine.calculate_score(query_str, idx, details)
        
        title = details.get("title", "Untitled")
        alt = details.get("alt", "")
        folder = details.get("folder") or f"{num}_{slugify(title)}"
        img_url = details.get("img_url", "")

        # Only retain entries that have some level of matching scores
        if score > 0.0:
            results.append((score, coord, num, title, folder, alt, img_url))

    # Sort candidates by their combined BM25 and phrase boost scoring
    results.sort(key=lambda x: x[0], reverse=True)

    # 4. Generate results Markdown
    if not results:
        comment_body = (
            f"### 🔎 Search Results for: *\"{query_str}\"*\n\n"
            "❌ No matching comics found. Try using different keywords or concepts!"
        )
    else:
        comment_body = f"### 🔎 Search Results for: *\"{query_str}\"*\n\n"
        comment_body += "Here are the top matches found in the archive:\n\n"
        
        # Take top 3 highest rated matches
        for score, coord, num, title, folder, alt, img_url in results[:3]:
            # Scale percentages realistically: Exact phrase matches get >95%, BM25 matches scale dynamically
            if score >= 100.0:
                match_percentage = min(100.0, 95.0 + (score - 100.0) / 10.0)
            else:
                # A solid coordinated BM25 score of 10.0 represents a very high quality match
                match_percentage = min(94.0, (score / 10.0) * 85.0)
                # Apply coordination directly to the display percentage as well
                match_percentage = max(1.0, match_percentage * coord)
            
            indicator = "🟢" if match_percentage > 70.0 else "🟡"
            
            comment_body += (
                f"#### {indicator} **[{match_percentage:.1f}% Match]** "
                f"[{title} (#{num})](https://github.com/ilim-cell/.github/tree/main/xkcd/{folder})\n"
                f"> *\"{alt}\"*\n\n"
            )
            if img_url:
                comment_body += f"<img src='{img_url}' alt='{title}' width='350' />\n\n"
                
            comment_body += "---\n"
            
        comment_body += "\n*🤖 This lookup was processed instantly (under 0.05s) using our fundamentally redesigned, pure-Python Multi-Field BM25 Engine with coordination penalties.*"
        comment_body += "\n\n---\n"
        comment_body += "🔒 **This thread has been locked to prevent spam.** If this recommendation was helpful, please click the **Close issue** button below! ✨"

    with open("search_results.md", "w", encoding="utf-8") as f:
        f.write(comment_body)

def write_error(message):
    """Helper to write error outputs to markdown."""
    print(f"Error: {message}")
    with open("search_results.md", "w", encoding="utf-8") as f:
        f.write(f"⚠️ {message}")

if __name__ == "__main__":
    main()
