#!/bin/bash
# Creates the two databases these services need. Deliberately does NOT
# rely on POSTGRES_DB (which only creates one database) — this container
# has no "default" database of its own, both are created explicitly here.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE erupee_ledger_simulator;
    CREATE DATABASE sovereignx_core;
EOSQL
