import os
from dotenv import load_dotenv
from supabase import create_client, Client

# 1) load env vars
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 2) initialize the client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3) simple test: fetch zero jobs
response = supabase.from_("jobs").select("*").limit(1).execute()

if response.error:
    print("Error:", response.error)
else:
    print("Success! Sample row:", response.data)
