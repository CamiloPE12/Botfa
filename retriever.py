# retriever.py
import json
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HR_SYNONYMS = [
    "contratación", "contratacion", "contratar", "selección", "seleccion",
    "rrhh", "recursos humanos", "talento", "talento humano",
    "trabaja con nosotros", "trabajar", "empleo", "vacante", "vacantes",
    "oferta laboral", "ofertas laborales", "postular", "postulación",
    "hoja de vida", "hv", "curriculum", "currículum", "cv"
]

class FanalcaRetriever:
    def __init__(self, kb_path="fanalca_knowledge_base_final.json"):
        with open(kb_path, "r", encoding="utf-8") as f:
            self.docs = json.load(f)

        # Normalizar corpus
        self.corpus = [re.sub(r"\s+", " ", d.get("texto", "")).strip() for d in self.docs]

        # n-gramas (1,2) mejora frases tipo "trabaja con nosotros"
        self.vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2))
        self.tfidf = self.vectorizer.fit_transform(self.corpus)

    def _expand_query(self, query: str) -> str:
        q = query.lower()
        if any(k in q for k in HR_SYNONYMS):
            # Añade sinónimos para subir el recall
            q += " " + " ".join(HR_SYNONYMS)
        return q

    def search(self, query, top_k=4, min_sim=0.02):
        q_expanded = self._expand_query(query)
        qv = self.vectorizer.transform([q_expanded])
        sims = cosine_similarity(qv, self.tfidf)[0]
        idxs = sims.argsort()[::-1]

        results = []
        for i in idxs:
            if sims[i] < min_sim:
                continue
            results.append({
                "url": self.docs[i].get("url", ""),
                "titulo": self.docs[i].get("titulo", ""),
                "texto": self.docs[i].get("texto", "")[:1500],
                "score": float(sims[i])
            })
            if len(results) >= top_k:
                break
        return results

    def build_context(self, query, top_k=4):
        hits = self.search(query, top_k=top_k)
        if not hits:
            return ""
        bloques = []
        for h in hits:
            titulo = f"[{h['titulo']}]" if h.get("titulo") else ""
            url = f"(Fuente: {h['url']})" if h.get("url") else ""
            bloques.append(f"{titulo} {h['texto']} {url}".strip())
        contexto = "\n\n---\n\n".join(bloques)
        return contexto
