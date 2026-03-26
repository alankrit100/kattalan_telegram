import pandas as pd
import os

# Create the data folder if it doesn't exist
os.makedirs("data", exist_ok=True)

# Create 3 minutes of mock market data
data = {
    "timestamp": [
        "2023-01-01 09:59:00", 
        "2023-01-01 10:00:00", 
        "2023-01-01 10:01:00"
    ],
    "symbol": ["BANKNIFTY", "BANKNIFTY", "BANKNIFTY"],
    "open": [48000.0, 48010.0, 48050.0],
    "high": [48020.0, 48060.0, 48110.0],
    "low": [47990.0, 48000.0, 48040.0],
    "close": [48010.0, 48050.0, 48100.0]
}

pd.DataFrame(data).to_csv("data/live_data.csv", index=False)
print("Success! data/live_data.csv created.")