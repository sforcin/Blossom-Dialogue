from flask import Flask

app = Flask(__name__)

@app.route("/start")
def start():
    print("start received")
    return "ok"

@app.route("/stop")
def stop():
    print("stop received")
    return "ok"

app.run(host="0.0.0.0", port=5001)