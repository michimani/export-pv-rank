import * as cdk from '@aws-cdk/core';
import lambda = require('@aws-cdk/aws-lambda');
import iam = require('@aws-cdk/aws-iam');
import events = require('@aws-cdk/aws-events');
import targets = require('@aws-cdk/aws-events-targets');
import fs = require('fs');


export class ExportPvRankStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const stackConfig = JSON.parse(fs.readFileSync('stack-config.json', {encoding: 'utf-8'}));

    // Lambda function
    const lambdaFn = new lambda.Function(this, 'fetchRank', {
      code: new lambda.AssetCode('lambda/dist'),
      runtime: lambda.Runtime.PYTHON_3_8,
      handler: 'fetch_rank.main',
      timeout: cdk.Duration.seconds(600),
      environment: {
        'CLIENT_SECRET_SSM_KEY': stackConfig['lambda']['env']['client_secret_ssm_key'],
        'VIEW_ID': stackConfig['lambda']['env']['view_id'],
        'OUT_S3_BUCKET': stackConfig['lambda']['env']['out_s3_bucket'],
        'OUT_JSON_KEY': stackConfig['lambda']['env']['out_json_key'],
        'SITE_BASE_URL': stackConfig['lambda']['env']['site_base_url'],
      }
    });

    lambdaFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        's3:PutObject',
        'ssm:DescribeParameters',
      ],
      resources: ['*']
    }));

    lambdaFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'ssm:GetParameter',
        'ssm:GetParameters',
        'ssm:GetParameterHistory',
        'ssm:GetParametersByPath',
      ],
      resources: ['arn:aws:ssm:*']
    }));

    // EventBridge rule
    const fetchPvRanking = new events.Rule(this, 'FetchPvRanking', {
      schedule: events.Schedule.expression(`cron(${stackConfig.event_bridge.cron_expression})`)
    });

    fetchPvRanking.addTarget(new targets.LambdaFunction(lambdaFn));
  }
}
