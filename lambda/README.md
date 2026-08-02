# Lambda Function

[日本語版](README.ja.md)

## Overview

`lambda_function.py` is the main application code for the AWS Cloud Cost Monitoring System. It retrieves cost data from AWS Cost Explorer, compares two seven-day periods, creates an HTML dashboard, uploads the dashboard to Amazon S3, and optionally sends a weekly report through Amazon SNS.

## Processing Flow

When the function runs, it:

1. Calculates the required date ranges in Japan Standard Time (JST).
2. Retrieves unblended costs grouped by AWS service.
3. Compares the last seven completed days with the preceding seven days.
4. Retrieves the month-to-date cost through yesterday.
5. Identifies services whose costs increased.
6. Generates a responsive HTML dashboard.
7. Uploads the dashboard to the configured S3 bucket.
8. Sends an SNS email report when email delivery is enabled.

> AWS Cost Explorer treats the end date as exclusive. Therefore, the function uses today's date as the end date and reports costs through yesterday.

## Runtime Configuration

Recommended Lambda settings:

| Setting | Value |
| --- | --- |
| Runtime | Python 3.x |
| Handler | `lambda_function.lambda_handler` |
| Architecture | `arm64` |
| Region | `us-east-1` |
| Timeout | 30 seconds |

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `S3_BUCKET_NAME` | Yes | None | S3 bucket that stores the generated dashboard |
| `SNS_TOPIC_ARN` | For email reports | None | SNS topic that receives the weekly report |
| `DASHBOARD_OBJECT_KEY` | No | `index.html` | S3 object key for the dashboard |
| `SEND_WEEKLY_EMAIL` | No | `true` | Set to `false` to disable SNS email delivery |

`AWS_REGION` is supplied automatically by Lambda. The code uses `us-east-1` as a fallback value.

Do not commit real AWS account IDs, email addresses, or private resource identifiers to a public repository.

## Required IAM Permissions

The Lambda execution role needs:

- `ce:GetCostAndUsage` to read cost data
- `s3:PutObject` for the configured dashboard object
- `sns:Publish` for the configured SNS topic when email reports are enabled
- CloudWatch Logs permissions, normally provided by `AWSLambdaBasicExecutionRole`

The policy examples are available in the repository's `iam/` directory. Restrict S3 and SNS access to the project resources whenever possible.

## Dependencies

The function uses Python standard-library modules and `boto3`, which is included in the AWS Lambda Python runtime. No external package or Lambda layer is required.

## Manual Test

The function does not require a special event payload. Use this test event in the Lambda console:

```json
{}
```

A successful invocation returns HTTP-style status code `200` and a JSON body containing the bucket name, dashboard key, cost totals, notification status, increased-service count, and generation time.

Example structure:

```json
{
  "statusCode": 200,
  "body": "{\"message\": \"AWS cost report generated successfully.\", ...}"
}
```

After the test, verify that:

- The Lambda result shows `statusCode: 200`.
- The configured dashboard object exists in S3.
- The dashboard displays current, previous, and month-to-date costs.
- CloudWatch Logs contain a successful completion message.
- The SNS email arrives when `SEND_WEEKLY_EMAIL=true` and `SNS_TOPIC_ARN` is configured.

## Scheduled Execution

Amazon EventBridge Scheduler can invoke this function automatically. The project uses a weekly schedule in the `Asia/Tokyo` time zone. For example, the following expression runs every Monday at 09:00 JST:

```text
cron(0 9 ? * MON *)
```

## Error Handling

The handler records errors with a stack trace in CloudWatch Logs and raises the exception again. This causes the Lambda invocation to be marked as failed, making operational problems visible in monitoring.

Common causes of failure include:

- Missing `S3_BUCKET_NAME`
- Incorrect S3 bucket name or object permission
- Missing Cost Explorer permission
- Incorrect SNS topic ARN or missing `sns:Publish` permission
- Cost Explorer not yet enabled for the AWS account

