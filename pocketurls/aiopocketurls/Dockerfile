FROM python:3
ENV PYTHONUNBUFFERED 1
RUN mkdir -p /code/pocketurls
RUN mkdir -p /code/config
WORKDIR /code
ADD requirements.txt /code/
RUN pip install -r requirements.txt
ADD pocketurls/ /code/pocketurls/
ADD config/ /code/config/
ADD start_app.sh /code/
CMD ./start_app.sh
