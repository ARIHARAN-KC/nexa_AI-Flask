from dotenv import load_dotenv
load_dotenv()
import json
import boto3
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from botocore.client import Config

# ==============================
# Configuration
# ==============================
BUCKET_NAME = os.getenv("BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_ENDPOINT_URL = os.getenv("S3_URL")

S3_ACCESS_KEY = os.getenv("S3_ACCESSKEY")
S3_SECRET_KEY = os.getenv("S3_SECRETKEY")

S3_PROFILE_FOLDER = "profile_pictures/"
S3_PROJECTS_FOLDER = "projects/"

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# ==============================
# ENV SAFETY CHECK (FAIL FAST)
# ==============================
missing = []
if not BUCKET_NAME: missing.append("BUCKET_NAME")
if not S3_ENDPOINT_URL: missing.append("S3_URL")
if not S3_ACCESS_KEY: missing.append("S3_ACCESSKEY")
if not S3_SECRET_KEY: missing.append("S3_SECRETKEY")

if missing:
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

# ==============================
# S3 / MinIO Client
# ==============================
s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=AWS_REGION,
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"}
    ),
)

# ==============================
# Helpers
# ==============================
def allowed_file(filename):
    return (
        isinstance(filename, str)
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def get_profile_pic_url(filename, expires_in=3600):
    if not filename:
        return None
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": f"{S3_PROFILE_FOLDER}{filename}",
            },
            ExpiresIn=expires_in,
        )
    except Exception as e:
        print(f"[S3] Presigned URL error: {e}")
        return None

# ==============================
# Profile Picture Upload
# ==============================
def upload_profile_picture(file, user_id):
    if not file or not file.filename:
        raise ValueError("No file uploaded")

    if not allowed_file(file.filename):
        raise ValueError("Invalid file type")

    file.stream.seek(0)

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = secure_filename(
        f"{user_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
    )

    try:
        s3.upload_fileobj(
            file,
            BUCKET_NAME,
            f"{S3_PROFILE_FOLDER}{filename}",
            ExtraArgs={
                "ContentType": file.mimetype or "image/png"
            },
        )
        #print(f"[MinIO] Uploaded profile picture: {filename}")
        return filename

    except Exception as e:
        print(f"[MinIO] Upload failed: {e}")
        raise

def delete_profile_picture(filename):
    if not filename:
        return
    try:
        s3.delete_object(
            Bucket=BUCKET_NAME,
            Key=f"{S3_PROFILE_FOLDER}{filename}",
        )
    except Exception as e:
        print(f"[S3] Delete error: {e}")

# ==============================
# Project Files
# ==============================
def _project_prefix(user_id, project_id):
    if not user_id or not project_id:
        raise ValueError("user_id and project_id required")
    return f"{S3_PROJECTS_FOLDER}{user_id}/{project_id}/"


def upload_project_file(user_id, project_id, file_path, content):
    if not file_path or content is None:
        raise ValueError("Invalid project file data")

    key = f"{_project_prefix(user_id, project_id)}{file_path}"

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=content.encode("utf-8"),
        ContentType="text/plain",
    )


def delete_project_file(user_id, project_id, file_path):
    if not file_path:
        return

    key = f"{_project_prefix(user_id, project_id)}{file_path}"
    s3.delete_object(Bucket=BUCKET_NAME, Key=key)


def get_project_file_content(user_id, project_id, file_path):
    if not file_path:
        return None

    try:
        obj = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=f"{_project_prefix(user_id, project_id)}{file_path}"
        )
        return obj["Body"].read().decode("utf-8")
    except s3.exceptions.NoSuchKey:
        return None


def list_project_files(user_id, project_id):
    prefix = _project_prefix(user_id, project_id)
    files = {}

    result = s3.list_objects_v2(
        Bucket=BUCKET_NAME,
        Prefix=prefix
    )

    for obj in result.get("Contents", []):
        key = obj["Key"]
        relative_path = key.replace(prefix, "")

        if not relative_path:
            continue

        file_obj = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=key
        )

        files[relative_path] = {
            "content": file_obj["Body"].read().decode("utf-8"),
            "last_modified": obj["LastModified"].isoformat()
        }

    return files

def save_full_project(user_id, project_id, files, metadata=None):
    """
    Save full project to S3
    files = { "path": "content" }
    """
    for path, content in files.items():
        upload_project_file(user_id, project_id, path, content)

    if metadata:
        upload_project_file(
            user_id,
            project_id,
            "metadata.json",
            json.dumps(metadata, indent=2)
        )
