import os
import sys

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def main():
    if load_dotenv:
        load_dotenv()

    endpoint = os.getenv('R2_ENDPOINT_URL')
    bucket = os.getenv('R2_BUCKET_NAME')
    key_id = os.getenv('R2_ACCESS_KEY_ID')
    secret = os.getenv('R2_SECRET_ACCESS_KEY')

    missing = [n for n, v in [
        ('R2_ENDPOINT_URL', endpoint),
        ('R2_BUCKET_NAME', bucket),
        ('R2_ACCESS_KEY_ID', key_id),
        ('R2_SECRET_ACCESS_KEY', secret),
    ] if not v]
    if missing:
        print('Missing env vars: ' + ', '.join(missing))
        print('Create a .env (copy from .env.example) and fill in values.')
        sys.exit(1)

    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except Exception as e:
        print('boto3 missing. Install requirements first. Error:', e)
        sys.exit(1)

    s3 = boto3.client(
        's3',
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        endpoint_url=endpoint,
        config=BotoConfig(signature_version='s3v4')
    )

    try:
        # Light touch: list up to 5 objects
        resp = s3.list_objects_v2(Bucket=bucket, MaxKeys=5)
        count = resp.get('KeyCount', 0)
        print(f'R2 connection OK. Bucket={bucket}, sample_count={count}')
        if count:
            for obj in resp.get('Contents', [])[:5]:
                print('-', obj.get('Key'), obj.get('Size'))
        sys.exit(0)
    except Exception as e:
        print('R2 check failed:', e)
        sys.exit(2)


if __name__ == '__main__':
    main()
