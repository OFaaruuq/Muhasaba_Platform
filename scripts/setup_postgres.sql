-- Run as postgres superuser: sudo -u postgres psql -f scripts/setup_postgres.sql
CREATE USER muhasaba WITH PASSWORD 'muhasaba';
CREATE DATABASE muhasaba OWNER muhasaba;
GRANT ALL PRIVILEGES ON DATABASE muhasaba TO muhasaba;
\c muhasaba
GRANT ALL ON SCHEMA public TO muhasaba;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO muhasaba;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO muhasaba;
