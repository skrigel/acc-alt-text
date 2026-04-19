# FROM python:3.11

# RUN useradd -m -u 1000 user

# WORKDIR /app

# COPY --chown=user ./requirements.txt requirements.txt
# RUN pip install --no-cache-dir --upgrade -r requirements.txt

# COPY --chown=user . .

# USER user

# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
FROM python:3.11

RUN useradd -m -u 1000 user

# Install Node
RUN apt-get update && apt-get install -y nodejs npm

WORKDIR /app
COPY --chown=user ./backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY --chown=user . /app

# Build React
RUN cd frontend && npm install && npm run build

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "7860"]