FROM python:3
RUN apt-get update && apt-get install -y powerline fonts-powerline zsh time less && apt-get clean
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
RUN sed -i 's/plugins=\(.*\)/plugins=(git-prompt)/' /root/.zshrc
RUN echo disable -r time >> /root/.zshrc
RUN echo 'alias time="time -p "' >> /root/.zshrc
ENTRYPOINT cd /docker_* && git --no-pager diff && zsh

RUN apt-get update && apt-get -y install libldap2-dev libsasl2-dev nmap && apt-get clean
RUN pip3 install python-ldap python-dotenv python-libnmap pyyaml