import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.repository import SupabaseRepository

def analyze_channel():
    print("📊 FETCHING ALGORITHMIC REPORT CARD...\n")
    repo = SupabaseRepository()
    
    # Fetch all evaluations
    response = repo.supabase.table('evaluations').select('*').execute()
    data = response.data
    
    if not data:
        print("❌ No evaluation data found.")
        return
        
    df = pd.DataFrame(data)
    
    # Filter to only look at trades that actually triggered (Ignore EXPIRED)
    df_active = df[df['status'] != 'EXPIRED'].copy()
    
    if df_active.empty:
        print("No active trades found to analyze.")
        return

    total_trades = len(df_active)
    
    # MFE is points gained. MAE is points lost. 
    avg_mfe = df_active['max_favorable_excursion'].mean()
    avg_mae = df_active['max_adverse_excursion'].mean()
    
    # Excursion Ratio: If this is under 1.0, the market goes against them harder than it goes for them.
    # To prevent division by zero, we use a tiny offset if MAE is exactly 0
    safe_mae = abs(avg_mae) if abs(avg_mae) > 0 else 0.01
    excursion_ratio = avg_mfe / safe_mae

    print("=================================================")
    print("📈 KATTALAN CHANNEL ANALYSIS REPORT")
    print("=================================================")
    print(f"Total Triggered Trades : {total_trades}")
    print(f"Average Max Favorable  : +{avg_mfe:.2f} points per trade (The Reward)")
    print(f"Average Max Adverse    : {avg_mae:.2f} points per trade (The Risk)")
    print("-------------------------------------------------")
    
    print(f"DIRECTIONAL EDGE RATIO : {excursion_ratio:.2f}")
    
    if excursion_ratio > 1.5:
        print("🟢 VERDICT: EXCELLENT EDGE. This channel accurately predicts massive breakouts.")
    elif excursion_ratio > 1.0:
        print("🟡 VERDICT: MODERATE EDGE. They pick the right direction, but risk/reward is tight.")
    else:
        print("🔴 VERDICT: FRAUD/GUESSING. The market moves against them more than it moves for them.")
    print("=================================================")

if __name__ == "__main__":
    analyze_channel()