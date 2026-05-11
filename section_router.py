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
    if best_score < 0.5:
        return None
    start_page = pages[best_idx]
    if best_idx + 1 < len(pages):
        end_page = pages[best_idx + 1] - 1
    else:
        end_page = start_page + 10
    return {
        "title": titles[best_idx],
        "start_page": start_page,
        "end_page": end_page,
        "score": best_score
    }
