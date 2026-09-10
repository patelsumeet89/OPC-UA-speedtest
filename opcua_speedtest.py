#!/usr/bin/env python3
"""Measure OPC UA tag read throughput and latency."""

from __future__ import annotations

import argparse
import asyncio
import csv
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from asyncua import Client


@dataclass(frozen=True)
class Sample:
    """One completed read request."""

    elapsed_seconds: float
    tag_count: int


async def read_batch(client: Client, node_ids: Sequence[str]) -> Sample:
    """Read all requested tags concurrently and record the batch latency."""
    nodes = [client.get_node(node_id) for node_id in node_ids]
    started = time.perf_counter()
    await asyncio.gather(*(node.read_value() for node in nodes))
    return Sample(time.perf_counter() - started, len(nodes))


async def worker(
    client: Client,
    node_ids: Sequence[str],
    requests: int,
    samples: list[Sample],
    semaphore: asyncio.Semaphore,
) -> None:
    for _ in range(requests):
        async with semaphore:
            samples.append(await read_batch(client, node_ids))


def percentile(values: Sequence[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((percentage / 100) * (len(ordered) - 1)))
    return ordered[index]


def write_csv(path: Path, samples: Sequence[Sample]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["elapsed_seconds", "tag_count", "tags_per_second"])
        for sample in samples:
            writer.writerow(
                [
                    f"{sample.elapsed_seconds:.9f}",
                    sample.tag_count,
                    f"{sample.tag_count / sample.elapsed_seconds:.3f}",
                ]
            )


async def run(args: argparse.Namespace) -> list[Sample]:
    node_ids = tuple(args.node_id)
    samples: list[Sample] = []
    semaphore = asyncio.Semaphore(args.concurrency)

    client = Client(url=args.endpoint)
    if args.security_string:
        await client.set_security_string(args.security_string)
    if args.username:
        client.set_user(args.username)
        client.set_password(args.password or "")

    async with client:
        if args.warmup:
            await read_batch(client, node_ids)

        requests_per_worker = args.requests // args.workers
        remainder = args.requests % args.workers
        tasks = [
            asyncio.create_task(
                worker(
                    client,
                    node_ids,
                    requests_per_worker + (worker_number < remainder),
                    samples,
                    semaphore,
                )
            )
            for worker_number in range(args.workers)
        ]
        started = time.perf_counter()
        await asyncio.gather(*tasks)
        total_seconds = time.perf_counter() - started

    print_results(samples, total_seconds)
    if args.csv:
        write_csv(Path(args.csv), samples)
        print(f"CSV written to {args.csv}")
    return samples


def print_results(samples: Sequence[Sample], total_seconds: float) -> None:
    durations = [sample.elapsed_seconds for sample in samples]
    total_tags = sum(sample.tag_count for sample in samples)
    tags_per_second = total_tags / total_seconds if total_seconds else 0.0
    print("\nOPC UA speed test")
    print("-----------------")
    print(f"Requests completed : {len(samples)}")
    print(f"Tags per request   : {samples[0].tag_count if samples else 0}")
    print(f"Total tags read    : {total_tags}")
    print(f"Elapsed            : {total_seconds:.3f} s")
    print(f"Throughput         : {tags_per_second:,.1f} tags/s")
    if durations:
        print(f"Latency average    : {statistics.mean(durations) * 1000:.2f} ms")
        print(f"Latency p50        : {percentile(durations, 50) * 1000:.2f} ms")
        print(f"Latency p95        : {percentile(durations, 95) * 1000:.2f} ms")
        print(f"Latency max        : {max(durations) * 1000:.2f} ms")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="opc.tcp://localhost:4840", help="OPC UA endpoint URL")
    parser.add_argument("--node-id", action="append", required=True, help="Node ID; repeat for each tag")
    parser.add_argument("--requests", type=int, default=100, help="Total read batches (default: 100)")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent client tasks (default: 1)")
    parser.add_argument("--concurrency", type=int, default=1, help="Maximum simultaneous reads (default: 1)")
    parser.add_argument("--username", help="Optional username")
    parser.add_argument("--password", help="Optional password")
    parser.add_argument(
        "--security-string",
        help="asyncua security string: Policy,Mode,client_certificate,private_key",
    )
    parser.add_argument("--warmup", action="store_true", help="Perform one read before collecting samples")
    parser.add_argument("--csv", help="Optional CSV output path")
    args = parser.parse_args()
    if args.requests < 1 or args.workers < 1 or args.concurrency < 1:
        parser.error("--requests, --workers, and --concurrency must be positive")
    return args


if __name__ == "__main__":
    try:
        asyncio.run(run(parse_args()))
    except KeyboardInterrupt:
        raise SystemExit("\nStopped")
