DEFAULTPORT=8080
PORT=$1
if [ -z "$PORT" ]; then
    PORT=$DEFAULTPORT
fi

echo "PORT: $PORT"
sudo docker build -t online-futhark-repl repl
sudo docker run -p $PORT:$PORT online-futhark-repl --host=0.0.0.0 --port=${PORT} --url-scheme=https --threads=4 views:app
