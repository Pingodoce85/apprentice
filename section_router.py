from rank_bm25 import BM25Okapi
import re

def tokenize(text):
    return re.findall(r"\w+", text.lower())

def route_question_to_section(question, toc):
    if not toc:
        return None
    titles = [item[0] for item in toc]
    pages = [item[1] for item in toc]
    corpus = [tokenize(title) for title in titles]
    bm25 = BM25Okapi(corpus)
    query_tokens = tokenize(question)
    scores = bm25.get_scores(query_tokens)
    best_idx = int(scores.argmax())
    best_score = scores[best_idx]
    if best_score < 2.0:
        return None
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:3]
    results = []
    for idx in top_indices:
        if scores[idx] < 2.0:
            continue
        start_page = pages[idx]
        if idx + 1 < len(pages):
            end_page = pages[idx + 1] - 1
        else:
            end_page = start_page + 10
        results.append({
            "title": titles[idx],
            "start_page": start_page,
            "end_page": end_page,
            "score": scores[idx]
        })
    return results if results else None
