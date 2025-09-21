import os
from flask import Flask
from gmail_fetcher import main_loop
import threading

app = Flask(__name__)

@app.route("/")
def index():
    return "Gmail fetcher running in background!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    # Run Gmail fetcher loop in a background thread
    t = threading.Thread(target=main_loop)
    t.daemon = True
    t.start()

    # Start Flask web server so Render sees a listening port
    app.run(host="0.0.0.0", port=port)
