"""Upload the new library PDFs the fresh DB points at (r2-upload-plan.csv from migrate_to_fresh.py) to R2.

NOT RUN by the build. Chase (or a session Chase approves) runs it once at go-live, BEFORE the app is switched:

    python scripts/r2_upload_new_library_files.py --plan r2-upload-plan.csv            # dry run: checks only
    python scripts/r2_upload_new_library_files.py --plan r2-upload-plan.csv --upload   # really uploads

R2 settings come from environment variables R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
(the same values as the Streamlit secrets). Each local file's sha256 is checked against the plan first. Keys that
already exist in R2 with the same size are skipped (re-running is safe). Never deletes or overwrites a different file:
an existing key with a different size stops the run.
"""
import argparse
import csv
import hashlib
import os
import sys


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--upload", action="store_true", help="really upload (default: dry run)")
    a = ap.parse_args(argv)
    rows = list(csv.DictReader(open(a.plan)))
    bad = [r for r in rows if not os.path.exists(r["local_pdf"]) or sha(r["local_pdf"]) != r["sha256"]]
    for r in bad:
        print("LOCAL FILE MISSING OR CHANGED:", r["document_id"], r["local_pdf"])
    if bad:
        return 2
    print(f"{len(rows)} files checked locally ({sum(os.path.getsize(r['local_pdf']) for r in rows) / 1e6:.1f} MB)")
    if not a.upload:
        print("dry run: nothing sent")
        return 0
    import boto3
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT_URL"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
    bucket = os.environ["R2_BUCKET_NAME"]
    sent = skipped = 0
    for r in rows:
        size = os.path.getsize(r["local_pdf"])
        try:
            head = s3.head_object(Bucket=bucket, Key=r["r2_key"])
            if head["ContentLength"] == size:
                skipped += 1
                continue
            print("STOP: a different file already exists at", r["r2_key"])
            return 3
        except s3.exceptions.ClientError:
            pass
        s3.upload_file(r["local_pdf"], bucket, r["r2_key"], ExtraArgs={"ContentType": "application/pdf"})
        if s3.head_object(Bucket=bucket, Key=r["r2_key"])["ContentLength"] != size:
            print("STOP: size mismatch after upload", r["r2_key"])
            return 4
        sent += 1
    print(f"uploaded {sent}, already there {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
