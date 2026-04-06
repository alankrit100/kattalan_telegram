import os
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv, set_key
from fyers_apiv3 import fyersModel

# Define paths to securely locate and update the .env file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Assuming .env is located in the /backend directory (one level up from /scripts)
ENV_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".env"))

# Load credentials from .env
load_dotenv(ENV_PATH)

client_id = os.environ.get("FYERS_CLIENT_ID")
secret_key = os.environ.get("FYERS_SECRET_KEY")
redirect_uri = os.environ.get("FYERS_REDIRECT_URI")

if not all([client_id, secret_key, redirect_uri]):
    raise ValueError("FATAL: Missing Fyers credentials in .env file.")

# --- Local Server to catch the Auth Code automatically ---
class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        if 'auth_code' in query_params:
            self.server.auth_code = query_params['auth_code'][0]
            success_html = """
            <html>
                <body style="font-family: sans-serif; text-align: center; margin-top: 50px; background-color: #0f172a; color: #f8fafc;">
                    <h1 style="color: #22c55e;">Authentication Successful!</h1>
                    <p>The Kattalan Quant Engine has received your token.</p>
                    <p style="color: #94a3b8;">You can close this tab and return to your terminal.</p>
                    <script>setTimeout(window.close, 3000);</script>
                </body>
            </html>
            """
            self.wfile.write(success_html.encode('utf-8'))
        else:
            self.server.auth_code = None
            error_html = """
            <html>
                <body style="font-family: sans-serif; text-align: center; margin-top: 50px; background-color: #0f172a; color: #f8fafc;">
                    <h1 style="color: #ef4444;">Authentication Failed</h1>
                    <p>No auth code found in the redirect URL.</p>
                </body>
            </html>
            """
            self.wfile.write(error_html.encode('utf-8'))

    def log_message(self, format, *args):
        # Suppress standard HTTP server logging to keep terminal clean
        pass

def generate_daily_token():
    # Parse the redirect URI to dynamically figure out which port to listen on
    parsed_uri = urllib.parse.urlparse(redirect_uri)
    host = parsed_uri.hostname or '127.0.0.1'
    port = parsed_uri.port or 8080

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
    print("🚀 AUTOMATED FYERS AUTHENTICATION")
    print("="*50)
    print("1. Your browser will open shortly.")
    print("2. Log into Fyers with your PIN/TOTP.")
    print("3. The script will automatically catch the token and update your .env file.")
    print("="*50 + "\n")
    
    # 2. Start the local server to listen for the callback
    server_address = (host, port)
    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    httpd.auth_code = None
    
    webbrowser.open(auth_link)
    print(f"⏳ Waiting for authorization on {host}:{port}...")
    
    # Wait for exactly one HTTP request (the redirect from Fyers)
    httpd.handle_request()
    auth_code = httpd.auth_code
    
    if not auth_code:
        print("❌ Error: Could not extract 'auth_code' from the redirect.")
        return

    print("✅ Auth code received! Generating access token...")

    # 3. Exchange auth_code for the access_token
    session.set_token(auth_code)
    response = session.generate_token()
    
    if "access_token" in response:
        token = response["access_token"]
        
        # 4. Automatically overwrite the old token in the .env file
        set_key(ENV_PATH, "FYERS_ACCESS_TOKEN", token)
        
        print("\n✅ SUCCESS! Token generated and safely written to .env")
        print(f"File updated: {ENV_PATH}")
        print("You can now start the Kattalan backend.")
    else:
        print(f"\n❌ Auth Exchange Failed: {response}")

if __name__ == "__main__":
    generate_daily_token()