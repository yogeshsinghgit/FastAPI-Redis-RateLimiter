
# What is Rate Limiting?

Rate limiting is the practice of restricting how many times a user, client, or system can make a request to an API or service within a specific time window (e.g., 100 requests per minute).

Think of it like a “speed breaker” for APIs to prevent overuse, abuse, or system overload.


Redis Conf:

``` cmd
docker pull redis:latest
```

``` cmd
docker run -d --name redis-server -p 6379:6379 redis
```