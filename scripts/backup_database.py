import datetime
import gzip
import os
import shutil
import subprocess
import tempfile

import boto3


def backup_database() -> None:
    """Dump the Postgres database and upload to S3."""
    db_url = os.environ.get("DATABASE_URL")
    bucket = os.environ.get("S3_BUCKET")
    if not db_url or not bucket:
        raise RuntimeError("DATABASE_URL and S3_BUCKET must be set")

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    key = f"backup-{timestamp}.sql.gz"

    with tempfile.TemporaryDirectory() as tmpdir:
        sql_path = os.path.join(tmpdir, "dump.sql")
        with open(sql_path, "wb") as f:
            subprocess.run(["pg_dump", db_url], check=True, stdout=f)

        gz_path = f"{sql_path}.gz"
        with open(sql_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
        s3.upload_file(gz_path, bucket, key)

        retention = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        objects = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
        for obj in objects:
            if (
                obj.get("LastModified")
                and obj["LastModified"].replace(tzinfo=None) < retention
            ):
                s3.delete_object(Bucket=bucket, Key=obj["Key"])


if __name__ == "__main__":
    backup_database()
