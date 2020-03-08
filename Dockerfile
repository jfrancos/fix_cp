FROM python:3
RUN apt-get update
RUN apt-get install -y powerline fonts-powerline zsh
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"

ENTRYPOINT cd /docker_cp; zsh
RUN apt-get install libldap2-dev libsasl2-dev
RUN pip3 install python-ldap python-dotenv