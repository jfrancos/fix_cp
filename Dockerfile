FROM python:3
# RUN apk update
# RUN apk add python3 bash git
# RUN echo "cd /docker_cp" >> ~/.bashrc
# RUN pip3 install --upgrade pip

# RUN apk add build-base python3-dev openldap-dev
RUN apt-get update
RUN apt-get install libldap2-dev libsasl2-dev
RUN pip3 install python-ldap python-dotenv
RUN git config --global user.email "justinfrancos@gmail.com"
RUN git config --global user.name "Justin Francos"
RUN git config --global credential.https://github.com.username justinfrancos@gmail.com