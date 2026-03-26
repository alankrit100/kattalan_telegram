import asyncio
import websockets
import json

async def test_audit():
    uri = "ws://127.0.0.1:8000/api/ws/audit"
    
    # We are pretending to be your Svelte frontend here
    payload = {
        "channel_name": "Trade With Logic (Index + Stock)", 
        "timeframe": "1_month"
    }

    async with websockets.connect(uri) as websocket:
        print("🔗 Connected to Kattalan Engine WebSocket...")
        
        # 1. Send the trigger
        await websocket.send(json.dumps(payload))
        
        # 2. Listen to the live stream
        try:
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                print(f"[{data.get('progress')}%] {data.get('status')}")
                
                # If we get the final results payload, the audit is done
                if "results" in data:
                    print("\n✅ FINAL AUDIT RESULTS:")
                    print(json.dumps(data["results"], indent=2))
                    break
                    
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket closed by server.")

if __name__ == "__main__":
    asyncio.run(test_audit())