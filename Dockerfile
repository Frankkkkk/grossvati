FROM python:3.10
RUN pip install pipenv

COPY Pipfile* /tmp/
RUN cd /tmp && pipenv install --dev --system --deploy

COPY src src
CMD ["python3", "./src/main.py"]

