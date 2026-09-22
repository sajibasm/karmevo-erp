-- DEVELOPMENT-ONLY credentials. Deployment profiles provision their own roles and secrets.
-- erp_owner creates tenant databases (CREATEDB) and runs migrations; services never use it.
CREATE ROLE erp_owner LOGIN PASSWORD 'erp_owner_dev' NOSUPERUSER NOBYPASSRLS NOCREATEROLE CREATEDB;
CREATE ROLE erp_app   LOGIN PASSWORD 'erp_app_dev'   NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;
CREATE ROLE erp_relay LOGIN PASSWORD 'erp_relay_dev' NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;

CREATE DATABASE erp_registry OWNER erp_owner;
CREATE DATABASE erp_registry_test OWNER erp_owner;

REVOKE CONNECT ON DATABASE erp_registry, erp_registry_test FROM PUBLIC;
GRANT CONNECT ON DATABASE erp_registry, erp_registry_test TO erp_app;
