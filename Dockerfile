# How to use:
# docker run -it --rm -v <your path to your data folder>:/data <your image>

FROM python:3.11
WORKDIR /src
COPY . .
RUN python -m pip install /src
RUN mkdir /data
WORKDIR /data

CMD echo '--------------------'; \
    echo 'To use the bids converter:'; \
    echo 'first run bids_helper'; \
    echo 'brkraw-legacy bids_helper <input dir> <output filename> -j'; \
    echo 'second, run converter'; \
    echo 'brkraw-legacy bids_convert <input dir> <BIDS datasheet.csv> -j <JSON syntax template.json> -o <output dir>';\
    echo '--------------------'; \
    bash

