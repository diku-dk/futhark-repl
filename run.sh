DEFAULTPORT=8080
PORT=$1
if [ -z "$PORT" ]; then
    PORT=$DEFAULTPORT
fi

echo "PORT: $PORT"
sudo docker build -t online-futhark-repl repl
sudo docker run -p $PORT:$PORT --env port=$PORT online-futhark-repl