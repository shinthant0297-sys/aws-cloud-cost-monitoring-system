import html
import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import boto3


# ============================================================
# Logging
# ============================================================

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ============================================================
# Project configuration
# ============================================================

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
DASHBOARD_OBJECT_KEY = os.getenv("DASHBOARD_OBJECT_KEY", "index.html")
SEND_WEEKLY_EMAIL = os.getenv("SEND_WEEKLY_EMAIL", "true").lower() == "true"

JST = ZoneInfo("Asia/Tokyo")


# ============================================================
# AWS clients
# ============================================================

ce = boto3.client(
    "ce",
    region_name=AWS_REGION
)

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION
)

sns = boto3.client(
    "sns",
    region_name=AWS_REGION
)


# ============================================================
# Helper functions
# ============================================================

def to_decimal(value):
    """Convert a Cost Explorer amount to Decimal safely."""

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def format_money(value):
    """Format a numeric value as a USD amount with four decimal places."""

    amount = to_decimal(value)
    return f"${amount:,.4f}"


def get_date_ranges():
    """
    Build date ranges using today's date as the exclusive end date.

    The periods cover the last seven completed days, the preceding seven
    days, and month-to-date through yesterday.
    """

    now_jst = datetime.now(JST)
    today = now_jst.date()

    current_end = today
    current_start = current_end - timedelta(days=7)

    previous_end = current_start
    previous_start = previous_end - timedelta(days=7)

    month_start = today.replace(day=1)
    month_end = today

    return {
        "generated_at": now_jst,
        "today": today,
        "current_start": current_start,
        "current_end": current_end,
        "previous_start": previous_start,
        "previous_end": previous_end,
        "month_start": month_start,
        "month_end": month_end
    }


def get_cost_and_usage(start_date, end_date):
    """
    Retrieve UnblendedCost grouped by AWS service for a date range.

    Follow Cost Explorer pagination so accounts with larger result sets are
    handled correctly.
    """

    if start_date >= end_date:
        logger.info(
            "Skipping Cost Explorer request because start date %s "
            "is not earlier than end date %s",
            start_date,
            end_date
        )

        return {
            "total": Decimal("0"),
            "services": {},
            "currency": "USD"
        }

    services = {}
    total_cost = Decimal("0")
    currency = "USD"
    next_page_token = None

    while True:
        request_parameters = {
            "TimePeriod": {
                "Start": start_date.isoformat(),
                "End": end_date.isoformat()
            },
            "Granularity": "DAILY",
            "Metrics": [
                "UnblendedCost"
            ],
            "GroupBy": [
                {
                    "Type": "DIMENSION",
                    "Key": "SERVICE"
                }
            ]
        }

        if next_page_token:
            request_parameters["NextPageToken"] = next_page_token

        response = ce.get_cost_and_usage(**request_parameters)

        for time_result in response.get("ResultsByTime", []):
            for group in time_result.get("Groups", []):
                service_name = (
                    group.get("Keys", ["Unknown service"])[0]
                )

                metric = (
                    group.get("Metrics", {})
                    .get("UnblendedCost", {})
                )

                amount = to_decimal(metric.get("Amount", "0"))
                currency = metric.get("Unit", currency)

                services[service_name] = (
                    services.get(service_name, Decimal("0"))
                    + amount
                )

                total_cost += amount

        next_page_token = response.get("NextPageToken")

        if not next_page_token:
            break

    return {
        "total": total_cost,
        "services": services,
        "currency": currency
    }


def compare_service_costs(current_services, previous_services):
    """Compare service costs between the current and previous periods."""

    service_names = set(current_services) | set(previous_services)
    comparison = []

    for service_name in service_names:
        current_cost = current_services.get(
            service_name,
            Decimal("0")
        )

        previous_cost = previous_services.get(
            service_name,
            Decimal("0")
        )

        difference = current_cost - previous_cost

        if previous_cost > 0:
            percentage_change = (
                difference / previous_cost
            ) * Decimal("100")
        elif current_cost > 0:
            percentage_change = None
        else:
            percentage_change = Decimal("0")

        comparison.append(
            {
                "service": service_name,
                "current": current_cost,
                "previous": previous_cost,
                "difference": difference,
                "percentage_change": percentage_change
            }
        )

    comparison.sort(
        key=lambda item: item["current"],
        reverse=True
    )

    return comparison


def get_increased_services(comparison):
    """Return services whose cost increased over the previous period."""

    increased_services = [
        item
        for item in comparison
        if item["difference"] > 0
    ]

    increased_services.sort(
        key=lambda item: item["difference"],
        reverse=True
    )

    return increased_services


