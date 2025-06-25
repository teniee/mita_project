#!/bin/bash
set -euo pipefail
DATE=$(date +%Y-%m-%d)
S3_PATH="${S3_BUCKET}/${DATE}/backup.sql.gz"
pg_dump --dbname="$DATABASE_URL" | gzip | aws s3 cp - "$S3_PATH"
# remove backups older than 7 days
OLD_DATE=$(date -d '7 days ago' +%Y-%m-%d)
aws s3 rm "${S3_BUCKET}/${OLD_DATE}/" --recursive || true
