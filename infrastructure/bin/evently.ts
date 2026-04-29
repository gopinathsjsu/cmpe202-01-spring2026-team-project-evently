import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { EventlyStack } from '../evently-stack';
import { EventlyApiStack } from '../api-stack';
import { Config } from '../config';

const app = new cdk.App();
const config = Config.fromApp(app);
const account = process.env.CDK_DEFAULT_ACCOUNT;
const region = config.awsRegion ?? process.env.CDK_DEFAULT_REGION;

new EventlyStack(app, config.stackName, {
  env: account && region ? { account, region } : undefined,
  description: 'Evently foundation: VPC, S3, SNS, ECR',
  tags: {
    Project: config.projectName,
    Environment: config.environment,
    ManagedBy: 'cdk',
  },
  ...config,
});

const foundationPrefix = `${config.projectName}-${config.environment}`;

const apiImageUri = app.node.tryGetContext('apiImageUri');
let apiStack: EventlyApiStack | undefined;
if (typeof apiImageUri === 'string' && apiImageUri.trim()) {
  const apiStackName = app.node.tryGetContext('apiStackName') ?? `${config.stackName}-api`;
  const instanceType = app.node.tryGetContext('apiInstanceType') ?? 't3.micro';
  const healthCheckPath = app.node.tryGetContext('apiHealthCheckPath') ?? '/health';
  const enableNotificationWorker =
    app.node.tryGetContext('enableNotificationWorker') !== 'false';
  const valkeyNodeType = app.node.tryGetContext('valkeyNodeType') ?? 'cache.t4g.micro';
  const parseCapacity = (value: unknown, fallback: number): number => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
  };

  const minCapacity = parseCapacity(app.node.tryGetContext('apiMinCapacity'), 2);
  const desiredCapacity = parseCapacity(app.node.tryGetContext('apiDesiredCapacity'), 2);
  const maxCapacity = parseCapacity(app.node.tryGetContext('apiMaxCapacity'), 4);

  apiStack = new EventlyApiStack(app, apiStackName, {
    env: account && region ? { account, region } : undefined,
    description: 'Evently API: ALB + Auto Scaling EC2',
    tags: {
      Project: config.projectName,
      Environment: config.environment,
      ManagedBy: 'cdk',
      Workload: 'api',
    },
    ...config,
    stackName: apiStackName,
    foundationVpcExportPrefix: foundationPrefix,
    apiImageUri,
    instanceType,
    minCapacity,
    desiredCapacity,
    maxCapacity,
    healthCheckPath,
    enableNotificationWorker,
    valkeyNodeType,
  });
} else {
  // Keeps existing one-stack behavior for teams not deploying API yet.
  console.warn(
    'Skipping API stack creation. Pass -c apiImageUri=<account>.dkr.ecr.<region>.amazonaws.com/<project>-<env>-backend:tag (see foundation stack ECR output) to create ALB + ASG stack.'
  );
}

app.synth();
