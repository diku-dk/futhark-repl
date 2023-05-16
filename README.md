# Online Futhark REPL
This is a website that can start Futhark REPL processes and let users interact with the REPLs through a website.

To run the website with a specific port using a docker container with waitress.
```
./run.sh PORT
```
An example of this could be `./run.sh 8080`, if the port is not specified then the port will be `8080`.
When `./run.sh PORT` is done executing then waitress will be serving the website on http://0.0.0.0:PORT.

## Settings
Inside [repl/settings.json](repl/settings.json) are some paramaters which have the following meanings:

* `check_time`: How often the webserver should check if there are sessions to clean up (in minutes). 
* `last_time_limit`: The amount of time an REPL session can be inactive before it is cleaned (in minutes).
* `token_lifespan`: The amount of time a tokens can exists before it becomes invalid (in minutes).
* `response_size_limit`: The maximum reponse size, the website can give to a user (in bytes). If this is null then there is no limit.
* `compute_time_limit`: The maximum amount of time a computation may take (in seconds).
* `session_amount_limit`: The maximum amount of active sessions, null the amount is unlimited.
* `step_timeout`: The amount of time select will wait before it gets timedout (in milliseconds). Select is used in each step of getting the reponse from the REPL, so it should be less than `compute_time_limit`. If stdout is written to within large gaps of time then it can be good to let this be a large value. But for the last step of reading from stdout then it will be needed to wait the full amount of `step_timeout`.
* `step_read_size`: After select have determined there are more input to be read the amount of input that will be read is `step_read_size` (in bytes). A worst case scenario is if select never gives an early result so `step_timeout` has to be waited for every step. Then the amount of bytes that can be read from the terminal is `step_read_size * compute_time_limit / (step_timeout * 0.001)`

## Development
For formatting just use the default settings for `black` and use `mypy` for type checking.

To start the website in debugging mode do.
```
cd repl && flask --app app run --debug
```
You may also just use `flask run`:
```
cd repl && flask run
```
