import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    models = client.models.list()
    ids = [m.id for m in models.data]
    with open("models.txt", "w") as f:
        f.write("\n".join(ids))
    print("Models written to models.txt")
except Exception as e:
    print(f"Error: {e}")
