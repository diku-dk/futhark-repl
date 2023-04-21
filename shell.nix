with import <nixpkgs> { };
pkgs.mkShell {
  buildInputs = [
    python3
    python3Packages.mypy
    python3Packages.flask-httpauth
    python3Packages.pyjwt
    python3Packages.black
    python3Packages.flask
    python3Packages.APScheduler
    futhark
  ];
}
