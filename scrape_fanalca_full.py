import os
import re
import json
import time
import fitz  # PyMuPDF
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag
from tqdm import tqdm
import tldextract

# ==========================================================
# 🌐 URLs base del sitio de Fanalca
# ==========================================================
BASE_URLS = [
    "https://fanalca.com/",
    "https://fanalca.com/nosotros/",
    "https://fanalca.com/nosotros/por-que-trabajar-en-fanalca/",
    "https://fanalca.com/sostenibilidad/",
    "https://fanalca.com/negocios/",
    "https://fanalca.com/negocios/honda-motocicletas/",
    "https://fanalca.com/negocios/honda-autos/",
    "https://fanalca.com/negocios/tubos-y-perfiles-de-acero/",
    "https://fanalca.com/negocios/autopartes/",
    "https://fanalca.com/negocios/ambiental/",
    "https://fanalca.com/negocios/fanalvias/",
    "https://fanalca.com/noticias/",
    "https://fanalca.com/contacto/",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FanalcaScraper/1.0; +https://fanalca.com)"
}

# ==========================================================
# 🧹 Función: limpiar texto del HTML
# ==========================================================
def limpiar_texto(html):
    soup = BeautifulSoup(html, "lxml")

    # Eliminar partes irrelevantes
    for tag in soup(["script", "style", "noscript", "footer", "nav", "form", "header", "svg"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ==========================================================
# 🧩 Función: comprobar dominio
# ==========================================================
def mismo_dominio(url, base="fanalca.com"):
    ext = tldextract.extract(url)
    return ext.registered_domain == "fanalca.com"

# ==========================================================
# 🧠 Scraper profundo (recorre enlaces hasta nivel 2)
# ==========================================================
def scrape_profundo(base_urls, max_depth=2):
    data = []
    visitados = set()

    def procesar(url, depth):
        url = urldefrag(url)[0]
        if url in visitados or depth > max_depth:
            return
        visitados.add(url)

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200 or "text/html" not in resp.headers.get("Content-Type", ""):
                return
            soup = BeautifulSoup(resp.text, "lxml")
            title = soup.title.string.strip() if soup.title else url
            text = limpiar_texto(resp.text)

            if len(text) > 300:
                data.append({"url": url, "titulo": title, "texto": text})
                print(f"[+] {url} ({len(text)} chars)")

            # Buscar enlaces internos
            for a in soup.find_all("a", href=True):
                next_url = urljoin(url, a["href"])
                if (
                    mismo_dominio(next_url)
                    and not any(ext in next_url for ext in [".jpg", ".png", ".svg", ".mp4", ".zip"])
                    and not next_url.endswith("#")
                ):
                    procesar(next_url, depth + 1)
            time.sleep(0.5)
        except Exception as e:
            print(f"[❌] Error en {url}: {e}")

    for u in tqdm(base_urls, desc="Raspando secciones"):
        procesar(u, 0)

    return data

# ==========================================================
# 📄 Extraer texto de PDFs encontrados en el sitio
# ==========================================================
def extraer_texto_pdf(url, carpeta="pdfs"):
    os.makedirs(carpeta, exist_ok=True)
    nombre = url.split("/")[-1]
    ruta = os.path.join(carpeta, nombre)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        with open(ruta, "wb") as f:
            f.write(resp.content)
        doc = fitz.open(ruta)
        texto = ""
        for pagina in doc:
            texto += pagina.get_text()
        doc.close()
        return re.sub(r"\s+", " ", texto).strip()
    except Exception as e:
        print(f"[PDF Error] {url}: {e}")
        return ""

def scrape_pdfs(base_urls):
    data = []
    for base in base_urls:
        try:
            resp = requests.get(base, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.lower().endswith(".pdf"):
                    pdf_url = urljoin(base, href)
                    texto = extraer_texto_pdf(pdf_url)
                    if len(texto) > 300:
                        data.append({
                            "url": pdf_url,
                            "titulo": "Documento PDF",
                            "texto": texto
                        })
                        print(f"[PDF] {pdf_url} ({len(texto)} chars)")
        except Exception as e:
            print(f"[PDF Scan Error] {base}: {e}")
    return data

# ==========================================================
# 🚀 MAIN
# ==========================================================
if __name__ == "__main__":
    print("🚀 Iniciando scraping profundo de Fanalca...\n")

    html_data = scrape_profundo(BASE_URLS, max_depth=2)
    pdf_data = scrape_pdfs(BASE_URLS)

    # Fusionar datos sin duplicados
    todo = html_data + pdf_data
    urls = set()
    final_data = []
    for d in todo:
        if d["url"] not in urls:
            urls.add(d["url"])
            final_data.append(d)

    with open("fanalca_knowledge_base_final.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Base final guardada: fanalca_knowledge_base_final.json")
    print(f"📄 Total de documentos: {len(final_data)}")
