"""
Vector Similarity Matcher for Knowledge Base & CBR
Uses TF-IDF + Cosine Similarity over incident symptoms and error vectors.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class VectorMatcher:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.articles: List[Dict[str, Any]] = []
        self.tfidf_matrix = None

    def index_articles(self, articles: List[Dict[str, Any]]) -> None:
        self.articles = articles
        if not articles:
            return

        corpus = []
        for a in articles:
            text = f"{a.get('title', '')} {a.get('primary_service', '')} {a.get('symptoms_summary', '')} {a.get('root_cause', '')} {' '.join(a.get('tags', []))}"
            corpus.append(text)

        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def find_similar_cases(self, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Finds top_k most similar historical incidents given an active incident's symptoms.
        """
        if not self.articles or self.tfidf_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query_text])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Rank indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0.05:  # Minimum relevance cutoff
                item = self.articles[idx].copy()
                item["similarity_score"] = round(score * 100, 1)
                results.append(item)

        return results
