#!/bin/bash
gunicorn pocketurls.main:gunicorn_entry_point --bind 0.0.0.0:5000 --worker-class aiohttp.worker.GunicornWebWorker

