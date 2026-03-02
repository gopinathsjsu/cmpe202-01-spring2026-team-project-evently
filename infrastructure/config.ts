import * as cdk from 'aws-cdk-lib';

export interface EventlyStackProps extends cdk.StackProps {
  projectName: string;
  environment: string;
  awsRegion: string;
  stackName?: string;
  s3EnableVersioning: boolean;
}

export class Config {
  readonly projectName: string;
  readonly environment: string;
  readonly awsRegion: string;
  readonly stackName: string;
  readonly s3EnableVersioning: boolean;

  constructor(props: EventlyStackProps) {
    this.projectName = props.projectName;
    this.environment = props.environment;
    this.awsRegion = props.awsRegion;
    this.stackName = props.stackName ?? `${props.projectName}-${props.environment}-stack`;
    this.s3EnableVersioning = props.s3EnableVersioning;
  }

  get namePrefix(): string {
    return `${this.projectName}-${this.environment}`;
  }

  static fromApp(app: cdk.App): Config {
    const projectName = app.node.tryGetContext('projectName') ?? 'evently';
    const environment = app.node.tryGetContext('environment') ?? 'dev';
    const awsRegion = app.node.tryGetContext('awsRegion') ?? process.env.CDK_DEFAULT_REGION ?? 'us-west-2';
    const stackName = app.node.tryGetContext('stackName') ?? `${projectName}-${environment}-stack`;

    return new Config({
      projectName,
      environment,
      awsRegion,
      stackName,
      s3EnableVersioning: app.node.tryGetContext('s3EnableVersioning') === 'true',
    } as EventlyStackProps);
  }
}
