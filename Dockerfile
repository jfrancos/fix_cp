FROM python:3
RUN apt-get update
RUN apt-get install libldap2-dev libsasl2-dev
RUN pip3 install python-ldap python-dotenv
RUN git config --global user.email "justinfrancos@gmail.com"
RUN git config --global user.name "Justin Francos"
RUN git config --global credential.https://github.com.username justinfrancos@gmail.com