# POCKETURLS

## APP OVERVIEW

POCKETURLS is an app that lets users shorten URLs and is designed to be scalable.  
Users can submit a long URL and get a unique shortened URL that redirects to a long one.

It is written using Python 3, aiohttp, aiopg, aioredis, etc.  
It uses PostgreSQL as a database and Redis as a cache. Database considerations are explained in the following paragraphs.  
Python app itself is stateless and can be started up in multiple machines to handle increasing load.

The app is served using Nginx + Gunicorn combo. Faster solutions are available as well (https://docs.aiohttp.org/en/stable/deployment.html).  
Properly configured Nginx + Gunicorn should be able to serve 10000s simultaneous connections.

The app is containerized using Docker and is ready to be deployed to a Kubernetes cluster.  

Postgres db has a persistent volume mounted in a cluster to ensure data persistence.

In the initial version of the architecture, all services are deployed as separate k8s pods each. Other architecture models are considered in a “SCALING IT UP” section.  

In the initial version logs from the app are generated to stdout and stderr, but later an external backend for exposing logs (both from the app and from the infrastructure) can be added, as explained in “METRICS & LOGGING” section.  

The app is already deployed to a Kubernetes cluster on DigitalOcean and can be accessed using this URL: http://pocketurls.com


## RUNNING THE APP

Ensure that you have Docker and Docker Compose installed.

Build and fire up the container from `./pocketworlds` using `docker compose up` command.  
Now you can access the app locally at http://localhost


## ENDPOINTS

| Endpoint        | HTTP Method           | CRUD Method  | Result |
| --------------- |-----------------------| -------------|--------|
| /     | GET | READ | POCKETURLS web application|
| /<short_form> | GET      |    READ | Get redirected to original URL from shortened form|
| /shorten/<url> | POST | CREATE | Shorten URL|


## DATABASE

First off, why would we want to use a db in the first place?  
If we created a hashing function that returns a short hash from a long url and is easily reversible (long url from a short hash) with no conflicts then the app is basically stateless and no db is necessary.

There are three problems with this approach:
1. Generating a hash and reversing it will most likely be much slower than simply reading it from an in-memory database;  
2. We want the URLs to be short and the shorter the URL the more potential for conflicts (i.e. two long urls pointing to the same hash) and the easiest way to resolve conflicts is to store unique hashes in a db. Of course we can simply use long-ass MD5, SHA1 or sth like this, but it’s not user friendly and hard to remember;  
3. By default reversing a hash is non-trivial.  

Therefore, ideally we want to 1. generate a unique hash for a particular url only once (because it’s time consuming), 2. be able to reverse the hash quickly and 3. avoid conflicts. This is where a db comes into the picture.

Let’s analyse what we want to accomplish from a db-performance standpoint.  
There will be only two queries - read from db and save to db - SELECTs and INSERTs INTO in relational dbs lingo.  
We can safely assume that SELECTs will be orders of magnitude more frequent than INSERTs. Just because we need to generate a short hash from a URL only once (and just read it from db if requested again), but original URL retrieval can be requested even millions of times per second and is critical to user experience.  
We also want to persist the data and want to avoid losing it due to a server or a k8s pod crash as it would frustrate our users to no end.  

Therefore I chose PostgreSQL as a database of choice mostly because it’s good enough for the task and it’s the one I am most familiar with.  
There won’t be any joins nor multi-table lookups. Simple SELECTs and INSERTS INTO are very well optimised within Postgres engine and can be optimised further as well for quicker lookups, for instance by setting up an index on a particular column.  

Downside to using Postgres is that for huge amounts of data the data is stored on a drive (not necessarily true for smaller amounts of data as Postgres has its own caching mechanism) which is orders of magnitude slower than storing the data in memory. On the other hand we want to persist the data so at some point we need to store it in a volume that extends the lifetime of a server or a k8s pod.  
Postgres can give us persistence if implemented correctly, i.e. backups or k8s volumes.  

But to handle large amounts of concurrent requests it would be great to make sure the data is served from memory, at least for the most common requests.  
That is what caching is for. Any fast, in-memory datastore will do, i.e. Memcached or Redis. I pick Redis.  

On a side note, solutions like ElasticSearch might be used for this task.


## METRICS & LOGGING

In the app itself I use Python logging to log events using common sense. For instance:
1. a new unique short URL was generated;
2. there was a hashing conflict;
3. there was a short->long URL redirection from cache or from a db;
4. there was a request to shorten a URL but it is is already shortened;
5. etc.

On top of those logs it’s worth having metrics such as:
1. n most frequent redirections from short URLs;
2. n most frequent shortening requests;
3. average response time;
4. peaks in number of simultaneous connections;
5. etc.

Besides app logs we need to store infrastructure logs such as k8s cluster-level logs about pods crashes, etc.

An external backend such as Datadog or Sumologic can be added and configured to expose logs both from the app and from the infrastructure.  
Those backends make logs easily accessible, searchable and visualisable from one place.  
Additionally a dashboard such as Grafana can be added for easier visualisation.  
There are plugins to connect Datadog to Grafana.


## SCALING IT UP

### Scenarios:
Millions of users (or one user millions of times or sth like that) want to read the same URL from a particular hash at the same time.
+ That’s easy. We have caching in place.
+ For the most common URLs we can also bypass the app altogether and hard-code short->long URL translations into a load balancer, for instance.

Millions of users want to shorten the same long URL at the same time.
+ That’s easy. The first request will result in URL shortening and for the subsequent requests it's the same scenario as 1.

Millions of users want to generate millions of unique hashes at the same time.  
+ First off, no problem with the Python app, we can just spin up more pods.
+ But Postgres might have a hard time handling that.
+ As the first step we can use a connection pooler like a PgBouncer which will “recycle” existing connections so Postgres won’t clog.
+ We can also use multiple Postgres instances or multiple k8s pods that each has its own Python app instance, Postgres and Redis instances. Load balancer can decide which pod or Postgres instance to forward traffic to based on simple arbitrary rules like if an url starts with ‘a’ letter forward it to one pod, but if with a ‘b’ letter forward it to another.
+ We can also add another cache on top and lookup-tables for load balancer.

### External CDNs and DDoS protection services:
Last, but not least this app is a perfect use-case for external DDoS protection services and CDNs.
For instance, Cloudflare could help handle large load even before it hits the app.
