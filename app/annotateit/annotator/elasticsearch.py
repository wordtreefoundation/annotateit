from __future__ import absolute_import

import csv
import json
import logging
import datetime
import urlparse

import iso8601

import elasticsearch
from flask import current_app
from flask import _app_ctx_stack as stack
from .atoi import atoi

log = logging.getLogger(__name__)

RESULTS_MAX_SIZE = 200


class ElasticSearch(object):
    """

    Thin wrapper around an ElasticSearch connection to make connection handling
    transparent in a Flask application. Usage:

        app = Flask(__name__)
        es = ElasticSearch(app)

    Or, you can bind the object to the application later:

        es = ElasticSearch()

        def create_app():
            app = Flask(__name__)
            es.init_app(app)
            return app

    """

    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)

        self.Model = make_model(self)

    def init_app(self, app):
        app.config.setdefault('ELASTICSEARCH_HOST', 'http://127.0.0.1:9200')
        app.config.setdefault('ELASTICSEARCH_INDEX', app.name)
        app.config.setdefault('ELASTICSEARCH_COMPATIBILITY_MODE', None)

    def connect(self):
        host = current_app.config['ELASTICSEARCH_HOST']
        parsed = urlparse.urlparse(host)

        connargs = {
          'host': parsed.hostname,
        }

        username = parsed.username
        password = parsed.password
        if username is not None or password is not None:
            connargs['http_auth'] = ((username or ''), (password or ''))

        if parsed.port is not None:
            connargs['port'] = parsed.port

        if parsed.path:
            connargs['url_prefix'] = parsed.path

        conn = elasticsearch.Elasticsearch(
            hosts=[connargs],
            connection_class=elasticsearch.Urllib3HttpConnection)
        return conn

    @property
    def conn(self):
        ctx = stack.top
        if not hasattr(ctx, 'elasticsearch'):
            ctx.elasticsearch = self.connect()
        return ctx.elasticsearch

    @property
    def index(self):
        return current_app.config['ELASTICSEARCH_INDEX']

    @property
    def compatibility_mode(self):
        return current_app.config['ELASTICSEARCH_COMPATIBILITY_MODE']


class _Model(dict):

    @classmethod
    def create_all(cls):
        logging.warn("creating index " + cls.es.index + " with mapping " + cls.__type__)
        try:
            cls.es.conn.indices.create(cls.es.index)
        except elasticsearch.exceptions.RequestError as e:
            # Reraise anything that isn't just a notification that the index
            # already exists
            if not e.error.startswith('IndexAlreadyExistsException'):
                raise
            log.warn('Index creation failed. If you are running against '
                     'Bonsai Elasticsearch, this is expected and ignorable.')
        mapping = {cls.__type__: {'properties': cls.__mapping__}}
        cls.es.conn.indices.put_mapping(index=cls.es.index,
                                        doc_type=cls.__type__,
                                        body=mapping)

    @classmethod
    def drop_all(cls):
        if cls.es.conn.indices.exists(cls.es.index):
            cls.es.conn.indices.close(cls.es.index)
            cls.es.conn.indices.delete(cls.es.index)

    # It would be lovely if this were called 'get', but the dict semantics
    # already define that method name.
    @classmethod
    def fetch(cls, id):
        try:
            doc = cls.es.conn.get(index=cls.es.index,
                                  doc_type=cls.__type__,
                                  id=id)
        except elasticsearch.exceptions.NotFoundError:
            return None
        return cls(doc['_source'], id=id)

    @classmethod
    def _build_query(cls, offset=0, limit=20, **kwargs):
        return _build_query(offset, limit, kwargs)

    @classmethod
    def _build_query_raw(cls, request):
        return _build_query_raw(request)

    @classmethod
    def search(cls, **kwargs):
        q = cls._build_query(**kwargs)
        if not q:
            return []

        res = cls.es.conn.search(index=cls.es.index,
                                 doc_type=cls.__type__,
                                 body=q)
        docs = res['hits']['hits']
        return [cls(d['_source'], id=d['_id']) for d in docs]

    @classmethod
    def search_raw(cls, request):
        q, params = cls._build_query_raw(request)
        if 'error' in q:
            return q
        try:
            res = cls.es.conn.search(index=cls.es.index,
                                     doc_type=cls.__type__,
                                     body=q,
                                     **params)
        except elasticsearch.exceptions.ElasticsearchException as e:
            return e.result
        else:
            return res

    @classmethod
    def count(cls, **kwargs):
        q = cls._build_query(**kwargs)
        if not q:
            return 0

        # Extract the query, and wrap it in the expected object. This has the
        # effect of removing sort or paging parameters that aren't allowed by
        # the count API.
        q = {'query': q['query']}

        # In elasticsearch prior to 1.0.0, the payload to `count` was a bare
        # query.
        if cls.es.compatibility_mode == 'pre-1.0.0':
            q = q['query']

        res = cls.es.conn.count(index=cls.es.index,
                                doc_type=cls.__type__,
                                body=q)
        return res['count']

    def _set_id(self, rhs):
        self['id'] = rhs

    def _get_id(self):
        return self.get('id')

    id = property(_get_id, _set_id)

    def save(self, refresh=True):
        _add_created(self)
        _add_updated(self)
        res = self.es.conn.index(index=self.es.index,
                                 doc_type=self.__type__,
                                 id=self.id,
                                 body=self,
                                 refresh=refresh)
        self.id = res['_id']

    def delete(self):
        if self.id:
            self.es.conn.delete(index=self.es.index,
                                doc_type=self.__type__,
                                id=self.id)


