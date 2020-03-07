FROM python:3
RUN apt-get update
RUN apt-get install libldap2-dev libsasl2-dev
RUN pip3 install python-ldap python-dotenv