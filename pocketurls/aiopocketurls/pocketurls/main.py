import asyncio
import logging
import pathlib

import aiohttp_jinja2
import jinja2
from aiohttp import web

from pocketurls.routes import setup_routes
from pocketurls.utils import init_postgres, init_redis, load_config
from pocketurls.views import SiteHandler


PROJ_ROOT = pathlib.Path(__file__).parent.parent
TEMPLATES_ROOT = pathlib.Path(__file__).parent / 'templates'


async def setup_redis(app, conf, loop):
    pool = await init_redis(conf['redis'], loop)

    async def close_redis(app):
        pool.close()
        await pool.wait_closed()

    app.on_cleanup.append(close_redis)
    app['redis_pool'] = pool
    return pool


async def setup_postgres(app, conf, loop):
    pool = await init_postgres(conf['postgres'], loop)

    async def close_postgres(app):
        pool.close()
        await pool.wait_closed()

    app.on_cleanup.append(close_postgres)
    app['postgres_pool'] = pool
    return pool


def setup_jinja(app):
    loader = jinja2.FileSystemLoader(str(TEMPLATES_ROOT))
    jinja_env = aiohttp_jinja2.setup(app, loader=loader)
    return jinja_env


async def init(loop):
    logging.basicConfig(level=logging.DEBUG)
    conf = load_config(PROJ_ROOT / 'config' / 'config.yml')

    app = web.Application()
    redis_pool = await setup_redis(app, conf, loop)
    postgres_pool = await setup_postgres(app, conf, loop)
    setup_jinja(app)

    handler = SiteHandler(conf, postgres_pool, redis_pool)

    setup_routes(app, handler)

    return app


async def gunicorn_entry_point():
    loop = asyncio.get_event_loop()

    return await init(loop)
