import json

with open("fanalca_knowledge_base.json", "r", encoding="utf-8") as f1, \
     open("fanalca_knowledge_base_final.json", "r", encoding="utf-8") as f2:
    base = json.load(f1)
    ext = json.load(f2)

urls = set()
merged = []
for d in base + ext:
    if d["url"] not in urls:
        urls.add(d["url"])
        merged.append(d)

with open("fanalca_knowledge_base_final.json", "w", encoding="utf-8") as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)

print(f"✅ Base final combinada con {len(merged)} páginas")
