from __future__ import annotations

import time
from statistics import mean, median

from django.core.management.base import BaseCommand, CommandParser
from django.core.files.storage import default_storage

from apps.ai.infrastructure.providers.registry import get_provider
from apps.ai.infrastructure.embeddings.vector_store import search_similar, upsert_embedding
from apps.ai.infrastructure.embeddings.image_attributes import extract_from_bytes
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Quick KPI check for Visual Search: embedding latency + search latency + basic sanity."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--store-id", type=int, required=True)
        parser.add_argument("--top-n", type=int, default=12)
        parser.add_argument("--samples", type=int, default=20)

    def handle(self, *args, **options):
        store_id = int(options["store_id"])
        top_n = int(options["top_n"])
        samples = int(options["samples"])

        provider = get_provider()

        qs = Product.objects.filter(store_id=store_id, is_active=True).exclude(image="")[: max(samples, 1)]
        prods = list(qs)

        if not prods:
            self.stdout.write(self.style.ERROR("No products with images found for this store."))
            return

        emb_times = []
        search_times = []
        for p in prods:
            image_bytes = p.image.read()

            t0 = time.perf_counter()
            emb = provider.embed_image(image_bytes=image_bytes)
            emb_times.append((time.perf_counter() - t0) * 1000)

            # ensure indexed (upsert for the same product so we have at least one vector)
            upsert_embedding(store_id=store_id, product_id=p.id, vector=emb.vector, provider=getattr(emb, "provider", ""), attributes=extract_from_bytes(image_bytes))

            t1 = time.perf_counter()
            _ = search_similar(store_id=store_id, vector=emb.vector, top_n=top_n)
            search_times.append((time.perf_counter() - t1) * 1000)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Visual Search KPI (approx)"))
        self.stdout.write(f"Store: {store_id} | samples: {len(prods)} | top_n: {top_n}")
        self.stdout.write(f"Embedding latency ms: mean={mean(emb_times):.1f} median={median(emb_times):.1f} p95≈{sorted(emb_times)[int(len(emb_times)*0.95)-1]:.1f}")
        self.stdout.write(f"Search latency ms:    mean={mean(search_times):.1f} median={median(search_times):.1f} p95≈{sorted(search_times)[int(len(search_times)*0.95)-1]:.1f}")
        self.stdout.write("")
        self.stdout.write("Tip: enable CLIP with env AI_USE_CLIP_EMBEDDINGS=1 (requires torch+transformers).")
