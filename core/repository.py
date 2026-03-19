import os
from dotenv import load_dotenv
from supabase import create_client, Client
from core.schemas import Signal, EvaluationResult

# Load the .env file
load_dotenv()

class SupabaseRepository:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("FATAL: Missing SUPABASE_URL or SUPABASE_KEY in .env file.")
        
        self.supabase: Client = create_client(url, key)

    def upsert_signal(self, signal: Signal):
        """Inserts a new signal, or updates it if channel_id + message_id already exists."""
        data = signal.model_dump()
        
        # Convert Python datetime to ISO format string for Postgres
        data['issued_at'] = data['issued_at'].isoformat()
        
        # UPSERT logic: If there's a conflict on the unique constraint, update the row
        response = self.supabase.table('signals').upsert(
            data, on_conflict='channel_id,message_id'
        ).execute()
        
        return response

    def upsert_evaluation(self, eval_result: EvaluationResult):
        """Inserts or updates the math evaluation tied to the signal."""
        data = eval_result.model_dump()
        
        # Convert datetimes if they exist
        if data.get('entry_time'): 
            data['entry_time'] = data['entry_time'].isoformat()
        if data.get('exit_time'): 
            data['exit_time'] = data['exit_time'].isoformat()
            
        # UPSERT logic based on the unique signal_id
        response = self.supabase.table('evaluations').upsert(
            data, on_conflict='signal_id'
        ).execute()
        
        return response