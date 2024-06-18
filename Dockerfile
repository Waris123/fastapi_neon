FROM python

RUN apt-get update && apt-get install -y pipx

RUN pipx install --force poetry

WORKDIR /app

ENV PATH="${PATH}:/root/.local/bin"

COPY . /app/

RUN poetry install

# Expose the port that FastAPI runs on
EXPOSE 8000

# Command to run the application
ENTRYPOINT ["poetry", "run", "uvicorn", "fastapi_neon.main:app", "--host", "0.0.0.0", "--port", "8000"]

