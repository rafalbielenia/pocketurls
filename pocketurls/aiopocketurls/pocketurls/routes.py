def setup_routes(app, handler):
    app.router.add_get('/', handler.index, name='index')
    app.router.add_get('/{short_form}', handler.redirect, name='short')
    app.router.add_post('/shorten', handler.shorten, name='shorten')
