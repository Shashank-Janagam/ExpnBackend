import os
from flask import Flask
from gmail_fetcher import main  # make sure gmail_fetcher.py has a main() function

app = Flask(__name__)

@app.route("/")
def index():
    main()  # runs your Gmail fetcher
    return "Gmail fetcher ran successfully!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
