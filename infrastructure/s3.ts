import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface CreateAssetsBucketProps {
  projectName: string;
  environment: string;
  account: string;
  versioned: boolean;
  removalPolicy: cdk.RemovalPolicy;
}

/**
 * Creates the S3 bucket used for event images, uploads, and static assets.
 */
export function createAssetsBucket(
  scope: Construct,
  props: CreateAssetsBucketProps
): s3.Bucket {
  const { projectName, environment, account, versioned, removalPolicy } = props;

  const bucket = new s3.Bucket(scope, 'AssetsBucket', {
    bucketName: `${projectName}-${environment}-assets-${account}`,
    encryption: s3.BucketEncryption.S3_MANAGED,
    blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    versioned,
    removalPolicy,
  });

  bucket.addCorsRule({
    allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.PUT, s3.HttpMethods.POST, s3.HttpMethods.HEAD],
    allowedOrigins: ['*'],
    allowedHeaders: ['*'],
    exposedHeaders: ['ETag'],
  });

  return bucket;
}
