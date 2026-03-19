import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseRepository:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY") 
        
        if not url or not key:
            raise ValueError("❌ Missing Supabase keys in .env file.")
            
        self.supabase: Client = create_client(url, key)

    def save_signal(self, signal):
        try:
            # Convert the Pydantic model to a dictionary
            data = signal.model_dump()
            
            # THE FIX: Swap 'signal_id' to 'id' for Supabase
            if 'signal_id' in data:
                data['id'] = data.pop('signal_id')
                
            # Convert datetime to string for PostgreSQL
            if 'issued_at' in data and data['issued_at']:
                data['issued_at'] = data['issued_at'].isoformat()
                
            # Execute the Upsert
            self.supabase.table("signals").upsert(data).execute()
        except Exception as e:
            raise Exception(f"Failed to save to Supabase: {e}")