FROM debian:11

WORKDIR /

RUN apt update && apt install -y libtinfo-dev libgmp-dev zlib1g-dev python pip wget
COPY . .
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir -r requirements.txt
RUN python3 -m pip install --no-cache-dir waitress
RUN wget https://futhark-lang.org/releases/futhark-nightly-linux-x86_64.tar.xz
RUN tar xvf futhark-nightly-linux-x86_64.tar.xz
RUN cd futhark-nightly-linux-x86_64 && make install
EXPOSE 8080

CMD [ "waitress-serve", "views:app"]