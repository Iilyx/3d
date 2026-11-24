# case-3:tex — XeLaTeX + Pandoc, Cyrillic-ready (leaner than full STP image)
FROM debian:stable-slim

ARG USER_NAME=tex
ARG USER_HOME=/home/tex
ARG USER_ID=1000
ARG USER_GECOS=TeX

RUN apt-get update && \
  apt-get install --no-install-recommends -y \
    adduser \
    latexmk \
    lmodern \
    texlive-xetex \
    texlive-lang-cyrillic \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    fonts-dejavu \
    pandoc \
  && \
  apt-get --purge remove -y '.*-doc$' && \
  apt-get clean -y && \
  rm -rf /var/lib/apt/lists/*

RUN adduser \
  --home "${USER_HOME}" \
  --uid "${USER_ID}" \
  --gecos "${USER_GECOS}" \
  --disabled-password \
  "${USER_NAME}"

WORKDIR /work
