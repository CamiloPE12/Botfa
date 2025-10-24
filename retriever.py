# retriever.py
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class FanalcaRetriever:
    def __init__(self, kb_path="fanalca_knowledge_base_final.json"):
        with open(kb_path, "r", encoding="utf-8") as f:
            self.docs = json.load(f)

        # Convertir cada texto en un vector
        self.corpus = [re.sub(r"\s+", " ", d["texto"]).strip() for d in self.docs]
        self.vectorizer = TfidfVectorizer(stop_words=None)
        self.tfidf = self.vectorizer.fit_transform(self.corpus)

    def search(self, query, top_k=4):
        qv = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self.tfidf)[0]
        idxs = sims.argsort()[::-1][:top_k]
        results = []
        for i in idxs:
            results.append({
                "url": self.docs[i]["url"],
                "titulo": self.docs[i].get("titulo", ""),
                "texto": self.docs[i]["texto"][:1500]  # recorta el texto
            })
        return results

    def build_context(self, query, top_k=4):
        hits = self.search(query, top_k)
        bloques = []
        for h in hits:
            bloques.append(f"[{h['titulo']}] {h['texto']} (Fuente: {h['url']})")
        contexto = "\n\n---\n\n".join(bloques)
        return contexto
