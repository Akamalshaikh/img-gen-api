import requests
import json
import time
import uuid
import os
from flask import Flask, request, jsonify, send_file
from io import BytesIO

# --- Flask App ---
app = Flask(__name__)

# --- Global variables to store keys ---
current_anon_id = None
current_client_id = None

# --- Lightweight key generation (NO SELENIUM NEEDED!) ---

def generate_new_keys():
    """
    Generates client keys without browser automation.
    Uses UUID-based generation similar to how the website does it.
    """
    global current_anon_id, current_client_id
    
    print("Generating new API keys...")
    
    # Generate UUID-based keys (similar format to what the site uses)
    current_anon_id = str(uuid.uuid4())
    current_client_id = str(uuid.uuid4())
    
    print(f"✓ Generated new keys:")
    print(f"  Anonymous ID: {current_anon_id}")
    print(f"  Client ID: {current_client_id}")
    
    return True

# --- Core API logic ---

def get_magic_image(prompt):
    """
    Calls the Magic Studio API with retry mechanism for expired keys.
    """
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Check if keys are missing (first run)
            if not current_anon_id or not current_client_id:
                print("No keys found. Generating initial keys...")
                generate_new_keys()

            # API Endpoint
            api_url = "https://ai-api.magicstudio.com/api/ai-art-generator"

            # Payload with current keys
            payload_data = {
                "prompt": prompt,
                "output_format": "bytes",
                "user_profile_id": "", 
                "anonymous_user_id": current_anon_id, 
                "request_timestamp": str(time.time()), 
                "user_is_subscribed": "false", 
                "client_id": current_client_id 
            }

            # Headers
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://magicstudio.com/ai-art-generator/",
                "Origin": "https://magicstudio.com"
            }

            print(f"\n{'='*50}")
            print(f"Request #{attempt + 1}/{max_retries}")
            print(f"Prompt: {prompt}")
            print(f"{'='*50}")

            # Make the POST request
            response = requests.post(api_url, data=payload_data, headers=headers, timeout=30)
            
            # Check response
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if response.content and 'image' in content_type:
                    print("✓ Successfully received image from Magic Studio.")
                    return response.content, content_type, 200
                else:
                    print("⚠ API returned 200 OK but no image.")
                    return {"error": "API returned 200 OK but no image"}, None, 500
            
            elif response.status_code == 422:
                print(f"✗ Got 422 Unprocessable Entity. Keys may be invalid.")
                if attempt < max_retries - 1:
                    print("Generating new keys and retrying...")
                    generate_new_keys()
                    time.sleep(1)  # Brief pause before retry
                    continue
                else:
                    return {"error": "Keys rejected after multiple attempts"}, None, 422
            
            else:
                print(f"✗ Unexpected status code: {response.status_code}")
                print(f"Response: {response.text[:200]}")
                return {
                    "error": f"API Error: {response.status_code}", 
                    "details": response.text[:500]
                }, None, response.status_code

        except requests.exceptions.Timeout:
            print(f"✗ Request timeout (attempt {attempt + 1})")
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(2)
                continue
            return {"error": "Request timeout after multiple attempts"}, None, 504
            
        except requests.exceptions.RequestException as e:
            print(f"✗ Network error: {str(e)}")
            if attempt < max_retries - 1:
                print("Retrying...")
                time.sleep(2)
                continue
            return {"error": "Network error", "details": str(e)}, None, 503
    
    # If loop finishes without success
    return {"error": "Failed to get image after all retries."}, None, 500


# --- API endpoints ---

@app.route("/api/generate", methods=["POST", "GET"])
def handle_generation_request():
    """
    Public endpoint for image generation.
    Accepts both GET and POST requests.
    """
    
    prompt = None
    
    # Handle GET request
    if request.method == "GET":
        prompt = request.args.get("prompt")
        if not prompt:
            return jsonify({
                "error": "Missing 'prompt' parameter",
                "example": "/api/generate?prompt=a blue cat"
            }), 400
    
    # Handle POST request
    elif request.method == "POST":
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Request body must be JSON"}), 400
            prompt = data.get("prompt")
        except Exception as e:
            return jsonify({
                "error": "Invalid JSON",
                "details": str(e)
            }), 400

    if not prompt or not prompt.strip():
        return jsonify({"error": "Prompt cannot be empty"}), 400

    # Generate image
    image_data, mime_type, status_code = get_magic_image(prompt.strip())

    if image_data and mime_type:
        return send_file(
            BytesIO(image_data),
            mimetype=mime_type,
            as_attachment=False,
            download_name=f"generated_{int(time.time())}.jpg"
        )
    else:
        return jsonify(image_data), status_code


@app.route("/", methods=["GET"])
def home():
    """Home endpoint with API information."""
    return jsonify({
        "name": "Magic Studio API Wrapper",
        "version": "3.0 - Render Edition",
        "status": "running",
        "description": "Lightweight API wrapper for Magic Studio AI Art Generator",
        "endpoints": {
            "generate": "/api/generate",
            "methods": ["GET", "POST"],
            "examples": {
                "get": "curl 'https://akamal-shaikh.onrender.com/api/generate?prompt=a+beautiful+sunset'",
                "post": "curl -X POST https://akamal-shaikh.onrender.com/api/generate -H 'Content-Type: application/json' -d '{\"prompt\":\"a beautiful sunset\"}'"
            }
        }
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "keys_loaded": bool(current_anon_id and current_client_id),
        "anon_id": current_anon_id[:8] + "..." if current_anon_id else None,
        "client_id": current_client_id[:8] + "..." if current_client_id else None
    })


@app.route("/refresh-keys", methods=["POST"])
def refresh_keys():
    """Manual endpoint to refresh API keys."""
    print("Manual key refresh requested...")
    generate_new_keys()
    return jsonify({
        "success": True,
        "message": "Keys refreshed successfully",
        "anon_id": current_anon_id[:8] + "...",
        "client_id": current_client_id[:8] + "..."
    })


@app.route("/test", methods=["GET"])
def test():
    """Quick test endpoint."""
    return jsonify({
        "message": "API is running!",
        "test_endpoint": "/api/generate?prompt=test",
        "timestamp": time.time()
    })


# --- Initialize keys on startup ---
print("=" * 60)
print("🚀 Magic Studio API - Render Edition")
print("=" * 60)
print("Initializing...")
generate_new_keys()
print("✓ Ready to accept requests")
print("=" * 60)


# --- Run the server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)