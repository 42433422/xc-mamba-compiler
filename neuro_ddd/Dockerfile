# Minimal image to run benchmarks / doctor (framework only)
FROM python:3.11-slim-bookworm
WORKDIR /app
COPY neuro_ddd /app/neuro_ddd
ENV PYTHONPATH=/app
RUN python -m neuro_ddd doctor
CMD ["python", "-m", "neuro_ddd", "doctor"]
