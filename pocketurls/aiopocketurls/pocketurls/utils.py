import aioredis
import aiopg
import hashlib
import logging
import trafaret
import yaml
from aiohttp import web


def load_config(fname):
    with open(fname, 'rt') as f:
        data = yaml.safe_load(f)
    return data


async def exec_postgres_query(pool, q):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            logging.info('Executing postgres query: {}'.format(q))
            result = await cur.execute(q)
            logging.info('Done.')

    return result


async def init_redis(conf, loop):
    pool = await aioredis.create_redis_pool(
        (conf['host'], conf['port']),
        minsize=1,
        maxsize=5,
        loop=loop,
    )
    return pool


async def init_postgres(conf, loop):
    pool = await aiopg.create_pool(
        dsn=conf['dsn'],
        minsize=1,
        maxsize=5,
        loop=loop)

    await exec_postgres_query(
        pool,
        'CREATE TABLE IF NOT EXISTS urls (short_form varchar(32) PRIMARY KEY, long_url varchar(255))')

    return pool


async def check_if_hash_already_exists(short_form, postgres_pool):
    short_form = await exec_postgres_query(postgres_pool,
                                           'SELECT short_form from urls WHERE short_form=\'{}\''.format(short_form))
    logging.info("Postgres result: {}".format(short_form))

    return bool(short_form)


async def encode(original_url, postgres_pool):
    md5hash = hashlib.md5(original_url.encode('utf-8')).hexdigest()

    for tries in range(1, 10):
        short_form = md5hash[-6 - tries:-tries]

        if not await check_if_hash_already_exists(short_form, postgres_pool):
            logging.info('Generated a new hash: {} for url: {}, attempts: {}.'.format(short_form, original_url, tries))
            return short_form

        logging.debug('Collision occurred for url: {}, resolution attempts so far: {}.'.format(original_url, tries))

    logging.error('Unable to find unique hash for url: {}. Returning md5 hash: {}.'.format(original_url, md5hash))

    return md5hash


def fetch_url(data):
    try:
        data = trafaret.Dict({trafaret.Key('url'): trafaret.URL})(data)
    except trafaret.DataError:
        raise web.HTTPBadRequest('URL is not valid')

    return data['url']
