from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

for m in client.models.list():
    methods = getattr(m, "supported_generation_methods", []) or getattr(m, "supported_actions", [])
    print(f"Name: {m.name} | Methods: {methods}")

#to test out