def percentage_text(value):
    """Format a percentage change for display on the dashboard."""

    if value is None:
        return "New cost"

    return f"{value:+.2f}%"


def difference_class(difference):
    """Return the CSS class corresponding to a cost difference."""

    if difference > 0:
        return "increase"

    if difference < 0:
        return "decrease"

    return "neutral"


# ============================================================
# HTML dashboard
# ============================================================

def build_service_rows(comparison):
    """Build HTML rows for the service cost comparison table."""

    rows = []

    for item in comparison:
        safe_service_name = html.escape(item["service"])

        css_class = difference_class(
            item["difference"]
        )

        rows.append(
            f"""
            <tr>
                <td>{safe_service_name}</td>
                <td>{format_money(item["current"])}</td>
                <td>{format_money(item["previous"])}</td>
                <td class="{css_class}">
                    {format_money(item["difference"])}
                </td>
                <td class="{css_class}">
                    {percentage_text(item["percentage_change"])}
                </td>
            </tr>
            """
        )

    if not rows:
        rows.append(
            """
            <tr>
                <td colspan="5">
                    Cost data is not available yet.
                </td>
            </tr>
            """
        )

    return "\n".join(rows)


def build_increased_service_cards(increased_services):
    """Build dashboard cards for services with increased costs."""

    cards = []

    for item in increased_services[:5]:
        safe_service_name = html.escape(item["service"])

        cards.append(
            f"""
            <div class="alert-card">
                <div class="alert-service">
                    {safe_service_name}
                </div>

                <div class="alert-amount">
                    +{format_money(item["difference"])}
                </div>

                <div class="alert-detail">
                    Current: {format_money(item["current"])}
                    &nbsp;|&nbsp;
                    Previous: {format_money(item["previous"])}
                </div>
            </div>
            """
        )

    if not cards:
        cards.append(
            """
            <div class="success-card">
                No increased service costs were detected.
            </div>
            """
        )

    return "\n".join(cards)


def generate_dashboard_html(
    dates,
    current_cost,
    previous_cost,
    monthly_cost,
    comparison,
    increased_services
):
    """Generate the complete HTML dashboard."""

    generated_at = dates["generated_at"].strftime(
        "%Y-%m-%d %H:%M:%S JST"
    )

    current_period = (
        f"{dates['current_start'].isoformat()} "
        f"to {(dates['current_end'] - timedelta(days=1)).isoformat()}"
    )

    previous_period = (
        f"{dates['previous_start'].isoformat()} "
        f"to {(dates['previous_end'] - timedelta(days=1)).isoformat()}"
    )

        if dates["month_start"] == dates["month_end"]:
        monthly_period = "No completed days in the current month yet"
    else:
        monthly_period = (
            f"{dates['month_start'].isoformat()} "
            f"to {(dates['month_end'] - timedelta(days=1)).isoformat()}"
        )

    weekly_difference = (
        current_cost["total"]
        - previous_cost["total"]
    )

    service_rows = build_service_rows(comparison)

    increased_cards = build_increased_service_cards(
        increased_services
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>AWS Cloud Cost Dashboard</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 0;
            background: #f3f6fa;
            color: #1f2937;
            font-family:
                Arial,
                Helvetica,
                sans-serif;
        }}

        .header {{
            padding: 36px 20px;
            background:
                linear-gradient(
                    135deg,
                    #152939,
                    #232f3e
                );
            color: white;
            text-align: center;
        }}

        .header h1 {{
            margin: 0 0 10px;
            font-size: 32px;
        }}

        .header p {{
            margin: 4px 0;
            color: #d6e1eb;
        }}

        .aws-orange {{
            color: #ff9900;
        }}

        .container {{
            width: min(1180px, 94%);
            margin: 30px auto;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            padding: 22px;
            background: white;
            border-radius: 12px;
            box-shadow:
                0 4px 14px rgba(0, 0, 0, 0.07);
        }}

        .summary-label {{
            margin-bottom: 12px;
            color: #6b7280;
            font-size: 14px;
        }}

        .summary-value {{
            font-size: 28px;
            font-weight: bold;
        }}

        .summary-period {{
            margin-top: 10px;
            color: #6b7280;
            font-size: 12px;
        }}

        .section {{
            margin-bottom: 30px;
            padding: 24px;
            background: white;
            border-radius: 12px;
            box-shadow:
                0 4px 14px rgba(0, 0, 0, 0.07);
        }}

        .section h2 {{
            margin-top: 0;
            color: #232f3e;
        }}

        .alert-card {{
            margin-bottom: 12px;
            padding: 16px;
            background: #fff7ed;
            border-left: 5px solid #f97316;
            border-radius: 8px;
        }}

        .success-card {{
            padding: 16px;
            background: #ecfdf5;
            color: #047857;
            border-left: 5px solid #10b981;
            border-radius: 8px;
        }}

        .alert-service {{
            font-weight: bold;
        }}

        .alert-amount {{
            margin-top: 6px;
            color: #dc2626;
            font-size: 20px;
            font-weight: bold;
        }}

        .alert-detail {{
            margin-top: 6px;
            color: #6b7280;
            font-size: 13px;
        }}

        .table-wrapper {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            padding: 14px 12px;
            border-bottom: 1px solid #e5e7eb;
            text-align: right;
            white-space: nowrap;
        }}

        th:first-child,
        td:first-child {{
            text-align: left;
        }}

        th {{
            background: #f8fafc;
            color: #374151;
        }}

        tr:hover {{
            background: #f9fafb;
        }}

        .increase {{
            color: #dc2626;
            font-weight: bold;
        }}

        .decrease {{
            color: #059669;
            font-weight: bold;
        }}

        .neutral {{
            color: #6b7280;
        }}

        .footer {{
            padding: 24px;
            color: #6b7280;
            text-align: center;
            font-size: 13px;
        }}

        @media (max-width: 600px) {{
            .header h1 {{
                font-size: 25px;
            }}

            .container {{
                width: 96%;
            }}

            .section {{
                padding: 16px;
            }}
        }}
    </style>
