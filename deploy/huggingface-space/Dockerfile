# n8n on a Hugging Face Space (CPU basic). Workflows, credentials and executions are stored in the
# Supabase PostgreSQL database, so a restart or rebuild of the Space loses nothing.
FROM n8nio/n8n:2.42.5

ENV N8N_PORT=7860 \
    N8N_LISTEN_ADDRESS=0.0.0.0 \
    N8N_PROTOCOL=https \
    N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
    N8N_DIAGNOSTICS_ENABLED=false \
    N8N_PERSONALIZATION_ENABLED=false \
    N8N_RUNNERS_ENABLED=true \
    N8N_PROXY_HOPS=1 \
    DB_TYPE=postgresdb \
    DB_POSTGRESDB_PORT=5432 \
    DB_POSTGRESDB_DATABASE=postgres \
    DB_POSTGRESDB_SCHEMA=n8n \
    DB_POSTGRESDB_SSL_ENABLED=true \
    DB_POSTGRESDB_SSL_REJECT_UNAUTHORIZED=false \
    EXECUTIONS_DATA_PRUNE=true \
    EXECUTIONS_DATA_MAX_AGE=168 \
    GENERIC_TIMEZONE=Europe/Berlin \
    TZ=Europe/Berlin

EXPOSE 7860
