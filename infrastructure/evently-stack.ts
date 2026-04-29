import * as cdk from 'aws-cdk-lib';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import { Construct } from 'constructs';
import { Config, EventlyStackProps } from './config';
import { createVpc } from './vpc';
import { createAssetsBucket } from './s3';
import { createSnsTopic } from './sns';
import { createOutputs } from './output';

export class EventlyStack extends cdk.Stack {
  readonly vpc: cdk.aws_ec2.IVpc;

  constructor(scope: Construct, id: string, props: EventlyStackProps & cdk.StackProps) {
    super(scope, id, props);

    const config = props as unknown as Config;
    const projectName = config.projectName ?? 'evently';
    const environment = config.environment ?? 'dev';
    const prefix = `${projectName}-${environment}`;
    const removalPolicy =
      environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY;

    const vpc = createVpc(this, { prefix });
    this.vpc = vpc;

    const assetsBucket = createAssetsBucket(this, {
      projectName,
      environment,
      account: this.account,
      versioned: config.s3EnableVersioning,
      removalPolicy,
    });

    const topic = createSnsTopic(this, { prefix });

    const backendRepository = new ecr.Repository(this, 'BackendEcrRepository', {
      repositoryName: `${prefix}-backend`,
      imageScanOnPush: true,
      lifecycleRules: [{ maxImageCount: 10, description: 'Keep last 10 images' }],
      removalPolicy,
    });

    new cdk.CfnOutput(this, 'BackendEcrRepositoryUri', {
      description: 'ECR URI for the backend Docker image (tag and push, then use with apiImageUri)',
      value: backendRepository.repositoryUri,
      exportName: `${prefix}-BackendEcrUri`,
    });

    createOutputs(this, {
      prefix,
      bucket: assetsBucket,
      vpc,
      topic,
    });
  }
}