</head>

<body>
    <header class="header">
        <h1>
            <span class="aws-orange">AWS</span>
            Cloud Cost Dashboard
        </h1>

        <p>Serverless Cost Monitoring System</p>
        <p>Generated: {generated_at}</p>
    </header>

    <main class="container">
        <section class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">
                    Current 7-Day Cost
                </div>

                <div class="summary-value">
                    {format_money(current_cost["total"])}
                </div>

                <div class="summary-period">
                    {current_period}
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-label">
                    Previous 7-Day Cost
                </div>

                <div class="summary-value">
                    {format_money(previous_cost["total"])}
                </div>

                <div class="summary-period">
                    {previous_period}
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-label">
                    Weekly Difference
                </div>

                <div class="summary-value
                    {difference_class(weekly_difference)}">
                    {format_money(weekly_difference)}
                </div>

                <div class="summary-period">
                    Current period minus previous period
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-label">
                    Month-to-Date Cost
                </div>

                <div class="summary-value">
                    {format_money(monthly_cost["total"])}
                </div>

                <div class="summary-period">
                    {monthly_period}
                </div>
            </div>
        </section>

        <section class="section">
            <h2>Services With Increased Costs</h2>
            {increased_cards}
        </section>

        <section class="section">
            <h2>Service Cost Comparison</h2>

            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>AWS Service</th>
                            <th>Current 7 Days</th>
                            <th>Previous 7 Days</th>
                            <th>Difference</th>
                            <th>Change</th>
                        </tr>
                    </thead>

                    <tbody>
                        {service_rows}
                    </tbody>
                </table>
            </div>
        </section>
    </main>

    <footer class="footer">
        Dashboard generated by AWS Lambda and Cost Explorer.
        Region: {AWS_REGION}
    </footer>
