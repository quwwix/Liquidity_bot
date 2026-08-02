#!/usr/bin/env python3
"""Manual scrape trigger for testing."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from app.scheduler.jobs import run_daily_scrape


if __name__ == "__main__":
    asyncio.run(run_daily_scrape())
