FROM jupyter/base-notebook:ubuntu-22.04

USER root
RUN apt update -y &&\
    apt install -y openjdk-11-jdk &&\
    rm -rf /var/lib/{apt,dpkg,cache,log}

WORKDIR /usr/local/share/ijava
COPY JavaInterpreter.java JavaInterpreter.java
COPY ijava.sh /usr/local/bin/ijava

RUN javac JavaInterpreter.java &&\
    chmod a+x /usr/local/bin/ijava

USER jovyan
WORKDIR /home/jovyan/work

ENV USER=jovyan