</body>
</html>
"""


# ============================================================
# S3 dashboard upload
# ============================================================

def upload_dashboard(dashboard_html):
    """Upload the generated dashboard to Amazon S3."""

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=DASHBOARD_OBJECT_KEY,
        Body=dashboard_html.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
        CacheControl="no-cache, no-store, must-revalidate"
    )

    logger.info(
        "Dashboard uploaded successfully to s3://%s/%s",
        BUCKET_NAME,
        DASHBOARD_OBJECT_KEY
    )


# ============================================================
# SNS weekly email
# ============================================================

def send_weekly_report(
    dates,
    current_cost,
    previous_cost,
    monthly_cost,
    increased_services
):
    """Publish the weekly cost summary through Amazon SNS."""

    current_end_display = (
        dates["current_end"] - timedelta(days=1)
    )

    previous_end_display = (
        dates["previous_end"] - timedelta(days=1)
    )

    weekly_difference = (
        current_cost["total"]
        - previous_cost["total"]
    )

    lines = [
        "AWS WEEKLY COST REPORT",
        "",
        (
            "Current period: "
            f"{dates['current_start'].isoformat()} "
            f"to {current_end_display.isoformat()}"
        ),
        (
            "Previous period: "
            f"{dates['previous_start'].isoformat()} "
            f"to {previous_end_display.isoformat()}"
        ),
        "",
        (
            "Current 7-day cost: "
            f"{format_money(current_cost['total'])}"
        ),
        (
            "Previous 7-day cost: "
            f"{format_money(previous_cost['total'])}"
        ),
        (
            "Weekly difference: "
            f"{format_money(weekly_difference)}"
        ),
        (
            "Month-to-date cost: "
            f"{format_money(monthly_cost['total'])}"
        ),
        "",
        "SERVICES WITH INCREASED COSTS"
    ]

    if increased_services:
        for item in increased_services[:10]:
            if item["percentage_change"] is None:
                change_description = "new cost"
            else:
                change_description = (
                    f"{item['percentage_change']:+.2f}%"
                )

            lines.append(
                (
                    f"- {item['service']}: "
                    f"+{format_money(item['difference'])} "
                    f"({change_description})"
                )
            )
    else:
        lines.append(
            "- No increased service costs detected."
        )

    lines.extend(
        [
            "",
            f"S3 dashboard: s3://{BUCKET_NAME}/{DASHBOARD_OBJECT_KEY}",
            f"Generated: {dates['generated_at'].strftime('%Y-%m-%d %H:%M:%S JST')}"
        ]
    )

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="AWS Weekly Cost Report",
        Message="\n".join(lines)
    )

    logger.info(
        "Weekly cost report published successfully to SNS topic %s",
        SNS_TOPIC_ARN
    )


# ============================================================
# Lambda handler
# ============================================================

def lambda_handler(event, context):
    """
    Lambda function entry point.
    """

    logger.info(
        "Lambda execution started. Event: %s",
        json.dumps(event, default=str)
    )

    try:
        dates = get_date_ranges()

        logger.info(
            "Getting current-period cost: %s to %s",
            dates["current_start"],
            dates["current_end"]
        )

        current_cost = get_cost_and_usage(
            dates["current_start"],
            dates["current_end"]
        )

        logger.info(
            "Getting previous-period cost: %s to %s",
            dates["previous_start"],
            dates["previous_end"]
        )

        previous_cost = get_cost_and_usage(
            dates["previous_start"],
            dates["previous_end"]
        )

        logger.info(
            "Getting month-to-date cost: %s to %s",
            dates["month_start"],
            dates["month_end"]
        )

        monthly_cost = get_cost_and_usage(
            dates["month_start"],
            dates["month_end"]
        )

        comparison = compare_service_costs(
            current_cost["services"],
            previous_cost["services"]
        )

        increased_services = get_increased_services(
            comparison
        )

        dashboard_html = generate_dashboard_html(
            dates=dates,
            current_cost=current_cost,
            previous_cost=previous_cost,
            monthly_cost=monthly_cost,
            comparison=comparison,
            increased_services=increased_services
        )

        upload_dashboard(dashboard_html)

        if SEND_WEEKLY_EMAIL and SNS_TOPIC_ARN:
            send_weekly_report(
                dates=dates,
                current_cost=current_cost,
                previous_cost=previous_cost,
                monthly_cost=monthly_cost,
                increased_services=increased_services
            )
        else:
            logger.info(
                "SNS weekly email is disabled or SNS_TOPIC_ARN is not set."
            )

        response_body = {
            "message": "AWS cost report generated successfully.",
            "region": AWS_REGION,
            "bucket": BUCKET_NAME,
            "dashboard_key": DASHBOARD_OBJECT_KEY,
            "sns_notification_enabled": bool(
                SEND_WEEKLY_EMAIL and SNS_TOPIC_ARN
            ),
            "current_7_day_cost": str(
                current_cost["total"]
            ),
            "previous_7_day_cost": str(
                previous_cost["total"]
            ),
            "month_to_date_cost": str(
                monthly_cost["total"]
            ),
            "increased_service_count": len(
                increased_services
            ),
            "generated_at": dates[
                "generated_at"
            ].isoformat()
        }

        logger.info(
            "Lambda execution completed successfully: %s",
            json.dumps(response_body)
        )

        return {
            "statusCode": 200,
            "body": json.dumps(response_body)
        }

    except Exception:
        logger.exception(
            "Failed to generate AWS cost report."
        )

        raise