def make_model(es):
    return type('Model', (_Model,), {'es': es})


def _csv_split(s, delimiter=','):
    return [r for r in csv.reader([s], delimiter=delimiter)][0]


def _build_query(offset, limit, kwds):
    # Base query is a filtered match_all
    q = {'match_all': {}}

    if kwds:
        f = {'and': []}
        q = {'filtered': {'query': q, 'filter': f}}

    # Add a term query for each keyword
    for k, v in kwds.iteritems():
        q['filtered']['filter']['and'].append({'term': {k: v}})

    return {
        'sort': [{'updated': {'order': 'desc'}}],  # Sort most recent first
        'from': max(0, offset),
        'size': min(RESULTS_MAX_SIZE, max(0, limit)),
        'query': q
    }


def _build_query_raw(request):
    query = {}
    params = {}

    if request.method == 'GET':
        for k, v in request.args.iteritems():
            _update_query_raw(query, params, k, v)

        if 'query' not in query:
            query['query'] = {'match_all': {}}

    elif request.method == 'POST':

        try:
            query = json.loads(request.json or
                               request.data or
                               request.form.keys()[0])
        except (ValueError, IndexError):
            return ({'error': 'Could not parse request payload!',
                     'status': 400},
                    None)

        params = request.args

    for o in (params, query):
        if 'from' in o:
            o['from'] = max(0, atoi(o['from']))
        if 'size' in o:
            o['size'] = min(RESULTS_MAX_SIZE, max(0, atoi(o['size'])))

    return query, params


def _update_query_raw(qo, params, k, v):
    if 'query' not in qo:
        qo['query'] = {}
    q = qo['query']

    if 'query_string' not in q:
        q['query_string'] = {}
    qs = q['query_string']

    if k == 'q':
        qs['query'] = v

    elif k == 'df':
        qs['default_field'] = v

    elif k in ('explain', 'track_scores', 'from', 'size', 'timeout',
               'lowercase_expanded_terms', 'analyze_wildcard'):
        qo[k] = v

    elif k == 'fields':
        qo[k] = _csv_split(v)

    elif k == 'sort':
        if 'sort' not in qo:
            qo[k] = []

        split = _csv_split(v, ':')

        if len(split) == 1:
            qo[k].append(split[0])
        else:
            fld = ':'.join(split[0:-1])
            drn = split[-1]
            qo[k].append({fld: drn})

    elif k == 'search_type':
        params[k] = v


def _add_created(ann):
    if 'created' not in ann:
        ann['created'] = datetime.datetime.now(iso8601.iso8601.UTC).isoformat()


def _add_updated(ann):
    ann['updated'] = datetime.datetime.now(iso8601.iso8601.UTC).isoformat()
