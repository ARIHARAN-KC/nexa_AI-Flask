import AWS from "aws-sdk";
import dotenv from "dotenv";

dotenv.config();

/* ---------------- ENV ---------------- */

const BUCKET_NAME = process.env.BUCKET_NAME;
if (!BUCKET_NAME) {
  throw new Error("BUCKET_NAME is missing in .env");
}

/* ---------------- S3 CLIENT ---------------- */

const s3 = new AWS.S3({
  endpoint: process.env.S3_URL || undefined,
  accessKeyId:
    process.env.AWS_ACCESS_KEY_ID || process.env.S3_ACCESSKEY,
  secretAccessKey:
    process.env.AWS_SECRET_ACCESS_KEY || process.env.S3_SECRETKEY,
  region: process.env.AWS_REGION || "us-east-1",
  s3ForcePathStyle: true,
  signatureVersion: "v4",
});

/* ---------------- CREATE BUCKET ---------------- */

export const createBucket = async (): Promise<void> => {
  const buckets = await s3.listBuckets().promise();

  const exists = buckets.Buckets?.some(
    (b: AWS.S3.Bucket) => b.Name === BUCKET_NAME
  );

  if (!exists) {
    await s3.createBucket({ Bucket: BUCKET_NAME }).promise();
    console.log(`Bucket created: ${BUCKET_NAME}`);
  } else {
    console.log(`Bucket already exists: ${BUCKET_NAME}`);
  }
};

/* ---------------- CREATE FOLDERS ---------------- */

export const createFolders = async (
  folders: string[]
): Promise<void> => {
  for (const folder of folders) {
    const key = folder.endsWith("/") ? folder : `${folder}/`;

    await s3
      .putObject({
        Bucket: BUCKET_NAME,
        Key: key,
        Body: "",
      })
      .promise();

    console.log(`Folder created: ${key}`);
  }
};

/* ---------------- LIST FOLDERS ---------------- */

export const listFolders = async (): Promise<string[]> => {
  const result = await s3
    .listObjectsV2({
      Bucket: BUCKET_NAME,
      Delimiter: "/",
    })
    .promise();

  return (
    result.CommonPrefixes?.map(
      (p: AWS.S3.CommonPrefix) => p.Prefix as string
    ) || []
  );
};

/* ---------------- INIT ---------------- */

export const init = async (): Promise<void> => {
  await createBucket();

  // THESE ARE FOLDERS INSIDE THE BUCKET
  const requiredFolders = ["profile_pictures", "projects"];

  const existingFolders = await listFolders();

  const foldersToCreate = requiredFolders.filter(
    (f) => !existingFolders.includes(`${f}/`)
  );

  if (foldersToCreate.length > 0) {
    await createFolders(foldersToCreate);
  } else {
    console.log("All required folders already exist.");
  }
};

/* ---------------- AUTO RUN ---------------- */

if (require.main === module) {
  init()
    .then(() => {
      console.log("S3 initialization completed");
      process.exit(0);
    })
    .catch((err) => {
      console.error("S3 initialization failed", err);
      process.exit(1);
    });
}

export default {
  s3,
  init,
  createBucket,
  createFolders,
  listFolders,
};
