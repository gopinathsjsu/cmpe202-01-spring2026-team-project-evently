import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { EventlyStack } from '../evently-stack';
import { Config } from '../config';

const app = new cdk.App();
const config = Config.fromApp(app);
const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = config.awsRegion ?? process.env.CDK_DEFAULT_REGION;

new EventlyStack(app, config.stackName, {
  env: account && region ? { account, region } : undefined,
  description: 'Evently minimal: VPC, S3, SNS',
  tags: {
    Project: config.projectName,
    Environment: config.environment,
    ManagedBy: 'cdk',
  },
  ...config,
});

app.synth();
