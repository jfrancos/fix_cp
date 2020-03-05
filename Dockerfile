FROM alpine:latest
RUN apk update
RUN apk add python3 bash git
RUN echo "cd /docker_cp" >> ~/.bashrc
RUN pip3 install --upgrade pip
VOLUME "/docker_cp"
ENTRYPOINT bash

RUN apk add build-base python3-dev openldap-dev
RUN pip3 install python_ldap
