import os
import webbrowser
from dotenv import load_dotenv
from fyers_apiv3 import fyersModel

# Load credentials from .env
load_dotenv()

client_id = os.environ.get("FYERS_CLIENT_ID")
secret_key = os.environ.get("FYERS_SECRET_KEY")
redirect_uri = os.environ.get("FYERS_REDIRECT_URI")

if not all([client_id, secret_key, redirect_uri]):
    raise ValueError("FATAL: Missing Fyers credentials in .env file.")

def generate_daily_token():
    session = fyersModel.SessionModel(
        client_id=client_id,
        secret_key=secret_key,
        redirect_uri=redirect_uri,
        response_type="code",
        grant_type="authorization_code"
    )

    # 1. Generate the login link
    auth_link = session.generate_authcode()
    print("\n" + "="*50)
    print("ACTION REQUIRED:")
    print("1. Your browser will open. Log into Fyers.")
    print("2. You will be redirected to an empty page (127.0.0.1).")
    print("3. Copy the ENTIRE URL from your browser's address bar.")
    print("="*50 + "\n")
    
    webbrowser.open(auth_link)
    
    # 2. Get the redirected URL from the user
    redirected_url = input("Paste the redirected URL here: ")
    
    # Extract the 'auth_code' from the URL
    try:
        auth_code = redirected_url.split("auth_code=")[1].split("&")[0]
    except IndexError:
        print("❌ Error: Could not find 'auth_code' in the provided URL.")
        return

    # 3. Exchange auth_code for the access_token
    session.set_token(auth_code)
    response = session.generate_token()
    
    if "access_token" in response:
        token = response["access_token"]
        print("\n✅ SUCCESS! Your Access Token for today is generated.")
        print("-" * 50)
        print(token)
        print("-" * 50)
        print("\n⚠️  NEXT STEP: Copy the token above and add it to your .env file as:")
        print("FYERS_ACCESS_TOKEN=\"paste_token_here\"")
    else:
        print(f"❌ Auth Failed: {response}")

if __name__ == "__main__":
    generate_daily_token()