# EventBridge Scheduler の設定

このファイルは、クラウド料金レポートを毎週自動で実行するための Amazon EventBridge Scheduler の設定を説明します。

## スケジュールの設定

| 設定 | 値 |
| --- | --- |
| スケジュール名 | `weekly-cloud-cost-report` |
| スケジュールグループ | `default` |
| スケジュールの種類 | 繰り返しスケジュール |
| スケジュール式 | `cron(0 9 ? * MON *)` |
| タイムゾーン | `Asia/Tokyo` |
| Flexible time window | Off |
| スケジュールの状態 | Enabled |
| 完了後のアクション | None |

このスケジュールは、毎週月曜日の午前9時（日本時間）に実行されます。

## ターゲットの設定

| 設定 | 値 |
| --- | --- |
| ターゲットサービス | AWS Lambda |
| Lambda 関数 | `cloud-cost-report-generator` |
| 入力データ | `{}` |
| 実行ロール | EventBridge Scheduler の実行ロール |

実行ロールには、対象の Lambda 関数に対する次の権限が必要です。

```text
lambda:InvokeFunction
```

関係する IAM ポリシーの例は、次のファイルにあります。

- `../iam/eventbridge-scheduler-invoke-lambda-policy.json`
- `../iam/eventbridge-scheduler-trust-policy.json`

## 再試行と失敗時の設定

このポートフォリオでは、AWS の標準の再試行設定を使うことができます。Dead-letter queue は必須ではありません。本番環境では、Amazon SQS の Dead-letter queue を設定し、運用に合う再試行ポリシーを使うことをおすすめします。

## AWS Console での作成手順

1. AWS Management Console で **Amazon EventBridge** を開きます。
2. **Scheduler** を選び、**Create schedule** をクリックします。
3. スケジュール名に `weekly-cloud-cost-report` を入力します。
4. **Recurring schedule** を選び、`cron(0 9 ? * MON *)` を入力します。
5. タイムゾーンを `Asia/Tokyo` にします。
6. **Flexible time window** を Off にします。
7. ターゲットに **AWS Lambda Invoke** を選びます。
8. `cloud-cost-report-generator` 関数を選びます。
9. 入力データに `{}` を使います。
10. この Lambda 関数だけを実行できる IAM ロールを選ぶか、新しく作ります。
11. スケジュールを Enabled にして作成します。

## 動作確認

設定した時間の後で、次の項目を確認します。

- Lambda 関数が正常に実行されたこと
- Amazon CloudWatch Logs に新しいログがあること
- S3 のダッシュボードが更新されたこと
- メール送信が有効な場合、SNS のレポートメールが届いたこと

## セキュリティについて

- AWS アカウント ID や、アカウント ID が入った ARN を GitHub に保存しません。
- `lambda:InvokeFunction` は、対象の Lambda 関数だけに許可します。
- Scheduler の信頼ポリシーは `scheduler.amazonaws.com` だけに許可します。
