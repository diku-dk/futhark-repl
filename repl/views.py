import os
from flask import Flask, render_template, request, Response, jsonify
from flask_httpauth import HTTPTokenAuth
from sessions import Sessions
from session import REPLErrors
import datetime
import json

app = Flask(
    __name__,
    template_folder="template",
    static_url_path='',
    static_folder='static'
)
SECRET_KEY = os.urandom(12)  # Just something I dunno yet.
app.config.update(SECRET_KEY=SECRET_KEY)
auth = HTTPTokenAuth(scheme="Bearer")

assert os.path.exists('settings.json'), 'The settings for the server needs to be specified.'

settings = json.load(open('settings.json'))
sessions = Sessions(
    secret_key=SECRET_KEY,
    check_time=datetime.timedelta(minutes=settings['check_time']),
    last_time_limit=datetime.timedelta(minutes=settings['last_time_limit']),
    token_lifespan=datetime.timedelta(minutes=settings['token_lifespan']),
    response_size_limit=settings['response_size_limit'],
    compute_time_limit=datetime.timedelta(seconds=settings['compute_time_limit']),
    session_amount_limit=settings['session_amount_limit']
)

@auth.error_handler
def auth_error(status):
    if status == 401:
        return (
            jsonify({"message": "Session ran out, refresh to start a new session."}),
            status,
        )
    return status

@auth.verify_token
def verify_token(token):
    return sessions.verify(token)


@app.route("/repl", methods=["POST"])
@auth.login_required
def repl():
    code = request.get_json()["code"]
    # Taking the token should be safe since it was checked by auth.
    token = request.headers.get("Authorization")[7:]
    session = sessions.get(token)

    if session.is_active():
        return jsonify({"message": "The request is already in progress."}), 412

    out = session.read_eval_print(code)

    if out == REPLErrors.TIMEOUT:
        sessions.remove(token)
        return (
            jsonify({"message": "The request took too long, please restart the session."}),
            400,
        )
    if out == REPLErrors.SIZELIMIT:
        sessions.remove(token)
        return jsonify({"message": "The request was too expensive for the repl."}), 400

    result, lastline = out

    return jsonify({"result": result, "lastline": lastline})


@app.route("/")
def index():
    result = sessions.create_session()

    if result is None:
        return Response(render_template("limit_error.html"))

    token, session = result
    banner = session.banner
    init_lastline = session.init_lastline
    context = dict(token=token, banner=banner, init_lastline=init_lastline)
    return Response(render_template("index.html", **context))
