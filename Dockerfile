# syntax=docker/dockerfile:1

FROM python:3 AS compile-image

WORKDIR /app
# install poetry
RUN pip install poetry
# Make new venv
RUN python -m venv /venv
# copy in config
COPY pyproject.toml poetry.lock ./
# install only dependencies (so that this caches)
RUN poetry export -f requirements.txt -o requirements.txt
RUN /venv/bin/python -m pip install -r requirements.txt

# copy in everything else and build wheel:
COPY README.md ./
COPY ncal ./ncal
RUN poetry build
RUN /venv/bin/python -m pip install dist/*.whl

# Final Image
FROM python:3 AS final
COPY --from=compile-image /venv /venv
ENV PATH="/venv/bin:$PATH"
ENTRYPOINT ["ncal"]
