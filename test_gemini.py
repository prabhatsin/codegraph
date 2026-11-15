import os
from google import genai
from dotenv import load_dotenv
load_dotenv(override=True)
for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
    v = os.environ.get(name)
    if v is None:
        print(f"{name}: not set")
        continue
    bad = any(c in v for c in [" ", '"', "'", "\n"])
    print(f"{name}: set, length {len(v)}, starts {v[:4]}, spaces/quotes: {bad}")

client = genai.Client()
res = client.models.embed_content(model="gemini-embedding-001", contents=["hello world"])
print("OK, embedding size:", len(res.embeddings[0].values))