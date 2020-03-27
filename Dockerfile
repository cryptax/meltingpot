FROM python:3.6

RUN mkdir -p /usr/share/meltingpot /var/meltingpot/fs /var/log /var/meltingpot/uploads

ADD meltingpot.py /usr/share/meltingpot
ADD meltingpot.cfg /usr/share/meltingpot
ADD requirements.txt /usr/share/meltingpot
ADD creds.cfg /usr/share/meltingpot
ADD ./fs /var/meltingpot/fs

RUN pip install -r /usr/share/meltingpot/requirements.txt

EXPOSE 2221
EXPOSE 30000-30009

WORKDIR /usr/share/meltingpot
CMD ["python3", "-u", "/usr/share/meltingpot/meltingpot.py"]
