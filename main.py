from flask import Flask, request, Response, jsonify, session, render_template, redirect, url_for
from multiprocessing import Process
import tracker
import time

app = Flask(__name__)
app.register_blueprint(tracker.bp)


@app.route('/')
def root():
    return render_template('welcome.html')

if __name__ == '__main__':
    p = Process(target = tracker.track)
    p.start()
    app.run(host='127.0.0.1', port=8080, debug=True)
    p.join()




