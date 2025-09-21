import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

# Load Firebase credentials from environment variable
firebase_config = json.loads(os.environ["FIREBASE_CONFIG"])
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)

db = firestore.client()
