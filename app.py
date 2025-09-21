# app.py
from flask import Flask, request, jsonify, redirect
from firebase_config import db
from firebase_admin import auth
from flask_cors import CORS
import requests
import json
from gemini_int import parse_expense

app = Flask(__name__)
CORS(app)

# Load Google OAuth JSON config
with open("OAuth.json") as f:
    google_config = json.load(f)["installed"]

CLIENT_ID = google_config["client_id"]
CLIENT_SECRET = google_config["client_secret"]
REDIRECT_URI = "http://localhost:5000/oauth2callback"
TOKEN_URI = google_config["token_uri"]
SCOPES = "https://www.googleapis.com/auth/gmail.readonly"

# ------------------ Firebase Token Verification ------------------
def verify_user():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    parts = auth_header.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer":
        return None
    id_token = parts[1]
    try:
        decoded = auth.verify_id_token(id_token)
        return decoded["uid"]
    except Exception as e:
        print("Token verification failed:", e)
        return None

# ------------------ Login Verification ------------------
@app.route("/verify_login", methods=["POST"])
def verify_login():
    data = request.json
    id_token = data.get("idToken")
    if not id_token:
        return jsonify({"error": "No ID token"}), 400
    try:
        decoded = auth.verify_id_token(id_token)
        uid = decoded["uid"]
        email = decoded.get("email", "")
        name = decoded.get("name", "")

        db.collection("users").document(uid).set({
            "name": name,
            "email": email
        }, merge=True)

        # Check if Gmail token exists
        user_doc = db.collection("users").document(uid).get()
        has_token = "gmail_refresh_token" in user_doc.to_dict() if user_doc.exists else False

        return jsonify({"success": True, "uid": uid, "requireGmailConsent": not has_token})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ------------------ Gmail Consent Flow ------------------
@app.route("/get_gmail_consent/<uid>")
def get_gmail_consent(uid):
    auth_url = (
        f"https://accounts.google.com/o/oauth2/auth"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPES}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={uid}"
    )
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    code = request.args.get("code")
    uid = request.args.get("state")
    if not code or not uid:
        return "Missing code or state", 400

    # Exchange code for refresh token
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    r = requests.post(TOKEN_URI, data=data)
    token_info = r.json()
    refresh_token = token_info.get("refresh_token")

    if not refresh_token:
        return "Failed to get refresh token", 400

    db.collection("users").document(uid).set({"gmail_refresh_token": refresh_token}, merge=True)
    return "Refresh token saved! You can close this page."

# ------------------ Check Gmail Token ------------------
@app.route("/check_gmail_token", methods=["GET"])
def check_gmail_token():
    uid = verify_user()
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401
    user_doc = db.collection("users").document(uid).get()
    has_access = "gmail_refresh_token" in user_doc.to_dict() if user_doc.exists else False
    return jsonify({"hasGmailAccess": has_access})

# ------------------ Expense Routes ------------------
@app.route("/add_expense", methods=["POST"])
def add_expense():
    data = request.json
    doc_ref = db.collection("expenses").add(data)
    return jsonify({"success": True, "id": doc_ref[1].id})

@app.route("/get_expenses", methods=["GET"])
def get_expenses():
    expenses = []
    docs = db.collection("expenses").stream()
    for doc in docs:
        expenses.append(doc.to_dict())
    return jsonify(expenses)

@app.route("/ai_expense", methods=["POST"])
def ai_expense():
    uid = verify_user()
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    parsed_data = parse_expense(data["text"])
    if parsed_data:
        doc_ref = db.collection("users").document(uid).collection("expenses").add(parsed_data)
        parsed_data["_id"] = doc_ref[1].id
        return jsonify({"success": True, "parsed_expense": parsed_data}), 200
    else:
        return jsonify({"error": "Failed to parse or store expense"}), 500

# ------------------ Home ------------------
@app.route("/")
def home():
    return "Backend is running!"

if __name__ == "__main__":
    app.run(debug=True)
