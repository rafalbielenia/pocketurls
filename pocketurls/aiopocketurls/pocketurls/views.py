import aiohttp_jinja2
import logging
from aiohttp import web

from .utils import encode, exec_postgres_query, fetch_url


class SiteHandler:

    def __init__(self, conf, postgres, redis):
        self._conf = conf
        self._postgres = postgres
        self._redis = redis

    @aiohttp_jinja2.template('index.html')
    async def index(self, request):
        return {}

    async def shorten(self, request):
        data = await request.json()
        long_url = fetch_url(data)

        key = 'pocketurls_long_to_short:{}'.format(long_url)
        short_form = await self._redis.get(key)

        if not short_form:
            short_form = await exec_postgres_query(self._postgres,
                                                   'SELECT short_form from urls WHERE long_url=\'{}\''.format(long_url))
            logging.info("Postgres result: {}".format(short_form))

            if not short_form:
                logging.info("Short-form doesn't exist. Generating a new one for {}.".format(long_url))
                short_form = await encode(long_url, self._postgres)

                await exec_postgres_query(self._postgres,
                                          'INSERT INTO urls VALUES(\'{}\', \'{}\')'.format(short_form, long_url))
                logging.info("Saved to postgres {} {}.".format(short_form, long_url))
            else:
                logging.info("Db hit. Postgres returned short_form {} for {}.".format(short_form, long_url))

            await self._redis.set(key, short_form)

            key = "pocketurls_short_to_long:{}".format(short_form)
            await self._redis.set(key, long_url)
        else:
            short_form = str(short_form, 'utf-8')
            logging.info("Cache hit. Redis returned short_form {} for {}.".format(short_form, long_url))

        url = "http://{host}{port}/{path}".format(
            host=self._conf['external_host'],
            port=":{}".format(self._conf['external_port']) if self._conf['external_port'] else "",
            path=short_form)

        return web.json_response({"url": url})

    async def redirect(self, request):
        short_form = request.match_info['short_form']
        if short_form == 'favicon.ico':
            return web.HTTPNotFound()

        key = 'pocketurls_short_to_long:{}'.format(short_form)
        long_url = await self._redis.get(key)

        if not long_url:
            logging.info("Cache miss for {}.".format(short_form))
            long_url = await exec_postgres_query(self._postgres,
                                                 'SELECT long_url from urls WHERE short_form=\'{}\''.format(short_form))
            logging.info("Db hit. Postgres returned url {} for {}.".format(long_url, short_form))

            if not long_url:
                raise web.HTTPNotFound()

            await self._redis.set(key, long_url)

            key = 'pocketurls_long_to_short:{}'.format(long_url)
            await self._redis.set(key, long_url)
        else:
            long_url = str(long_url, 'utf-8')
            logging.info("Cache hit. Redis returned url {} for {}.".format(long_url, short_form))

        return web.HTTPFound(location=long_url)
