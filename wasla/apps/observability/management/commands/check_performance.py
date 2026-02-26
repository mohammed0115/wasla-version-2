from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from apps.observability.performance.service import build_performance_report


DEFAULT_ENDPOINTS = [
    {"path": "/api/schema/", "method": "GET"},
    {"path": "/api/docs/", "method": "GET"},
    {"path": "/api/redoc/", "method": "GET"},
]

CRITICAL_BUSINESS_ENDPOINTS = [
    {"path": "/storefront", "method": "GET"},
    {"path": "/dashboard/", "method": "GET"},
]

CRITICAL_WEB_PUBLIC_ENDPOINTS = [
    {"path": "/", "method": "GET"},
    {"path": "/auth/", "method": "GET"},
    {"path": "/onboarding/welcome/", "method": "GET"},
    {"path": "/persona/plans/", "method": "GET"},
    {"path": "/persona/business/", "method": "GET"},
]


class Command(BaseCommand):
    help = "Measure API response latency and DB query counts using Django test client and output JSON report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--runs",
            type=int,
            default=3,
            help="Number of runs per endpoint (default: 3).",
        )
        parser.add_argument(
            "--slow-threshold-ms",
            type=float,
            default=500.0,
            help="Threshold in ms to classify an endpoint as slow (default: 500).",
        )
        parser.add_argument(
            "--endpoints",
            default="",
            help="Comma-separated endpoint paths (GET) to test, e.g. /api/schema/,/api/docs/",
        )
        parser.add_argument(
            "--profile",
            default="default",
            choices=["default", "critical", "critical_web_public"],
            help="Endpoint profile: default (docs/schema), critical (cart/checkout web), or critical_web_public (public web pages).",
        )
        parser.add_argument(
            "--output",
            default="",
            help="Optional file path to write JSON report.",
        )
        parser.add_argument(
            "--host",
            default="localhost",
            help="HTTP_HOST header value for test client requests (default: localhost).",
        )
        parser.add_argument(
            "--store-slug",
            default="store1",
            help="Optional store slug used for store-specific endpoints in critical profile.",
        )
        parser.add_argument(
            "--product-id",
            type=int,
            default=1,
            help="Product id used for product detail and price endpoints in critical profile.",
        )
        parser.add_argument(
            "--save-report",
            action="store_true",
            help="Persist benchmark report into observability database table.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output simplified JSON array with endpoint avg_duration_ms and query_count.",
        )
        parser.add_argument(
            "--store-id",
            type=int,
            default=1,
            help="Store id used for wallet summary endpoint.",
        )

    def handle(self, *args, **options):
        runs = max(1, int(options.get("runs") or 1))
        slow_threshold_ms = float(options.get("slow_threshold_ms") or 500.0)
        output_path = str(options.get("output") or "").strip()
        host = str(options.get("host") or "localhost").strip() or "localhost"
        profile = str(options.get("profile") or "default").strip().lower() or "default"
        store_slug = str(options.get("store_slug") or "").strip()
        product_id = int(options.get("product_id") or 1)
        save_report = bool(options.get("save_report"))
        json_mode = bool(options.get("json"))
        store_id = int(options.get("store_id") or 1)

        endpoints_raw = str(options.get("endpoints") or "").strip()
        if endpoints_raw:
            endpoint_specs = [
                {"path": item.strip(), "method": "GET"}
                for item in endpoints_raw.split(",")
                if item.strip()
            ]
        else:
            if profile == "critical":
                endpoint_specs = list(CRITICAL_BUSINESS_ENDPOINTS)
                if product_id > 0:
                    endpoint_specs.extend(
                        [
                            {
                                "path": f"/store/{store_slug}/products/{product_id}/",
                                "method": "GET",
                            },
                            {
                                "path": f"/api/catalog/products/{product_id}/price/",
                                "method": "GET",
                            },
                            {
                                "path": f"/api/wallet/stores/{store_id}/wallet/summary/",
                                "method": "GET",
                            },
                        ]
                    )
            elif profile == "critical_web_public":
                endpoint_specs = list(CRITICAL_WEB_PUBLIC_ENDPOINTS)
            else:
                endpoint_specs = list(DEFAULT_ENDPOINTS)

        report = build_performance_report(
            endpoint_specs=endpoint_specs,
            runs_per_endpoint=runs,
            slow_threshold_ms=slow_threshold_ms,
            host=host,
        )
        report["profile"] = profile
        report["host"] = host
        report["store_slug"] = store_slug
        report["product_id"] = product_id
        report["store_id"] = store_id

        summary_rows = [
            {
                "endpoint": item.get("path"),
                "avg_duration_ms": item.get("average_response_ms", 0),
                "query_count": item.get("average_query_count", 0),
            }
            for item in report.get("endpoints", [])
        ]

        if save_report:
            try:
                from apps.observability.models import PerformanceBenchmarkReport, PerformanceReport

                PerformanceBenchmarkReport.objects.create(
                    profile=profile,
                    host=host,
                    runs_per_endpoint=runs,
                    slow_threshold_ms=slow_threshold_ms,
                    summary=report.get("summary", {}),
                    report=report,
                )
                PerformanceReport.objects.create(summary_json={"results": summary_rows}, status="ok")
            except Exception as exc:  # pragma: no cover - defensive persistence path
                self.stderr.write(self.style.WARNING(f"Unable to persist benchmark report: {exc}"))
        output_payload = summary_rows if json_mode else report
        output = json.dumps(output_payload, ensure_ascii=False, indent=2)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as handle:
                handle.write(output)
            self.stdout.write(self.style.SUCCESS(f"Performance report written to: {output_path}"))

        self.stdout.write(output)
