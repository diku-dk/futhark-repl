FROM debian:11

WORKDIR /

ARG VERSION=nightly

ENV PORT=8080
RUN apt update && apt install -y libtinfo-dev libgmp-dev zlib1g-dev python pip wget
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir waitress
RUN wget https://futhark-lang.org/releases/futhark-$VERSION-linux-x86_64.tar.xz
RUN tar xvf futhark-$VERSION-linux-x86_64.tar.xz
RUN cd futhark-$VERSION-linux-x86_64 && make install
COPY . .
RUN python3 -m pip install --no-cache-dir -r requirements.txt
EXPOSE ${PORT}

ENTRYPOINT ["waitress-serve"]
