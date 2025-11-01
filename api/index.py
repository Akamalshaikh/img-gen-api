import requests
import json
import time
import uuid
from flask import Flask, request, jsonify, send_file, Response
from io import BytesIO

# --- Flask App ---
app = Flask(__name__)

# --- Helper Functions ---

def generate_keys():
    """Generate UUID-based API keys."""
    return str(uuid.uuid4()), str(uuid.uuid4())

def get_magic_image(prompt):
    """
    Calls the Magic Studio API with retry mechanism.
    """
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Generate fresh keys for each request
            anon_id, client_id = generate_keys()
            
            # API Endpoint
            api_url = "https://ai-api.magicstudio.com/api/ai-art-generator"

            # Payload
            payload_data = {
                "prompt": prompt,
                "output_format": "bytes",
                "user_profile_id": "", 
                "anonymous_user_id": anon_id, 
                "request_timestamp": str(time.time()), 
                "user_is_subscribed": "false", 
                "client_id": client_id 
            }

            # Headers
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://magicstudio.com/ai-art-generator/",
                "Origin": "https://magicstudio.com"
            }

            print(f"Request #{attempt + 1}/{max_retries} - Prompt: {prompt}")

            # Make the POST request
            response = requests.post(api_url, data=payload_data, headers=headers, timeout=30)
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if response.content and 'image' in content_type:
                    print("✓ Successfully received image")
                    return response.content, content_type, 200
                else:
                    return {"error": "API returned 200 OK but no image"}, None, 500
            
            elif response.status_code == 422:
                print(f"✗ Got 422 - Retrying with new keys...")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return {"error": "Keys rejected after multiple attempts"}, None, 422
            
            else:
                return {
                    "error": f"API Error: {response.status_code}", 
                    "details": response.text[:500]
                }, None, response.status_code

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"error": "Request timeout"}, None, 504
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return {"error": "Network error", "details": str(e)}, None, 503
    
    return {"error": "Failed after all retries"}, None, 500


# --- API Routes ---

@app.route("/", methods=["GET"])
@app.route("/api", methods=["GET"])
@app.route("/api/", methods=["GET"])
def home():
    """Home endpoint with API information."""
    host = request.host
    return jsonify({
        "name": "Magic Studio API by Akamal Shaikh",
        "version": "3.0 - Vercel Edition",
        "status": "running ✅",
        "description": "Lightweight API wrapper for Magic Studio AI Art Generator",
        "endpoints": {
            "health": f"https://{host}/api/health",
            "test": f"https://{host}/api/test",
            "generate": f"https://{host}/api/generate?prompt=YOUR_PROMPT"
        },
        "usage_examples": {
            "get": f"curl 'https://{host}/api/generate?prompt=a+beautiful+sunset'",
            "post": f"curl -X POST https://{host}/api/generate -H 'Content-Type: application/json' -d '{{\"prompt\":\"a beautiful sunset\"}}'"
        },
        "author": "Akamal Shaikh",
        "github": "https://github.com"
    })


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
                "example": f"https://{request.host}/api/generate?prompt=a+blue+cat",
                "usage": "Add ?prompt=YOUR_PROMPT to the URL"
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


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy ✅",
        "platform": "vercel",
        "serverless": True,
        "timestamp": time.time(),
        "message": "API is running perfectly!"
    })


@app.route("/api/test", methods=["GET"])
def test():
    """Quick test endpoint."""
    return jsonify({
        "message": "🎉 API is running on Vercel!",
        "status": "success ✅",
        "test_image_url": f"https://{request.host}/api/generate?prompt=test",
        "timestamp": time.time(),
        "author": "Akamal Shaikh"
    })


# Catch-all route for other paths
@app.route("/<path:path>")
def catch_all(path):
    """Catch-all route to redirect to API home."""
    return jsonify({
        "error": "Route not found",
        "message": f"The path '/{path}' does not exist",
        "available_endpoints": {
            "home": f"https://{request.host}/api",
            "health": f"https://{request.host}/api/health",
            "test": f"https://{request.host}/api/test",
            "generate": f"https://{request.host}/api/generate?prompt=YOUR_PROMPT"
        },
        "suggestion": f"Try visiting https://{request.host}/api"
    }), 404


# Error handlers
@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist",
        "available_endpoints": {
            "home": f"https://{request.host}/api",
            "health": f"https://{request.host}/api/health",
            "test": f"https://{request.host}/api/test",
            "generate": f"https://{request.host}/api/generate?prompt=YOUR_PROMPT"
        }
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    return jsonify({
        "error": "Internal Server Error",
        "message": str(e)
    }), 500
