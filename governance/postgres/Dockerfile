FROM postgres:16.16

# Hold the server so installing pgaudit can never silently upgrade it.
RUN apt-mark hold postgresql-16 \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgaudit=16.2-1.pgdg13+1 \
    && rm -rf /var/lib/apt/lists/*
