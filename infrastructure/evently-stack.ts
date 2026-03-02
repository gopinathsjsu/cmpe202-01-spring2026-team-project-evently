import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { Config, EventlyStackProps } from './config';
import { createVpc } from './vpc';
import { createAssetsBucket } from './s3';
import { createSnsTopic } from './sns';
import { createOutputs } from './output';

export class EventlyStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: EventlyStackProps & cdk.StackProps) {
    super(scope, id, props);

    const config = props as unknown as Config;
    const projectName = config.projectName ?? 'evently';
    const environment = config.environment ?? 'dev';
    const prefix = `${projectName}-${environment}`;
    const removalPolicy =
      environment === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY;

    const vpc = createVpc(this, { prefix });

    const assetsBucket = createAssetsBucket(this, {
      projectName,
      environment,
      account: this.account,
      versioned: config.s3EnableVersioning,
      removalPolicy,
    });

    const topic = createSnsTopic(this, { prefix });

    createOutputs(this, {
      prefix,
      bucket: assetsBucket,
      vpc,
      topic,
    });
  }
}
